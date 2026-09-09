import json
from pathlib import Path

import pytest

from ingest.canary import RESPONSE_MODELS
from ingest.registry import (
    IndicatorDefinition,
    IndicatorRegistry,
    assert_registry_coverage,
    load_registry,
)

GOLDEN_DIRECTORY = Path(__file__).with_name("goldens")


def golden_keys() -> set[str]:
    return {
        json.loads(path.read_text(encoding="utf-8"))["indicator_key"]
        for path in GOLDEN_DIRECTORY.glob("*.json")
    }


def definition(
    key: str = "new_indicator",
    vendor: str = "new-vendor",
    required_bars: int | None = 1,
) -> IndicatorDefinition:
    return IndicatorDefinition.model_construct(
        key=key,
        vendor=vendor,
        endpoint="https://example.test/data",
        source_field="data.value",
        definable_for=("BTC",),
        required_bars=required_bars,
        expected_update_interval_seconds=86_400,
        freshness_warn_seconds=108_000,
        freshness_stale_seconds=172_800,
    )


def registry_with(*entries: IndicatorDefinition) -> IndicatorRegistry:
    return IndicatorRegistry.model_construct(root=entries)


def test_every_registry_entry_has_a_golden_file() -> None:
    uncovered = definition()

    with pytest.raises(AssertionError, match=r"new_indicator.*golden file"):
        assert_registry_coverage(
            registry_with(uncovered),
            golden_keys=set(),
            response_models={uncovered.key: object()},
        )


def test_every_registry_entry_has_a_required_bars_declaration() -> None:
    uncovered = definition(required_bars=None)

    with pytest.raises(AssertionError, match=r"new_indicator.*required_bars"):
        assert_registry_coverage(
            registry_with(uncovered),
            golden_keys={uncovered.key},
            response_models={uncovered.key: object()},
        )


def test_every_registered_vendor_has_a_response_model() -> None:
    uncovered = definition()

    with pytest.raises(AssertionError, match=r"new-vendor.*response model"):
        assert_registry_coverage(
            registry_with(uncovered),
            golden_keys={uncovered.key},
            response_models={},
        )


def test_adding_an_indicator_fails_coverage_until_it_is_covered() -> None:
    registered = load_registry()
    added = definition()
    expanded = IndicatorRegistry.model_validate((*registered.root, added))

    with pytest.raises(AssertionError, match="new_indicator"):
        assert_registry_coverage(
            expanded,
            golden_keys=golden_keys(),
            response_models=RESPONSE_MODELS,
        )


@pytest.mark.integration
def test_assembled_coverage_check_passes_over_the_real_registry() -> None:
    assert_registry_coverage(
        load_registry(),
        golden_keys=golden_keys(),
        response_models=RESPONSE_MODELS,
    )
