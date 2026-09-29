from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from ingest.registry import load_registry
from scripts.generate_indicator_keys import render_indicator_keys

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "ingest" / "registry.yaml"
GENERATED_PATH = REPO_ROOT / "web" / "src" / "registry.generated.ts"
GOLDEN_DIRECTORY = REPO_ROOT / "tests" / "goldens"
FIXTURE_DIRECTORY = REPO_ROOT / "tests" / "fixtures"


def generated_indicator_keys() -> tuple[str, ...]:
    contents = GENERATED_PATH.read_text(encoding="utf-8")
    return tuple(re.findall(r'  "([^"]+)"', contents))


GENERATED_INDICATOR_KEYS = generated_indicator_keys()


def golden_path(name: str) -> Path:
    if name.startswith("fixtures/"):
        return FIXTURE_DIRECTORY / name.removeprefix("fixtures/")
    return GOLDEN_DIRECTORY / name


def test_committed_indicator_key_union_matches_registry_codegen() -> None:
    assert GENERATED_PATH.read_text(encoding="utf-8") == render_indicator_keys(
        REGISTRY_PATH
    )


def test_codegen_reflects_registry_key_changes(tmp_path: Path) -> None:
    mutated = tmp_path / "registry.yaml"
    contents = REGISTRY_PATH.read_text(encoding="utf-8")
    mutated.write_text(
        contents.replace("- key: fear_greed_index", "- key: test_fear_greed_index", 1),
        encoding="utf-8",
        newline="\n",
    )

    rendered = render_indicator_keys(mutated)

    assert '"test_fear_greed_index"' in rendered
    assert '"fear_greed_index"' not in rendered
    assert rendered != GENERATED_PATH.read_text(encoding="utf-8")


def test_every_generated_key_has_a_real_golden_and_the_goldens_have_substance() -> None:
    registry = {entry.key: entry for entry in load_registry(REGISTRY_PATH).root}
    missing = [
        key
        for key in GENERATED_INDICATOR_KEYS
        if registry[key].golden is None
        or not golden_path(registry[key].golden).is_file()
    ]

    assert missing == []

    hashes = {
        key: hashlib.sha256(
            golden_path(registry[key].golden or "").read_bytes()
        ).hexdigest()
        for key in GENERATED_INDICATOR_KEYS
    }
    assert len(set(hashes.values())) >= 2


@pytest.mark.parametrize(
    "indicator_key", GENERATED_INDICATOR_KEYS, ids=GENERATED_INDICATOR_KEYS
)
def test_generated_indicator_key_is_wired_to_registry_and_golden(
    indicator_key: str,
) -> None:
    registry = {entry.key: entry for entry in load_registry(REGISTRY_PATH).root}

    assert indicator_key in registry
    assert registry[indicator_key].golden is not None
    assert golden_path(registry[indicator_key].golden).is_file()


def test_every_generated_union_key_is_referenced_by_a_running_test_function() -> None:
    marks = test_generated_indicator_key_is_wired_to_registry_and_golden.pytestmark
    parametrized_keys = {
        key
        for mark in marks
        if mark.name == "parametrize"
        for key in mark.args[1]
    }

    assert parametrized_keys == set(GENERATED_INDICATOR_KEYS)
