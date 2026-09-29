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
FIXTURE_DIRECTORY = Path(__file__).with_name("fixtures")


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


def definition(
    key: str = "new_indicator",
    vendor: str = "new-vendor",
    required_bars: int | None = 1,
    parameters: tuple[tuple[str, int | float], ...] | None = (),
    golden: str | None = "new_indicator.json",
    response_model: str | None = "test_response",
) -> IndicatorDefinition:
    return IndicatorDefinition.model_construct(
        key=key,
        vendor=vendor,
        endpoint="https://example.test/data",
        source_field="data.value",
        definable_for=("BTC",),
        required_bars=required_bars,
        parameters=None if parameters is None else dict(parameters),
        golden=golden,
        response_model=response_model,
        expected_update_interval_seconds=86_400,
        freshness_warn_seconds=108_000,
        freshness_stale_seconds=172_800,
    )


def registry_with(*entries: IndicatorDefinition) -> IndicatorRegistry:
    return IndicatorRegistry.model_construct(root=entries)


def test_every_registry_entry_has_a_golden_required_bars_and_response_model() -> (
    None
):
    registry = load_registry()

    assert len(registry.root) == 81
    assert_registry_coverage(
        registry,
        golden_keys=golden_keys(),
        response_models=RESPONSE_MODELS,
    )
    for entry in registry.root:
        assert entry.golden in golden_keys(), entry.key
        assert entry.required_bars is not None, entry.key
        assert entry.key in RESPONSE_MODELS, entry.key


def test_adding_an_uncovered_indicator_fails_coverage_naming_what_is_missing() -> (
    None
):
    registered = load_registry()
    added = definition(
        required_bars=None,
        parameters=None,
        golden=None,
        response_model=None,
    )
    expanded = registry_with(*registered.root, added)

    with pytest.raises(AssertionError) as raised:
        assert_registry_coverage(
            expanded,
            golden_keys=golden_keys(),
            response_models=RESPONSE_MODELS,
        )

    message = str(raised.value)
    assert "new_indicator is missing a golden file" in message
    assert "new_indicator is missing required_bars" in message
    assert "new_indicator is missing a response model" in message
    assert "new_indicator is missing parameters" in message


def test_no_indicator_key_is_duplicated_across_assets() -> None:
    registry = load_registry()
    keys = [entry.key for entry in registry.root]

    assert len(keys) == len(set(keys))


def test_every_indicator_declares_its_parameters_explicitly() -> None:
    for entry in load_registry().root:
        assert entry.parameters is not None, entry.key


@pytest.mark.parametrize(
    ("entry", "goldens", "models", "missing"),
    (
        (
            definition(golden=None),
            set(),
            {"new_indicator": object()},
            "a golden file",
        ),
        (
            definition(required_bars=None),
            {"new_indicator.json"},
            {"new_indicator": object()},
            "required_bars",
        ),
        (definition(), {"new_indicator.json"}, {}, "a response model"),
        (
            definition(parameters=None),
            {"new_indicator.json"},
            {"new_indicator": object()},
            "parameters",
        ),
    ),
)
def test_each_coverage_failure_names_the_specific_indicator_key(
    entry: IndicatorDefinition,
    goldens: set[str],
    models: dict[str, object],
    missing: str,
) -> None:
    with pytest.raises(
        AssertionError,
        match=rf"{entry.key} is missing {missing}",
    ):
        assert_registry_coverage(
            registry_with(entry),
            golden_keys=goldens,
            response_models=models,
        )


@pytest.mark.integration
def test_assembled_coverage_check_passes_over_the_real_registry() -> None:
    assert_registry_coverage(
        load_registry(),
        golden_keys=golden_keys(),
        response_models=RESPONSE_MODELS,
    )
