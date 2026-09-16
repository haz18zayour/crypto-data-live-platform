"""Fetch SOL active addresses from public Solana JSON-RPC blocks."""

import os
import time as time_module
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from datetime import time as time_of_day

import httpx
from pydantic import ValidationError

from ingest.schemas import SolanaBlock, SolanaGetBlockResponse, SolanaInstruction
from ingest.status import Error, Ok, Reason, Result

VOTE_PROGRAM_ID = "Vote111111111111111111111111111111111111111"
HELIUS_RPC_ENDPOINT = "https://mainnet.helius-rpc.com/"
REQUEST_TIMEOUT_SECONDS = 30
FIXED_UTC_HOUR = time_of_day(0, 0, tzinfo=UTC)


class SolanaRpcFailure(RuntimeError):
    """A JSON-RPC or transport failure with a user-facing detail."""


def _rpc_endpoint() -> str:
    api_key = os.environ.get("HELIUS_API_KEY")
    if api_key is None or not api_key.strip():
        return HELIUS_RPC_ENDPOINT
    return f"{HELIUS_RPC_ENDPOINT}?api-key={api_key}"


_SLOT_SKIPPED_ERROR_CODE = -32009


class _SlotSkipped:
    """Sentinel: the requested slot was skipped, or is missing in long-term storage.

    Solana's own documented, normal behavior — not every slot produces a block. Returned only
    when the caller opts in via `treat_slot_skipped_as_none`, since the meaning of "skipped"
    differs by method (getBlockTime: no block time for this slot; other methods do not expect
    a per-slot skip at all and should keep raising).
    """


_SLOT_SKIPPED = _SlotSkipped()

RPC_MAX_ATTEMPTS = 3
RPC_RETRY_BACKOFF_SECONDS = 2.0


def _post_json_with_retry(
    body: Mapping[str, object], *, client: httpx.Client | None
) -> object:
    """POST one JSON-RPC body and return the parsed payload, retrying transient failures only.

    Fetching one UTC hour of Solana blocks is ~9,000 individual requests; a transport-level
    disconnect or an empty/invalid response body is close to guaranteed somewhere in a sequence
    that long, confirmed live twice (a "Server disconnected" transport error, and a
    "Helius RPC returned invalid JSON: Expecting value: line 1 column 1" empty body) — neither
    is a reason to discard everything already fetched. An HTTP error status is a real,
    non-transient outcome and is never retried here.
    """

    last_error: Exception | None = None
    for attempt in range(1, RPC_MAX_ATTEMPTS + 1):
        try:
            response = (
                httpx.post(_rpc_endpoint(), json=body, timeout=REQUEST_TIMEOUT_SECONDS)
                if client is None
                else client.post(
                    _rpc_endpoint(), json=body, timeout=REQUEST_TIMEOUT_SECONDS
                )
            )
            payload: object = response.json()
            response.raise_for_status()
            return payload
        except httpx.HTTPStatusError as error:
            raise SolanaRpcFailure(
                f"Helius RPC returned HTTP {error.response.status_code}"
            ) from error
        except (httpx.RequestError, ValueError) as error:
            last_error = error
            if attempt == RPC_MAX_ATTEMPTS:
                raise SolanaRpcFailure(
                    f"Helius RPC request failed after {RPC_MAX_ATTEMPTS} attempts: {error}"
                ) from error
            time_module.sleep(RPC_RETRY_BACKOFF_SECONDS)
    raise SolanaRpcFailure(f"Helius RPC request failed: {last_error}")  # pragma: no cover


def _post_rpc(
    method: str,
    params: Sequence[object],
    *,
    client: httpx.Client | None,
    request_id: int | str = 1,
    treat_slot_skipped_as_none: bool = False,
) -> object:
    body = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": list(params),
    }
    payload = _post_json_with_retry(body, client=client)

    if isinstance(payload, dict) and "error" in payload:
        error_payload = payload["error"]
        if isinstance(error_payload, dict):
            if (
                treat_slot_skipped_as_none
                and error_payload.get("code") == _SLOT_SKIPPED_ERROR_CODE
            ):
                return _SLOT_SKIPPED
            message = error_payload.get("message")
            if isinstance(message, str):
                raise SolanaRpcFailure(message)
        raise SolanaRpcFailure("Helius RPC returned an error")
    if not isinstance(payload, dict) or "result" not in payload:
        raise SolanaRpcFailure("Helius RPC response omitted result")
    return payload["result"]


