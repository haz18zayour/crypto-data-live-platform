"""Validate every registered live endpoint without collecting datapoints."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError

from ingest.heartbeat import _ping
from ingest.registry import IndicatorDefinition, load_registry
from ingest.schemas import (
    CoinMetricsAssetMetricsResponse,
    OkxCandleResponse,
    OkxFundingRateHistoryResponse,
    OkxLongShortRatioResponse,
    OkxOpenInterestResponse,
    OkxTakerVolumeResponse,
)

REQUEST_TIMEOUT_SECONDS = 10
RESPONSE_MODEL_TYPES: dict[str, type[BaseModel]] = {
    "okx_candle": OkxCandleResponse,
    "okx_funding_rate_history": OkxFundingRateHistoryResponse,
    "okx_open_interest": OkxOpenInterestResponse,
    "okx_long_short_ratio": OkxLongShortRatioResponse,
    "okx_taker_volume": OkxTakerVolumeResponse,
    "coinmetrics_asset_metrics": CoinMetricsAssetMetricsResponse,
}
RESPONSE_MODELS: dict[str, type[BaseModel]] = {
    definition.key: RESPONSE_MODEL_TYPES[definition.response_model]
    for definition in load_registry().root
    if definition.response_model in RESPONSE_MODEL_TYPES
}


@dataclass(frozen=True)
class CanaryResult:
    """The shape-check outcome for one registered vendor endpoint."""

    vendor: str
    endpoint: str
    status: Literal["OK", "ERROR"]
    detail: str | None


class CanaryFailure(RuntimeError):
    """Raised after all endpoints have run when any contract check failed."""

    def __init__(self, results: tuple[CanaryResult, ...]) -> None:
        self.results = results
        failures = [result.detail for result in results if result.status == "ERROR"]
        super().__init__("; ".join(detail for detail in failures if detail))


def _validation_detail(vendor: str, error: ValidationError) -> str:
    first_error = error.errors()[0]
    field = ".".join(str(part) for part in first_error["loc"]) or "response"
    return f"{vendor} field {field}: {first_error['msg']}"


def _check_endpoint(
    definition: IndicatorDefinition,
    client: httpx.Client,
) -> CanaryResult:
    model = RESPONSE_MODELS.get(definition.key)
    if model is None:
        return CanaryResult(
            vendor=definition.vendor,
            endpoint=definition.endpoint,
            status="ERROR",
            detail=(
                f"{definition.vendor} field model: no response model registered"
            ),
        )

    try:
        response = client.get(
            definition.endpoint,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        model.model_validate(payload)
    except ValidationError as error:
        detail = _validation_detail(definition.vendor, error)
    except ValueError as error:
        detail = f"{definition.vendor} field response: invalid JSON: {error}"
    except httpx.HTTPError as error:
        detail = f"{definition.vendor} request failed: {error}"
    else:
        return CanaryResult(
            vendor=definition.vendor,
            endpoint=definition.endpoint,
            status="OK",
            detail=None,
        )

    return CanaryResult(
        vendor=definition.vendor,
        endpoint=definition.endpoint,
        status="ERROR",
        detail=detail,
    )


def run_canary(
    heartbeat_url: str,
    *,
    client: httpx.Client | None = None,
    heartbeat_client: httpx.Client | None = None,
) -> tuple[CanaryResult, ...]:
    """Check all registry endpoints, signal health, and never write datapoints."""

    if client is None:
        with httpx.Client() as live_client:
            return run_canary(
                heartbeat_url,
                client=live_client,
                heartbeat_client=heartbeat_client,
            )

    try:
        results = tuple(
            _check_endpoint(definition, client)
            for definition in load_registry().root
        )
    except Exception:
        _ping(heartbeat_url, failed=True, client=heartbeat_client)
        raise

    failed = any(result.status == "ERROR" for result in results)
    _ping(heartbeat_url, failed=failed, client=heartbeat_client)
    if failed:
        raise CanaryFailure(results)
    return results


def format_report(results: tuple[CanaryResult, ...]) -> str:
    """Render stable per-vendor status output for the scheduled job log."""

    return json.dumps([asdict(result) for result in results], sort_keys=True)


def main() -> int:
    """Run the live canary using its dedicated dead-man's-switch."""

    try:
        results = run_canary(os.environ["HEALTHCHECK_URL_CONTRACT_CANARY"])
        exit_code = 0
    except CanaryFailure as error:
        results = error.results
        exit_code = 1

    print(format_report(results))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
