import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from ingest.fetchers.defillama_stablecoins import (
    DEFILLAMA_STABLECOINCHAINS_ENDPOINT,
    DefiLlamaStablecoinSupplyOk,
    fetch_stablecoin_supply,
)
from ingest.schemas import DefiLlamaStablecoinChainsResponse
from ingest.status import Error, Reason

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "defillama_stablecoinchains.json"


def stablecoinchains_payload() -> list[dict[str, object]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("asset", "chain", "expected"),
    (
        ("ETH", "Ethereum", Decimal("146938000000.25")),
        ("SOL", "Solana", Decimal("16511000000.0")),
        ("BNB", "BSC", Decimal("13316000000.0")),
    ),
)
def test_eth_sol_and_bsc_return_real_pegged_usd_chain_values(
    asset: str,
    chain: str,
    expected: Decimal,
) -> None:
    requests: list[httpx.Request] = []
    fetched_at = datetime(2026, 9, 28, 8, 30, tzinfo=UTC)

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=stablecoinchains_payload(),
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_stablecoin_supply(asset, client=client, now=fetched_at)

    assert isinstance(result, DefiLlamaStablecoinSupplyOk)
    assert result.value == expected
    assert not isinstance(result.value, float)
    assert result.chain == chain
    assert result.reference_period == "current"
    assert result.source_timestamp == fetched_at
    assert result.published_at == fetched_at
    assert result.source_field.endswith("(USD-pegged only)")
    assert str(requests[0].url) == DEFILLAMA_STABLECOINCHAINS_ENDPOINT


def test_btc_returns_not_definable_with_defillama_chain_list_reason() -> None:
    result = fetch_stablecoin_supply("BTC")

    assert isinstance(result, Error)
    assert result.reason is Reason.NOT_DEFINABLE
    assert "DefiLlama" in result.detail
    assert "/stablecoinchains" in result.detail
    assert "no Bitcoin entry" in result.detail
    assert "SoSoValue" not in result.detail
    assert "BNB" not in result.detail


def test_fetcher_never_calls_defillama_per_asset_stablecoin_endpoint() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return httpx.Response(
            200,
            json=stablecoinchains_payload(),
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_stablecoin_supply("ETH", client=client)

    assert isinstance(result, DefiLlamaStablecoinSupplyOk)
    assert requested_paths == ["/stablecoinchains"]
    assert not any(path.startswith("/stablecoin/") for path in requested_paths)


def test_response_model_rejects_added_renamed_or_retyped_fields() -> None:
    payload = stablecoinchains_payload()
    payload[0]["unexpected"] = "vendor reshape"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        DefiLlamaStablecoinChainsResponse.model_validate(payload)

    renamed = stablecoinchains_payload()
    renamed[0]["totalCirculating"] = renamed[0].pop("totalCirculatingUSD")
    with pytest.raises(ValidationError, match="totalCirculatingUSD"):
        DefiLlamaStablecoinChainsResponse.model_validate(renamed)

    retyped = stablecoinchains_payload()
    total = retyped[0]["totalCirculatingUSD"]
    assert isinstance(total, dict)
    total["peggedUSD"] = "146938000000.25"
    with pytest.raises(ValidationError):
        DefiLlamaStablecoinChainsResponse.model_validate(retyped)


def test_malformed_response_becomes_fetch_failed_error() -> None:
    payload = stablecoinchains_payload()
    payload[0]["unexpected"] = "vendor reshape"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_stablecoin_supply("SOL", client=client)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "unexpected" in result.detail


@pytest.mark.integration
def test_live_defillama_request_returns_real_stablecoin_supply_for_one_chain() -> None:
    result = fetch_stablecoin_supply("ETH")

    assert isinstance(result, DefiLlamaStablecoinSupplyOk), result
    assert result.chain == "Ethereum"
    assert result.value > 0
    assert result.reference_period == "current"
    assert result.source_timestamp.tzinfo is not None
    assert result.source_timestamp <= datetime.now(UTC)
