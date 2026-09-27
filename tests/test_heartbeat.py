from collections.abc import Callable
from datetime import UTC, datetime
from typing import Self

import httpx
import pytest

from ingest import heartbeat
from ingest.pipeline import FullAssetRun
from ingest.status import Error, Ok, Reason, Result, Unavailable

DATABASE_URL = "postgresql://example.test/app"
HEARTBEAT_URL = "https://hc-ping.com/check-id"
SOURCE_TIMESTAMP = datetime(2026, 9, 8, tzinfo=UTC)


class FakeConnection:
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def install_ingestion_fakes(
    monkeypatch: pytest.MonkeyPatch,
    pipeline: Callable[
        [object, Callable[[], Result | FullAssetRun]], int | tuple[int, ...]
    ],
) -> None:
    monkeypatch.setattr(heartbeat.psycopg, "connect", lambda _: FakeConnection())
    monkeypatch.setattr(heartbeat, "run_pipeline", pipeline)


def test_heartbeat_is_pinged_only_after_a_successful_persist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    def persisted_pipeline(
        connection: object, fetcher: Callable[[], Result]
    ) -> int:
        assert isinstance(connection, FakeConnection)
        fetcher()
        events.append("persisted")
        return 41

    install_ingestion_fakes(monkeypatch, persisted_pipeline)
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: (
                events.append(f"ping:{request.url}")
                or httpx.Response(200, request=request)
            )
        )
    )

    row_id = heartbeat.run_ingestion(
        DATABASE_URL,
        HEARTBEAT_URL,
        fetcher=lambda: Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
        heartbeat_client=client,
    )

    assert row_id == 41
    assert events == ["persisted", f"ping:{HEARTBEAT_URL}"]

    events.clear()
    with pytest.raises(RuntimeError, match="did not fetch a value"):
        heartbeat.run_ingestion(
            DATABASE_URL,
            HEARTBEAT_URL,
            fetcher=lambda: Unavailable(reason=Reason.FETCH_FAILED),
            heartbeat_client=client,
        )

    assert events == ["persisted", f"ping:{HEARTBEAT_URL}/fail"]


def test_failed_run_pings_the_failure_endpoint_rather_than_staying_silent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_urls: list[str] = []

    def failed_persist(
        connection: object, fetcher: Callable[[], Result]
    ) -> int:
        fetcher()
        raise RuntimeError("database write failed")

    install_ingestion_fakes(monkeypatch, failed_persist)
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: (
                requested_urls.append(str(request.url))
                or httpx.Response(200, request=request)
            )
        )
    )

    with pytest.raises(RuntimeError, match="database write failed"):
        heartbeat.run_ingestion(
            DATABASE_URL,
            HEARTBEAT_URL,
            fetcher=lambda: Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
            heartbeat_client=client,
        )

    assert requested_urls == [f"{HEARTBEAT_URL}/fail"]


def test_board_cell_failure_still_pings_success_after_completed_persist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_urls: list[str] = []
    board = FullAssetRun(
        indicators={
            "btc_rsi": Error(
                reason=Reason.FETCH_FAILED,
                detail="forced cell failure",
            ),
            "eth_rsi": Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
        },
        history={},
    )

    def persisted_pipeline(
        connection: object, fetcher: Callable[[], Result | FullAssetRun]
    ) -> tuple[int, ...]:
        assert isinstance(connection, FakeConnection)
        assert fetcher() == board
        return (1, 2)

    install_ingestion_fakes(monkeypatch, persisted_pipeline)
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: (
                requested_urls.append(str(request.url))
                or httpx.Response(200, request=request)
            )
        )
    )

    row_ids = heartbeat.run_ingestion(
        DATABASE_URL,
        HEARTBEAT_URL,
        fetcher=lambda: board,
        heartbeat_client=client,
    )

    assert row_ids == (1, 2)
    assert requested_urls == [HEARTBEAT_URL]


def test_default_heartbeat_run_uses_the_scheduled_board_fetcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    board = FullAssetRun(
        indicators={"btc_rsi": Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP)},
        history={},
    )

    def scheduled_board() -> FullAssetRun:
        events.append("scheduled-board")
        return board

    def persisted_pipeline(
        connection: object, fetcher: Callable[[], Result | FullAssetRun]
    ) -> tuple[int, ...]:
        assert isinstance(connection, FakeConnection)
        assert fetcher() == board
        events.append("persisted")
        return (1,)

    install_ingestion_fakes(monkeypatch, persisted_pipeline)
    monkeypatch.setattr(heartbeat, "run_scheduled_board", scheduled_board)
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: (
                events.append(f"ping:{request.url}")
                or httpx.Response(200, request=request)
            )
        )
    )

    row_ids = heartbeat.run_ingestion(
        DATABASE_URL,
        HEARTBEAT_URL,
        heartbeat_client=client,
    )

    assert row_ids == (1,)
    assert events == [
        "scheduled-board",
        "persisted",
        f"ping:{HEARTBEAT_URL}",
    ]


def test_main_accepts_tier_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def record_ingestion(
        database_url: str,
        heartbeat_url: str,
        *,
        tier: str | None = None,
    ) -> tuple[int, ...]:
        calls.append(
            {
                "database_url": database_url,
                "heartbeat_url": heartbeat_url,
                "tier": tier,
            }
        )
        return (1,)

    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("HEALTHCHECKS_PING_URL", HEARTBEAT_URL)
    monkeypatch.setattr(heartbeat, "run_ingestion", record_ingestion)

    heartbeat.main(["--tier", "fast"])

    assert calls == [
        {
            "database_url": DATABASE_URL,
            "heartbeat_url": HEARTBEAT_URL,
            "tier": "fast",
        }
    ]


def test_heartbeat_failure_does_not_fail_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def persisted_pipeline(
        connection: object, fetcher: Callable[[], Result]
    ) -> int:
        assert isinstance(fetcher(), Ok)
        return 42

    def fail_to_ping(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("healthchecks unavailable", request=request)

    install_ingestion_fakes(monkeypatch, persisted_pipeline)
    client = httpx.Client(transport=httpx.MockTransport(fail_to_ping))

    row_id = heartbeat.run_ingestion(
        DATABASE_URL,
        HEARTBEAT_URL,
        fetcher=lambda: Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
        heartbeat_client=client,
    )

    assert row_id == 42
