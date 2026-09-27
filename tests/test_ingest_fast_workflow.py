from pathlib import Path

WORKFLOW = Path(".github/workflows/ingest-fast.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_ingest_fast_workflow_uses_repository_dispatch_clock_only() -> None:
    text = _workflow_text()

    assert "repository_dispatch:" in text
    assert "types: [ingest-fast]" in text
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "push:" not in text


def test_ingest_fast_workflow_runs_shared_entrypoint_for_fast_tier() -> None:
    text = _workflow_text()

    assert "run: uv run python -m ingest.heartbeat --tier fast" in text


def test_ingest_fast_workflow_uses_dedicated_heartbeat_secret() -> None:
    text = _workflow_text()

    assert "HEALTHCHECKS_PING_URL: ${{ secrets.HEALTHCHECK_URL_INGEST_FAST }}" in text
    assert "HEALTHCHECKS_PING_URL: ${{ secrets.HEALTHCHECKS_PING_URL }}" not in text
    assert "HEALTHCHECK_URL_INGEST_MEDIUM" not in text
    assert "HEALTHCHECK_URL_CONTRACT_CANARY" not in text
