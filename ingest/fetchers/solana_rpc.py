"""Fetch SOL active addresses from public Solana JSON-RPC blocks."""

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, time, timedelta
import os

import httpx
from pydantic import ValidationError

from ingest.schemas import SolanaBlock, SolanaGetBlockResponse, SolanaInstruction
from ingest.status import Error, Ok, Reason, Result

VOTE_PROGRAM_ID = "Vote111111111111111111111111111111111111111"
HELIUS_RPC_ENDPOINT = "https://mainnet.helius-rpc.com/"
REQUEST_TIMEOUT_SECONDS = 30
FIXED_UTC_HOUR = time(0, 0, tzinfo=UTC)


class SolanaRpcFailure(RuntimeError):
    """A JSON-RPC or transport failure with a user-facing detail."""


def _rpc_endpoint() -> str:
    api_key = os.environ.get("HELIUS_API_KEY")
    if api_key is None or not api_key.strip():
        return HELIUS_RPC_ENDPOINT
    return f"{HELIUS_RPC_ENDPOINT}?api-key={api_key}"


def _post_rpc(
    method: str,
    params: Sequence[object],
    *,
    client: httpx.Client | None,
    request_id: int | str = 1,
) -> object:
    body = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": list(params),
    }
    try:
        response = (
            httpx.post(
                _rpc_endpoint(),
                json=body,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.post(
                _rpc_endpoint(),
                json=body,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        )
        payload: object = response.json()
        response.raise_for_status()
    except httpx.RequestError as error:
        raise SolanaRpcFailure(f"Helius RPC request failed: {error}") from error
    except httpx.HTTPStatusError as error:
        raise SolanaRpcFailure(
            f"Helius RPC returned HTTP {error.response.status_code}"
        ) from error
    except ValueError as error:
        raise SolanaRpcFailure(f"Helius RPC returned invalid JSON: {error}") from error

    if isinstance(payload, dict) and "error" in payload:
        error_payload = payload["error"]
        if isinstance(error_payload, dict):
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
    result = _post_rpc("getBlockTime", [slot], client=client)
    if result is None:
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
    try:
        response = (
            httpx.post(
                _rpc_endpoint(),
                json=body,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.post(
                _rpc_endpoint(),
                json=body,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        )
        payload: object = response.json()
        response.raise_for_status()
        if isinstance(payload, dict) and "error" in payload:
            error_payload = payload["error"]
            if isinstance(error_payload, dict):
                message = error_payload.get("message")
                if isinstance(message, str):
                    raise SolanaRpcFailure(message)
            raise SolanaRpcFailure("Helius getBlock returned an error")
        parsed = SolanaGetBlockResponse.model_validate(payload)
    except httpx.RequestError as error:
        raise SolanaRpcFailure(f"Helius getBlock request failed: {error}") from error
    except httpx.HTTPStatusError as error:
        raise SolanaRpcFailure(
            f"Helius getBlock returned HTTP {error.response.status_code}"
        ) from error
    except ValidationError as error:
        raise SolanaRpcFailure(f"Invalid Helius getBlock response: {error}") from error
    except ValueError as error:
        raise SolanaRpcFailure(f"Helius getBlock returned invalid JSON: {error}") from error

    return parsed.result


def is_vote_transaction(instructions: Iterable[SolanaInstruction]) -> bool:
    """Classify votes from top-level instructions; there is no RPC vote filter."""

    instruction_tuple = tuple(instructions)
    return bool(instruction_tuple) and all(
        instruction.program_id == VOTE_PROGRAM_ID
        for instruction in instruction_tuple
    )


def count_active_fee_payers(blocks: Iterable[SolanaBlock]) -> int:
    """Count distinct fee-payer signers from non-vote transactions."""

    fee_payers: set[str] = set()
    for block in blocks:
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
    return len(fee_payers)


def _default_measured_hour_start(now: datetime) -> datetime:
    current = now.astimezone(UTC)
    today_boundary = datetime.combine(current.date(), FIXED_UTC_HOUR)
    if today_boundary >= current:
        today_boundary -= timedelta(days=1)
    return today_boundary - timedelta(days=1)


def _fetch_blocks_for_hour(
    measured_hour_start: datetime,
    *,
    client: httpx.Client | None,
    slots: Sequence[int] | None,
) -> tuple[SolanaBlock, ...]:
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

    blocks: list[SolanaBlock] = []
    start_timestamp = int(measured_hour_start.timestamp())
    end_timestamp = int((measured_hour_start + timedelta(hours=1)).timestamp())
    for slot in slots:
        block = _get_block(slot, client=client)
        if block is None or block.block_time is None:
            continue
        if start_timestamp <= block.block_time < end_timestamp:
            blocks.append(block)
    return tuple(blocks)


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
        blocks = _fetch_blocks_for_hour(hour_start, client=client, slots=slots)
        return Ok(
            value=float(count_active_fee_payers(blocks)),
            source_timestamp=hour_start,
        )
    except (SolanaRpcFailure, ValidationError, TypeError, ValueError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Solana RPC active-addresses fetch failed: {error}",
        )
