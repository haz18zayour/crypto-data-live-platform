"""Run ingestion and report its outcome to the dead-man's-switch."""

import argparse
import os
import sys
from collections.abc import Callable, Sequence

import httpx
import psycopg

from ingest.pipeline import (
    FullAssetRun,
    run_pipeline,
    run_scheduled_board,
    run_sol_active_addresses,
)
from ingest.registry import CadenceTier
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
    tier: CadenceTier | None = None,
    fetcher: Callable[[], Result | FullAssetRun] | None = None,
    heartbeat_client: httpx.Client | None = None,
) -> int | tuple[int, ...]:
    """Persist the selected scheduled run, then signal success or explicit failure."""

    fetch_result: Result | FullAssetRun | None = None
    if fetcher is not None:
        selected_fetcher = fetcher
    elif tier is None:
        selected_fetcher = run_scheduled_board
    else:
        selected_fetcher = lambda: run_scheduled_board(tier=tier)

    def observed_fetcher() -> Result | FullAssetRun:
        nonlocal fetch_result
        fetch_result = selected_fetcher()
        return fetch_result

    try:
        with psycopg.connect(database_url) as connection:
            persisted = run_pipeline(connection, fetcher=observed_fetcher)
        if isinstance(fetch_result, FullAssetRun):
            if not isinstance(persisted, tuple) or len(persisted) != len(
                fetch_result.indicators
            ):
                raise RuntimeError("ingestion did not persist the full board")
        elif fetch_result is None or fetch_result.status not in ("OK", "STALE"):
            raise RuntimeError("ingestion did not fetch a value")
    except Exception:
        _ping(heartbeat_url, failed=True, client=heartbeat_client)
        raise

    _ping(heartbeat_url, failed=False, client=heartbeat_client)
    return persisted


def main(argv: Sequence[str] = ()) -> None:
    """Run the scheduled ingestion using GitHub Actions secrets."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=("fast", "medium", "daily"))
    args = parser.parse_args(argv)

    run_ingestion(
        os.environ["DATABASE_URL"],
        os.environ["HEALTHCHECKS_PING_URL"],
        tier=args.tier,
    )


def main_sol_active_addresses() -> None:
    """Run the long SOL active-addresses ingestion using GitHub Actions secrets."""

    run_ingestion(
        os.environ["DATABASE_URL"],
        os.environ["HEALTHCHECKS_PING_URL"],
        fetcher=run_sol_active_addresses,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
