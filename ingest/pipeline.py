"""Assemble registry declarations, venue history, computation, and persistence."""

import math
import re
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from functools import partial
from typing import Literal, cast
from urllib.parse import parse_qs, urlparse

import httpx
import psycopg

from ingest.compute import compute_indicator, daily_close
from ingest.fetchers import (
    alternative_me,
    coinbase,
    coinmetrics,
    defillama_stablecoins,
    fred,
    okx,
    solana_rpc,
    sosovalue,
    validators_app,
)
from ingest.fetchers.alternative_me import (
    AlternativeMeFearGreedOk,
    AlternativeMeFearGreedResult,
)
from ingest.fetchers.defillama_stablecoins import (
    DefiLlamaStablecoinSupplyOk,
    DefiLlamaStablecoinSupplyResult,
)
from ingest.fetchers.fred import FredOk, FredResult, FredSeries
from ingest.fetchers.okx import (
    INDICATOR_KEY,
    MEASURED_ON,
    BackfilledOkxValue,
    fetch_btc_daily_close,
)
from ingest.fetchers.okx_derivatives import (
    BackfilledOkxDerivativeOk,
    FundingRateOk,
    FundingRateResult,
    LongShortRatioOk,
    LongShortRatioResult,
    OpenInterestOk,
    OpenInterestResult,
    TakerRatioOk,
    TakerRatioResult,
    fetch_btc_funding_rate_history,
    fetch_long_short_ratio,
    fetch_open_interest,
    fetch_taker_ratio,
)
from ingest.fetchers.sosovalue import SosoValueEtfFlowOk, SosoValueEtfFlowResult
from ingest.indicators import atr, bollinger_bands, ema, macd, obv, rsi, stochrsi
from ingest.persist import persist_datapoint
from ingest.registry import (
    TIER_INTERVAL_SECONDS,
    CadenceTier,
    IndicatorDefinition,
    load_registry,
)
from ingest.status import Error, Ok, Reason, Result, Stale, Unavailable

type Venue = Literal["okx", "coinbase"]
type HistoryStatus = Literal["AVAILABLE", "UNCORROBORATED"]
type Bar = Mapping[str, float]
type BarFetcher = Callable[[Venue, str, int], "FetchedBars | Error"]
type FundingRateFetcher = Callable[[str], FundingRateResult]
type OpenInterestFetcher = Callable[[str], OpenInterestResult]
type LongShortRatioFetcher = Callable[[str], LongShortRatioResult]
type TakerRatioFetcher = Callable[[str], TakerRatioResult]
type MvrvFetcher = Callable[[str], Result]
type ActiveAddressesFetcher = Callable[[str], Result]
type ExchangeFlowFetcher = Callable[[str], Result]
type StakingFetcher = Callable[[str], Result]
type FredFetcher = Callable[[FredSeries], FredResult]
type EtfFlowFetcher = Callable[[str], SosoValueEtfFlowResult]
type StablecoinSupplyFetcher = Callable[[str], DefiLlamaStablecoinSupplyResult]
type FearGreedFetcher = Callable[[], AlternativeMeFearGreedResult]
type BoardResult = (
    Result
    | FundingRateOk
    | OpenInterestOk
    | LongShortRatioOk
    | TakerRatioOk
    | FredOk
    | SosoValueEtfFlowOk
    | DefiLlamaStablecoinSupplyOk
    | AlternativeMeFearGreedOk
    | BackfilledOkxValue
    | BackfilledOkxDerivativeOk
)

SOL_ACTIVE_ADDRESSES_KEY = "sol_active_addresses"
_MULTI_ASSET_RESULT_SEPARATOR = "\x1f"

