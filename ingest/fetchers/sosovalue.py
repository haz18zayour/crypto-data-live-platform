"""Fetch US spot ETF net flows from SoSoValue's authenticated Demo API."""

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

import httpx
from pydantic import ValidationError

from ingest.schemas import SosoValueEtfSummaryHistoryResponse
from ingest.status import Error, Reason

SOSOVALUE_SUMMARY_HISTORY_ENDPOINT = (
    "https://openapi.sosovalue.com/openapi/v1/etfs/summary-history"
)
REQUEST_TIMEOUT_SECONDS = 10
SOSOVALUE_SOURCE_FIELD = "SoSoValue /etfs/summary-history total_net_inflow"
SUPPORTED_SYMBOLS = frozenset({"BTC", "ETH", "SOL"})


@dataclass(frozen=True, slots=True)
class SosoValueEtfFlowOk:
    """A reported ETF net flow, preserving vendor money precision."""

    value: Decimal
    source_timestamp: datetime
    reference_period: str
    published_at: datetime
    source_field: str = SOSOVALUE_SOURCE_FIELD
    status: Literal["OK"] = field(default="OK", init=False)

    def __post_init__(self) -> None:
        if self.source_timestamp.tzinfo is None:
            raise ValueError("source_timestamp must be timezone-aware")
        if self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")
        if not self.reference_period.strip():
            raise ValueError("reference_period must be non-empty")


type SosoValueEtfFlowResult = SosoValueEtfFlowOk | Error


def _api_key() -> str | None:
    token = os.environ.get("SOSOVALUE_API_KEY")
    if token is None or not token.strip():
        return None
    return token.strip()


def _parse_money(value: float) -> Decimal:
    # Convert via str(), never Decimal(float) directly - the latter preserves the float's
    # own binary imprecision (e.g. Decimal(0.1) != Decimal("0.1")), which would drift
    # PRD-002's determinism golden files despite the source value being unchanged.
    try:
        return Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"SoSoValue money field is not numeric: {value}") from error


def _parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def fetch_etf_net_flow(
    symbol: Literal["BTC", "ETH", "SOL"] | str,
    *,
    client: httpx.Client | None = None,
    api_key: str | None = None,
) -> SosoValueEtfFlowResult:
    """Return the newest US aggregate spot ETF net-flow row for one asset."""

    normalized_symbol = symbol.upper()
    if normalized_symbol not in SUPPORTED_SYMBOLS:
        return Error(
            reason=Reason.NOT_DEFINABLE,
            detail=(
                "SoSoValue /etfs/summary-history symbol enum includes BTC, ETH, "
                "SOL, LTC, HBAR, XRP, DOGE, LINK, AVAX, DOT; it does not include BNB"
            ),
        )

    token = _api_key() if api_key is None else api_key.strip()
    if not token:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail="SOSOVALUE_API_KEY is not configured",
        )

    headers = {"x-soso-api-key": token}
    params = {"symbol": normalized_symbol, "country_code": "US", "limit": "1"}
    try:
        response = (
            httpx.get(
                SOSOVALUE_SUMMARY_HISTORY_ENDPOINT,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.get(
                SOSOVALUE_SUMMARY_HISTORY_ENDPOINT,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        )
    except httpx.RequestError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"SoSoValue request failed: {error.__class__.__name__}",
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"SoSoValue returned HTTP {error.response.status_code}",
        )

    try:
        payload = SosoValueEtfSummaryHistoryResponse.model_validate(response.json())
        if payload.code != 0:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"SoSoValue returned code {payload.code}: {payload.message}",
            )
        if not payload.data:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"SoSoValue returned no {normalized_symbol} ETF flow rows",
            )

        row = payload.data[0]
        flow_date = _parse_date(row.date)
        return SosoValueEtfFlowOk(
            value=_parse_money(row.total_net_inflow),
            source_timestamp=flow_date,
            reference_period=row.date,
            published_at=flow_date,
        )
    except (ValidationError, TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid SoSoValue summary-history response: {error}",
        )


def fetch_btc_etf_net_flow() -> SosoValueEtfFlowResult:
    return fetch_etf_net_flow("BTC")


def fetch_eth_etf_net_flow() -> SosoValueEtfFlowResult:
    return fetch_etf_net_flow("ETH")


def fetch_sol_etf_net_flow() -> SosoValueEtfFlowResult:
    return fetch_etf_net_flow("SOL")
