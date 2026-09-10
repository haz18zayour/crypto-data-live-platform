from collections.abc import Iterator

import pytest
import talib

TALIB_UNSTABLE_FUNCTIONS = (
    "ADX",
    "ADXR",
    "ATR",
    "CMO",
    "DX",
    "EMA",
    "HT_DCPERIOD",
    "HT_DCPHASE",
    "HT_PHASOR",
    "HT_SINE",
    "HT_TRENDLINE",
    "HT_TRENDMODE",
    "KAMA",
    "MAMA",
    "MFI",
    "MINUS_DI",
    "MINUS_DM",
    "NATR",
    "PLUS_DI",
    "PLUS_DM",
    "RSI",
    "STOCHRSI",
    "T3",
)


def assert_talib_unstable_periods_are_default() -> None:
    changed = {
        function: period
        for function in TALIB_UNSTABLE_FUNCTIONS
        if (period := talib.get_unstable_period(function)) != 0
    }
    assert not changed, f"TA-Lib unstable periods must remain at default 0; changed: {changed}"


@pytest.fixture(autouse=True)
def guard_talib_unstable_periods() -> Iterator[None]:
    assert_talib_unstable_periods_are_default()
    yield
    assert_talib_unstable_periods_are_default()
