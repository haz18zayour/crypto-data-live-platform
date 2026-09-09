"""Assemble the registry, OKX fetcher, and provenance writer."""

from collections.abc import Callable

import psycopg

from ingest.fetchers.okx import INDICATOR_KEY, MEASURED_ON, fetch_btc_daily_close
from ingest.persist import persist_datapoint
from ingest.registry import load_registry
from ingest.status import Reason, Result, Unavailable


def run_pipeline(
    connection: psycopg.Connection[tuple[object, ...]],
    fetcher: Callable[[], Result] | None = fetch_btc_daily_close,
) -> int:
    """Fetch and persist the registered BTC daily close."""

    definition = next(
        entry for entry in load_registry().root if entry.key == INDICATOR_KEY
    )
    result = Unavailable(reason=Reason.NOT_FETCHED) if fetcher is None else fetcher()
    return persist_datapoint(
        connection,
        definition=definition,
        asset=definition.definable_for[0],
        measured_on=MEASURED_ON,
        result=result,
    )
