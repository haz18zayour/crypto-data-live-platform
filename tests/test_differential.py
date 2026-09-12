import math
from importlib import import_module
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import pandas_ta_classic as pandas_ta
import pytest
import talib

from ingest.indicators import macd, stochrsi
from ingest.registry import IndicatorDefinition, load_registry

EPSILON = 1e-6
CONVERGED_TAIL_LENGTH = 32


def registered_definition(talib_function: str) -> IndicatorDefinition:
    return next(
        definition
        for definition in load_registry().root
        if definition.talib_function == talib_function
    )


def market_bars(length: int = 500) -> tuple[dict[str, float], ...]:
    return tuple(
        {
            "close": 100
            + index * 0.04
            + math.sin(index / 7) * 3
            + math.cos(index / 3) * 0.7
        }
        for index in range(length)
    )


def native_macd_oracle(
    closes: pd.Series,
    parameters: dict[str, int | float],
    *,
    talib_enabled: bool = False,
) -> pd.DataFrame:
    assert pandas_ta.Imports["talib"] is True, (
        "TA-Lib must be installed so this test can prove delegation was prevented"
    )
    with patch.object(talib, "MACD", wraps=talib.MACD) as delegated:
        result = pandas_ta.macd(
            closes,
            fast=int(parameters["fastperiod"]),
            slow=int(parameters["slowperiod"]),
            signal=int(parameters["signalperiod"]),
            talib=talib_enabled,
        )

    assert delegated.call_count == 0, (
        "the pandas-ta-classic differential oracle delegated to TA-Lib"
    )
    assert result is not None
    return result


def native_stochrsi_oracle(
    closes: pd.Series,
    parameters: dict[str, int | float],
) -> pd.DataFrame:
    assert pandas_ta.Imports["talib"] is True, (
        "TA-Lib must be installed so this test can prove delegation was prevented"
    )
    stochrsi_module = import_module(pandas_ta.stochrsi.__module__)
    native_rsi = stochrsi_module.rsi

    def force_native_rsi(*args: Any, **kwargs: Any) -> Any:
        kwargs["talib"] = False
        return native_rsi(*args, **kwargs)

    with (
        patch.object(talib, "STOCHRSI", wraps=talib.STOCHRSI) as delegated_stochrsi,
        patch.object(talib, "RSI", wraps=talib.RSI) as delegated_rsi,
        patch.object(
            stochrsi_module,
            "rsi",
            side_effect=force_native_rsi,
        ),
    ):
        result = pandas_ta.stochrsi(
            closes,
            length=int(parameters["fastk_period"]),
            rsi_length=int(parameters["timeperiod"]),
            k=int(parameters["fastd_period"]),
            d=3,
            mamode="sma",
            talib=False,
        )

    assert delegated_stochrsi.call_count == delegated_rsi.call_count == 0, (
        "the pandas-ta-classic differential oracle delegated to TA-Lib"
    )
    assert result is not None
    return result


def assert_macd_differential(*, talib_enabled: bool = False) -> None:
    definition = registered_definition("MACD")
    assert definition.parameters is not None
    parameters = definition.parameters
    bars = market_bars()
    closes = pd.Series([bar["close"] for bar in bars], dtype="float64")
    oracle = native_macd_oracle(
        closes, parameters, talib_enabled=talib_enabled
    )
    oracle_tail = np.column_stack(
        (
            oracle.iloc[-CONVERGED_TAIL_LENGTH:, 0],
            oracle.iloc[-CONVERGED_TAIL_LENGTH:, 2],
            oracle.iloc[-CONVERGED_TAIL_LENGTH:, 1],
        )
    )
    actual_tail = np.asarray(
        [
            macd(
                bars[:end],
                fast_period=int(parameters["fastperiod"]),
                slow_period=int(parameters["slowperiod"]),
                signal_period=int(parameters["signalperiod"]),
            )
            for end in range(
                len(bars) - CONVERGED_TAIL_LENGTH + 1,
                len(bars) + 1,
            )
        ]
    )

    assert actual_tail == pytest.approx(oracle_tail, abs=EPSILON, rel=0.0)


def test_the_differential_oracle_asserts_talib_false_is_actually_in_effect() -> None:
    bars = market_bars()
    closes = pd.Series([bar["close"] for bar in bars], dtype="float64")
    macd_parameters = registered_definition("MACD").parameters
    stochrsi_parameters = registered_definition("STOCHRSI").parameters
    assert macd_parameters is not None
    assert stochrsi_parameters is not None

    macd_result = native_macd_oracle(closes, macd_parameters)
    stochrsi_result = native_stochrsi_oracle(closes, stochrsi_parameters)

    assert not macd_result.empty
    assert not stochrsi_result.empty


def test_forcing_the_oracle_to_delegate_to_talib_makes_the_differential_fail() -> (
    None
):
    with pytest.raises(AssertionError, match="oracle delegated to TA-Lib"):
        assert_macd_differential(talib_enabled=True)


def test_macd_agrees_with_the_independent_implementation_within_epsilon_after_warmup() -> (
    None
):
    assert_macd_differential()


def test_stochrsi_agrees_with_the_independent_tradingview_k_after_warmup() -> None:
    definition = registered_definition("STOCHRSI")
    assert definition.parameters is not None
    parameters = definition.parameters
    bars = market_bars()
    closes = pd.Series([bar["close"] for bar in bars], dtype="float64")
    oracle = native_stochrsi_oracle(closes, parameters)
    oracle_k_tail = oracle.iloc[-CONVERGED_TAIL_LENGTH:, 0].to_numpy()
    actual_tail = np.asarray(
        [
            stochrsi(
                bars[:end],
                rsi_period=int(parameters["timeperiod"]),
                stochastic_period=int(parameters["fastk_period"]),
                k_smoothing_period=int(parameters["fastd_period"]),
            )
            for end in range(
                len(bars) - CONVERGED_TAIL_LENGTH + 1,
                len(bars) + 1,
            )
        ]
    )

    assert actual_tail == pytest.approx(oracle_k_tail, abs=EPSILON, rel=0.0)
