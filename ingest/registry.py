"""Validated indicator definitions loaded from the declarative registry."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    RootModel,
    StringConstraints,
    field_validator,
    model_validator,
)

REGISTRY_PATH = Path(__file__).with_name("registry.yaml")
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class IndicatorDefinition(BaseModel):
    """One indicator's source, applicability, and freshness contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: NonEmptyString
    vendor: NonEmptyString
    endpoint: NonEmptyString
    source_field: NonEmptyString
    definable_for: tuple[NonEmptyString, ...] = Field(min_length=1)
    required_bars: PositiveInt | None = None
    expected_update_interval_seconds: PositiveInt
    freshness_warn_seconds: PositiveInt
    freshness_stale_seconds: PositiveInt

    @field_validator("definable_for")
    @classmethod
    def reject_wildcards(cls, assets: tuple[str, ...]) -> tuple[str, ...]:
        if any("*" in asset or asset.casefold() == "all" for asset in assets):
            raise ValueError(
                "definable_for must list explicit assets; wildcards are forbidden"
            )
        return assets


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
        return value


def _parse_yaml(contents: str) -> list[dict[str, Any]]:
    """Parse the registry's deliberately small YAML subset without another dependency."""

    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line_number, original_line in enumerate(contents.splitlines(), start=1):
        line = _without_comment(original_line).rstrip()
        if not line.strip():
            continue

        stripped = line.lstrip()
        if line == stripped and stripped.startswith("- "):
            current = {}
            entries.append(current)
            stripped = stripped[2:]
        elif current is None or line == stripped:
            raise ValueError(f"invalid registry YAML on line {line_number}")

        field, separator, value = stripped.partition(":")
        if not separator or not field.strip():
            raise ValueError(f"invalid registry YAML on line {line_number}")
        field = field.strip()
        if field in current:
            raise ValueError(f"duplicate field {field!r} on line {line_number}")
        current[field] = _parse_value(value)

    if not entries:
        raise ValueError("registry must contain at least one indicator")
    return entries


def load_registry(path: Path = REGISTRY_PATH) -> IndicatorRegistry:
    """Load and validate every indicator, rejecting ambiguous keys."""

    raw_entries = _parse_yaml(path.read_text(encoding="utf-8"))
    return IndicatorRegistry.model_validate(raw_entries)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the indicator registry")
    parser.add_argument("--validate", action="store_true", required=True)
    parser.parse_args()
    load_registry()


if __name__ == "__main__":
    main()
