import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from ingest.fetchers.solana_rpc import (
    VOTE_PROGRAM_ID,
    count_active_fee_payers,
    fetch_sol_active_addresses,
    is_vote_transaction,
)
from ingest.registry import load_registry
from ingest.schemas import SolanaBlock, SolanaGetBlockResponse, SolanaInstruction
from ingest.status import Error, Ok, Reason

NOW = datetime(2026, 9, 15, 12, tzinfo=UTC)
HOUR_START = datetime(2026, 9, 14, 0, tzinfo=UTC)


def instruction(program_id: str) -> SolanaInstruction:
    return SolanaInstruction.model_validate(
        {"accounts": [], "data": "3Bxs", "programId": program_id, "stackHeight": None}
    )


def block_payload(
    *,
    fee_payer: str,
    program_ids: list[str],
    block_time: datetime = HOUR_START + timedelta(minutes=5),
) -> dict[str, object]:
    return {
        "blockHeight": 123,
        "blockTime": int(block_time.timestamp()),
        "blockhash": "BlockHash1111111111111111111111111111111111",
        "parentSlot": 42,
        "previousBlockhash": "PrevHash11111111111111111111111111111111111",
        "transactions": [
            {
                "meta": None,
                "transaction": {
                    "message": {
                        "accountKeys": [
                            {
                                "pubkey": fee_payer,
                                "signer": True,
                                "source": "transaction",
                                "writable": True,
                            }
                        ],
                        "instructions": [
                            {
                                "accounts": [],
                                "data": "3Bxs",
                                "programId": program_id,
                                "stackHeight": None,
                            }
                            for program_id in program_ids
                        ],
                        "recentBlockhash": (
                            "RecentHash111111111111111111111111111111111"
                        ),
                    },
                    "signatures": [
                        "Signature111111111111111111111111111111111111111111111"
                    ],
                },
                "version": "legacy",
            }
        ],
    }


def rpc_response(slot: int, result: dict[str, object]) -> dict[str, object]:
    return {"jsonrpc": "2.0", "result": result, "id": slot}


