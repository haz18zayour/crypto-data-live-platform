from datetime import UTC, datetime

import httpx

from ingest.backfill import BACKFILL_RECIPES
from ingest.fetchers.alternative_me import (
    ALTERNATIVE_ME_FNG_HISTORY_ENDPOINT,
    BackfilledAlternativeMeFearGreedOk,
    backfill_alternative_me_fear_greed,
)
from ingest.registry import load_registry


def _payload() -> dict[str, object]:
    return {
        "name": "Fear and Greed Index",
        "data": [
            {
                "value": "70",
                "value_classification": "Greed",
                "timestamp": "1790553600",
                "time_until_update": "74231",
            },
            {
                "value": "66",
                "value_classification": "Greed",
                "timestamp": "1790467200",
            },
        ],
        "metadata": {"error": None},
    }


def test_alternative_me_registry_entry_is_wired_to_real_backfill_recipe() -> None:
    entry = next(entry for entry in load_registry().root if entry.key == "fear_greed_index")

    assert entry.backfill_recipe == "alternative_me_fng_history"
    assert BACKFILL_RECIPES[entry.backfill_recipe] is backfill_alternative_me_fear_greed


def test_alternative_me_backfill_reads_history_limit_zero_without_verdict_label() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_payload(), request=request)

    entry = next(entry for entry in load_registry().root if entry.key == "fear_greed_index")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runs = backfill_alternative_me_fear_greed(entry, client=client)

    assert str(requests[0].url) == ALTERNATIVE_ME_FNG_HISTORY_ENDPOINT
    values = [next(iter(run.indicators.values())) for run in runs]
    assert len(values) == 2
    assert all(isinstance(value, BackfilledAlternativeMeFearGreedOk) for value in values)
    assert all(not hasattr(value, "value_classification") for value in values)
    assert values[0].value == 70
    assert values[0].source_timestamp == datetime(2026, 9, 28, tzinfo=UTC)
    assert values[0].reference_period == "2026-09-28"
