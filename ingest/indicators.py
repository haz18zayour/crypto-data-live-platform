"""TA-Lib indicator calculations pinned to externally published conventions."""

from collections.abc import Mapping, Sequence

import numpy as np
import talib
from talib._ta_lib import MA_Type


def rsi(bars: Sequence[Mapping[str, float]], period: int = 14) -> float:
    """Return Wilder's RSI for the newest bar."""

    closes = np.asarray([bar["close"] for bar in bars], dtype=np.float64)
    return float(talib.RSI(closes, timeperiod=period)[-1])


def ema(bars: Sequence[Mapping[str, float]], period: int) -> float:
    """Return the exponential moving average for the newest bar."""

    closes = np.asarray([bar["close"] for bar in bars], dtype=np.float64)
    return float(talib.EMA(closes, timeperiod=period)[-1])


def atr(bars: Sequence[Mapping[str, float]], period: int = 14) -> float:
    """Return Wilder's ATR for the newest bar using the first high-low as TR."""

    first_close = bars[0]["close"]
    highs = np.asarray(
        [first_close, *(bar["high"] for bar in bars)], dtype=np.float64
    )
    lows = np.asarray(
        [first_close, *(bar["low"] for bar in bars)], dtype=np.float64
    )
    closes = np.asarray(
        [first_close, *(bar["close"] for bar in bars)], dtype=np.float64
    )
    return float(talib.ATR(highs, lows, closes, timeperiod=period)[-1])


def bollinger_bands(
    bars: Sequence[Mapping[str, float]],
    period: int = 20,
    deviations: float = 2.0,
) -> tuple[float, float, float]:
    """Return upper, middle, and lower simple bands using population stdev."""

    closes = np.asarray([bar["close"] for bar in bars], dtype=np.float64)
    upper, middle, lower = talib.BBANDS(
        closes,
        timeperiod=period,
        nbdevup=deviations,
        nbdevdn=deviations,
        matype=MA_Type.SMA,
    )
    return float(upper[-1]), float(middle[-1]), float(lower[-1])


def obv(bars: Sequence[Mapping[str, float]]) -> float:
    """Return OBV for the newest bar, accumulating venue base volume."""

    closes = np.asarray([bar["close"] for bar in bars], dtype=np.float64)
    base_volumes = np.asarray([bar["volume"] for bar in bars], dtype=np.float64)
    return float(talib.OBV(closes, base_volumes)[-1])


def macd(
    bars: Sequence[Mapping[str, float]],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[float, float, float]:
    """Return the MACD line, signal line, and histogram for the newest bar."""

    closes = np.asarray([bar["close"] for bar in bars], dtype=np.float64)
    line, signal, histogram = talib.MACD(
        closes,
        fastperiod=fast_period,
        slowperiod=slow_period,
        signalperiod=signal_period,
    )
    return float(line[-1]), float(signal[-1]), float(histogram[-1])


def stochrsi(
    bars: Sequence[Mapping[str, float]],
    rsi_period: int = 14,
    stochastic_period: int = 14,
    k_smoothing_period: int = 3,
) -> float:
    """Return TradingView-style StochRSI K for the newest bar."""

    closes = np.asarray([bar["close"] for bar in bars], dtype=np.float64)
    _, fastd = talib.STOCHRSI(
        closes,
        timeperiod=rsi_period,
        fastk_period=stochastic_period,
        fastd_period=k_smoothing_period,
        fastd_matype=MA_Type.SMA,
    )
    return float(fastd[-1])