def _get_int_rpc(
    method: str,
    params: Sequence[object],
    *,
    client: httpx.Client | None,
) -> int:
    result = _post_rpc(method, params, client=client)
    if not isinstance(result, int):
        raise SolanaRpcFailure(f"{method} returned a non-integer result")
    return result


def _get_slot(client: httpx.Client | None) -> int:
    return _get_int_rpc("getSlot", [{"commitment": "finalized"}], client=client)


def _get_block_time(slot: int, client: httpx.Client | None) -> int | None:
    # A skipped slot has no block time at all — _nearest_block_time already walks backward
    # through slots for exactly this case, so it must be told "no result", not raised as a
    # failure. Confirmed live: -32009 for a skipped slot is common, not exceptional, here.
    result = _post_rpc(
        "getBlockTime", [slot], client=client, treat_slot_skipped_as_none=True
    )
    if result is None or isinstance(result, _SlotSkipped):
        return None
    if not isinstance(result, int):
        raise SolanaRpcFailure("getBlockTime returned a non-integer result")
    return result


def _nearest_block_time(slot: int, client: httpx.Client | None) -> int | None:
    block_time = _get_block_time(slot, client)
    if block_time is not None:
        return block_time
    for offset in range(1, 101):
        block_time = _get_block_time(slot - offset, client)
        if block_time is not None:
            return block_time
    return None


def _find_first_slot_at_or_after(
    boundary: datetime,
    *,
    current_slot: int,
    client: httpx.Client | None,
) -> int:
    target = int(boundary.timestamp())
    low = 0
    high = current_slot
    while low < high:
        mid = (low + high) // 2
        block_time = _nearest_block_time(mid, client)
        if block_time is None or block_time < target:
            low = mid + 1
        else:
            high = mid
    return low


def _get_blocks(
    start_slot: int,
    end_slot: int,
    *,
    client: httpx.Client | None,
) -> tuple[int, ...]:
    if end_slot < start_slot:
        return ()
    result = _post_rpc(
        "getBlocks",
        [start_slot, end_slot, {"commitment": "finalized"}],
        client=client,
    )
    if not isinstance(result, list) or not all(isinstance(slot, int) for slot in result):
        raise SolanaRpcFailure("getBlocks returned a malformed slot list")
    return tuple(result)


def _get_block(slot: int, *, client: httpx.Client | None) -> SolanaBlock | None:
    body = {
        "jsonrpc": "2.0",
        "id": slot,
        "method": "getBlock",
        "params": [
            slot,
            {
                "commitment": "finalized",
                "encoding": "jsonParsed",
                "transactionDetails": "full",
                "maxSupportedTransactionVersion": 0,
                "rewards": False,
            },
        ],
    }
    payload = _post_json_with_retry(body, client=client)

    if isinstance(payload, dict) and "error" in payload:
        error_payload = payload["error"]
        if isinstance(error_payload, dict):
            # -32009: "Slot N was skipped, or missing in long-term storage" — confirmed live.
            # Not every slot produces a block (a validator can miss its turn); this is Solana's
            # normal, documented behavior, not a fetch failure.
            if error_payload.get("code") == _SLOT_SKIPPED_ERROR_CODE:
                return None
            message = error_payload.get("message")
            if isinstance(message, str):
                raise SolanaRpcFailure(message)
        raise SolanaRpcFailure("Helius getBlock returned an error")

    try:
        parsed = SolanaGetBlockResponse.model_validate(payload)
    except ValidationError as error:
        raise SolanaRpcFailure(f"Invalid Helius getBlock response: {error}") from error

    return parsed.result


def is_vote_transaction(instructions: Iterable[SolanaInstruction]) -> bool:
    """Classify votes from top-level instructions; there is no RPC vote filter."""

    instruction_tuple = tuple(instructions)
    return bool(instruction_tuple) and all(
        instruction.program_id == VOTE_PROGRAM_ID
        for instruction in instruction_tuple
    )


