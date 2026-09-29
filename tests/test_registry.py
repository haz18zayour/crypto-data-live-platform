from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from ingest.canary import RESPONSE_MODELS
from ingest.registry import (
    REGISTRY_PATH,
    TIER_INTERVAL_SECONDS,
    IndicatorRegistry,
    assert_registry_coverage,
    load_registry,
)

GOLDEN_DIRECTORY = Path(__file__).with_name("goldens")
FIXTURE_DIRECTORY = Path(__file__).with_name("fixtures")
FRED_SERIES_KEYS = {
    "VIXCLS": "macro_vixcls",
    "DFF": "macro_dff",
    "T10Y2Y": "macro_t10y2y",
    "DFII10": "macro_dfii10",
    "DTWEXBGS": "macro_dtwexbgs",
    "CPIAUCSL": "macro_cpiaucsl",
    "M2SL": "macro_m2sl",
}
FRED_UNCORROBORATED_NOTE = (
    "FRED mirrors the Fed/BLS directly; a second source would check the "
    "mirror against its origin rather than provide genuine independent "
    "corroboration."
)
NON_BTC_TALIB_PROPAGATION_REASON = (
    "No per-asset close/volume series is separately registered for this asset; "
    "technical indicators are computed directly from freshly-fetched OHLCV bars "
    "in ingest/pipeline.py, never from a persisted per-asset close indicator. "
    "Only BTC also exposes its close as a board cell by product decision; "
    'ETH/SOL/BNB daily close renders "Daily close is intentionally BTC-only on '
    'this board".'
)

VALID_ENTRY = """\
- key: btc_daily_close
  vendor: okx
  endpoint: https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D
  source_field: 'candle[4] (close), where candle[8] == "1"'
  definable_for: [BTC]
  expected_update_interval_seconds: 86400
  freshness_warn_seconds: 108000
  freshness_stale_seconds: 172800
  frozen_after_observations: 3
"""


