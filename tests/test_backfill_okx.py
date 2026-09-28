import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql
from talib import abstract

from ingest import pipeline
from ingest.backfill import BACKFILL_RECIPES, run_backfill
from ingest.fetchers.okx import (
    HISTORY_ENDPOINT,
    _backfill_seed_bars,
    backfill_okx_candle_indicator,
)
from ingest.fetchers.okx_derivatives import (
    BACKFILL_PAGE_LIMIT,
    BACKFILL_PERIOD,
    BTC_FUNDING_RATE_HISTORY_ENDPOINT,
    OKX_LONG_SHORT_RATIO_ENDPOINT,
    OKX_OPEN_INTEREST_ENDPOINT,
    OKX_OPEN_INTEREST_HISTORY_ENDPOINT,
    OKX_TAKER_VOLUME_ENDPOINT,
    RUBIK_DAILY_PERIOD_PROVENANCE,
    backfill_okx_funding_rate,
    backfill_okx_long_short_ratio,
    backfill_okx_open_interest,
    backfill_okx_taker_ratio,
)
from ingest.registry import load_registry

NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)
DAY_MS = 86_400_000
MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
ENV_FILE = MIGRATIONS.parents[1] / ".env.local"


def milliseconds(value: datetime) -> str:
    return str(int(value.timestamp() * 1000))


def candle(opened_at: datetime, close: float, volume: float = 100.0) -> list[str]:
    return [
        milliseconds(opened_at),
        str(close),
        str(close + 1),
        str(close - 1),
        str(close),
        str(volume),
        str(volume),
        str(volume),
        "1",
    ]


