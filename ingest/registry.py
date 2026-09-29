"""Validated indicator definitions loaded from the declarative registry."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    PositiveInt,
    RootModel,
    StringConstraints,
    field_validator,
    model_validator,
)
from talib import abstract

REGISTRY_PATH = Path(__file__).with_name("registry.yaml")
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
RECURSIVE_TALIB_FUNCTIONS = frozenset({"RSI", "ATR", "EMA", "STOCHRSI", "MACD"})
CadenceTier = Literal["fast", "medium", "daily"]
TIER_INTERVAL_SECONDS: Mapping[CadenceTier, int] = {
    "fast": 300,
    "medium": 28800,
    "daily": 86400,
}
SUPPORTED_TIER_INTERVAL_SECONDS = frozenset(TIER_INTERVAL_SECONDS.values())
SUPPORTED_REGISTRY_INTERVAL_SECONDS = frozenset(
    (*TIER_INTERVAL_SECONDS.values(), 604800)
)


class CorroborationDefinition(BaseModel):
    """A second venue and the measured tolerance for comparing it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    venue: NonEmptyString
    pair: NonEmptyString
    tolerance_bps: PositiveFloat


class UncorroboratedDefinition(BaseModel):
    """Why this indicator has no independent second source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    note: NonEmptyString


class NotDefinableDefinition(BaseModel):
    """Assets deliberately excluded from an indicator family, and why."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assets: tuple[NonEmptyString, ...] = Field(min_length=1)
    reason: NonEmptyString | None = None
    reasons: tuple[NonEmptyString, ...] | None = None

    @model_validator(mode="after")
    def require_one_reason_shape(self) -> NotDefinableDefinition:
        if self.reason is None and self.reasons is None:
            raise ValueError("not_definable must declare reason or reasons")
        if self.reason is not None and self.reasons is not None:
            raise ValueError("not_definable must not mix reason and reasons")
        if self.reasons is None:
            return self
        declared_assets = set()
        for reason in self.reasons:
            asset, separator, detail = reason.partition(":")
            if not separator or not asset.strip() or not detail.strip():
                raise ValueError("not_definable reasons must use 'ASSET: reason'")
            declared_assets.add(asset.strip())
        if declared_assets != set(self.assets):
            raise ValueError("not_definable reasons must match assets")
        return self

    def reason_for(self, asset: str) -> str:
        if self.reasons is not None:
            prefix = f"{asset}:"
            for reason in self.reasons:
                if reason.startswith(prefix):
                    return reason.removeprefix(prefix).strip()
            raise KeyError(asset)
        if self.reason is None:
            raise KeyError(asset)
        return self.reason


