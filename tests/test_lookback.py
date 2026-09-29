import pytest
from pydantic import ValidationError
from talib import abstract

from ingest.registry import IndicatorDefinition, IndicatorRegistry, load_registry


def definition(
    function: str,
    parameters: dict[str, int | float] | None,
    required_bars: int,
) -> IndicatorDefinition:
    return IndicatorDefinition.model_validate(
        {
            "key": f"fixture_{function.casefold()}",
            "vendor": "okx",
            "endpoint": "https://example.test/history-candles",
            "source_field": "closed UTC daily candles",
            "definable_for": ["BTC"],
            "required_bars": required_bars,
            "frozen_after_observations": 3,
            "expected_update_interval_seconds": 86_400,
            "freshness_warn_seconds": 108_000,
            "freshness_stale_seconds": 172_800,
            "talib_function": function,
            "derives_from": "btc_daily_close",
            "parameters": parameters,
        }
    )


def lookback(indicator: IndicatorDefinition) -> int:
    assert indicator.talib_function is not None
    assert indicator.parameters is not None
    function = abstract.Function(indicator.talib_function)
    function.set_parameters(indicator.parameters)
    return function.lookback


def test_every_registry_indicator_declares_required_bars_greater_than_its_talib_lookback() -> (
    None
):
    registry = IndicatorRegistry.model_validate(
        (
            *load_registry().root,
            definition("RSI", {"timeperiod": 14}, 250),
            definition("ATR", {"timeperiod": 14}, 250),
            definition("EMA", {"timeperiod": 20}, 250),
            definition(
                "STOCHRSI",
                {
                    "timeperiod": 14,
                    "fastk_period": 14,
                    "fastd_period": 3,
                    "fastd_matype": 0,
                },
                250,
            ),
            definition(
                "MACD",
                {"fastperiod": 12, "slowperiod": 26, "signalperiod": 9},
                250,
            ),
            definition(
                "BBANDS",
                {
                    "timeperiod": 20,
                    "nbdevup": 2.0,
                    "nbdevdn": 2.0,
                    "matype": 0,
                },
                20,
            ),
            definition("OBV", {}, 1),
        )
    )

    talib_indicators = tuple(
        indicator
        for indicator in registry.root
        if indicator.talib_function is not None
    )
    assert talib_indicators
    for indicator in talib_indicators:
        assert indicator.required_bars is not None
        assert indicator.required_bars > lookback(indicator), indicator.key


def test_lookback_is_read_for_the_indicators_actual_parameters_not_defaults() -> None:
    rsi_14 = definition("RSI", {"timeperiod": 14}, 15)

    assert lookback(rsi_14) == 14
    with pytest.raises(ValidationError, match=r"RSI.*lookback 21"):
        definition("RSI", {"timeperiod": 21}, 15)
    with pytest.raises(ValidationError, match="missing TA-Lib parameters"):
        definition("RSI", None, 250)


def test_an_indicator_whose_required_bars_is_below_its_lookback_fails_validation() -> (
    None
):
    with pytest.raises(
        ValidationError,
        match=r"BBANDS.*required_bars 18.*lookback 19",
    ):
        definition("BBANDS", {"timeperiod": 20}, 18)


@pytest.mark.parametrize(
    ("function", "parameters"),
    (
        ("RSI", {"timeperiod": 14}),
        ("ATR", {"timeperiod": 14}),
        ("EMA", {"timeperiod": 20}),
        (
            "STOCHRSI",
            {
                "timeperiod": 14,
                "fastk_period": 14,
                "fastd_period": 3,
                "fastd_matype": 0,
            },
        ),
        ("MACD", {"fastperiod": 12, "slowperiod": 26, "signalperiod": 9}),
    ),
)
def test_recursive_indicators_declare_at_least_250_bars(
    function: str,
    parameters: dict[str, int],
) -> None:
    under_converged = definition(function, parameters, 249)

    with pytest.raises(ValidationError, match=rf"{function}.*at least 250"):
        IndicatorRegistry.model_validate((under_converged,))