_HISTORY_NOTE = re.compile(
    r"^History availability measured (?P<date>\d{4}-\d{2}-\d{2}): "
    r"okx (?P<okx_kind>at least|exactly) (?P<okx_bars>\d+) daily bars; "
    r"coinbase (?P<coinbase_kind>at least|exactly) "
    r"(?P<coinbase_bars>\d+) daily bars\.$"
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class HistoryAvailability:
    """A dated count measured for one asset at one venue."""

    asset: str
    venue: Venue
    available_bars: int
    measured_on: date
    exact: bool


@dataclass(frozen=True, slots=True)
class HistoryAssessment:
    """Whether a venue can honestly meet an asset's bar contract."""

    availability: HistoryAvailability
    required_bars: int
    status: HistoryStatus
    reason: str | None = None
    fetched_bars: int | None = None

    @property
    def surplus_bars(self) -> int:
        return self.availability.available_bars - self.required_bars


@dataclass(frozen=True, slots=True)
class FetchedBars:
    """Normalized oldest-first bars and the newest completed bucket end."""

    bars: tuple[Bar, ...]
    source_timestamp: datetime


@dataclass(frozen=True, slots=True)
class FullAssetRun:
    """Every technical cell plus each venue's explicit history assessment."""

    indicators: dict[str, BoardResult]
    history: dict[tuple[str, Venue], HistoryAssessment]


def load_history_availability() -> tuple[HistoryAvailability, ...]:
    """Read the dated per-asset venue measurements declared in the registry."""

    availability: list[HistoryAvailability] = []
    technical_assets: set[str] = set()
    for definition in load_registry().root:
        if definition.talib_function is not None:
            technical_assets.update(definition.definable_for)
        match = _HISTORY_NOTE.fullmatch(definition.note or "")
        if match is None:
            continue

        asset = definition.definable_for[0]
        measured_on = date.fromisoformat(match.group("date"))
        for venue in ("okx", "coinbase"):
            availability.append(
                HistoryAvailability(
                    asset=asset,
                    venue=venue,
                    available_bars=int(match.group(f"{venue}_bars")),
                    measured_on=measured_on,
                    exact=match.group(f"{venue}_kind") == "exactly",
                )
            )

    declared = {(item.asset, item.venue) for item in availability}
    expected = {
        (asset, venue)
        for asset in technical_assets
        for venue in ("okx", "coinbase")
    }
    if declared != expected or len(declared) != len(availability):
        missing = sorted(expected - declared)
        duplicates = len(availability) - len(declared)
        raise ValueError(
            "registry history availability must declare each asset and venue once; "
            f"missing={missing}, duplicates={duplicates}"
        )
    return tuple(sorted(availability, key=lambda item: (item.asset, item.venue)))


def assess_history(
    availability: HistoryAvailability, required_bars: int
) -> HistoryAssessment:
    """Declare a short history uncorroborated before any venue request."""

    if availability.available_bars >= required_bars:
        return HistoryAssessment(
            availability=availability,
            required_bars=required_bars,
            status="AVAILABLE",
        )

    qualifier = "measured" if availability.exact else "measured lower-bound"
    return HistoryAssessment(
        availability=availability,
        required_bars=required_bars,
        status="UNCORROBORATED",
        reason=(
            f"{availability.venue} has {availability.available_bars} {qualifier} "
            f"daily bars for {availability.asset}, fewer than the {required_bars} "
            "required"
        ),
    )


class _AssetClient:
    """Retarget the already-verified BTC fetchers to another declared pair."""

    def __init__(self, venue: Venue, asset: str) -> None:
        self.venue = venue
        self.asset = asset

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        timeout: int,
    ) -> httpx.Response:
        request_params = dict(params or {})
        if self.venue == "okx":
            request_params["instId"] = f"{self.asset}-USDT"
        else:
            url = url.replace("BTC-USD", f"{self.asset}-USD")
        return httpx.get(url, params=request_params, timeout=timeout)


class _FundingAssetClient:
    """Retarget the verified BTC funding fetcher to another swap instrument."""

    def __init__(self, asset: str) -> None:
        self.asset = asset

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        timeout: int,
    ) -> httpx.Response:
        request_params = dict(params or {})
        request_params["instId"] = f"{self.asset}-USDT-SWAP"
        return httpx.get(url, params=request_params, timeout=timeout)


