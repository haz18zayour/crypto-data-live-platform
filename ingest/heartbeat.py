"""Run ingestion and report its outcome to the dead-man's-switch."""

import os
from collections.abc import Callable

import httpx
import psycopg

from ingest.fetchers.okx import fetch_btc_daily_close
from ingest.pipeline import run_pipeline
from ingest.status import Result

HEARTBEAT_TIMEOUT_SECONDS = 10


def _ping(
    heartbeat_url: str,
    *,
    failed: bool,
    client: httpx.Client | None,
) -> None:
    url = f"{heartbeat_url.rstrip('/')}/fail" if failed else heartbeat_url
    try:
        response = (
            httpx.get(url, timeout=HEARTBEAT_TIMEOUT_SECONDS)
            if client is None
            else client.get(url, timeout=HEARTBEAT_TIMEOUT_SECONDS)
        )
        response.raise_for_status()
    except httpx.HTTPError:
        # The ingest result is authoritative; monitoring must not change it.
        return


def run_ingestion(
    database_url: str,
    heartbeat_url: str,
    *,
    fetcher: Callable[[], Result] = fetch_btc_daily_close,
    heartbeat_client: httpx.Client | None = None,
) -> int:
    """Persist one fetched value, then signal success or explicit failure."""

    fetch_result: Result | None = None

    def observed_fetcher() -> Result:
        nonlocal fetch_result
        fetch_result = fetcher()
        return fetch_result

    try:
        with psycopg.connect(database_url) as connection:
            row_id = run_pipeline(connection, fetcher=observed_fetcher)
        if fetch_result is None or fetch_result.status not in ("OK", "STALE"):
            raise RuntimeError("ingestion did not fetch a value")
    except Exception:
        _ping(heartbeat_url, failed=True, client=heartbeat_client)
        raise

    _ping(heartbeat_url, failed=False, client=heartbeat_client)
    return row_id


def main() -> None:
    """Run the scheduled ingestion using GitHub Actions secrets."""

    run_ingestion(
        os.environ["DATABASE_URL"],
        os.environ["HEALTHCHECKS_PING_URL"],
    )


if __name__ == "__main__":
    main()
