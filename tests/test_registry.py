import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest.registry import load_registry

VALID_ENTRY = {
    "key": "btc_daily_close",
    "vendor": "okx",
    "endpoint": "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D",
    "source_field": 'candle[4] (close), where candle[8] == "1"',
    "definable_for": ["BTC"],
    "expected_update_interval_seconds": 86400,
    "freshness_warn_seconds": 108000,
    "freshness_stale_seconds": 172800,
}


def write_registry(path: Path, entries: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(entries), encoding="utf-8")


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
    entry = VALID_ENTRY.copy()
    entry.pop(missing_field)
    registry_path = tmp_path / "registry.yaml"
    write_registry(registry_path, [entry])

    with pytest.raises(ValidationError):
        load_registry(registry_path)


def test_entry_without_source_field_is_rejected(tmp_path: Path) -> None:
    entry = VALID_ENTRY.copy()
    entry.pop("source_field")
    registry_path = tmp_path / "registry.yaml"
    write_registry(registry_path, [entry])

    with pytest.raises(ValidationError, match="source_field"):
        load_registry(registry_path)


def test_registry_rejects_duplicate_indicator_keys(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.yaml"
    write_registry(registry_path, [VALID_ENTRY, VALID_ENTRY])

    with pytest.raises(
        ValidationError, match="Duplicate indicator key: btc_daily_close"
    ):
        load_registry(registry_path)


@pytest.mark.parametrize("wildcard", ("*", "all", "ALL"))
def test_definable_for_rejects_wildcards(tmp_path: Path, wildcard: str) -> None:
    entry = VALID_ENTRY | {"definable_for": [wildcard]}
    registry_path = tmp_path / "registry.yaml"
    write_registry(registry_path, [entry])

    with pytest.raises(ValidationError, match="wildcard"):
        load_registry(registry_path)


def test_shipped_registry_declares_only_btc_daily_close() -> None:
    registry = load_registry()

    assert [entry.key for entry in registry.root] == ["btc_daily_close"]
    assert registry.root[0].definable_for == ("BTC",)
