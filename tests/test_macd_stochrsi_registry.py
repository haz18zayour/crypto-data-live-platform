from ingest.registry import IndicatorDefinition, load_registry


def registered_talib_indicators() -> dict[str, IndicatorDefinition]:
    return {
        definition.talib_function: definition
        for definition in load_registry().root
        if definition.talib_function is not None
    }


def test_load_registry_returns_macd_and_stochrsi_definitions() -> None:
    definitions = registered_talib_indicators()

    assert isinstance(definitions["MACD"], IndicatorDefinition)
    assert isinstance(definitions["STOCHRSI"], IndicatorDefinition)


def test_macd_and_stochrsi_declare_full_parameters_and_250_bars() -> None:
    definitions = registered_talib_indicators()

    assert definitions["MACD"].talib_function == "MACD"
    assert definitions["MACD"].parameters == {
        "fastperiod": 12,
        "slowperiod": 26,
        "signalperiod": 9,
    }
    assert definitions["MACD"].required_bars == 250

    assert definitions["STOCHRSI"].talib_function == "STOCHRSI"
    assert definitions["STOCHRSI"].parameters == {
        "timeperiod": 14,
        "fastk_period": 14,
        "fastd_period": 3,
        "fastd_matype": 0,
    }
    assert definitions["STOCHRSI"].required_bars == 250


def test_stochrsi_note_maps_talib_fastd_to_tradingview_k() -> None:
    stochrsi = registered_talib_indicators()["STOCHRSI"]

    assert stochrsi.note == (
        "TA-Lib fastd corresponds to TradingView K (not D)."
    )
