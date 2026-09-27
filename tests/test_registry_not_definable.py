from pathlib import Path

import pytest
from pydantic import ValidationError

from ingest.canary import RESPONSE_MODELS
from ingest.registry import (
    IndicatorDefinition,
    assert_registry_coverage,
    load_registry,
)

GOLDEN_DIRECTORY = Path(__file__).with_name("goldens")
FIXTURE_DIRECTORY = Path(__file__).with_name("fixtures")


def definition_data() -> dict[str, object]:
    return {
        "key": "btc_daily_close",
        "vendor": "okx",
        "endpoint": "https://example.test/data",
        "source_field": "data.value",
        "definable_for": ["BTC"],
        "required_bars": 1,
        "parameters": {},
        "expected_update_interval_seconds": 86_400,
        "freshness_warn_seconds": 108_000,
        "freshness_stale_seconds": 172_800,
    }


def test_btc_daily_close_declares_three_reasoned_not_definable_assets() -> None:
    daily_close = next(
        entry for entry in load_registry().root if entry.key == "btc_daily_close"
    )

    assert daily_close.not_definable is not None
    assert daily_close.not_definable.assets == ("ETH", "SOL", "BNB")
    for asset in daily_close.not_definable.assets:
        assert daily_close.not_definable.reason_for(asset).strip()


@pytest.mark.parametrize("reason", (None, "", "   "))
def test_not_definable_requires_a_non_empty_reason(reason: str | None) -> None:
    data = definition_data()
    declaration: dict[str, object] = {"assets": ["ETH", "SOL", "BNB"]}
    if reason is not None:
        declaration["reason"] = reason
    data["not_definable"] = declaration

    with pytest.raises(ValidationError, match="reason"):
        IndicatorDefinition.model_validate(data)


def test_not_definable_accepts_distinct_per_asset_reasons() -> None:
    data = definition_data()
    data["not_definable"] = {
        "assets": ["ETH", "BNB"],
        "reasons": [
            "ETH: Out of scope for this board.",
            "BNB: Out of scope for this board.",
        ],
    }

    definition = IndicatorDefinition.model_validate(data)

    assert definition.not_definable is not None
    assert definition.not_definable.reason_for("ETH") == "Out of scope for this board."
    assert definition.not_definable.reason_for("BNB") == "Out of scope for this board."


def test_not_definable_per_asset_reasons_must_cover_exactly_the_assets() -> None:
    data = definition_data()
    data["not_definable"] = {
        "assets": ["ETH", "BNB"],
        "reasons": ["ETH: Out of scope for this board."],
    }

    with pytest.raises(ValidationError, match="reasons must match assets"):
        IndicatorDefinition.model_validate(data)


def test_asset_cannot_be_both_definable_and_not_definable() -> None:
    data = definition_data()
    data["not_definable"] = {
        "assets": ["BTC", "ETH"],
        "reason": "This board declares daily close for BTC only.",
    }

    with pytest.raises(ValidationError, match="BTC.*definable_for.*not_definable"):
        IndicatorDefinition.model_validate(data)


def test_us_708_registry_not_definable_reasons_are_unique() -> None:
    seen: dict[str, tuple[str, str]] = {}

    for entry in load_registry().root:
        if entry.not_definable is None:
            continue
        for asset in entry.not_definable.assets:
            reason = entry.not_definable.reason_for(asset)
            assert reason not in seen, (
                f"{entry.key}/{asset} repeats not_definable reason from "
                f"{seen[reason][0]}/{seen[reason][1]}: {reason}"
            )
            seen[reason] = (entry.key, asset)


def test_registry_coverage_still_passes_for_all_79_entries() -> None:
    registry = load_registry()

    assert len(registry.root) == 79
    assert_registry_coverage(
        registry,
        golden_keys={
            path.relative_to(GOLDEN_DIRECTORY).as_posix()
            for path in GOLDEN_DIRECTORY.rglob("*.json")
        }
        | {
            f"fixtures/{path.relative_to(FIXTURE_DIRECTORY).as_posix()}"
            for path in FIXTURE_DIRECTORY.rglob("*.json")
        },
        response_models=RESPONSE_MODELS,
    )


def test_bnb_etf_flow_declares_sosovalue_enum_not_definable_reason() -> None:
    etf_flow = next(
        entry for entry in load_registry().root if entry.key == "spot_etf_net_flow"
    )

    assert etf_flow.definable_for == ("BTC", "ETH", "SOL")
    assert etf_flow.not_definable is not None
    assert etf_flow.not_definable.assets == ("BNB",)
    reason = etf_flow.not_definable.reason_for("BNB")
    assert "SoSoValue" in reason
    assert "/etfs/summary-history" in reason
    assert "does not include BNB" in reason
