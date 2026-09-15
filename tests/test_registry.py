from pathlib import Path

import pytest
from pydantic import ValidationError

from ingest.registry import load_registry

VALID_ENTRY = """\
- key: btc_daily_close
  vendor: okx
  endpoint: https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D
  source_field: 'candle[4] (close), where candle[8] == "1"'
  definable_for: [BTC]
  expected_update_interval_seconds: 86400
  freshness_warn_seconds: 108000
  freshness_stale_seconds: 172800
"""


def write_registry(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")


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

    assert len(registry.root) == 64
    assert {asset for entry in registry.root for asset in entry.definable_for} == {
        "BTC",
        "ETH",
        "SOL",
        "BNB",
    }
    assert all(len(entry.definable_for) == 1 for entry in registry.root)


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
    entries = tuple(entry for entry in load_registry().root if entry.key.endswith("_mvrv"))

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
    entries = tuple(entry for entry in load_registry().root if entry.key.endswith("_mvrv"))

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
    entries = tuple(entry for entry in load_registry().root if entry.key.endswith("_mvrv"))

    assert len(entries) == 3
    for entry in entries:
        assert entry.uncorroborated is not None
        assert entry.corroboration is None
        assert entry.uncorroborated.note == (
            "Coin Metrics is the only researched source for CapMVRVCur in this "
            "PRD, so this MVRV value has no independent corroborating venue."
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
    assert all(
        entry.response_model == "okx_long_short_ratio" for entry in entries
    )


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
