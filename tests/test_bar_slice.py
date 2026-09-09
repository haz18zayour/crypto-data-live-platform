import struct
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
from pydantic import ValidationError

from ingest.compute import compute_indicator
from ingest.registry import IndicatorDefinition, load_registry


def definition(required_bars: int) -> IndicatorDefinition:
    return IndicatorDefinition(
        key="test_indicator",
        vendor="test-vendor",
        endpoint="https://example.test/bars",
        source_field="bars.close",
        definable_for=("BTC",),
        required_bars=required_bars,
        expected_update_interval_seconds=86_400,
        freshness_warn_seconds=108_000,
        freshness_stale_seconds=172_800,
    )


def mean(bars: Sequence[float]) -> float:
    return sum(bars) / len(bars)


def test_registry_rejects_an_indicator_with_no_required_bars(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """\
- key: btc_daily_close
  vendor: okx
  endpoint: https://example.test/bars
  source_field: candle[4]
  definable_for: [BTC]
  expected_update_interval_seconds: 86400
  freshness_warn_seconds: 108000
  freshness_stale_seconds: 172800
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="required_bars"):
        load_registry(registry_path)


def test_compute_rejects_a_slice_longer_than_required_bars() -> None:
    bars = tuple(float(value) for value in range(600))

    with pytest.raises(ValueError, match="expected exactly 500 bars, received 600"):
        compute_indicator(definition(500), bars, mean)


def test_compute_rejects_a_slice_shorter_than_required_bars() -> None:
    bars = tuple(float(value) for value in range(499))

    with pytest.raises(ValueError, match="expected exactly 500 bars, received 499"):
        compute_indicator(definition(500), bars, mean)


def test_the_same_bars_produce_the_same_value_across_repeated_calls() -> None:
    indicator = definition(3)
    bars = (1.25, 2.5, 5.0)
    first = struct.pack("!d", compute_indicator(indicator, bars, mean))
    second = struct.pack("!d", compute_indicator(indicator, bars, mean))

    program = """
import struct
from collections.abc import Sequence
from ingest.compute import compute_indicator
from ingest.registry import IndicatorDefinition

def mean(bars: Sequence[float]) -> float:
    return sum(bars) / len(bars)

indicator = IndicatorDefinition(
    key="test_indicator",
    vendor="test-vendor",
    endpoint="https://example.test/bars",
    source_field="bars.close",
    definable_for=("BTC",),
    required_bars=3,
    expected_update_interval_seconds=86400,
    freshness_warn_seconds=108000,
    freshness_stale_seconds=172800,
)
print(struct.pack("!d", compute_indicator(indicator, (1.25, 2.5, 5.0), mean)).hex())
"""
    fresh_process = subprocess.run(
        [sys.executable, "-c", program],
        check=True,
        capture_output=True,
        text=True,
    )

    assert first == second == bytes.fromhex(fresh_process.stdout.strip())


def test_a_growing_cache_cannot_change_a_computed_value() -> None:
    indicator = definition(500)
    cache = [float(value) for value in range(500)]
    value_from_seed = compute_indicator(indicator, cache, mean)

    cache.extend(float(value) for value in range(500, 600))

    assert value_from_seed == 249.5
    with pytest.raises(ValueError, match="expected exactly 500 bars, received 600"):
        compute_indicator(indicator, cache, mean)
