from pathlib import Path

WORKFLOW = Path(".github/workflows/ingest.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_ingest_workflow_cron_runs_once_daily_at_existing_offset() -> None:
    text = _workflow_text()

    assert "cron: '17 0 * * *'" in text
    assert "cron: '17 */6 * * *'" not in text


def test_ingest_workflow_runs_shared_entrypoint_for_daily_tier() -> None:
    text = _workflow_text()

    assert "run: uv run python -m ingest.heartbeat --tier daily" in text


def test_ingest_workflow_keeps_existing_heartbeat_secret() -> None:
    text = _workflow_text()

    assert "HEALTHCHECKS_PING_URL: ${{ secrets.HEALTHCHECKS_PING_URL }}" in text
