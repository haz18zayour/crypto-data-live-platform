from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from ingest.registry import load_registry
from scripts.generate_indicator_keys import render_indicator_keys

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "ingest" / "registry.yaml"
GENERATED_PATH = REPO_ROOT / "web" / "src" / "registry.generated.ts"
REGISTRY_TS_PATH = REPO_ROOT / "web" / "src" / "registry.ts"
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


def load_golden_json(name: str) -> object:
    return json.loads(golden_path(name).read_text(encoding="utf-8"))


def _test_function_nodes() -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    nodes: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for path in sorted((REPO_ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        nodes.extend(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name.startswith("test_")
        )
    return nodes


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

    hashes_by_golden = {
        registry[key].golden: hashlib.sha256(
            golden_path(registry[key].golden or "").read_bytes()
        ).hexdigest()
        for key in GENERATED_INDICATOR_KEYS
    }
    duplicate_files = {
        digest: sorted(
            str(golden)
            for golden, candidate_digest in hashes_by_golden.items()
            if candidate_digest == digest
        )
        for digest in set(hashes_by_golden.values())
    }
    copied_distinct_files = sorted(
        files for files in duplicate_files.values() if len(files) > 1
    )

    assert copied_distinct_files == []
    assert len(set(hashes_by_golden.values())) >= 2

    empty_or_trivial = []
    for key in GENERATED_INDICATOR_KEYS:
        golden_name = registry[key].golden
        assert golden_name is not None
        payload = load_golden_json(golden_name)
        if (
            (isinstance(payload, dict) and not payload)
            or (isinstance(payload, list) and not payload)
            or not isinstance(payload, dict | list)
        ):
            empty_or_trivial.append(key)

    assert empty_or_trivial == []


@pytest.mark.parametrize(
    "indicator_key", GENERATED_INDICATOR_KEYS, ids=GENERATED_INDICATOR_KEYS
)
def test_generated_indicator_key_exercises_its_declared_golden_contract(
    indicator_key: str,
) -> None:
    registry = {entry.key: entry for entry in load_registry(REGISTRY_PATH).root}
    entry = registry[indicator_key]

    assert indicator_key in registry
    assert entry.key == indicator_key
    assert entry.golden is not None
    assert golden_path(entry.golden).is_file()
    assert entry.response_model is not None
    assert entry.source_field
    assert entry.freshness_stale_seconds > entry.freshness_warn_seconds

    golden = load_golden_json(entry.golden)
    assert isinstance(golden, dict | list)
    if isinstance(golden, dict) and "indicator_key" in golden:
        assert str(golden["indicator_key"]).split("_", 1)[1] == indicator_key.split(
            "_", 1
        )[1]
        assert "expected" in golden or "expected_outputs" in golden
    else:
        assert len(golden) > 0


def test_every_generated_union_key_is_referenced_by_a_substantive_running_test_function() -> (
    None
):
    tested_function = test_generated_indicator_key_exercises_its_declared_golden_contract
    marks = tested_function.pytestmark
    parametrized_keys = {
        key
        for mark in marks
        if mark.name == "parametrize"
        for key in mark.args[1]
    }
    referenced_by_name = {
        "btc_daily_close",
        "btc_rsi",
        "btc_funding_rate",
        "btc_mvrv",
        "btc_active_addresses",
        "btc_exchange_flow",
        "btc_open_interest",
        "btc_long_short_ratio",
        "btc_taker_ratio",
        "btc_ema_20",
        "btc_ema_50",
        "btc_ema_200",
        "btc_atr",
        "btc_bollinger_upper",
        "btc_bollinger_middle",
        "btc_bollinger_lower",
        "btc_obv",
        "btc_macd",
        "btc_stochrsi",
        "eth_rsi",
        "eth_funding_rate",
        "eth_mvrv",
        "eth_active_addresses",
        "eth_exchange_flow",
        "eth_open_interest",
        "eth_long_short_ratio",
        "eth_taker_ratio",
        "eth_ema_20",
        "eth_ema_50",
        "eth_ema_200",
        "eth_atr",
        "eth_bollinger_upper",
        "eth_bollinger_middle",
        "eth_bollinger_lower",
        "eth_obv",
        "eth_macd",
        "eth_stochrsi",
        "sol_rsi",
        "sol_funding_rate",
        "sol_active_addresses",
        "sol_staking",
        "sol_open_interest",
        "sol_long_short_ratio",
        "sol_taker_ratio",
        "sol_ema_20",
        "sol_ema_50",
        "sol_ema_200",
        "sol_atr",
        "sol_bollinger_upper",
        "sol_bollinger_middle",
        "sol_bollinger_lower",
        "sol_obv",
        "sol_macd",
        "sol_stochrsi",
        "bnb_rsi",
        "bnb_funding_rate",
        "bnb_mvrv",
        "bnb_active_addresses",
        "bnb_open_interest",
        "bnb_long_short_ratio",
        "bnb_taker_ratio",
        "bnb_ema_20",
        "bnb_ema_50",
        "bnb_ema_200",
        "bnb_atr",
        "bnb_bollinger_upper",
        "bnb_bollinger_middle",
        "bnb_bollinger_lower",
        "bnb_obv",
        "bnb_macd",
        "bnb_stochrsi",
        "macro_vixcls",
        "macro_dff",
        "macro_t10y2y",
        "macro_dfii10",
        "macro_dtwexbgs",
        "macro_cpiaucsl",
        "macro_m2sl",
        "spot_etf_net_flow",
        "stablecoin_supply",
        "fear_greed_index",
    }
    story_key_reference_tests = {
        test_generated_indicator_key_exercises_its_declared_golden_contract.__name__,
        "test_every_generated_union_key_is_referenced_by_a_substantive_running_test_function",
    }
    empty_story_key_reference_tests = [
        node.name
        for node in _test_function_nodes()
        if node.name in story_key_reference_tests
        and not any(isinstance(child, ast.Assert) for child in ast.walk(node))
    ]
    todo_shells = [
        path
        for path in [
            *Path(REPO_ROOT / "tests").glob("test_*.py"),
            *Path(REPO_ROOT / "web" / "src").glob("*.test.ts*"),
        ]
        if re.search(r"\bit\.todo\s*\(", path.read_text(encoding="utf-8"))
    ]

    assert parametrized_keys == set(GENERATED_INDICATOR_KEYS)
    assert referenced_by_name == set(GENERATED_INDICATOR_KEYS)
    assert empty_story_key_reference_tests == []
    assert todo_shells == []


def test_indicator_stale_after_seconds_mapping_is_compile_time_exhaustive(
    tmp_path: Path,
) -> None:
    source = REGISTRY_TS_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"export const indicatorStaleAfterSeconds = (?P<object>\{.*?\n\}) "
        r"satisfies \{ \[K in IndicatorKey\]: number \};",
        source,
        flags=re.DOTALL,
    )
    assert match is not None

    broken_mapping = re.sub(
        r"\n  btc_daily_close: \d+,\n",
        "\n",
        match.group("object"),
        count=1,
    )
    assert broken_mapping != match.group("object")

    shutil.copyfile(
        GENERATED_PATH,
        tmp_path / "registry.generated.ts",
    )
    proof = tmp_path / "exhaustive-proof.ts"
    proof.write_text(
        'import type { IndicatorKey } from "./registry.generated";\n\n'
        f"const broken = {broken_mapping} "
        "satisfies { [K in IndicatorKey]: number };\n"
        "void broken;\n",
        encoding="utf-8",
        newline="\n",
    )
    tsc = REPO_ROOT / "web" / "node_modules" / ".bin" / "tsc.cmd"
    if not tsc.exists():
        tsc = REPO_ROOT / "web" / "node_modules" / ".bin" / "tsc"
    result = subprocess.run(
        [
            str(tsc),
            "--noEmit",
            "--strict",
            "--module",
            "ESNext",
            "--moduleResolution",
            "Bundler",
            "--target",
            "ES2022",
            "--skipLibCheck",
            str(proof),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "btc_daily_close" in result.stdout + result.stderr
