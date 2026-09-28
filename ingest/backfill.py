"""Shared backfill entry point and recipe dispatch."""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Mapping, Sequence

import psycopg

from ingest.fetchers.coinmetrics import backfill_coinmetrics_asset_metrics
from ingest.fetchers.fred import backfill_fred_initial_release
from ingest.fetchers.okx import backfill_okx_candle_indicator
from ingest.fetchers.okx_derivatives import (
    backfill_okx_funding_rate,
    backfill_okx_long_short_ratio,
    backfill_okx_open_interest,
    backfill_okx_taker_ratio,
)
from ingest.pipeline import FullAssetRun, persist_board
from ingest.registry import (
    IndicatorDefinition,
    IndicatorRegistry,
    assert_backfill_coverage,
    load_registry,
)

type BackfillRecipeResult = FullAssetRun | Sequence[FullAssetRun]
type BackfillRecipe = Callable[[IndicatorDefinition], BackfillRecipeResult]


def _not_implemented_recipe(_: IndicatorDefinition) -> FullAssetRun:
    """Infrastructure-only placeholder until vendor recipe stories land."""

    return FullAssetRun(indicators={}, history={})


BACKFILL_RECIPES: Mapping[str, BackfillRecipe] = {
    "noop": _not_implemented_recipe,
    "okx_candles": backfill_okx_candle_indicator,
    "okx_funding": backfill_okx_funding_rate,
    "okx_open_interest_history": backfill_okx_open_interest,
    "okx_long_short_1d": backfill_okx_long_short_ratio,
    "okx_taker_volume_1d": backfill_okx_taker_ratio,
    "coinmetrics_asset_metrics": backfill_coinmetrics_asset_metrics,
    "fred_initial_release": backfill_fred_initial_release,
}


def _recipe_runs(result: BackfillRecipeResult) -> tuple[FullAssetRun, ...]:
    if isinstance(result, FullAssetRun):
        return (result,)
    return tuple(result)


def _selected_entries(
    registry: IndicatorRegistry,
    indicator_key: str | None,
) -> tuple[IndicatorDefinition, ...]:
    if indicator_key is None:
        return registry.root

    selected = tuple(entry for entry in registry.root if entry.key == indicator_key)
    if not selected:
        raise KeyError(f"unknown indicator_key: {indicator_key}")
    return selected


def run_backfill(
    connection: psycopg.Connection[tuple[object, ...]],
    *,
    indicator_key: str | None = None,
    registry: IndicatorRegistry | None = None,
    recipes: Mapping[str, BackfillRecipe] = BACKFILL_RECIPES,
) -> tuple[int, ...]:
    """Run backfill for one indicator key, or every registered key."""

    selected_registry = load_registry() if registry is None else registry
    assert_backfill_coverage(
        selected_registry,
        registered_recipes=recipes.keys(),
    )

    row_ids: list[int] = []
    for entry in _selected_entries(selected_registry, indicator_key):
        if entry.not_backfillable is not None:
            if indicator_key is None:
                continue
            raise ValueError(
                f"{entry.key} is not backfillable: "
                f"{entry.not_backfillable.reason}"
            )
        if entry.backfill_recipe is None:
            raise AssertionError(f"{entry.key} is missing backfill_recipe")

        for run in _recipe_runs(recipes[entry.backfill_recipe](entry)):
            row_ids.extend(persist_board(connection, run, origin="backfill"))
    return tuple(row_ids)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Backfill indicator history")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--indicator-key")
    selection.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)

    indicator_key = None if args.all else args.indicator_key
    if indicator_key is None and not args.all:
        parser.error("choose --indicator-key KEY or --all")

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        run_backfill(connection, indicator_key=indicator_key)


if __name__ == "__main__":
    main()
