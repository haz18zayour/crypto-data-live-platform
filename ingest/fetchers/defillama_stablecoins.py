"""Fetch per-chain USD-pegged stablecoin supply from DefiLlama."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Literal, NoReturn

import httpx
from pydantic import ValidationError

from ingest.registry import IndicatorDefinition
from ingest.schemas import (
    DefiLlamaStablecoinChainsResponse,
    DefiLlamaStablecoinChartsResponse,
)
from ingest.status import Error, Reason

if TYPE_CHECKING:
    from ingest.pipeline import FullAssetRun

DEFILLAMA_STABLECOINCHAINS_ENDPOINT = (
    "https://stablecoins.llama.fi/stablecoinchains"
)
DEFILLAMA_STABLECOINCHARTS_ENDPOINT = (
    "https://stablecoins.llama.fi/stablecoincharts/{chain}"
)
REQUEST_TIMEOUT_SECONDS = 10
DEFILLAMA_SOURCE_FIELD = (
    "DefiLlama /stablecoinchains totalCirculatingUSD.peggedUSD "
    "(USD-pegged only)"
)
DEFILLAMA_CHARTS_SOURCE_FIELD = (
    "DefiLlama /stablecoincharts/{chain} totalCirculatingUSD.peggedUSD "
    "(USD-pegged only)"
)
ASSET_TO_CHAIN = {
    "ETH": "Ethereum",
    "SOL": "Solana",
    "BNB": "BSC",
    "BSC": "BSC",
}
BTC_NOT_DEFINABLE_DETAIL = (
    "DefiLlama's own /stablecoinchains chain list has no Bitcoin entry; "
    "Bitcoin has no stablecoin-supply concept to source here"
)


@dataclass(frozen=True, slots=True)
class DefiLlamaStablecoinSupplyOk:
    """A current USD-pegged stablecoin-supply total for one chain."""

    value: Decimal
    source_timestamp: datetime
    reference_period: str
    published_at: datetime
    chain: str
    source_field: str = DEFILLAMA_SOURCE_FIELD
    # None for the live fetcher, which relies on persist_board's fallback to the
    # registry's own static endpoint (correct there, since that IS the live snapshot
    # URL). Backfill sets this explicitly to the per-chain stablecoincharts URL it
    # actually called - otherwise persist_board's duck-typed getattr(result, "endpoint",
    # None) silently falls back to the live URL for a backfilled row too, misrepresenting
    # where the historical value actually came from.
    endpoint: str | None = None
    status: Literal["OK"] = field(default="OK", init=False)

    def __post_init__(self) -> None:
        if self.source_timestamp.tzinfo is None:
            raise ValueError("source_timestamp must be timezone-aware")
        if self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")
        if not self.reference_period.strip():
            raise ValueError("reference_period must be non-empty")
        if not self.chain.strip():
            raise ValueError("chain must be non-empty")


type DefiLlamaStablecoinSupplyResult = DefiLlamaStablecoinSupplyOk | Error


def _parse_amount(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"DefiLlama peggedUSD value is not numeric: {value}") from error


def _parse_unix_seconds(value: str) -> datetime:
    return datetime.fromtimestamp(int(value), tz=UTC)


def _run_key(definition: IndicatorDefinition, asset: str) -> str:
    if definition.definable_for == (asset,):
        return definition.key
    return f"{definition.key}\x1f{asset}"


def _get_json(
    endpoint: str,
    *,
    client: httpx.Client | None = None,
) -> object:
    try:
        response = (
            httpx.get(endpoint, timeout=REQUEST_TIMEOUT_SECONDS)
            if client is None
            else client.get(endpoint, timeout=REQUEST_TIMEOUT_SECONDS)
        )
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as error:
        raise RuntimeError(
            f"DefiLlama request failed: {error.__class__.__name__}"
        ) from error
    except httpx.HTTPStatusError as error:
        raise RuntimeError(
            f"DefiLlama returned HTTP {error.response.status_code}"
        ) from error


def _runs_for(
    definition: IndicatorDefinition,
    values: list[tuple[str, DefiLlamaStablecoinSupplyOk]],
) -> tuple["FullAssetRun", ...]:
    from ingest.pipeline import FullAssetRun

    return tuple(
        FullAssetRun(indicators={_run_key(definition, asset): value}, history={})
        for asset, value in values
    )


def _raise_backfill_fetch_error(error: Exception) -> NoReturn:
    raise RuntimeError(str(error)) from error


def backfill_defillama_stablecoin_supply(
    definition: IndicatorDefinition,
    *,
    client: httpx.Client | None = None,
) -> tuple["FullAssetRun", ...]:
    """Backfill per-chain stablecoin supply from DefiLlama's chart endpoint."""

    values: list[tuple[str, DefiLlamaStablecoinSupplyOk]] = []
    try:
        for asset in definition.definable_for:
            chain = ASSET_TO_CHAIN.get(asset.upper())
            if chain is None:
                continue
            endpoint = DEFILLAMA_STABLECOINCHARTS_ENDPOINT.format(chain=chain)
            rows = DefiLlamaStablecoinChartsResponse.model_validate(
                _get_json(endpoint, client=client)
            ).root
            for row in rows:
                source_timestamp = _parse_unix_seconds(row.date)
                values.append(
                    (
                        asset,
                        DefiLlamaStablecoinSupplyOk(
                            value=_parse_amount(
                                row.total_circulating_usd.pegged_usd
                            ),
                            source_timestamp=source_timestamp,
                            reference_period=source_timestamp.date().isoformat(),
                            published_at=source_timestamp,
                            chain=chain,
                            source_field=DEFILLAMA_CHARTS_SOURCE_FIELD.format(
                                chain=chain
                            ),
                            endpoint=endpoint,
                        ),
                    )
                )
    except (
        RuntimeError,
        ValidationError,
        TypeError,
        ValueError,
        OverflowError,
    ) as error:
        _raise_backfill_fetch_error(error)
    return _runs_for(definition, values)


