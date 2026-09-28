from datetime import UTC, datetime

import pytest

from ingest import backfill
from ingest.pipeline import FullAssetRun
from ingest.registry import (
    IndicatorDefinition,
    IndicatorRegistry,
    NotBackfillableDefinition,
    assert_backfill_coverage,
    load_registry,
)
from ingest.status import Ok

SOURCE_TIMESTAMP = datetime(2026, 9, 1, tzinfo=UTC)


def definition(
    key: str = "test_indicator",
    *,
    backfill_recipe: str | None = "test_recipe",
    not_backfillable: NotBackfillableDefinition | None = None,
) -> IndicatorDefinition:
    return IndicatorDefinition.model_construct(
        key=key,
        vendor="test_vendor",
        endpoint="https://example.test/data",
        source_field="data.value",
        definable_for=("BTC",),
        backfill_recipe=backfill_recipe,
        not_backfillable=not_backfillable,
        golden="fixtures/example.json",
        response_model="example",
        required_bars=1,
        parameters={},
        expected_update_interval_seconds=86_400,
        freshness_warn_seconds=108_000,
        freshness_stale_seconds=172_800,
    )


def registry_with(*entries: IndicatorDefinition) -> IndicatorRegistry:
    return IndicatorRegistry.model_construct(root=entries)


def one_point_run(entry: IndicatorDefinition) -> FullAssetRun:
    return FullAssetRun(
        indicators={entry.key: Ok(value=42.0, source_timestamp=SOURCE_TIMESTAMP)},
        history={},
    )


def test_backfill_entry_point_dispatches_one_key_to_its_recipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []
    persisted: list[tuple[dict[str, object], str]] = []

    def recipe(entry: IndicatorDefinition) -> FullAssetRun:
        called.append(entry.key)
        return one_point_run(entry)

    def persist_board(
        connection: object,
        run: FullAssetRun,
        *,
        origin: str = "live",
    ) -> tuple[int, ...]:
        persisted.append((run.indicators, origin))
        return (7,)

    monkeypatch.setattr(backfill, "persist_board", persist_board)
    registry = registry_with(
        definition("wanted"),
        definition("skipped"),
    )

    row_ids = backfill.run_backfill(
        object(),  # type: ignore[arg-type]
        indicator_key="wanted",
        registry=registry,
        recipes={"test_recipe": recipe},
    )

    assert called == ["wanted"]
    assert row_ids == (7,)
    assert persisted == [({"wanted": Ok(42.0, SOURCE_TIMESTAMP)}, "backfill")]


def test_backfill_entry_point_can_run_all_registered_backfillable_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []

    def recipe(entry: IndicatorDefinition) -> FullAssetRun:
        called.append(entry.key)
        return one_point_run(entry)

    monkeypatch.setattr(
        backfill,
        "persist_board",
        lambda *_args, **_kwargs: (len(called),),
    )
    registry = registry_with(
        definition("first"),
        definition(
            "not_backfilled",
            backfill_recipe=None,
            not_backfillable=NotBackfillableDefinition(
                reason="This test source has no historical endpoint."
            ),
        ),
        definition("second"),
    )

    row_ids = backfill.run_backfill(
        object(),  # type: ignore[arg-type]
        registry=registry,
        recipes={"test_recipe": recipe},
    )

    assert called == ["first", "second"]
    assert row_ids == (1, 2)


def test_backfill_writes_through_persist_board_with_backfill_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origins: list[str] = []

    def persist_board(
        connection: object,
        run: FullAssetRun,
        *,
        origin: str = "live",
    ) -> tuple[int, ...]:
        origins.append(origin)
        assert run.indicators == {
            "test_indicator": Ok(value=42.0, source_timestamp=SOURCE_TIMESTAMP)
        }
        return (1,)

    monkeypatch.setattr(backfill, "persist_board", persist_board)

    backfill.run_backfill(
        object(),  # type: ignore[arg-type]
        indicator_key="test_indicator",
        registry=registry_with(definition()),
        recipes={"test_recipe": one_point_run},
    )

    assert origins == ["backfill"]


def test_backfill_rerun_uses_one_identity_without_duplicate_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows: dict[tuple[str, str, str, datetime], int] = {}

    def persist_board(
        connection: object,
        run: FullAssetRun,
        *,
        origin: str = "live",
    ) -> tuple[int, ...]:
        assert origin == "backfill"
        ids: list[int] = []
        for result_key, result in run.indicators.items():
            assert isinstance(result, Ok)
            identity = (result_key, "BTC", "test_vendor", result.source_timestamp)
            ids.append(rows.setdefault(identity, len(rows) + 1))
        return tuple(ids)

    monkeypatch.setattr(backfill, "persist_board", persist_board)
    registry = registry_with(definition())

    first = backfill.run_backfill(
        object(),  # type: ignore[arg-type]
        indicator_key="test_indicator",
        registry=registry,
        recipes={"test_recipe": one_point_run},
    )
    second = backfill.run_backfill(
        object(),  # type: ignore[arg-type]
        indicator_key="test_indicator",
        registry=registry,
        recipes={"test_recipe": one_point_run},
    )

    assert first == second == (1,)
    assert len(rows) == 1


def test_backfill_coverage_fails_by_name_without_recipe_or_absence() -> None:
    uncovered = definition("silent_indicator", backfill_recipe=None)

    with pytest.raises(AssertionError, match="silent_indicator"):
        assert_backfill_coverage(
            registry_with(uncovered),
            registered_recipes={"test_recipe"},
        )


def test_backfill_coverage_fails_by_name_for_unknown_recipe() -> None:
    unknown = definition("unknown_recipe_indicator", backfill_recipe="missing_recipe")

    with pytest.raises(AssertionError, match="unknown_recipe_indicator"):
        assert_backfill_coverage(
            registry_with(unknown),
            registered_recipes={"test_recipe"},
        )


def test_solana_and_validators_app_declare_distinct_not_backfillable_reasons() -> None:
    entries = {entry.key: entry for entry in load_registry().root}
    sol_active = entries["sol_active_addresses"]
    sol_staking = entries["sol_staking"]

    assert sol_active.not_backfillable is not None
    assert sol_staking.not_backfillable is not None
    assert "getBlock" in sol_active.not_backfillable.reason
    assert "Validators.app" in sol_staking.not_backfillable.reason
    assert sol_active.not_backfillable.reason != sol_staking.not_backfillable.reason

    assert_backfill_coverage(
        load_registry(),
        registered_recipes=backfill.BACKFILL_RECIPES.keys(),
    )