def write_registry(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")


def golden_keys() -> set[str]:
    keys = {
        path.relative_to(GOLDEN_DIRECTORY).as_posix()
        for path in GOLDEN_DIRECTORY.rglob("*.json")
    }
    keys.update(
        f"fixtures/{path.relative_to(FIXTURE_DIRECTORY).as_posix()}"
        for path in FIXTURE_DIRECTORY.rglob("*.json")
    )
    return keys


def entry_without(field: str) -> str:
    return "\n".join(
        line
        for line in VALID_ENTRY.splitlines()
        if not line.lstrip().startswith(f"{field}:")
    )


@pytest.mark.parametrize(
    "missing_field",
    (
        "vendor",
        "endpoint",
        "source_field",
        "definable_for",
        "expected_update_interval_seconds",
        "freshness_warn_seconds",
        "freshness_stale_seconds",
    ),
)
def test_every_registry_entry_requires_all_declared_fields(
    tmp_path: Path,
    missing_field: str,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    write_registry(registry_path, entry_without(missing_field))

    with pytest.raises(ValidationError):
        load_registry(registry_path)


def test_entry_without_source_field_is_rejected(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.yaml"
    write_registry(registry_path, entry_without("source_field"))

    with pytest.raises(ValidationError, match="source_field"):
        load_registry(registry_path)


def test_registry_rejects_an_entry_with_no_frozen_detection_declaration(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    write_registry(registry_path, entry_without("frozen_after_observations"))

    with pytest.raises(ValidationError, match="frozen detection declaration"):
        load_registry(registry_path)


def test_registry_rejects_an_entry_with_both_frozen_detection_declarations(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    write_registry(
        registry_path,
        VALID_ENTRY + "  expected_constant: This fixture deliberately repeats.\n",
    )

    with pytest.raises(ValidationError, match="frozen detection declaration"):
        load_registry(registry_path)


def test_registry_rejects_a_talib_entry_without_frozen_propagation_declaration(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    write_registry(
        registry_path,
        VALID_ENTRY
        + """\
- key: btc_rsi
  vendor: okx
  endpoint: https://example.test/bars
  source_field: close
  definable_for: [BTC]
  required_bars: 250
  talib_function: RSI
  parameters:
    timeperiod: 14
  expected_update_interval_seconds: 86400
  freshness_warn_seconds: 108000
  freshness_stale_seconds: 172800
  frozen_after_observations: 3
""",
    )

    with pytest.raises(ValidationError, match="TA-Lib frozen propagation"):
        load_registry(registry_path)


def test_registry_rejects_a_talib_entry_with_both_propagation_declarations(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    write_registry(
        registry_path,
        VALID_ENTRY
        + """\
- key: btc_rsi
  vendor: okx
  endpoint: https://example.test/bars
  source_field: close
  definable_for: [BTC]
  required_bars: 250
  talib_function: RSI
  parameters:
    timeperiod: 14
  expected_update_interval_seconds: 86400
  freshness_warn_seconds: 108000
  freshness_stale_seconds: 172800
  frozen_after_observations: 3
  derives_from: btc_daily_close
  frozen_propagation_unavailable: Fixture says both, which is invalid.
""",
    )

    with pytest.raises(ValidationError, match="TA-Lib frozen propagation"):
        load_registry(registry_path)


def test_registry_rejects_derived_roots_that_are_unknown_or_self_referential(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    talib_entry = """\
- key: btc_rsi
  vendor: okx
  endpoint: https://example.test/bars
  source_field: close
  definable_for: [BTC]
  required_bars: 250
  talib_function: RSI
  parameters:
    timeperiod: 14
  expected_update_interval_seconds: 86400
  freshness_warn_seconds: 108000
  freshness_stale_seconds: 172800
  frozen_after_observations: 3
  derives_from: {root}
"""

    write_registry(registry_path, VALID_ENTRY + talib_entry.format(root="missing_root"))
    with pytest.raises(ValidationError, match="unknown registry key missing_root"):
        load_registry(registry_path)

    write_registry(registry_path, VALID_ENTRY + talib_entry.format(root="btc_rsi"))
    with pytest.raises(ValidationError, match="must not point to itself"):
        load_registry(registry_path)


def test_registry_rejects_duplicate_indicator_keys(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.yaml"
    write_registry(registry_path, VALID_ENTRY + VALID_ENTRY)

    with pytest.raises(
        ValidationError, match="Duplicate indicator key: btc_daily_close"
    ):
        load_registry(registry_path)


@pytest.mark.parametrize("wildcard", ("*", "all", "ALL"))
def test_definable_for_rejects_wildcards(tmp_path: Path, wildcard: str) -> None:
    registry_path = tmp_path / "registry.yaml"
    write_registry(registry_path, VALID_ENTRY.replace("[BTC]", f"[{wildcard}]"))

    with pytest.raises(ValidationError, match="wildcard"):
        load_registry(registry_path)


@pytest.mark.parametrize("assets", ("BTC", "[]"))
def test_definable_for_requires_a_nonempty_asset_list(
    tmp_path: Path,
    assets: str,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    write_registry(registry_path, VALID_ENTRY.replace("[BTC]", assets))

    with pytest.raises(ValidationError, match="definable_for"):
        load_registry(registry_path)


def test_shipped_registry_definitions_cover_four_assets_at_scale() -> None:
    registry = load_registry()

    assert len(registry.root) == 81
    crypto_entries = tuple(
        entry for entry in registry.root if entry.definable_for != ("MACRO",)
    )
    assert {asset for entry in crypto_entries for asset in entry.definable_for} == {
        "BTC",
        "ETH",
        "SOL",
        "BNB",
    }
    assert all(
        len(entry.definable_for) == 1
        or entry.key in {"spot_etf_net_flow", "stablecoin_supply"}
        for entry in crypto_entries
    )


def test_registry_cadence_intervals_partition_the_shipped_entries() -> None:
    registry = load_registry()

    by_tier = {
        tier: {
            entry.key
            for entry in registry.root
            if entry.expected_update_interval_seconds == interval
        }
        for tier, interval in TIER_INTERVAL_SECONDS.items()
    }

    assert {tier: len(keys) for tier, keys in by_tier.items()} == {
        "fast": 12,
        "medium": 4,
        "daily": 64,
    }
    assert set().union(*by_tier.values()) == {
        entry.key
        for entry in registry.root
        if entry.key != "sol_active_addresses"
    }
    assert sum(len(keys) for keys in by_tier.values()) == len(registry.root) - 1


def test_every_shipped_entry_declares_exactly_one_frozen_detection_contract() -> None:
    entries = {entry.key: entry for entry in load_registry().root}

    assert entries["btc_daily_close"].frozen_after_observations is not None
    for entry in entries.values():
        assert (
            entry.frozen_after_observations is not None
        ) != (entry.expected_constant is not None), entry.key


def test_btc_talib_indicators_derive_from_the_registered_btc_close_cell() -> None:
    entries = tuple(
        entry
        for entry in load_registry().root
        if entry.talib_function is not None and entry.definable_for == ("BTC",)
    )

    assert entries
    assert {entry.derives_from for entry in entries} == {"btc_daily_close"}
    assert all(entry.frozen_propagation_unavailable is None for entry in entries)


def test_non_btc_talib_indicators_declare_frozen_propagation_unavailable() -> None:
    entries = tuple(
        entry
        for entry in load_registry().root
        if entry.talib_function is not None and entry.definable_for != ("BTC",)
    )

    assert {entry.definable_for[0] for entry in entries} == {"ETH", "SOL", "BNB"}
    assert entries
    for entry in entries:
        assert entry.derives_from is None
        assert entry.frozen_propagation_unavailable == NON_BTC_TALIB_PROPAGATION_REASON


def test_wall_clock_fetchers_declare_freshness_unmeasurable_reasons() -> None:
    entries = {entry.key: entry for entry in load_registry().root}

    stablecoin_reason = entries["stablecoin_supply"].freshness_unmeasurable
    staking_reason = entries["sol_staking"].freshness_unmeasurable
    assert stablecoin_reason is not None
    assert "DefiLlama stablecoinchains provides no per-chain observation timestamp" in (
        stablecoin_reason
    )
    assert "fetch wall clock" in stablecoin_reason
    assert staking_reason is not None
    assert "Validators.app validators/mainnet provides no aggregate observation timestamp" in (
        staking_reason
    )
    assert "fetch wall clock" in staking_reason


def test_sol_active_addresses_declares_its_real_weekly_schedule() -> None:
    entry = next(
        entry for entry in load_registry().root if entry.key == "sol_active_addresses"
    )

    assert entry.expected_update_interval_seconds == 604800
    assert entry.freshness_warn_seconds > entry.expected_update_interval_seconds
    assert entry.freshness_stale_seconds > entry.freshness_warn_seconds
    assert entry.freshness_warn_seconds == 691200
    assert entry.freshness_stale_seconds == 777600


def test_only_declared_slow_release_entries_use_non_tier_freshness_fields() -> None:
    freshness_by_interval = {
        300: (450, 600),
        28800: (43200, 57600),
        86400: (108000, 172800),
    }
    non_tier_keys = {
        "sol_active_addresses",
        "macro_dtwexbgs",
        "macro_cpiaucsl",
        "macro_m2sl",
    }

    for entry in load_registry().root:
        if entry.key in non_tier_keys:
            continue
        assert entry.expected_update_interval_seconds in freshness_by_interval
        assert (
            entry.freshness_warn_seconds,
            entry.freshness_stale_seconds,
        ) == freshness_by_interval[entry.expected_update_interval_seconds]


def test_sol_active_addresses_weekly_cron_datapoint_stays_fresh_until_next_run() -> None:
    entry = next(
        entry for entry in load_registry().root if entry.key == "sol_active_addresses"
    )
    last_sunday_cron = datetime(2026, 9, 27, 3, 43, tzinfo=UTC)
    just_before_next_sunday_cron = last_sunday_cron + timedelta(days=7) - timedelta(
        seconds=1
    )

    datapoint_age_seconds = (
        just_before_next_sunday_cron - last_sunday_cron
    ).total_seconds()

    assert datapoint_age_seconds == 604799
    assert datapoint_age_seconds < entry.freshness_stale_seconds


def test_seven_confirmed_fred_series_are_registered_with_shared_fetcher_contract() -> (
    None
):
    entries = {
        series_id: next(
            entry for entry in load_registry().root if entry.key == key
        )
        for series_id, key in FRED_SERIES_KEYS.items()
    }

    assert set(entries) == set(FRED_SERIES_KEYS)
    for series_id, entry in entries.items():
        assert entry.vendor == "fred"
        assert entry.definable_for == ("MACRO",)
        assert f"series_id={series_id}" in entry.endpoint
        assert "output_type=4" in entry.endpoint
        assert entry.response_model == "fred_series_observations"
        assert entry.golden == "fixtures/fred_series_observations.json"
        assert entry.required_bars == 1
        assert entry.parameters == {}
        assert "output_type=4 realtime_start" in entry.source_field


def test_dtwexbgs_runs_on_daily_tier_with_weekly_release_staleness_thresholds() -> None:
    entry = next(entry for entry in load_registry().root if entry.key == "macro_dtwexbgs")

    assert entry.expected_update_interval_seconds == 86400
    assert entry.freshness_warn_seconds == 864000
    assert entry.freshness_stale_seconds == 1209600
    assert entry.freshness_stale_seconds > 3 * 86400


def test_cpiaucsl_and_m2sl_run_on_daily_tier_with_monthly_staleness_thresholds() -> None:
    entries = {
        entry.key: entry
        for entry in load_registry().root
        if entry.key in {"macro_cpiaucsl", "macro_m2sl"}
    }

    assert set(entries) == {"macro_cpiaucsl", "macro_m2sl"}
    for entry in entries.values():
        assert entry.expected_update_interval_seconds == 86400
        assert entry.freshness_warn_seconds == 3888000
        assert entry.freshness_stale_seconds == 5184000
        assert entry.freshness_stale_seconds > 30 * 86400


def test_fred_entries_disclose_mirror_not_independent_corroboration_reason() -> None:
    entries = tuple(entry for entry in load_registry().root if entry.vendor == "fred")

    assert {entry.key for entry in entries} == set(FRED_SERIES_KEYS.values())
    for entry in entries:
        assert entry.corroboration is None
        assert entry.uncorroborated is not None
        assert entry.uncorroborated.note == FRED_UNCORROBORATED_NOTE


def test_fred_entries_pass_registry_coverage() -> None:
    fred_entries = tuple(entry for entry in load_registry().root if entry.vendor == "fred")

    assert len(fred_entries) == 7
    assert_registry_coverage(
        IndicatorRegistry.model_validate(fred_entries),
        golden_keys=golden_keys(),
        response_models=RESPONSE_MODELS,
    )


def test_stablecoin_supply_is_registered_for_eth_sol_and_bsc_only() -> None:
    entry = next(entry for entry in load_registry().root if entry.key == "stablecoin_supply")

    assert entry.vendor == "defillama"
    assert entry.endpoint == "https://stablecoins.llama.fi/stablecoinchains"
    assert "/stablecoin/" not in entry.endpoint
    assert entry.definable_for == ("ETH", "SOL", "BNB")
    assert entry.response_model == "defillama_stablecoinchains"
    assert entry.golden == "fixtures/defillama_stablecoinchains.json"
    assert entry.required_bars == 1
    assert entry.parameters == {}
    assert "totalCirculatingUSD.peggedUSD" in entry.source_field
    assert "USD-pegged only" in entry.source_field
    assert "all pegs" not in entry.source_field.casefold()


def test_btc_stablecoin_supply_declares_bitcoin_chain_list_absence() -> None:
    entry = next(entry for entry in load_registry().root if entry.key == "stablecoin_supply")

    assert entry.not_definable is not None
    assert entry.not_definable.assets == ("BTC",)
    reason = entry.not_definable.reason_for("BTC")
    assert "DefiLlama" in reason
    assert "/stablecoinchains" in reason
    assert "no Bitcoin entry" in reason
    assert "Bitcoin has no stablecoin-supply concept" in reason
    assert "SoSoValue" not in reason
    assert "BNB" not in reason


def test_no_global_stablecoin_supply_total_is_registered() -> None:
    entries = tuple(entry for entry in load_registry().root if "stablecoin" in entry.key)

    assert {entry.key for entry in entries} == {"stablecoin_supply"}
    stablecoin_entry = entries[0]
    assert stablecoin_entry.endpoint.endswith("/stablecoinchains")
    assert stablecoin_entry.definable_for == ("ETH", "SOL", "BNB")
    assert "global" not in stablecoin_entry.key
    assert "global" not in stablecoin_entry.source_field.casefold()


def test_registry_rejects_unsupported_cadence_interval_at_load_time(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        REGISTRY_PATH.read_text(encoding="utf-8").replace(
            "expected_update_interval_seconds: 86400",
            "expected_update_interval_seconds: 604801",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="unsupported.*cadence tier filter"):
        load_registry(registry_path)


def test_funding_rate_is_registered_once_per_asset_without_talib() -> None:
    entries = tuple(
        entry for entry in load_registry().root if entry.key.endswith("_funding_rate")
    )

    assert {entry.definable_for[0] for entry in entries} == {
        "BTC",
        "ETH",
        "SOL",
        "BNB",
    }
    assert all(entry.talib_function is None for entry in entries)


def test_mvrv_is_registered_for_btc_eth_bnb_without_talib() -> None:
    entries = tuple(
        entry for entry in load_registry().root if entry.key.endswith("_mvrv")
    )

    assert {entry.definable_for[0] for entry in entries} == {
        "BTC",
        "ETH",
        "BNB",
    }
    assert len(entries) == 3
    assert all(entry.vendor == "coinmetrics" for entry in entries)
    assert all(entry.talib_function is None for entry in entries)
    assert all(entry.parameters == {} for entry in entries)
    assert all(entry.response_model == "coinmetrics_asset_metrics" for entry in entries)


def test_mvrv_entries_declare_sol_not_definable_with_researched_reason() -> None:
    entries = tuple(
        entry for entry in load_registry().root if entry.key.endswith("_mvrv")
    )

    assert len(entries) == 3
    for entry in entries:
        assert entry.not_definable is not None
        assert entry.not_definable.assets == ("SOL",)
        reason = entry.not_definable.reason
        assert "account-based" in reason
        assert "no UTXO" in reason
        assert "No vendor researched" in reason
        assert "Coin Metrics, Glassnode, CryptoQuant, Messari, Santiment" in reason


def test_mvrv_entries_declare_uncorroborated_coinmetrics_source() -> None:
    entries = tuple(
        entry for entry in load_registry().root if entry.key.endswith("_mvrv")
    )

    assert len(entries) == 3
    for entry in entries:
        assert entry.uncorroborated is not None
        assert entry.corroboration is None
        assert entry.uncorroborated.note == (
            "Coin Metrics is the only researched source for CapMVRVCur in this "
            "PRD, so this MVRV value has no independent corroborating venue."
        )


def test_active_addresses_is_registered_for_btc_eth_bnb_without_talib() -> None:
    entries = tuple(
        entry
        for entry in load_registry().root
        if entry.key.endswith("_active_addresses")
    )

    assert {entry.definable_for[0] for entry in entries} == {
        "BTC",
        "ETH",
        "BNB",
        "SOL",
    }
    assert len(entries) == 4
    coinmetrics_entries = tuple(
        entry for entry in entries if entry.definable_for[0] != "SOL"
    )
    sol_entry = next(entry for entry in entries if entry.definable_for[0] == "SOL")
    assert all(entry.vendor == "coinmetrics" for entry in coinmetrics_entries)
    assert sol_entry.vendor == "helius"
    assert all(entry.talib_function is None for entry in entries)
    assert all(entry.parameters == {} for entry in entries)
    assert all(
        entry.response_model == "coinmetrics_asset_metrics"
        for entry in coinmetrics_entries
    )
    assert sol_entry.response_model == "solana_get_block"
    assert all(entry.source_field == "data[].AdrActCnt" for entry in coinmetrics_entries)
    assert "not a 24-hour count" in sol_entry.source_field
    assert all("metrics=AdrActCnt" in entry.endpoint for entry in coinmetrics_entries)


def test_active_addresses_entries_declare_uncorroborated_coinmetrics_source() -> None:
    entries = tuple(
        entry
        for entry in load_registry().root
        if entry.key.endswith("_active_addresses")
    )

    assert len(entries) == 4
    for entry in entries:
        assert entry.uncorroborated is not None
        assert entry.corroboration is None
    for entry in entries:
        if entry.definable_for[0] == "SOL":
            assert "one-hour method" in entry.uncorroborated.note
            continue
        assert entry.uncorroborated.note == (
            "Coin Metrics is the only researched source for AdrActCnt in this "
            "PRD, so this active-addresses value has no independent corroborating "
            "venue."
        )


def test_staking_is_registered_for_sol_without_talib() -> None:
    entries = tuple(
        entry for entry in load_registry().root if entry.key.endswith("_staking")
    )

    assert len(entries) == 1
    entry = entries[0]
    assert entry.key == "sol_staking"
    assert entry.vendor == "validators_app"
    assert entry.definable_for == ("SOL",)
    assert entry.talib_function is None
    assert entry.parameters == {}
    assert entry.response_model == "validators_app_validators"
    assert entry.source_field == (
        "sum of active_stake across every mainnet validator from Validators.app "
        "validators/mainnet, converted from lamports to SOL (the epochs endpoint's "
        "total_active_stake is permanently null, confirmed live 2026-09-16)"
    )
    assert "validators/mainnet.json?per=2000" in entry.endpoint


def test_sol_staking_entry_declares_uncorroborated_validators_app_source() -> None:
    entry = next(entry for entry in load_registry().root if entry.key == "sol_staking")

    assert entry.uncorroborated is not None
    assert entry.corroboration is None
    assert entry.uncorroborated.note == (
        "Validators.app is the only researched free source used for SOL staking "
        "in this PRD, so this staking value has no independent corroborating venue."
    )


def test_staking_declares_btc_eth_bnb_not_definable_with_distinct_reasons() -> None:
    entry = next(entry for entry in load_registry().root if entry.key == "sol_staking")

    assert entry.not_definable is not None
    assert entry.not_definable.assets == ("BTC", "ETH", "BNB")
    reasons = {
        asset: entry.not_definable.reason_for(asset)
        for asset in entry.not_definable.assets
    }

    assert "Proof-of-work has no staking concept" in reasons["BTC"]
    for asset in ("ETH", "BNB"):
        assert "Out of scope for this PRD's on-chain panel" in reasons[asset]
        assert (
            "SOL staking is research R8's specific build recommendation"
            in reasons[asset]
        )
        assert f"not a claim that {asset} staking is undefined" in reasons[asset]
        assert "proof-of-work" not in reasons[asset].casefold()
    assert reasons["ETH"] != reasons["BTC"]
    assert reasons["BNB"] != reasons["BTC"]


def test_exchange_flow_is_registered_for_btc_eth_only_without_talib() -> None:
    entries = tuple(
        entry
        for entry in load_registry().root
        if entry.key.endswith("_exchange_flow")
    )

    assert {entry.definable_for[0] for entry in entries} == {"BTC", "ETH"}
    assert len(entries) == 2
    assert all(entry.vendor == "coinmetrics" for entry in entries)
    assert all(entry.talib_function is None for entry in entries)
    assert all(entry.parameters == {} for entry in entries)
    assert all(entry.response_model == "coinmetrics_asset_metrics" for entry in entries)
    assert all(
        entry.source_field == "data[].FlowInExNtv - data[].FlowOutExNtv"
        for entry in entries
    )
    assert all(
        "metrics=FlowInExNtv,FlowOutExNtv" in entry.endpoint for entry in entries
    )


def test_exchange_flow_declares_bnb_and_sol_not_definable_with_distinct_reasons() -> None:
    entries = tuple(
        entry
        for entry in load_registry().root
        if entry.key.endswith("_exchange_flow")
    )
    reasons = {
        asset: entry.not_definable.reason
        for entry in entries
        if entry.not_definable is not None
        for asset in entry.not_definable.assets
    }

    assert set(reasons) == {"BNB", "SOL"}
    assert "Coin Metrics" in reasons["BNB"]
    assert "NO-METRIC" in reasons["BNB"] or "bad_parameter" in reasons["BNB"]
    assert "FlowInExNtv" in reasons["BNB"]
    assert "FlowOutExNtv" in reasons["BNB"]
    assert "exchange-wallet labeling ecosystem" in reasons["SOL"]
    assert "confidently-wrong number" in reasons["SOL"]
    assert reasons["BNB"] != reasons["SOL"]


def test_exchange_flow_entries_declare_uncorroborated_coinmetrics_source() -> None:
    entries = tuple(
        entry
        for entry in load_registry().root
        if entry.key.endswith("_exchange_flow")
    )

    assert len(entries) == 2
    for entry in entries:
        assert entry.uncorroborated is not None
        assert entry.corroboration is None
        assert entry.uncorroborated.note == (
            "Coin Metrics is the only researched source for FlowInExNtv and "
            "FlowOutExNtv in this PRD, so this exchange-flow value has no "
            "independent corroborating venue."
        )


def test_funding_rate_entries_declare_g1_uncorroborated_reason() -> None:
    entries = tuple(
        entry for entry in load_registry().root if entry.key.endswith("_funding_rate")
    )

    assert len(entries) == 4
    for entry in entries:
        assert entry.uncorroborated is not None
        assert entry.uncorroborated.note == (
            "No second venue's derivatives public endpoints were confirmed to "
            "exist or be reachable; Binance's futures API returns HTTP 451 to "
            "US IPs on public endpoints."
        )


def test_open_interest_is_registered_once_per_asset_without_talib() -> None:
    entries = tuple(
        entry for entry in load_registry().root if entry.key.endswith("_open_interest")
    )

    assert {entry.definable_for[0] for entry in entries} == {
        "BTC",
        "ETH",
        "SOL",
        "BNB",
    }
    assert all(entry.talib_function is None for entry in entries)
    assert all(entry.uncorroborated is not None for entry in entries)
    assert all("USDT-SWAP" in entry.endpoint for entry in entries)
    assert all("-USD-SWAP" not in entry.endpoint for entry in entries)


def test_long_short_ratio_is_registered_once_per_asset_without_talib() -> None:
    entries = tuple(
        entry
        for entry in load_registry().root
        if entry.key.endswith("_long_short_ratio")
    )

    assert {entry.definable_for[0] for entry in entries} == {
        "BTC",
        "ETH",
        "SOL",
        "BNB",
    }
    assert len(entries) == 4
    assert all(entry.talib_function is None for entry in entries)
    assert all(entry.uncorroborated is not None for entry in entries)
    assert all(entry.response_model == "okx_long_short_ratio" for entry in entries)


def test_taker_ratio_is_registered_once_per_asset_without_talib() -> None:
    entries = tuple(
        entry for entry in load_registry().root if entry.key.endswith("_taker_ratio")
    )

    assert {entry.definable_for[0] for entry in entries} == {
        "BTC",
        "ETH",
        "SOL",
        "BNB",
    }
    assert len(entries) == 4
    assert all(entry.talib_function is None for entry in entries)
    assert all(entry.uncorroborated is not None for entry in entries)
    assert all(entry.response_model == "okx_taker_volume" for entry in entries)
