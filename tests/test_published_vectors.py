import json
import math
from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any, cast

import pytest

from ingest.indicators import atr, rsi

PUBLISHED_GOLDEN_DIRECTORY = Path(__file__).with_name("goldens") / "published"
RSI_GOLDEN_PATH = PUBLISHED_GOLDEN_DIRECTORY / "stockcharts_rsi_14.json"
ATR_GOLDEN_PATH = PUBLISHED_GOLDEN_DIRECTORY / "stockcharts_atr_14.json"
PUBLISHED_GOLDEN_PATHS = (RSI_GOLDEN_PATH, ATR_GOLDEN_PATH)
CONVERGENCE_EPSILON = 1e-6


def load_golden(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_rsi_14_reproduces_the_stockcharts_published_worked_example() -> None:
    golden = load_golden(RSI_GOLDEN_PATH)
    actual = [
        rsi(golden["input_bars"][: output["input_length"]], period=golden["period"])
        for output in golden["expected_outputs"]
    ]

    assert actual == pytest.approx(
        [output["value"] for output in golden["expected_outputs"]],
        abs=golden["absolute_tolerance"],
    )


def test_atr_14_reproduces_the_stockcharts_published_worked_example() -> None:
    golden = load_golden(ATR_GOLDEN_PATH)
    actual = [
        atr(golden["input_bars"][: output["input_length"]], period=golden["period"])
        for output in golden["expected_outputs"]
    ]

    assert actual == pytest.approx(
        [output["value"] for output in golden["expected_outputs"]],
        abs=golden["absolute_tolerance"],
    )


def test_each_published_golden_names_its_external_source() -> None:
    for path in PUBLISHED_GOLDEN_PATHS:
        golden = load_golden(path)

        assert golden.get("external") is True, f"{path.name} is not marked external"
        assert "StockCharts" in golden.get("source", ""), (
            f"{path.name} does not name its publisher"
        )
        assert golden.get("source_artifact", "").endswith(".xls"), (
            f"{path.name} does not name its published workbook"
        )
        assert golden.get("source_url", "").startswith(
            "https://chartschool.stockcharts.com/"
        ), f"{path.name} does not cite the publisher's source page"


def ema_smoothed_rsi(closes: Sequence[float], period: int) -> float:
    changes = [current - previous for previous, current in pairwise(closes)]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period
    alpha = 2 / (period + 1)

    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = alpha * gain + (1 - alpha) * average_gain
        average_loss = alpha * loss + (1 - alpha) * average_loss

    relative_strength = average_gain / average_loss
    return 100 - 100 / (1 + relative_strength)


def test_an_ema_smoothed_rsi_variant_fails_the_published_vector() -> None:
    golden = load_golden(RSI_GOLDEN_PATH)
    closes = [bar["close"] for bar in golden["input_bars"]]
    published = golden["expected_outputs"][-1]["value"]

    assert ema_smoothed_rsi(closes, golden["period"]) != pytest.approx(
        published, abs=golden["absolute_tolerance"]
    )


def convergence_bars() -> tuple[dict[str, float], ...]:
    bars = []
    for index in range(500):
        close = 100 + index * 0.03 + math.sin(index / 7) * 2
        bars.append({"high": close + 0.8, "low": close - 0.6, "close": close})
    return tuple(bars)


def test_the_same_tail_at_250_and_500_bars_agrees_within_epsilon() -> None:
    bars = convergence_bars()
    tail = bars[-250:]

    assert rsi(bars) == pytest.approx(rsi(tail), abs=CONVERGENCE_EPSILON)
    assert atr(bars) == pytest.approx(atr(tail), abs=CONVERGENCE_EPSILON)
