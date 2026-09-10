"""TA-Lib indicator calculations pinned to externally published conventions."""

from collections.abc import Mapping, Sequence

import numpy as np
import talib
from talib._ta_lib import MA_Type


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