def fetch_stablecoin_supply(
    asset: Literal["ETH", "SOL", "BNB", "BSC", "BTC"] | str,
    *,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> DefiLlamaStablecoinSupplyResult:
    """Return current USD-pegged stablecoin supply for a tracked chain."""

    normalized_asset = asset.upper()
    if normalized_asset == "BTC":
        return Error(reason=Reason.NOT_DEFINABLE, detail=BTC_NOT_DEFINABLE_DETAIL)
    chain = ASSET_TO_CHAIN.get(normalized_asset)
    if chain is None:
        return Error(
            reason=Reason.NOT_DEFINABLE,
            detail=f"No DefiLlama stablecoin-supply chain mapping for {asset}",
        )

    try:
        response = (
            httpx.get(
                DEFILLAMA_STABLECOINCHAINS_ENDPOINT,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.get(
                DEFILLAMA_STABLECOINCHAINS_ENDPOINT,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        )
    except httpx.RequestError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"DefiLlama request failed: {error.__class__.__name__}",
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"DefiLlama returned HTTP {error.response.status_code}",
        )

    try:
        payload = DefiLlamaStablecoinChainsResponse.model_validate(response.json())
        row = next((entry for entry in payload.root if entry.name == chain), None)
        if row is None:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"DefiLlama stablecoinchains returned no {chain} row",
            )
        fetched_at = now or datetime.now(UTC)
        if fetched_at.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return DefiLlamaStablecoinSupplyOk(
            value=_parse_amount(row.total_circulating_usd.pegged_usd),
            source_timestamp=fetched_at,
            reference_period="current",
            published_at=fetched_at,
            chain=chain,
        )
    except (ValidationError, TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid DefiLlama stablecoinchains response: {error}",
        )


def fetch_eth_stablecoin_supply() -> DefiLlamaStablecoinSupplyResult:
    return fetch_stablecoin_supply("ETH")


def fetch_sol_stablecoin_supply() -> DefiLlamaStablecoinSupplyResult:
    return fetch_stablecoin_supply("SOL")


def fetch_bsc_stablecoin_supply() -> DefiLlamaStablecoinSupplyResult:
    return fetch_stablecoin_supply("BNB")
