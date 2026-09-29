from pathlib import Path

import pytest

from ingest.registry import (
    IndicatorDefinition,
    IndicatorRegistry,
    assert_registry_coverage,
    load_registry,
)

MVRV_REGISTRY_ENTRY = """\
- key: btc_mvrv
  vendor: coin_metrics
  endpoint: https://community-api.coinmetrics.io/v4/timeseries/asset-metrics
  source_field: data[].CapMVRVCur
  definable_for: [BTC]
  required_bars: 1
  frozen_after_observations: 3
  expected_update_interval_seconds: 86400
  freshness_warn_seconds: 108000
  freshness_stale_seconds: 172800
  uncorroborated:
    note: Coin Metrics resolves multiple venues, excludes market VWAPs over 3% from the median, and publishes no dispersion.
"""


def write_registry(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")


def test_an_indicator_with_no_second_source_is_marked_uncorroborated_in_the_registry(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    write_registry(registry_path, MVRV_REGISTRY_ENTRY)

    definition = load_registry(registry_path).root[0]

    assert definition.corroboration is None
    assert definition.uncorroborated is not None
    assert "resolves multiple venues" in definition.uncorroborated.note
    assert "publishes no dispersion" in definition.uncorroborated.note


def test_a_corroborated_and_an_uncorroborated_value_are_distinguishable_in_stored_data(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    write_registry(registry_path, MVRV_REGISTRY_ENTRY)
    uncorroborated = load_registry(registry_path).root[0]
    corroborated = load_registry().root[0]

    corroborated_storage = corroborated.model_dump(
        include={"corroboration", "uncorroborated"}
    )
    uncorroborated_storage = uncorroborated.model_dump(
        include={"corroboration", "uncorroborated"}
    )

    assert corroborated_storage != uncorroborated_storage
    assert corroborated_storage["corroboration"] is not None
    assert corroborated_storage["uncorroborated"] is None
    assert uncorroborated_storage["corroboration"] is None
    assert uncorroborated_storage["uncorroborated"] is not None
    assert corroborated.corroboration is not None
    assert corroborated.uncorroborated is None
    assert uncorroborated.corroboration is None
    assert uncorroborated.uncorroborated is not None


def test_registry_validation_rejects_an_indicator_that_declares_neither_a_second_source_nor_uncorroborated(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    write_registry(
        registry_path,
        MVRV_REGISTRY_ENTRY.replace(
            "  uncorroborated:\n"
            "    note: Coin Metrics resolves multiple venues, excludes market VWAPs over 3% from the median, and publishes no dispersion.\n",
            "",
        ),
    )

    with pytest.raises(ValueError, match="corroboration declaration"):
        load_registry(registry_path)


def test_coverage_from_prd_002_includes_the_corroboration_declaration() -> None:
    missing_declaration = IndicatorDefinition.model_construct(
        key="new_indicator",
        vendor="new-vendor",
        endpoint="https://example.test/data",
        source_field="data.value",
        definable_for=("BTC",),
        required_bars=1,
        frozen_after_observations=3,
        expected_update_interval_seconds=86_400,
        freshness_warn_seconds=108_000,
        freshness_stale_seconds=172_800,
    )
    registry = IndicatorRegistry.model_construct(root=(missing_declaration,))

    with pytest.raises(AssertionError, match="corroboration declaration"):
        assert_registry_coverage(
            registry,
            golden_keys={missing_declaration.key},
            response_models={missing_declaration.key: object()},
        )