def candle_client(rows_newest_first: list[list[str]]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        limit = int(request.url.params["limit"])
        after = int(request.url.params["after"])
        page = [row for row in rows_newest_first if int(row[0]) < after][:limit]
        return httpx.Response(
            200,
            json={"code": "0", "msg": "", "data": page},
            request=request,
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def definition(key: str):
    return next(entry for entry in load_registry().root if entry.key == key)


def _database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "DATABASE_URL" and value.strip():
                return value.strip().strip("'\"")

    raise RuntimeError(
        "Live OKX backfill persistence tests require TEST_DATABASE_URL, DATABASE_URL, "
        "or DATABASE_URL in .env.local"
    )


@pytest.fixture(scope="module")
def postgres() -> psycopg.Connection[tuple[object, ...]]:
    schema = f"test_backfill_okx_{uuid4().hex}"
    try:
        connection = psycopg.connect(_database_url(), autocommit=True)
    except psycopg.OperationalError:
        raise RuntimeError(
            "Live OKX backfill persistence tests could not connect; check "
            "TEST_DATABASE_URL, DATABASE_URL, or DATABASE_URL in .env.local"
        ) from None

    with connection:
        with connection.transaction():
            connection.execute(
                """
                DO $$
                BEGIN
                  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
                    CREATE ROLE anon NOLOGIN;
                  END IF;
                  IF NOT EXISTS (
                    SELECT FROM pg_roles WHERE rolname = 'authenticated'
                  ) THEN
                    CREATE ROLE authenticated NOLOGIN;
                  END IF;
                END
                $$;
                """
            )
            connection.execute(
                sql.SQL("create schema {}").format(sql.Identifier(schema))
            )
            schema_name = sql.Identifier(schema).as_string(connection)
            for migration in sorted(MIGRATIONS.glob("*.sql")):
                migration_sql = migration.read_text(encoding="utf-8").replace(
                    "public.", f"{schema_name}."
                )
                connection.execute(migration_sql)
        connection.execute(
            sql.SQL("set search_path to {}").format(sql.Identifier(schema))
        )

        try:
            yield connection
        finally:
            connection.execute(
                sql.SQL("drop schema if exists {} cascade").format(
                    sql.Identifier(schema)
                )
            )


def test_okx_registry_entries_are_wired_to_real_backfill_recipes() -> None:
    entries = {entry.key: entry for entry in load_registry().root}

    assert entries["btc_daily_close"].backfill_recipe == "okx_candles"
    assert entries["btc_rsi"].backfill_recipe == "okx_candles"
    assert entries["btc_ema_20"].backfill_recipe == "okx_candles"
    assert entries["btc_ema_50"].backfill_recipe == "okx_candles"
    assert entries["btc_ema_200"].backfill_recipe == "okx_candles"
    assert entries["btc_macd"].backfill_recipe == "okx_candles"
    assert entries["btc_stochrsi"].backfill_recipe == "okx_candles"
    assert entries["btc_bollinger_upper"].backfill_recipe == "okx_candles"
    assert entries["btc_atr"].backfill_recipe == "okx_candles"
    assert entries["btc_obv"].backfill_recipe == "okx_candles"
    assert entries["btc_funding_rate"].backfill_recipe == "okx_funding"
    assert entries["btc_open_interest"].backfill_recipe == "okx_open_interest_history"
    assert entries["btc_long_short_ratio"].backfill_recipe == "okx_long_short_1d"
    assert entries["btc_taker_ratio"].backfill_recipe == "okx_taker_volume_1d"
    assert set(entries["btc_open_interest"].endpoint.split("?")[:1]) == {
        OKX_OPEN_INTEREST_ENDPOINT
    }
    assert BACKFILL_RECIPES.keys() >= {
        "okx_candles",
        "okx_funding",
        "okx_open_interest_history",
        "okx_long_short_1d",
        "okx_taker_volume_1d",
    }


@pytest.mark.parametrize(
    "key",
    (
        "btc_rsi",
        "btc_ema_20",
        "btc_ema_50",
        "btc_ema_200",
        "btc_macd",
        "btc_stochrsi",
        "btc_bollinger_upper",
        "btc_bollinger_middle",
        "btc_bollinger_lower",
        "btc_atr",
        "btc_obv",
    ),
)
def test_candle_backfill_reseeds_each_talib_indicator_before_plotted_window(
    key: str,
) -> None:
    entry = definition(key)
    assert entry.required_bars is not None
    seed_bars = _backfill_seed_bars(
        entry.required_bars,
        entry.talib_function,
        entry.parameters,
    )
    if entry.talib_function != "OBV":
        function = abstract.Function(entry.talib_function)  # type: ignore[arg-type]
        function.set_parameters(entry.parameters or {})
        assert seed_bars >= function.lookback * 4 + 1

    plotted_points = 2
    total = seed_bars + plotted_points - 1
    oldest = NOW - timedelta(days=total + 1)
    rows = [
        candle(oldest + timedelta(days=index), close=100.0 + index, volume=10 + index)
        for index in range(total)
    ]
    with candle_client(list(reversed(rows))) as client:
        runs = backfill_okx_candle_indicator(
            entry,
            plotted_points=plotted_points,
            client=client,
            now=NOW,
        )

    assert len(runs) == plotted_points
    values = [run.indicators[key] for run in runs]
    assert all(f"backfill_seed_bars={seed_bars}" in value.source_field for value in values)
    assert [value.source_timestamp for value in values] == [
        oldest + timedelta(days=seed_bars),
        oldest + timedelta(days=seed_bars + 1),
    ]


def test_backfilled_macd_matches_existing_golden_at_the_same_history_depth() -> None:
    golden = json.loads(
        (Path(__file__).with_name("goldens") / "btc_macd.json").read_text(
            encoding="utf-8"
        )
    )
    rows = [
        candle(NOW - timedelta(days=len(golden["input_bars"]) - index + 1), bar["close"])
        for index, bar in enumerate(golden["input_bars"])
    ]

    with candle_client(list(reversed(rows))) as client:
        runs = backfill_okx_candle_indicator(
            definition("btc_macd"),
            plotted_points=1,
            client=client,
            now=NOW,
        )

    result = runs[0].indicators["btc_macd"]
    assert result.value == pytest.approx(golden["expected"], abs=1e-6, rel=0.0)


def funding_row(settled_at: datetime, realized_rate: str) -> dict[str, str]:
    return {
        "formulaType": "withRate",
        "fundingRate": "0.0",
        "fundingTime": milliseconds(settled_at),
        "instId": "BTC-USDT-SWAP",
        "instType": "SWAP",
        "method": "current_period",
        "realizedRate": realized_rate,
    }


def test_funding_backfill_persists_only_the_vendor_returned_history_window() -> None:
    rows = [
        funding_row(NOW - timedelta(days=2), "0.0003"),
        funding_row(NOW - timedelta(days=10), "0.0002"),
        funding_row(NOW - timedelta(days=90), "0.0001"),
    ]
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(
            200,
            json={"code": "0", "msg": "", "data": rows},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runs = backfill_okx_funding_rate(definition("btc_funding_rate"), client=client)

    source_timestamps = [
        run.indicators["btc_funding_rate"].source_timestamp for run in runs
    ]
    assert len(runs) == len(rows)
    assert min(source_timestamps) == datetime.fromtimestamp(
        int(rows[-1]["fundingTime"]) / 1000,
        tz=UTC,
    )
    assert requested_urls == [
        (
            f"{BTC_FUNDING_RATE_HISTORY_ENDPOINT}?instId=BTC-USDT-SWAP"
            f"&limit={BACKFILL_PAGE_LIMIT}&before=1"
        )
    ]


def test_open_interest_backfill_uses_history_endpoint_and_persists_its_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [[milliseconds(NOW - timedelta(days=1)), "100", "10", "1000"]]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": "0", "msg": "", "data": rows},
            request=request,
        )

    persisted: dict[str, str] = {}

    def record_datapoint(_connection: object, *, definition, **_kwargs) -> int:
        persisted["endpoint"] = definition.endpoint
        persisted["source_field"] = definition.source_field
        return 1

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        run = backfill_okx_open_interest(
            definition("btc_open_interest"),
            client=client,
        )[0]
        pipeline.persist_board(object(), run, origin="backfill")  # type: ignore[arg-type]

    assert OKX_OPEN_INTEREST_HISTORY_ENDPOINT in persisted["endpoint"]
    assert OKX_OPEN_INTEREST_ENDPOINT not in persisted["endpoint"]
    assert "open-interest-history" in persisted["source_field"]
    assert "public/open-interest" not in persisted["source_field"]


def test_long_short_and_taker_backfills_request_raw_1d_points_without_resampling() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        row = [milliseconds(NOW - timedelta(days=1)), "2", "6"]
        if "long-short-account-ratio" in str(request.url):
            row = [milliseconds(NOW - timedelta(days=1)), "1.5"]
        return httpx.Response(
            200,
            json={"code": "0", "msg": "", "data": [row]},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        long_short = backfill_okx_long_short_ratio(
            definition("btc_long_short_ratio"),
            client=client,
        )[0].indicators["btc_long_short_ratio"]
        taker = backfill_okx_taker_ratio(
            definition("btc_taker_ratio"),
            client=client,
        )[0].indicators["btc_taker_ratio"]

    assert requested_urls == [
        f"{OKX_LONG_SHORT_RATIO_ENDPOINT}?ccy=BTC&period={BACKFILL_PERIOD}",
        (
            f"{OKX_TAKER_VOLUME_ENDPOINT}?ccy=BTC&instType=CONTRACTS"
            f"&period={BACKFILL_PERIOD}"
        ),
    ]
    assert long_short.source_timestamp == NOW - timedelta(days=1)
    assert taker.source_timestamp == NOW - timedelta(days=1)
    assert "no resampling" in long_short.source_field
    assert "no resampling" in taker.source_field
    assert RUBIK_DAILY_PERIOD_PROVENANCE in long_short.source_field
    assert RUBIK_DAILY_PERIOD_PROVENANCE in taker.source_field
    assert taker.value == 3.0


@pytest.mark.integration
def test_live_okx_candle_backfill_seed_matches_project_calculation_at_historical_bar() -> (
    None
):
    entry = definition("btc_macd")
    runs = backfill_okx_candle_indicator(entry, plotted_points=3)

    assert runs
    returned = runs[-1].indicators["btc_macd"]
    assert f"backfill_seed_bars={_backfill_seed_bars(250, 'MACD', entry.parameters)}" in (
        returned.source_field
    )

    target_open = returned.source_timestamp - timedelta(days=1)
    response = httpx.get(
        HISTORY_ENDPOINT,
        params={
            "instId": "BTC-USDT",
            "bar": "1Dutc",
            "after": str(int((returned.source_timestamp + timedelta(days=1)).timestamp() * 1000)),
            "limit": "100",
        },
        timeout=10,
    )
    response.raise_for_status()
    direct_rows = response.json()["data"]
    assert any(
        datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC) == target_open
        for row in direct_rows
    )

    seed_bars = _backfill_seed_bars(250, "MACD", entry.parameters)
    raw_rows = []
    cursor = int((returned.source_timestamp + timedelta(days=1)).timestamp() * 1000)
    while len(raw_rows) < seed_bars:
        page = httpx.get(
            HISTORY_ENDPOINT,
            params={
                "instId": "BTC-USDT",
                "bar": "1Dutc",
                "after": str(cursor),
                "limit": str(min(100, seed_bars - len(raw_rows))),
            },
            timeout=10,
        )
        page.raise_for_status()
        rows = page.json()["data"]
        assert rows
        raw_rows.extend(rows)
        cursor = int(rows[-1][0])

    bars = tuple(
        {
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        }
        for row in reversed(raw_rows[:seed_bars])
    )
    expected = pipeline._calculate(entry, bars)

    assert returned.source_timestamp == target_open + timedelta(days=1)
    assert returned.value == pytest.approx(expected, abs=1e-9, rel=0.0)


@pytest.mark.integration
def test_live_okx_rubik_rejects_or_fails_to_commit_to_1dutc_period() -> None:
    probes = [
        (
            OKX_LONG_SHORT_RATIO_ENDPOINT,
            {"ccy": "BTC", "period": "1Dutc"},
        ),
        (
            OKX_TAKER_VOLUME_ENDPOINT,
            {"ccy": "BTC", "instType": "CONTRACTS", "period": "1Dutc"},
        ),
    ]

    for endpoint, params in probes:
        response = httpx.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
        assert payload.get("code") != "0" or not payload.get("data"), (
            f"OKX now appears to accept {endpoint} period=1Dutc; "
            "switch the backfill recipe off period=1D before shipping."
        )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("indicator_key", "endpoint", "params", "value_from_row", "timestamp_from_row"),
    (
        (
            "btc_daily_close",
            HISTORY_ENDPOINT,
            {"instId": "BTC-USDT", "bar": "1Dutc", "limit": "100"},
            lambda row: float(row[4]),
            lambda row: datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC)
            + timedelta(days=1),
        ),
        (
            "btc_funding_rate",
            BTC_FUNDING_RATE_HISTORY_ENDPOINT,
            {
                "instId": "BTC-USDT-SWAP",
                "limit": str(BACKFILL_PAGE_LIMIT),
                "before": "1",
            },
            lambda row: float(row["realizedRate"]),
            lambda row: datetime.fromtimestamp(int(row["fundingTime"]) / 1000, tz=UTC),
        ),
        (
            "btc_open_interest",
            OKX_OPEN_INTEREST_HISTORY_ENDPOINT,
            {
                "instId": "BTC-USDT-SWAP",
                "period": BACKFILL_PERIOD,
                "limit": str(BACKFILL_PAGE_LIMIT),
            },
            lambda row: float(row[3]),
            lambda row: datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC),
        ),
        (
            "btc_long_short_ratio",
            OKX_LONG_SHORT_RATIO_ENDPOINT,
            {"ccy": "BTC", "period": BACKFILL_PERIOD},
            lambda row: float(row[1]),
            lambda row: datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC),
        ),
        (
            "btc_taker_ratio",
            OKX_TAKER_VOLUME_ENDPOINT,
            {"ccy": "BTC", "instType": "CONTRACTS", "period": BACKFILL_PERIOD},
            lambda row: float(row[2]) / float(row[1]),
            lambda row: datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC),
        ),
    ),
)
def test_live_okx_run_backfill_persists_real_rows_cross_checked_against_fresh_vendor_read(
    postgres: psycopg.Connection[tuple[object, ...]],
    indicator_key: str,
    endpoint: str,
    params: dict[str, str],
    value_from_row,
    timestamp_from_row,
) -> None:
    row_ids = run_backfill(postgres, indicator_key=indicator_key)

    assert row_ids
    persisted = postgres.execute(
        """
        select value, source_timestamp, endpoint, source_field, origin
        from datapoints
        where id = any(%s)
        order by source_timestamp asc
        limit 1
        """,
        (list(row_ids),),
    ).fetchone()
    assert persisted is not None
    value, source_timestamp, persisted_endpoint, source_field, origin = persisted
    assert origin == "backfill"

    response = httpx.get(endpoint, params=params, timeout=10)
    response.raise_for_status()
    rows = response.json()["data"]
    direct = next(
        row
        for row in rows
        if timestamp_from_row(row) == source_timestamp
    )

    assert float(value) == pytest.approx(value_from_row(direct), abs=1e-9, rel=0.0)
    assert endpoint in persisted_endpoint
    assert source_field
