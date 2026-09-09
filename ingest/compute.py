"""Indicator computation guarded by exact bar-slice contracts."""

from collections.abc import Callable, Sequence

from ingest.registry import IndicatorDefinition


def compute_indicator[Bar](
    definition: IndicatorDefinition,
    bars: Sequence[Bar],
    calculation: Callable[[Sequence[Bar]], float],
) -> float:
    """Compute from exactly the number of bars declared by the indicator."""

    received_bars = len(bars)
    if received_bars != definition.required_bars:
        raise ValueError(
            f"{definition.key} expected exactly {definition.required_bars} bars, "
            f"received {received_bars}"
        )
    return calculation(bars)
