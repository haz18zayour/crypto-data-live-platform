"""Fetch US spot ETF net flows from SoSoValue's authenticated Demo API."""

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Literal, NoReturn

import httpx
from pydantic import ValidationError

from ingest.registry import IndicatorDefinition
from ingest.schemas import SosoValueEtfSummaryHistoryResponse
from ingest.status import Error, Reason

if TYPE_CHECKING:
    from ingest.pipeline import FullAssetRun

SOSOVALUE_SUMMARY_HISTORY_ENDPOINT = (
    "https://openapi.sosovalue.com/openapi/v1/etfs/summary-history"
)
REQUEST_TIMEOUT_SECONDS = 10
SOSOVALUE_SOURCE_FIELD = "SoSoValue /etfs/summary-history total_net_inflow"
SUPPORTED_SYMBOLS = frozenset({"BTC", "ETH", "SOL"})
BACKFILL_LIMIT = 300


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


@dataclass(frozen=True, slots=True)
class SosoValueHistoryProbe:
    """Measured shape, range, and rate-limit behavior for summary-history."""

    symbol: str
    requested_limit: int
    rows: int
    newest_date: str
    oldest_date: str
    fields: tuple[str, ...]
    rate_limit_status: int
    rate_limit_detail: str
    rate_limit_limit: int | None = None
    rate_limit_remaining: int | None = None
    rate_limit_reset: str | None = None


@dataclass(frozen=True, slots=True)
class _SosoValueSummaryHistory:
    payload: SosoValueEtfSummaryHistoryResponse
    headers: httpx.Headers
    status_code: int


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


def _run_key(definition: IndicatorDefinition, asset: str) -> str:
    if definition.definable_for == (asset,):
        return definition.key
    return f"{definition.key}\x1f{asset}"