class NotBackfillableDefinition(BaseModel):
    """Why this indicator's history cannot be honestly backfilled."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: NonEmptyString


class IndicatorDefinition(BaseModel):
    """One indicator's source, applicability, and freshness contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: NonEmptyString
    vendor: NonEmptyString
    endpoint: NonEmptyString
    source_field: NonEmptyString
    definable_for: tuple[NonEmptyString, ...] = Field(min_length=1)
    not_definable: NotDefinableDefinition | None = None
    backfill_recipe: NonEmptyString | None = None
    not_backfillable: NotBackfillableDefinition | None = None
    golden: NonEmptyString | None = None
    response_model: NonEmptyString | None = None
    required_bars: PositiveInt | None = None
    talib_function: NonEmptyString | None = None
    derives_from: NonEmptyString | None = None
    parameters: dict[NonEmptyString, int | float] | None = None
    note: NonEmptyString | None = None
    expected_update_interval_seconds: PositiveInt
    freshness_warn_seconds: PositiveInt
    freshness_stale_seconds: PositiveInt
    frozen_after_observations: PositiveInt | None = None
    expected_constant: NonEmptyString | None = None
    freshness_unmeasurable: NonEmptyString | None = None
    corroboration: CorroborationDefinition | None = None
    uncorroborated: UncorroboratedDefinition | None = None

    @field_validator("definable_for")
    @classmethod
    def reject_wildcards(cls, assets: tuple[str, ...]) -> tuple[str, ...]:
        if any("*" in asset or asset.casefold() == "all" for asset in assets):
            raise ValueError(
                "definable_for must list explicit assets; wildcards are forbidden"
            )
        return assets

    @model_validator(mode="after")
    def reject_contradictory_asset_declarations(self) -> IndicatorDefinition:
        if self.not_definable is None:
            return self
        overlap = set(self.definable_for) & set(self.not_definable.assets)
        if overlap:
            assets = ", ".join(sorted(overlap))
            raise ValueError(
                f"{assets} cannot appear in both definable_for and not_definable"
            )
        return self

    @model_validator(mode="after")
    def reject_contradictory_backfill_declarations(self) -> IndicatorDefinition:
        if self.backfill_recipe is not None and self.not_backfillable is not None:
            raise ValueError(
                f"{self.key} must not declare both backfill_recipe and "
                "not_backfillable"
            )
        return self

    @model_validator(mode="after")
    def require_exactly_one_frozen_declaration(self) -> IndicatorDefinition:
        has_threshold = self.frozen_after_observations is not None
        has_expected_constant = self.expected_constant is not None
        if has_threshold == has_expected_constant:
            raise ValueError(
                f"{self.key} must declare exactly one frozen-detection declaration: "
                "frozen_after_observations or expected_constant"
            )
        return self

    @model_validator(mode="after")
    def require_more_bars_than_talib_lookback(self) -> IndicatorDefinition:
        if self.talib_function is None:
            if self.derives_from is not None:
                raise ValueError("derives_from requires a talib_function")
            if self.parameters not in (None, {}):
                raise ValueError(
                    "parameters without a talib_function must be an empty mapping"
                )
            return self
        if self.derives_from is None:
            raise ValueError(f"{self.key} is missing derives_from")
        if self.parameters is None:
            raise ValueError(f"{self.key} is missing TA-Lib parameters")

        function = abstract.Function(self.talib_function)  # type: ignore[attr-defined]
        function.set_parameters(self.parameters)
        if self.required_bars is not None and self.required_bars <= function.lookback:
            raise ValueError(
                f"{self.talib_function} required_bars {self.required_bars} must be "
                f"greater than its TA-Lib lookback {function.lookback}"
            )
        return self


class IndicatorRegistry(RootModel[tuple[IndicatorDefinition, ...]]):
    """The complete set of uniquely keyed indicator definitions."""

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def reject_duplicate_keys(self) -> IndicatorRegistry:
        seen: set[str] = set()
        for entry in self.root:
            if entry.key in seen:
                raise ValueError(f"Duplicate indicator key: {entry.key}")
            seen.add(entry.key)
        return self

    @model_validator(mode="after")
    def require_bar_counts(self) -> IndicatorRegistry:
        for entry in self.root:
            if entry.required_bars is None:
                raise ValueError(f"{entry.key} is missing required_bars")
            if (
                entry.talib_function is not None
                and entry.talib_function.upper() in RECURSIVE_TALIB_FUNCTIONS
                and entry.required_bars < 250
            ):
                raise ValueError(
                    f"{entry.talib_function} must declare at least 250 required bars"
                )
        return self

    @model_validator(mode="after")
    def reject_unsupported_tier_intervals(self) -> IndicatorRegistry:
        unsupported = sorted(
            {
                entry.expected_update_interval_seconds
                for entry in self.root
                if entry.expected_update_interval_seconds
                not in SUPPORTED_REGISTRY_INTERVAL_SECONDS
            }
        )
        if unsupported:
            supported = ", ".join(
                str(interval) for interval in sorted(SUPPORTED_REGISTRY_INTERVAL_SECONDS)
            )
            raise ValueError(
                "unsupported expected_update_interval_seconds for cadence tier "
                f"filter: {unsupported}; supported intervals are {supported}"
            )
        return self

    @model_validator(mode="after")
    def reject_unknown_derived_roots(self) -> IndicatorRegistry:
        keys = {entry.key for entry in self.root}
        for entry in self.root:
            if entry.derives_from is not None and entry.derives_from not in keys:
                raise ValueError(
                    f"{entry.key} derives_from unknown indicator key: "
                    f"{entry.derives_from}"
                )
        return self


def _without_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
        elif character == "\\" and quote == '"':
            escaped = True
        elif character in {'"', "'"}:
            quote = (
                None if quote == character else character if quote is None else quote
            )
        elif character == "#" and quote is None:
            return line[:index]
    return line


