"""TA-Lib indicator calculations pinned to externally published conventions."""

from collections.abc import Mapping, Sequence

import numpy as np
import talib


def rsi(bars: Sequence[Mapping[str, float]], period: int = 14) -> float:
    """Return Wilder's RSI for the newest bar."""

    closes = np.asarray([bar["close"] for bar in bars], dtype=np.float64)
    return float(talib.RSI(closes, timeperiod=period)[-1])


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