def _add_active_fee_payers(block: SolanaBlock, fee_payers: set[str]) -> None:
    """Add one block's non-vote fee-payer signers to the running set, in place."""

    for row in block.transactions:
        message = row.transaction.message
        account_keys = message.account_keys
        if (
            not account_keys
            or not account_keys[0].signer
            or is_vote_transaction(message.instructions)
        ):
            continue
        fee_payers.add(account_keys[0].pubkey)


def count_active_fee_payers(blocks: Iterable[SolanaBlock]) -> int:
    """Count distinct fee-payer signers from non-vote transactions.

    Kept for the unit tests that exercise classification against a handful of blocks held in
    memory. The live fetch path (`_fetch_blocks_for_hour`) does NOT call this — it streams each
    block through `_add_active_fee_payers` and discards it immediately, because accumulating a
    full UTC hour's fully-parsed blocks (~9,000 of them, `encoding: jsonParsed`,
    `transactionDetails: full`, tens of millions of transactions network-wide per hour at
    Solana's real throughput) before counting exhausted this machine's memory outright when
    verified live — a genuine defect, not a hypothetical one.
    """

    fee_payers: set[str] = set()
    for block in blocks:
        _add_active_fee_payers(block, fee_payers)
    return len(fee_payers)


def _default_measured_hour_start(now: datetime) -> datetime:
    current = now.astimezone(UTC)
    today_boundary = datetime.combine(current.date(), FIXED_UTC_HOUR)
    if today_boundary >= current:
        today_boundary -= timedelta(days=1)
    return today_boundary - timedelta(days=1)


def _count_active_fee_payers_for_hour(
    measured_hour_start: datetime,
    *,
    client: httpx.Client | None,
    slots: Sequence[int] | None,
) -> int:
    """Stream one UTC hour's blocks, one at a time, never holding more than one in memory.

    A full hour is ~9,000 blocks at Solana's ~400ms block time, each with full parsed
    transaction detail — accumulating them into a list before counting exhausted memory outright
    when verified live. Each block is fetched, its fee-payers folded into the running set, then
    the block itself is dropped before the next fetch.
    """

    if slots is None:
        current_slot = _get_slot(client)
        start_slot = _find_first_slot_at_or_after(
            measured_hour_start,
            current_slot=current_slot,
            client=client,
        )
        end_slot = _find_first_slot_at_or_after(
            measured_hour_start + timedelta(hours=1),
            current_slot=current_slot,
            client=client,
        )
        slots = _get_blocks(start_slot, end_slot - 1, client=client)

    fee_payers: set[str] = set()
    start_timestamp = int(measured_hour_start.timestamp())
    end_timestamp = int((measured_hour_start + timedelta(hours=1)).timestamp())
    for slot in slots:
        block = _get_block(slot, client=client)
        if block is None or block.block_time is None:
            continue
        if start_timestamp <= block.block_time < end_timestamp:
            _add_active_fee_payers(block, fee_payers)
    return len(fee_payers)


def fetch_sol_active_addresses(
    *,
    client: httpx.Client | None = None,
    now: datetime | None = None,
    measured_hour_start: datetime | None = None,
    slots: Sequence[int] | None = None,
) -> Result:
    """Return SOL's exact active fee-payer count for one fixed UTC hour."""

    current_time = datetime.now(UTC) if now is None else now.astimezone(UTC)
    hour_start = (
        _default_measured_hour_start(current_time)
        if measured_hour_start is None
        else measured_hour_start.astimezone(UTC)
    )
    hour_end = hour_start + timedelta(hours=1)
    if hour_end >= current_time:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail="Solana measured hour must be strictly in the past",
        )

    try:
        active_count = _count_active_fee_payers_for_hour(
            hour_start, client=client, slots=slots
        )
        return Ok(
            value=float(active_count),
            source_timestamp=hour_start,
        )
    except (SolanaRpcFailure, ValidationError, TypeError, ValueError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Solana RPC active-addresses fetch failed: {error}",
        )
