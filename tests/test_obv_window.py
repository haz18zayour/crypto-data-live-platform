import json
from pathlib import Path
from typing import Any

from ingest.compute import compute_indicator
from ingest.indicators import obv
from ingest.registry import load_registry

GOLDEN_PATH = (
    Path(__file__).with_name("goldens") / "hand_computed" / "obv_base_volume.json"
)


def load_golden() -> dict[str, Any]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def test_obv_declares_a_real_window_and_its_value_depends_on_history() -> None:
    golden = load_golden()
    bars = golden["input_bars"]
    definitions = tuple(
        definition
        for definition in load_registry().root
        if definition.talib_function == "OBV"
    )
    one_bar_value = obv(bars[-1:])
    history_value = obv(bars)

    assert len(definitions) == 4
    assert one_bar_value == bars[-1]["volume"]
    assert history_value != one_bar_value
    for definition in definitions:
        assert definition.required_bars == len(bars) > 1


def test_obv_over_each_declared_window_matches_the_hand_computed_golden() -> None:
    golden = load_golden()
    expected = golden["expected_outputs"][-1]
    definitions = tuple(
        definition
        for definition in load_registry().root
        if definition.talib_function == "OBV"
    )

    assert len(definitions) == 4
    for definition in definitions:
        assert compute_indicator(definition, golden["input_bars"], obv) == expected
