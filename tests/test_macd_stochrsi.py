import json
from pathlib import Path
from typing import Any

import pytest

from ingest.canary import RESPONSE_MODELS
from ingest.indicators import macd, stochrsi
from ingest.registry import load_registry
from ingest.schemas import OkxCandleResponse

GOLDEN_DIRECTORY = Path(__file__).with_name("goldens")


def load_golden(name: str) -> dict[str, Any]:
    return json.loads(
        (GOLDEN_DIRECTORY / name).read_text(encoding="utf-8")
    )


def test_macd_and_stochrsi_goldens_record_the_native_oracle_provenance() -> None:
    for name in ("btc_macd.json", "btc_stochrsi.json"):
        golden = load_golden(name)

        assert len(golden["input_bars"]) == 250
        assert golden["external"] is True
        assert "pandas-ta-classic 0.6.52 native" in golden["source"]
        assert "TA-Lib calls were rejected by spies" in golden["source"]


def test_oracle_goldens_match_talib_using_the_loaded_registry_parameters() -> None:
    definitions = {entry.key: entry for entry in load_registry().root}
    macd_golden = load_golden("btc_macd.json")
    stochrsi_golden = load_golden("btc_stochrsi.json")
    macd_parameters = definitions["btc_macd"].parameters
    stochrsi_parameters = definitions["btc_stochrsi"].parameters
    assert macd_parameters is not None
    assert stochrsi_parameters is not None

    actual_macd = macd(
        macd_golden["input_bars"],
        fast_period=int(macd_parameters["fastperiod"]),
        slow_period=int(macd_parameters["slowperiod"]),
        signal_period=int(macd_parameters["signalperiod"]),
    )
    actual_stochrsi = stochrsi(
        stochrsi_golden["input_bars"],
        rsi_period=int(stochrsi_parameters["timeperiod"]),
        stochastic_period=int(stochrsi_parameters["fastk_period"]),
        k_smoothing_period=int(stochrsi_parameters["fastd_period"]),
    )

    assert actual_macd == pytest.approx(
        macd_golden["expected_outputs"],
        abs=macd_golden["absolute_tolerance"],
        rel=0.0,
    )
    assert actual_stochrsi == pytest.approx(
        stochrsi_golden["expected"],
        abs=stochrsi_golden["absolute_tolerance"],
        rel=0.0,
    )


def test_macd_and_stochrsi_reuse_the_strict_okx_candle_response_model() -> None:
    assert RESPONSE_MODELS["btc_macd"] is OkxCandleResponse
    assert RESPONSE_MODELS["btc_stochrsi"] is OkxCandleResponse
