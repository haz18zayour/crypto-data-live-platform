"""Fetch SOL staking data from Validators.app."""

import os
from datetime import UTC, datetime

import httpx
from pydantic import ValidationError

from ingest.schemas import ValidatorsAppEpochsResponse
from ingest.status import Error, Ok, Reason, Result

VALIDATORS_APP_EPOCHS_ENDPOINT = "https://www.validators.app/api/v1/epochs/mainnet.json"
REQUEST_TIMEOUT_SECONDS = 10
LAMPORTS_PER_SOL = 1_000_000_000


def _api_token() -> str | None:
    token = os.environ.get("VALIDATORS_APP_API_TOKEN")
    if token is None or not token.strip():
        return None
    return token.strip()


def _parse_validators_app_time(value: str) -> datetime:
    normalized = value.removesuffix("Z")
    if "." in normalized:
        prefix, suffix = normalized.split(".", 1)
        normalized = f"{prefix}.{suffix[:6]}"
    return datetime.fromisoformat(normalized).replace(tzinfo=UTC)


def fetch_sol_staking(
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> Result:
    """Return SOL total active stake from Validators.app's latest epoch."""

    token = _api_token()
    if token is None:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail="VALIDATORS_APP_API_TOKEN is not configured",
        )

    try:
        response = (
            httpx.get(
                VALIDATORS_APP_EPOCHS_ENDPOINT,
                params={"per": "1"},
                headers={"Token": token},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.get(
                VALIDATORS_APP_EPOCHS_ENDPOINT,
                params={"per": "1"},
                headers={"Token": token},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        )
    except httpx.RequestError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Validators.app request failed: {error}",
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Validators.app returned HTTP {error.response.status_code}",
        )

    try:
        payload = response.json()
        rows = ValidatorsAppEpochsResponse.model_validate(payload).epochs
        if len(rows) != 1:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="Validators.app returned an unexpected number of epoch rows",
            )
        row = rows[0]
        if row.network != "mainnet":
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"Validators.app returned network {row.network}, expected mainnet",
            )
        source_timestamp = _parse_validators_app_time(row.created_at)
        current_time = datetime.now(UTC) if now is None else now
        if source_timestamp >= current_time:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="Validators.app source timestamp is in the future or present",
            )
        return Ok(
            value=row.total_active_stake / LAMPORTS_PER_SOL,
            source_timestamp=source_timestamp,
        )
    except (ValidationError, TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid Validators.app epochs response: {error}",
        )
