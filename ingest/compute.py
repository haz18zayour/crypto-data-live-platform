"""Indicator computation guarded by exact bar-slice contracts."""

from collections.abc import Callable, Mapping, Sequence

from ingest.registry import IndicatorDefinition


def daily_close(bars: Sequence[Mapping[str, float]]) -> float:
    """Return the close carried by the newest input bar."""

    return bars[-1]["close"]


def compute_indicator[Bar](
    definition: IndicatorDefinition,
    bars: Sequence[Bar],
    calculation: Callable[[Sequence[Bar]], float],
) -> float:
    """Compute from exactly the number of bars declared by the indicator."""

    required_bars = definition.required_bars
    if required_bars is None:
        raise ValueError(f"{definition.key} has no required_bars contract")

    received_bars = len(bars)
    if received_bars != required_bars:
        raise ValueError(
            f"{definition.key} expected exactly {required_bars} bars, "
            f"received {received_bars}"
        )
    return calculation(bars)
