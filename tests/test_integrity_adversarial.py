"""US-1010: the adversarial case for PRD-010's integrity dashboard.

Proves this PRD's five hardest claims directly against the real implementation, not a
simplified re-derivation of it. Written directly by the owner because codex hit a multi-day
usage block (confirmed via direct probe) partway through PRD-010; claude still verifies this
independently as usual.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest

from ingest.registry import load_registry
from tests.test_integrity_read import NOW, _entry, _insert, _integrity_read, postgres  # noqa: F401
from tests.test_registry_codegen import golden_path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_frozen_trips_at_exactly_the_registered_boundary_not_one_short(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    """US-1010-C1: a real sequence of distinct-source_timestamp OK rows holding an identical
    value for exactly frozen_after_observations observations reports frozen; one fewer
    observation, or any single differing value, reports not frozen."""
    connection, _ = postgres
    threshold = _entry("btc_daily_close").frozen_after_observations
    assert threshold == 3

    # Exactly `threshold` identical observations -> frozen.
    for offset_days in range(threshold):
        _insert(
            connection,
            indicator_key="btc_daily_close",
            asset="BTC",
            source_vendor="okx",
            value=78000.0,
            source_timestamp=NOW - timedelta(days=offset_days),
        )
    row = _integrity_read(connection)[("btc_daily_close", "BTC", "okx")]
    assert row["frozen"] is True
    assert row["frozen_state"] == "frozen"

    # One fewer observation than the threshold, on a distinct asset scope (same registered
    # vendor - the RPC's cells CTE only matches rows whose vendor equals the registry's own
    # declared vendor for that key) so it cannot inherit the frozen row above -> not frozen.
    for offset_days in range(threshold - 1):
        _insert(
            connection,
            indicator_key="btc_daily_close",
            asset="ETH",
            source_vendor="okx",
            value=78500.0,
            source_timestamp=NOW - timedelta(days=offset_days),
        )
    short_row = _integrity_read(connection)[("btc_daily_close", "ETH", "okx")]
    assert short_row["frozen"] is False
    assert short_row["frozen_state"] == "not_frozen"

    # Exactly `threshold` observations but one value differs -> not frozen.
    for offset_days in range(threshold):
        _insert(
            connection,
            indicator_key="btc_daily_close",
            asset="SOL",
            source_vendor="okx",
            value=78000.0 if offset_days != 1 else 78001.0,
            source_timestamp=NOW - timedelta(days=offset_days),
        )
    differing_row = _integrity_read(connection)[("btc_daily_close", "SOL", "okx")]
    assert differing_row["frozen"] is False
    assert differing_row["frozen_state"] == "not_frozen"


def test_a_moving_dependent_still_reports_frozen_when_its_real_root_is_frozen(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    """US-1010-C2: the finding that motivated this whole PRD, proven end to end. A dependent
    indicator (real derives_from link from the shipped registry) whose own values are
    genuinely moving is still correctly flagged frozen, because what matters is its root's
    honesty, not its own superficial variance."""
    connection, _ = postgres
    dependent = _entry("btc_rsi")
    assert dependent.derives_from == "btc_daily_close"
    threshold = _entry("btc_daily_close").frozen_after_observations

    for offset_days in range(threshold):
        _insert(
            connection,
            indicator_key="btc_daily_close",
            asset="BTC",
            source_vendor="okx",
            value=78000.0,
            source_timestamp=NOW - timedelta(days=offset_days),
        )
    # The dependent's own values genuinely move bar to bar - an independent identical-value
    # check on btc_rsi alone would report not_frozen every time.
    for offset_days, value in enumerate((61.4, 58.9, 55.2, 49.7, 44.1)):
        _insert(
            connection,
            indicator_key="btc_rsi",
            asset="BTC",
            source_vendor="okx",
            value=value,
            source_timestamp=NOW - timedelta(days=offset_days),
        )

    rows = _integrity_read(connection)
    root_values = {NOW - timedelta(days=d) for d in range(threshold)}
    assert len(root_values) == threshold  # sanity: genuinely distinct timestamps

    dependent_row = rows[("btc_rsi", "BTC", "okx")]
    assert dependent_row["frozen"] is True
    assert dependent_row["frozen_state"] == "frozen"
    assert dependent_row["derives_from"] == "btc_daily_close"


def test_unmeasurable_never_reports_a_freshness_state_at_any_age(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    """US-1010-C3: the false-comfort gap closed, proven at the boundary. A registry entry
    declaring freshness_unmeasurable never reports fresh/warn/stale, whether its most recent
    row is brand new or years old."""
    connection, _ = postgres
    entry = _entry("stablecoin_supply")
    assert entry.freshness_unmeasurable

    _insert(
        connection,
        indicator_key="stablecoin_supply",
        asset="ETH",
        source_vendor="defillama",
        value=124_000_000_000.0,
        source_timestamp=NOW,
    )
    fresh_looking = _integrity_read(connection)[("stablecoin_supply", "ETH", "defillama")]
    assert fresh_looking["freshness_state"] == "unmeasurable"
    assert fresh_looking["freshness_unmeasurable_reason"]

    _insert(
        connection,
        indicator_key="stablecoin_supply",
        asset="SOL",
        source_vendor="defillama",
        value=5_000_000_000.0,
        source_timestamp=NOW - timedelta(days=3650),
    )
    ancient_looking = _integrity_read(connection)[("stablecoin_supply", "SOL", "defillama")]
    assert ancient_looking["freshness_state"] == "unmeasurable"
    assert ancient_looking["freshness_unmeasurable_reason"]


def test_frontend_classifies_a_stale_computed_at_even_when_every_row_looks_healthy() -> None:
    """US-1010-C4: the panel cannot present a false all-clear from an old snapshot. Runs the
    real frontend classifier (US-1003's own function, via a Node subprocess against the real
    compiled module) against a computed_at older than its threshold."""
    script = (
        "import { classifyIntegritySelfCheck, INTEGRITY_SELF_CHECK_STALE_AFTER_MS } "
        "from './integrity.ts';\n"
        "const staleComputedAt = new Date(Date.now() - INTEGRITY_SELF_CHECK_STALE_AFTER_MS - 1000).toISOString();\n"
        "const currentComputedAt = new Date().toISOString();\n"
        "const staleResult = classifyIntegritySelfCheck(staleComputedAt);\n"
        "const currentResult = classifyIntegritySelfCheck(currentComputedAt);\n"
        "if (staleResult !== 'stale-self-check') { throw new Error(`expected stale-self-check, got ${staleResult}`); }\n"
        "if (currentResult !== 'current') { throw new Error(`expected current, got ${currentResult}`); }\n"
        "console.log('OK');\n"
    )
    web = REPO_ROOT / "web"
    script_path = web / "src" / "_us1010_stale_self_check_probe.ts"
    script_path.write_text(script, encoding="utf-8", newline="\n")
    try:
        result = subprocess.run(
            [
                "npx",
                "vite-node",
                "--config",
                str(web / "vite.config.ts"),
                str(script_path),
            ],
            cwd=web,
            check=False,
            capture_output=True,
            text=True,
            shell=sys.platform == "win32",
        )
        assert "OK" in result.stdout, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    finally:
        script_path.unlink(missing_ok=True)


def test_coverage_gate_rejects_a_real_placeholder_golden(tmp_path: Path) -> None:
    """US-1010-C5: the gate resists exactly the gaming research warned about. Injects a real
    copy-pasted placeholder golden into a scratch copy of the repo's tests directory and
    confirms the REAL, unmodified coverage test (test_registry_codegen.py, from US-1009)
    fails against it - not a simplified re-derivation of its logic."""
    registry = {entry.key: entry for entry in load_registry().root}
    source_golden = golden_path(registry["btc_daily_close"].golden)
    target_golden = golden_path(registry["eth_rsi"].golden)
    assert source_golden.is_file()
    assert target_golden.is_file()
    assert source_golden != target_golden

    original_target_bytes = target_golden.read_bytes()
    try:
        # A copy-pasted placeholder: eth_rsi's golden becomes a byte-for-byte copy of
        # btc_daily_close's, exactly the gaming pattern the story's spec calls out.
        target_golden.write_bytes(source_golden.read_bytes())

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_registry_codegen.py::test_every_generated_key_has_a_real_golden_and_the_goldens_have_substance",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, (
            "the coverage gate accepted a byte-identical copy-pasted golden\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "copied_distinct_files" in result.stdout or "assert" in result.stdout
    finally:
        target_golden.write_bytes(original_target_bytes)

    # Restored: the real gate is green again on the real, unmutated repo state.
    restored = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_registry_codegen.py::test_every_generated_key_has_a_real_golden_and_the_goldens_have_substance",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert restored.returncode == 0, restored.stdout + restored.stderr
