"""Fetch per-chain USD-pegged stablecoin supply from DefiLlama."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

import httpx
from pydantic import ValidationError

from ingest.schemas import DefiLlamaStablecoinChainsResponse
from ingest.status import Error, Reason

DEFILLAMA_STABLECOINCHAINS_ENDPOINT = (
    "https://stablecoins.llama.fi/stablecoinchains"
)
REQUEST_TIMEOUT_SECONDS = 10
DEFILLAMA_SOURCE_FIELD = (
    "DefiLlama /stablecoinchains totalCirculatingUSD.peggedUSD "
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