def test_get_block_is_called_without_a_vote_filter_parameter() -> None:
    requested: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        payload = json.loads(body)
        requested.append(payload)
        return httpx.Response(
            200,
            json=rpc_response(
                payload["id"],
                block_payload(
                    fee_payer="NonVoteFeePayer111111111111111111111111111",
                    program_ids=["11111111111111111111111111111111"],
                ),
            ),
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_sol_active_addresses(
            client=client,
            now=NOW,
            measured_hour_start=HOUR_START,
            slots=(10,),
        )

    assert isinstance(result, Ok)
    get_block = requested[0]
    assert get_block["method"] == "getBlock"
    config = get_block["params"][1]
    assert config == {
        "commitment": "finalized",
        "encoding": "jsonParsed",
        "transactionDetails": "full",
        "maxSupportedTransactionVersion": 0,
        "rewards": False,
    }
    assert "votes" not in config
    assert "vote" not in config


def test_vote_only_transaction_is_classified_as_vote_and_excluded() -> None:
    vote_block = SolanaBlock.model_validate(
        block_payload(
            fee_payer="VoteFeePayer111111111111111111111111111111",
            program_ids=[VOTE_PROGRAM_ID],
        )
    )

    assert is_vote_transaction(
        vote_block.transactions[0].transaction.message.instructions
    )
    assert count_active_fee_payers((vote_block,)) == 0


def test_transaction_with_any_non_vote_instruction_counts_fee_payer() -> None:
    mixed_block = SolanaBlock.model_validate(
        block_payload(
            fee_payer="ActiveFeePayer111111111111111111111111111",
            program_ids=[VOTE_PROGRAM_ID, "11111111111111111111111111111111"],
        )
    )

    assert not is_vote_transaction(
        mixed_block.transactions[0].transaction.message.instructions
    )
    assert count_active_fee_payers((mixed_block,)) == 1


def test_exact_one_hour_count_is_distinct_non_vote_fee_payers_only() -> None:
    slots = (1, 2, 3, 4, 5)
    payloads = {
        1: block_payload(
            fee_payer="A111111111111111111111111111111111111111",
            program_ids=["11111111111111111111111111111111"],
        ),
        2: block_payload(
            fee_payer="A111111111111111111111111111111111111111",
            program_ids=["11111111111111111111111111111111"],
        ),
        3: block_payload(
            fee_payer="B111111111111111111111111111111111111111",
            program_ids=["11111111111111111111111111111111"],
        ),
        4: block_payload(
            fee_payer="VoteFeePayer111111111111111111111111111111",
            program_ids=[VOTE_PROGRAM_ID],
        ),
        5: block_payload(
            fee_payer="OutsideHour111111111111111111111111111111",
            program_ids=["11111111111111111111111111111111"],
            block_time=HOUR_START + timedelta(hours=1),
        ),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.read())
        slot = int(payload["id"])
        return httpx.Response(
            200,
            json=rpc_response(slot, payloads[slot]),
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_sol_active_addresses(
            client=client,
            now=NOW,
            measured_hour_start=HOUR_START,
            slots=slots,
        )

    assert result == Ok(value=2.0, source_timestamp=HOUR_START)


def test_registry_source_field_discloses_fixed_hour_and_not_daily_count() -> None:
    entry = next(
        definition
        for definition in load_registry().root
        if definition.key == "sol_active_addresses"
    )

    assert "00:00-01:00 UTC" in entry.source_field
    assert "not a 24-hour count" in entry.source_field


def test_http_or_rpc_error_returns_error_with_detail_and_no_value() -> None:
    def http_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "nope"}, request=request)

    with httpx.Client(transport=httpx.MockTransport(http_handler)) as client:
        http_result = fetch_sol_active_addresses(
            client=client,
            now=NOW,
            measured_hour_start=HOUR_START,
            slots=(1,),
        )

    assert isinstance(http_result, Error)
    assert http_result.reason is Reason.FETCH_FAILED
    assert "HTTP 500" in http_result.detail
    with pytest.raises(AttributeError):
        _ = http_result.value  # type: ignore[attr-defined]

    def rpc_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "error": {"message": "block unavailable"}, "id": 1},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(rpc_handler)) as client:
        rpc_result = fetch_sol_active_addresses(
            client=client,
            now=NOW,
            measured_hour_start=HOUR_START,
            slots=(1,),
        )

    assert isinstance(rpc_result, Error)
    assert rpc_result.reason is Reason.FETCH_FAILED
    assert "block unavailable" in rpc_result.detail
    with pytest.raises(AttributeError):
        _ = rpc_result.value  # type: ignore[attr-defined]


def test_malformed_get_block_response_is_rejected_by_response_model() -> None:
    payload = rpc_response(
        1,
        block_payload(
            fee_payer="FeePayer111111111111111111111111111111111",
            program_ids=["11111111111111111111111111111111"],
        ),
    )
    result = payload["result"]
    assert isinstance(result, dict)
    result["unexpected"] = "vendor reshape"

    with pytest.raises(ValidationError, match="extra_forbidden"):
        SolanaGetBlockResponse.model_validate(payload)


def test_source_timestamp_is_measured_hour_boundary_and_strictly_past() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.read())
        return httpx.Response(
            200,
            json=rpc_response(
                int(payload["id"]),
                block_payload(
                    fee_payer="FeePayer111111111111111111111111111111111",
                    program_ids=["11111111111111111111111111111111"],
                ),
            ),
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_sol_active_addresses(
            client=client,
            now=NOW,
            measured_hour_start=HOUR_START,
            slots=(1,),
        )

    assert isinstance(result, Ok)
    assert result.source_timestamp == HOUR_START
    assert result.source_timestamp < NOW

    future_result = fetch_sol_active_addresses(
        now=NOW,
        measured_hour_start=NOW - timedelta(minutes=30),
        slots=(),
    )
    assert isinstance(future_result, Error)
    assert future_result.reason is Reason.FETCH_FAILED


@pytest.mark.integration
def test_live_helius_request_returns_nonzero_sol_active_address_count() -> None:
    if not os.environ.get("HELIUS_API_KEY"):
        pytest.skip("HELIUS_API_KEY is required for the live Helius integration test")

    result = fetch_sol_active_addresses()

    assert isinstance(result, Ok), result
    assert result.source_timestamp < datetime.now(UTC)
    assert result.value > 0
