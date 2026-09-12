import json
from pathlib import Path
from typing import Any

import pytest

from ingest.indicators import ema
from ingest.registry import IndicatorDefinition, load_registry

ASSETS = {"BTC", "ETH", "SOL", "BNB"}
PERIODS = {20, 50, 200}
GOLDEN_PATH = (
    Path(__file__).with_name("goldens") / "hand_computed" / "ema_20_50_200.json"
)


def load_golden() -> dict[str, Any]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def ema_definitions() -> tuple[IndicatorDefinition, ...]:
    return tuple(
        definition
        for definition in load_registry().root
        if definition.talib_function == "EMA"
    )


def test_load_registry_returns_ema_20_50_200_for_every_supported_asset() -> None:
    definitions = ema_definitions()

    assert len(definitions) == len(ASSETS) * len(PERIODS) == 12
    assert all(
        isinstance(definition, IndicatorDefinition) for definition in definitions
    )
    assert {
        (definition.definable_for[0], int(definition.parameters["timeperiod"]))
        for definition in definitions
        if definition.parameters is not None
    } == {(asset, period) for asset in ASSETS for period in PERIODS}


def test_each_ema_declares_250_bars_and_its_timeperiod_explicitly() -> None:
    definitions = ema_definitions()

    assert len(definitions) == 12
    for definition in definitions:
        assert definition.required_bars == 250
        assert definition.parameters in (
            {"timeperiod": 20},
            {"timeperiod": 50},
            {"timeperiod": 200},
        )


def test_ema_matches_the_independently_computed_golden_for_each_period() -> None:
    golden = load_golden()
    series = golden["input_series"]
    bars = tuple(
        {"close": float(value)}
        for value in range(int(series["start"]), int(series["stop"]) + 1)
    )

    assert golden["external"] is True
    assert golden["source"].strip()
    assert golden["source_url"].startswith("https://")
    assert golden["source_convention"].strip()
    assert series["step"] == 1.0
    assert len(bars) == series["bars"] == 250
    for period in PERIODS:
        hand_computed = 250 - (period - 1) / 2
        assert golden["expected"][str(period)] == hand_computed
        assert ema(bars, period=period) == pytest.approx(
            hand_computed,
            abs=golden["absolute_tolerance"],
            rel=0.0,
        )
