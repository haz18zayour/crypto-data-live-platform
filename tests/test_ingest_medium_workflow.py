from pathlib import Path

WORKFLOW = Path(".github/workflows/ingest-medium.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_ingest_medium_workflow_cron_runs_every_eight_hours_off_peak() -> None:
    text = _workflow_text()

    assert "cron: '37 */8 * * *'" in text
    assert "cron: '0 */8 * * *'" not in text
    assert "cron: '5 */8 * * *'" not in text


def test_ingest_medium_workflow_runs_shared_entrypoint_for_medium_tier() -> None:
    text = _workflow_text()

    assert "run: uv run python -m ingest.heartbeat --tier medium" in text


def test_ingest_medium_workflow_uses_dedicated_heartbeat_secret() -> None:
    text = _workflow_text()

    assert "HEALTHCHECKS_PING_URL: ${{ secrets.HEALTHCHECK_URL_INGEST_MEDIUM }}" in text
    assert "HEALTHCHECKS_PING_URL: ${{ secrets.HEALTHCHECKS_PING_URL }}" not in text
    assert "HEALTHCHECK_URL_CONTRACT_CANARY" not in text