def _fetch_asset_bars(
    venue: Venue, asset: str, required_bars: int
) -> FetchedBars | Error:
    client = cast(httpx.Client, _AssetClient(venue, asset))
    if venue == "okx":
        okx_result = okx.fetch_btc_daily_bars(required_bars, client=client)
        if isinstance(okx_result, Error):
            return okx_result
        newest_open = datetime.fromtimestamp(
            int(okx_result[0][0]) / 1000, tz=UTC
        )
        bars = tuple(
            {
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
            for row in reversed(okx_result)
        )
    else:
        coinbase_result = coinbase.fetch_btc_daily_bars(
            required_bars, client=client
        )
        if isinstance(coinbase_result, Error):
            return coinbase_result
        newest_open = datetime.fromtimestamp(coinbase_result[0].time, tz=UTC)
        bars = tuple(
            {
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume,
            }
            for row in reversed(coinbase_result)
        )
    return FetchedBars(bars=bars, source_timestamp=newest_open + timedelta(days=1))


def _fetch_asset_funding_rate(asset: str) -> FundingRateResult:
    client = cast(httpx.Client, _FundingAssetClient(asset))
    return fetch_btc_funding_rate_history(client=client)


def _fetch_asset_open_interest(asset: str) -> OpenInterestResult:
    return fetch_open_interest(asset)


def _fetch_asset_long_short_ratio(asset: str) -> LongShortRatioResult:
    return fetch_long_short_ratio(asset)


def _fetch_asset_taker_ratio(asset: str) -> TakerRatioResult:
    return fetch_taker_ratio(asset)


def _fetch_asset_mvrv(
    asset: str,
    rate_limiter: coinmetrics.CoinMetricsRateLimiter | None = None,
) -> Result:
    return coinmetrics.fetch_mvrv(asset, rate_limiter=rate_limiter)


def _fetch_asset_active_addresses(
    asset: str,
    rate_limiter: coinmetrics.CoinMetricsRateLimiter | None = None,
) -> Result:
    if asset == "SOL":
        return solana_rpc.fetch_sol_active_addresses()
    return coinmetrics.fetch_active_addresses(asset, rate_limiter=rate_limiter)


def _fetch_asset_exchange_flow(
    asset: str,
    rate_limiter: coinmetrics.CoinMetricsRateLimiter | None = None,
) -> Result:
    return coinmetrics.fetch_exchange_flow(asset, rate_limiter=rate_limiter)


def _fetch_asset_staking(asset: str) -> Result:
    if asset == "SOL":
        return validators_app.fetch_sol_staking()
    return Unavailable(reason=Reason.NOT_DEFINABLE)


def _fetch_fear_greed_index() -> AlternativeMeFearGreedResult:
    return alternative_me.fetch_fear_greed_index()


def _fetch_fred_series(series: FredSeries) -> FredResult:
    return fred.fetch_fred_series(series)


def _fetch_etf_net_flow(asset: str) -> SosoValueEtfFlowResult:
    return sosovalue.fetch_etf_net_flow(asset)


def _fetch_stablecoin_supply(asset: str) -> DefiLlamaStablecoinSupplyResult:
    return defillama_stablecoins.fetch_stablecoin_supply(asset)


def _series_id_from_endpoint(endpoint: str) -> str:
    values = parse_qs(urlparse(endpoint).query).get("series_id")
    if not values or not values[0].strip():
        raise ValueError(f"FRED endpoint is missing series_id: {endpoint}")
    return values[0]


def _result_key(definition: IndicatorDefinition, asset: str) -> str:
    if definition.definable_for == (asset,):
        return definition.key
    return f"{definition.key}{_MULTI_ASSET_RESULT_SEPARATOR}{asset}"


def _definition_and_asset_for_result_key(
    result_key: str,
    definitions_by_key: Mapping[str, IndicatorDefinition],
) -> tuple[IndicatorDefinition, str]:
    if result_key in definitions_by_key:
        definition = definitions_by_key[result_key]
        return definition, definition.definable_for[0]

    definition_key, separator, asset = result_key.partition(
        _MULTI_ASSET_RESULT_SEPARATOR
    )
    if not separator:
        raise KeyError(result_key)
    definition = definitions_by_key[definition_key]
    if asset not in definition.definable_for:
        raise ValueError(f"{asset} is not declared for {definition.key}")
    return definition, asset


def _calculate(definition: IndicatorDefinition, bars: Sequence[Bar]) -> float:
    parameters = definition.parameters or {}
    if definition.key == INDICATOR_KEY:
        return daily_close(bars)
    if definition.talib_function == "RSI":
        return rsi(bars, period=int(parameters["timeperiod"]))
    if definition.talib_function == "EMA":
        return ema(bars, period=int(parameters["timeperiod"]))
    if definition.talib_function == "ATR":
        return atr(bars, period=int(parameters["timeperiod"]))
    if definition.talib_function == "BBANDS":
        values = bollinger_bands(
            bars,
            period=int(parameters["timeperiod"]),
            deviations=float(parameters["nbdevup"]),
        )
        suffixes = ("upper", "middle", "lower")
        return values[
            next(
                index
                for index, suffix in enumerate(suffixes)
                if definition.key.endswith(suffix)
            )
        ]
    if definition.talib_function == "OBV":
        return obv(bars)
    if definition.talib_function == "MACD":
        return macd(
            bars,
            fast_period=int(parameters["fastperiod"]),
            slow_period=int(parameters["slowperiod"]),
            signal_period=int(parameters["signalperiod"]),
        )[0]
    if definition.talib_function == "STOCHRSI":
        return stochrsi(
            bars,
            rsi_period=int(parameters["timeperiod"]),
            stochastic_period=int(parameters["fastk_period"]),
            k_smoothing_period=int(parameters["fastd_period"]),
        )
    raise ValueError(f"{definition.key} has no registered calculation")


def run_all_assets(
    *,
    tier: CadenceTier | None = None,
    fetch_bars: BarFetcher | None = None,
    fetch_funding_rate: FundingRateFetcher | None = None,
    fetch_open_interest: OpenInterestFetcher | None = None,
    fetch_long_short_ratio: LongShortRatioFetcher | None = None,
    fetch_taker_ratio: TakerRatioFetcher | None = None,
    fetch_mvrv: MvrvFetcher | None = None,
    fetch_active_addresses: ActiveAddressesFetcher | None = None,
    fetch_exchange_flow: ExchangeFlowFetcher | None = None,
    fetch_staking: StakingFetcher | None = None,
    fetch_fred: FredFetcher | None = None,
    fetch_etf_flow: EtfFlowFetcher | None = None,
    fetch_stablecoin_supply: StablecoinSupplyFetcher | None = None,
    fetch_fear_greed: FearGreedFetcher | None = None,
    excluded_indicator_keys: Collection[str] = (),
) -> FullAssetRun:
    """Fetch both venues and compute every registered board cell."""

    excluded_keys = frozenset(excluded_indicator_keys)
    registered = tuple(
        definition
        for definition in load_registry().root
        if tier is None
        or definition.expected_update_interval_seconds == TIER_INTERVAL_SECONDS[tier]
    )
    definitions = tuple(
        definition
        for definition in registered
        if definition.key not in excluded_keys
        and (definition.talib_function is not None or definition.key == INDICATOR_KEY)
    )
    funding_definitions = tuple(
        definition
        for definition in registered
        if definition.key not in excluded_keys
        and definition.response_model == "okx_funding_rate_history"
    )
    open_interest_definitions = tuple(
        definition
        for definition in registered
        if definition.key not in excluded_keys
        and definition.response_model == "okx_open_interest"
    )
    long_short_definitions = tuple(
        definition
        for definition in registered
        if definition.key not in excluded_keys
        and definition.response_model == "okx_long_short_ratio"
    )
    taker_ratio_definitions = tuple(
        definition
        for definition in registered
        if definition.key not in excluded_keys
        and definition.response_model == "okx_taker_volume"
    )
    mvrv_definitions = tuple(
        definition
        for definition in registered
        if definition.key not in excluded_keys and definition.key.endswith("_mvrv")
    )
    active_address_definitions = tuple(
        definition
        for definition in registered
        if definition.key not in excluded_keys
        and definition.key.endswith("_active_addresses")
    )
    exchange_flow_definitions = tuple(
        definition
        for definition in registered
        if definition.key not in excluded_keys
        and definition.key.endswith("_exchange_flow")
    )
    staking_definitions = tuple(
        definition
        for definition in registered
        if definition.key not in excluded_keys and definition.key.endswith("_staking")
    )
    fred_definitions = tuple(
        definition
        for definition in registered
        if definition.key not in excluded_keys
        and definition.response_model == "fred_series_observations"
    )
    etf_flow_definitions = tuple(
        definition
        for definition in registered
        if definition.key not in excluded_keys
        and definition.response_model == "sosovalue_etf_summary_history"
    )
    stablecoin_supply_definitions = tuple(
        definition
        for definition in registered
        if definition.key not in excluded_keys
        and definition.response_model == "defillama_stablecoinchains"
    )
    fear_greed_definitions = tuple(
        definition
        for definition in registered
        if definition.key not in excluded_keys
        and definition.response_model == "alternative_me_fear_greed"
    )
    by_asset = {
        asset: tuple(
            definition
            for definition in definitions
            if definition.definable_for == (asset,)
        )
        for asset in sorted({entry.definable_for[0] for entry in definitions})
    }
    declared = {
        (item.asset, item.venue): item for item in load_history_availability()
    }
    fetch = _fetch_asset_bars if fetch_bars is None else fetch_bars
    fetch_funding = (
        _fetch_asset_funding_rate
        if fetch_funding_rate is None
        else fetch_funding_rate
    )
    fetch_interest = (
        _fetch_asset_open_interest
        if fetch_open_interest is None
        else fetch_open_interest
    )
    fetch_long_short = (
        _fetch_asset_long_short_ratio
        if fetch_long_short_ratio is None
        else fetch_long_short_ratio
    )
    fetch_taker = (
        _fetch_asset_taker_ratio if fetch_taker_ratio is None else fetch_taker_ratio
    )
    fetch_coinmetrics_mvrv: MvrvFetcher = (
        _fetch_asset_mvrv if fetch_mvrv is None else fetch_mvrv
    )
    fetch_coinmetrics_active_addresses: ActiveAddressesFetcher = (
        _fetch_asset_active_addresses
        if fetch_active_addresses is None
        else fetch_active_addresses
    )
    fetch_coinmetrics_exchange_flow: ExchangeFlowFetcher = (
        _fetch_asset_exchange_flow
        if fetch_exchange_flow is None
        else fetch_exchange_flow
    )
    fetch_validators_app_staking: StakingFetcher = (
        _fetch_asset_staking if fetch_staking is None else fetch_staking
    )
    fetch_fred_macro: FredFetcher = (
        _fetch_fred_series if fetch_fred is None else fetch_fred
    )
    fetch_sosovalue_etf_flow: EtfFlowFetcher = (
        _fetch_etf_net_flow if fetch_etf_flow is None else fetch_etf_flow
    )
    fetch_defillama_stablecoin_supply: StablecoinSupplyFetcher = (
        _fetch_stablecoin_supply
        if fetch_stablecoin_supply is None
        else fetch_stablecoin_supply
    )
    fetch_alternative_me_fear_greed: FearGreedFetcher = (
        _fetch_fear_greed_index if fetch_fear_greed is None else fetch_fear_greed
    )
    history: dict[tuple[str, Venue], HistoryAssessment] = {}
    indicators: dict[str, BoardResult] = {}

    for asset, asset_definitions in by_asset.items():
        required_bars = max(
            cast(int, definition.required_bars)
            for definition in asset_definitions
        )
        venue_bars: dict[Venue, FetchedBars | Error] = {}
        for venue in ("okx", "coinbase"):
            assessment = assess_history(declared[(asset, venue)], required_bars)
            if assessment.status == "UNCORROBORATED":
                history[(asset, venue)] = assessment
                continue

            fetched = fetch(venue, asset, required_bars)
            venue_bars[venue] = fetched
            if isinstance(fetched, Error):
                history[(asset, venue)] = replace(
                    assessment,
                    status="UNCORROBORATED",
                    reason=f"{venue} history fetch failed: {fetched.detail}",
                )
            else:
                history[(asset, venue)] = replace(
                    assessment, fetched_bars=len(fetched.bars)
                )

        primary = venue_bars.get("okx")
        if primary is None:
            for definition in asset_definitions:
                indicators[definition.key] = Unavailable(reason=Reason.NOT_FETCHED)
            continue
        if isinstance(primary, Error):
            for definition in asset_definitions:
                indicators[definition.key] = primary
            continue

        for definition in asset_definitions:
            count = cast(int, definition.required_bars)
            selected = primary.bars[-count:]
            try:
                value = compute_indicator(
                    definition,
                    selected,
                    partial(_calculate, definition),
                )
                if not math.isfinite(value):
                    raise ValueError("TA-Lib returned a non-finite value")
                indicators[definition.key] = Ok(
                    value=value,
                    source_timestamp=primary.source_timestamp,
                )
            except (IndexError, KeyError, TypeError, ValueError) as error:
                indicators[definition.key] = Error(
                    reason=Reason.FETCH_FAILED,
                    detail=f"{definition.key} computation failed: {error}",
                )

    for definition in funding_definitions:
        indicators[definition.key] = fetch_funding(definition.definable_for[0])

    for definition in open_interest_definitions:
        indicators[definition.key] = fetch_interest(definition.definable_for[0])

    for definition in long_short_definitions:
        indicators[definition.key] = fetch_long_short(definition.definable_for[0])

    for definition in taker_ratio_definitions:
        indicators[definition.key] = fetch_taker(definition.definable_for[0])

    for definition in mvrv_definitions:
        indicators[definition.key] = fetch_coinmetrics_mvrv(
            definition.definable_for[0]
        )

    for definition in active_address_definitions:
        indicators[definition.key] = fetch_coinmetrics_active_addresses(
            definition.definable_for[0]
        )

    for definition in exchange_flow_definitions:
        indicators[definition.key] = fetch_coinmetrics_exchange_flow(
            definition.definable_for[0]
        )

    for definition in staking_definitions:
        indicators[definition.key] = fetch_validators_app_staking(
            definition.definable_for[0]
        )

    for definition in fred_definitions:
        series = FredSeries(
            series_id=_series_id_from_endpoint(definition.endpoint),
            source_field=definition.source_field,
        )
        indicators[definition.key] = fetch_fred_macro(series)

    for definition in etf_flow_definitions:
        for asset in definition.definable_for:
            indicators[_result_key(definition, asset)] = fetch_sosovalue_etf_flow(asset)

    for definition in stablecoin_supply_definitions:
        for asset in definition.definable_for:
            indicators[_result_key(definition, asset)] = (
                fetch_defillama_stablecoin_supply(asset)
            )

    for definition in fear_greed_definitions:
        indicators[definition.key] = fetch_alternative_me_fear_greed()

    return FullAssetRun(indicators=indicators, history=history)


def run_scheduled_board(*, tier: CadenceTier | None = None) -> FullAssetRun:
    """Fetch the scheduled board, leaving SOL active addresses to its slow job."""

    return run_all_assets(
        tier=tier,
        excluded_indicator_keys=(SOL_ACTIVE_ADDRESSES_KEY,),
    )


def run_sol_active_addresses() -> FullAssetRun:
    """Fetch only SOL active addresses for the separate long-running schedule."""

    return FullAssetRun(
        indicators={
            SOL_ACTIVE_ADDRESSES_KEY: _fetch_asset_active_addresses("SOL"),
        },
        history={},
    )


def persist_board(
    connection: psycopg.Connection[tuple[object, ...]],
    run: FullAssetRun,
    *,
    origin: str = "live",
) -> tuple[int, ...]:
    """Persist one visible datapoint for every result in a full board run."""

    definitions_by_key = {
        definition.key: definition for definition in load_registry().root
    }
    row_ids: list[int] = []
    for result_key, result in run.indicators.items():
        definition, asset = _definition_and_asset_for_result_key(
            result_key, definitions_by_key
        )
        persisted_definition = definition
        persisted_result: Result
        if isinstance(result, (Ok, Stale, Unavailable, Error)):
            persisted_result = result
        else:
            source_field = getattr(result, "source_field", None)
            endpoint = getattr(result, "endpoint", None)
            updates: dict[str, str] = {}
            if source_field is not None:
                updates["source_field"] = source_field
            if endpoint is not None:
                updates["endpoint"] = endpoint
            if updates:
                persisted_definition = definition.model_copy(update=updates)
            persisted_result = Ok(float(result.value), result.source_timestamp)
        if (
            isinstance(persisted_result, Ok)
            and (_utc_now() - persisted_result.source_timestamp).total_seconds()
            > definition.freshness_warn_seconds
        ):
            persisted_result = Stale(
                persisted_result.value,
                persisted_result.source_timestamp,
            )

        reference_period = getattr(result, "reference_period", None)
        published_at = getattr(result, "published_at", None)
        origin_kwargs = {} if origin == "live" else {"origin": origin}
        row_ids.append(
            persist_datapoint(
                connection,
                definition=persisted_definition,
                asset=asset,
                measured_on=asset,
                result=persisted_result,
                reference_period=(
                    reference_period if isinstance(reference_period, str) else None
                ),
                published_at=(
                    published_at if isinstance(published_at, datetime) else None
                ),
                **origin_kwargs,
            ),
        )
    return tuple(row_ids)


def run_pipeline(
    connection: psycopg.Connection[tuple[object, ...]],
    fetcher: Callable[[], Result | FullAssetRun] | None = fetch_btc_daily_close,
) -> int | tuple[int, ...]:
    """Persist either the computed board or the legacy single close result."""

    result = Unavailable(reason=Reason.NOT_FETCHED) if fetcher is None else fetcher()
    if isinstance(result, FullAssetRun):
        return persist_board(connection, result)

    definition = next(
        entry for entry in load_registry().root if entry.key == INDICATOR_KEY
    )
    return persist_datapoint(
        connection,
        definition=definition,
        asset=definition.definable_for[0],
        measured_on=MEASURED_ON,
        result=result,
    )