def _parse_value(value: str) -> object:
    value = value.strip()
    if not value:
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [_parse_value(item) for item in inner.split(",")]
    if value[:1] in {'"', "'"}:
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError) as error:
            raise ValueError(f"invalid quoted registry value: {value}") from error
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def _parse_yaml(contents: str) -> list[dict[str, Any]]:
    """Parse the registry's deliberately small YAML subset without another dependency."""

    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    nested: dict[str, Any] | None = None
    for line_number, original_line in enumerate(contents.splitlines(), start=1):
        line = _without_comment(original_line).rstrip()
        if not line.strip():
            continue

        stripped = line.lstrip()
        if line == stripped and stripped.startswith("- "):
            current = {}
            entries.append(current)
            nested = None
            stripped = stripped[2:]
            indentation = 0
        else:
            indentation = len(line) - len(stripped)

        if current is None or (indentation == 0 and not original_line.startswith("- ")):
            raise ValueError(f"invalid registry YAML on line {line_number}")

        field, separator, value = stripped.partition(":")
        if not separator or not field.strip():
            raise ValueError(f"invalid registry YAML on line {line_number}")
        field = field.strip()
        target = nested if indentation == 4 and nested is not None else current
        if indentation not in (0, 2, 4) or (indentation == 4 and nested is None):
            raise ValueError(f"invalid registry YAML indentation on line {line_number}")
        if field in target:
            raise ValueError(f"duplicate field {field!r} on line {line_number}")
        parsed = _parse_value(value)
        if indentation in (0, 2):
            nested = {} if parsed is None else None
            target[field] = nested if nested is not None else parsed
        else:
            target[field] = parsed

    if not entries:
        raise ValueError("registry must contain at least one indicator")
    return entries


def load_registry(path: Path = REGISTRY_PATH) -> IndicatorRegistry:
    """Load and validate every indicator, rejecting ambiguous keys."""

    raw_entries = _parse_yaml(path.read_text(encoding="utf-8"))
    registry = IndicatorRegistry.model_validate(raw_entries)
    for entry in raw_entries:
        has_second_source = entry.get("corroboration") is not None
        is_uncorroborated = entry.get("uncorroborated") is not None
        if has_second_source == is_uncorroborated:
            key = entry.get("key", "unknown indicator")
            raise ValueError(
                f"{key} must declare exactly one corroboration declaration: "
                "corroboration or uncorroborated"
            )
    return registry


def assert_registry_coverage(
    registry: IndicatorRegistry,
    *,
    golden_keys: Collection[str],
    response_models: Mapping[str, object],
) -> None:
    """Fail with every missing integrity artifact derived from the registry."""

    failures: list[str] = []
    for entry in registry.root:
        has_second_source = entry.corroboration is not None
        is_uncorroborated = entry.uncorroborated is not None
        if has_second_source == is_uncorroborated:
            failures.append(
                f"{entry.key} is missing exactly one corroboration declaration"
            )
        has_frozen_threshold = entry.frozen_after_observations is not None
        has_expected_constant = entry.expected_constant is not None
        if has_frozen_threshold == has_expected_constant:
            failures.append(
                f"{entry.key} is missing exactly one frozen-detection declaration"
            )
        if entry.talib_function is not None and entry.derives_from is None:
            failures.append(f"{entry.key} is missing derives_from")
        if entry.golden is None or entry.golden not in golden_keys:
            failures.append(f"{entry.key} is missing a golden file")
        if entry.required_bars is None:
            failures.append(f"{entry.key} is missing required_bars")
        if entry.response_model is None or entry.key not in response_models:
            failures.append(f"{entry.key} is missing a response model")
        if entry.parameters is None:
            failures.append(f"{entry.key} is missing parameters")

    if failures:
        raise AssertionError("; ".join(failures))


def assert_backfill_coverage(
    registry: IndicatorRegistry,
    *,
    registered_recipes: Collection[str],
) -> None:
    """Fail when an indicator lacks both a backfill recipe and an honest absence."""

    failures: list[str] = []
    for entry in registry.root:
        has_recipe = entry.backfill_recipe is not None
        has_absence = entry.not_backfillable is not None
        if has_recipe == has_absence:
            failures.append(
                f"{entry.key} must declare exactly one backfill declaration: "
                "backfill_recipe or not_backfillable"
            )
            continue
        if entry.backfill_recipe is not None and (
            entry.backfill_recipe not in registered_recipes
        ):
            failures.append(
                f"{entry.key} declares unknown backfill_recipe "
                f"{entry.backfill_recipe}"
            )

    if failures:
        raise AssertionError("; ".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the indicator registry")
    parser.add_argument("--validate", action="store_true", required=True)
    parser.parse_args()
    load_registry()


if __name__ == "__main__":
    main()
