"""Fetch SOL staking data from Validators.app."""

import os
from datetime import UTC, datetime

import httpx
from pydantic import ValidationError

from ingest.schemas import ValidatorsAppValidatorsResponse
from ingest.status import Error, Ok, Reason, Result

VALIDATORS_APP_VALIDATORS_ENDPOINT = (
    "https://www.validators.app/api/v1/validators/mainnet.json"
)
REQUEST_TIMEOUT_SECONDS = 10
LAMPORTS_PER_SOL = 1_000_000_000
# Comfortably above the live mainnet validator count (681, confirmed 2026-09-16) so a full,
# untruncated page is requested in one call; the truncation check below still guards it.
VALIDATORS_PAGE_SIZE = 2000


def _api_token() -> str | None:
    token = os.environ.get("VALIDATORS_APP_API_TOKEN")
    if token is None or not token.strip():
        return None
    return token.strip()


def fetch_sol_staking(
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> Result:
    """Return SOL total active stake, summed live across every mainnet validator.

    Validators.app's epochs endpoint (this project's original source) returns
    total_active_stake as null on every epoch checked, current or already completed -
    confirmed live across a month of epochs, 2026-09-16. The validators-list endpoint
    carries a real, non-null active_stake per validator instead.
    """

    token = _api_token()
    if token is None:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail="VALIDATORS_APP_API_TOKEN is not configured",
        )

    source_timestamp = datetime.now(UTC) if now is None else now

    try:
        response = (
            httpx.get(
                VALIDATORS_APP_VALIDATORS_ENDPOINT,
                params={"per": str(VALIDATORS_PAGE_SIZE)},
                headers={"Token": token},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.get(
                VALIDATORS_APP_VALIDATORS_ENDPOINT,
                params={"per": str(VALIDATORS_PAGE_SIZE)},
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
        validators = ValidatorsAppValidatorsResponse.model_validate(payload).root
        if len(validators) >= VALIDATORS_PAGE_SIZE:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=(
                    f"Validators.app returned {len(validators)} validators, at or above "
                    f"the requested page size ({VALIDATORS_PAGE_SIZE}) — the result may "
                    "be truncated"
                ),
            )
        mainnet_validators = [row for row in validators if row.network == "mainnet"]
        if not mainnet_validators:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="Validators.app returned no mainnet validators",
            )
        total_active_stake = sum(
            row.active_stake or 0 for row in mainnet_validators
        )
        if total_active_stake <= 0:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=(
                    "Validators.app returned zero total active stake across all "
                    "mainnet validators"
                ),
            )
        return Ok(
            value=total_active_stake / LAMPORTS_PER_SOL,
            source_timestamp=source_timestamp,
        )
    except (ValidationError, TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid Validators.app validators response: {error}",
        )