def _get_summary_history(
    symbol: str,
    *,
    limit: int,
    client: httpx.Client | None = None,
    api_key: str | None = None,
) -> _SosoValueSummaryHistory:
    token = _api_key() if api_key is None else api_key.strip()
    if not token:
        raise RuntimeError("SOSOVALUE_API_KEY is not configured")

    response = (
        httpx.get(
            SOSOVALUE_SUMMARY_HISTORY_ENDPOINT,
            headers={"x-soso-api-key": token},
            params={"symbol": symbol, "country_code": "US", "limit": str(limit)},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if client is None
        else client.get(
            SOSOVALUE_SUMMARY_HISTORY_ENDPOINT,
            headers={"x-soso-api-key": token},
            params={"symbol": symbol, "country_code": "US", "limit": str(limit)},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    )
    response.raise_for_status()
    payload = SosoValueEtfSummaryHistoryResponse.model_validate(response.json())
    if payload.code != 0:
        raise RuntimeError(f"SoSoValue returned code {payload.code}: {payload.message}")
    return _SosoValueSummaryHistory(
        payload=payload,
        headers=response.headers,
        status_code=response.status_code,
    )


def _header_int(headers: httpx.Headers, name: str) -> int | None:
    value = headers.get(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _rate_limit_detail(
    response: _SosoValueSummaryHistory,
) -> tuple[int, str, int | None, int | None, str | None]:
    limit = _header_int(response.headers, "X-RateLimit-Limit")
    remaining = _header_int(response.headers, "X-RateLimit-Remaining")
    reset = response.headers.get("X-RateLimit-Reset")
    if limit is None and remaining is None and reset is None:
        return (
            response.status_code,
            "no rate-limit headers on first response",
            None,
            None,
            None,
        )
    return (
        response.status_code,
        f"headers report limit={limit}, remaining={remaining}, reset={reset}",
        limit,
        remaining,
        reset,
    )


def probe_sosovalue_summary_history(
    symbol: Literal["BTC", "ETH", "SOL"] | str = "BTC",
    *,
    client: httpx.Client | None = None,
    api_key: str | None = None,
    sample_limit: int = BACKFILL_LIMIT,
    rate_probe_requests: int = 25,
) -> SosoValueHistoryProbe:
    """Live-probe the endpoint's real row shape, date range, and rate limit."""

    normalized_symbol = symbol.upper()
    response = _get_summary_history(
        normalized_symbol,
        limit=sample_limit,
        client=client,
        api_key=api_key,
    )
    payload = response.payload
    if not payload.data:
        raise RuntimeError(f"SoSoValue returned no {normalized_symbol} rows")

    dates = sorted(row.date for row in payload.data)
    fields = tuple(payload.data[0].model_dump().keys())
    (
        rate_limit_status,
        rate_limit_detail,
        rate_limit_limit,
        rate_limit_remaining,
        rate_limit_reset,
    ) = _rate_limit_detail(response)
    if (
        rate_limit_limit is None
        and rate_limit_remaining is None
        and rate_limit_reset is None
    ):
        rate_limit_status = 200
        rate_limit_detail = f"no 429 across {rate_probe_requests} immediate probe requests"
        for index in range(rate_probe_requests):
            try:
                _get_summary_history(
                    normalized_symbol,
                    limit=1,
                    client=client,
                    api_key=api_key,
                )
            except httpx.HTTPStatusError as error:
                rate_limit_status = error.response.status_code
                rate_limit_detail = (
                    f"request {index + 1} returned HTTP {error.response.status_code}"
                )
                break

    return SosoValueHistoryProbe(
        symbol=normalized_symbol,
        requested_limit=sample_limit,
        rows=len(payload.data),
        newest_date=dates[-1],
        oldest_date=dates[0],
        fields=fields,
        rate_limit_status=rate_limit_status,
        rate_limit_detail=rate_limit_detail,
        rate_limit_limit=rate_limit_limit,
        rate_limit_remaining=rate_limit_remaining,
        rate_limit_reset=rate_limit_reset,
    )


def _runs_for(
    definition: IndicatorDefinition,
    values: list[tuple[str, SosoValueEtfFlowOk]],
) -> tuple["FullAssetRun", ...]:
    from ingest.pipeline import FullAssetRun

    return tuple(
        FullAssetRun(indicators={_run_key(definition, asset): value}, history={})
        for asset, value in values
    )


def _raise_backfill_fetch_error(error: Exception) -> NoReturn:
    raise RuntimeError(str(error)) from error


def backfill_sosovalue_etf_flows(
    definition: IndicatorDefinition,
    *,
    client: httpx.Client | None = None,
    api_key: str | None = None,
    limit: int = BACKFILL_LIMIT,
) -> tuple["FullAssetRun", ...]:
    """Backfill US spot ETF net flows from SoSoValue's own summary history."""

    values: list[tuple[str, SosoValueEtfFlowOk]] = []
    try:
        for asset in definition.definable_for:
            if asset not in SUPPORTED_SYMBOLS:
                continue
            response = _get_summary_history(
                asset,
                limit=limit,
                client=client,
                api_key=api_key,
            )
            payload = response.payload
            dates = sorted(row.date for row in payload.data)
            range_detail = (
                f"observed rows={len(payload.data)}"
                if not dates
                else (
                    f"observed rows={len(payload.data)} "
                    f"range={dates[0]}..{dates[-1]}"
                )
            )
            for row in payload.data:
                flow_date = _parse_date(row.date)
                values.append(
                    (
                        asset,
                        SosoValueEtfFlowOk(
                            value=_parse_money(row.total_net_inflow),
                            source_timestamp=flow_date,
                            reference_period=row.date,
                            published_at=flow_date,
                            source_field=(
                                f"{SOSOVALUE_SOURCE_FIELD}; request limit={limit}; "
                                f"{range_detail}"
                            ),
                        ),
                    )
                )
    except (
        RuntimeError,
        ValidationError,
        httpx.HTTPError,
        TypeError,
        ValueError,
        OverflowError,
    ) as error:
        _raise_backfill_fetch_error(error)
    return _runs_for(definition, values)


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
