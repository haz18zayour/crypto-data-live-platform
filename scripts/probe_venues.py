from __future__ import annotations

import argparse
import json
import os
import platform
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


BODY_PREFIX_BYTES = 200
REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = "crypto-data-live-platform-reachability-spike/1.0"

VENUES = (
    {
        "venue": "okx",
        "url": "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D&limit=1",
    },
    {
        "venue": "coinbase",
        "url": "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400",
    },
    {
        "venue": "kraken",
        "url": "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=1440",
    },
    {
        "venue": "binance_spot",
        "url": "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1",
    },
    {
        "venue": "binance_futures",
        "url": "https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1",
    },
    {
        "venue": "bybit",
        "url": "https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT",
    },
    {
        "venue": "coinmetrics",
        "url": "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=CapMVRVCur",
    },
    {
        "venue": "alternative_me",
        "url": "https://api.alternative.me/fng/?limit=1",
    },
)

EGRESS_URL = "https://ipinfo.io/json"
UrlOpener = Callable[[urllib.request.Request, int], Any]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request_for(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "Accept": "*/*",
            "User-Agent": USER_AGENT,
        },
    )


def decode_body_prefix(body: bytes) -> str:
    return body[:BODY_PREFIX_BYTES].decode("utf-8", errors="replace")


def read_response_prefix(response: Any) -> str:
    try:
        return decode_body_prefix(response.read(BODY_PREFIX_BYTES))
    finally:
        close = getattr(response, "close", None)
        if close is not None:
            close()


def probe_venue(
    venue: str,
    url: str,
    opener: UrlOpener = urllib.request.urlopen,
) -> dict[str, Any]:
    started = time.monotonic()
    row: dict[str, Any] = {
        "venue": venue,
        "url": url,
        "status": None,
        "latency_ms": None,
        "body_prefix": "",
        "error": None,
    }

    try:
        response = opener(request_for(url), REQUEST_TIMEOUT_SECONDS)
        row["status"] = getattr(response, "status", response.getcode())
        row["body_prefix"] = read_response_prefix(response)
    except urllib.error.HTTPError as exc:
        row["status"] = exc.code
        row["body_prefix"] = read_response_prefix(exc)
    except Exception as exc:
        row["error"] = f"{exc.__class__.__name__}: {exc}"
    finally:
        row["latency_ms"] = round((time.monotonic() - started) * 1000)

    return row


def probe_all(
    venues: Iterable[dict[str, str]] = VENUES,
    opener: UrlOpener = urllib.request.urlopen,
) -> list[dict[str, Any]]:
    return [probe_venue(row["venue"], row["url"], opener=opener) for row in venues]


def runner_metadata() -> dict[str, Any]:
    return {
        "github_actions": os.getenv("GITHUB_ACTIONS") == "true",
        "github_run_id": os.getenv("GITHUB_RUN_ID"),
        "github_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        "runner_name": os.getenv("RUNNER_NAME"),
        "runner_os": os.getenv("RUNNER_OS"),
        "runner_arch": os.getenv("RUNNER_ARCH"),
        "python": platform.python_version(),
    }


def probe_egress(opener: UrlOpener = urllib.request.urlopen) -> dict[str, Any]:
    result: dict[str, Any] = {
        "url": EGRESS_URL,
        "status": None,
        "ip": None,
        "city": None,
        "region": None,
        "country": None,
        "org": None,
        "error": None,
    }

    try:
        response = opener(request_for(EGRESS_URL), REQUEST_TIMEOUT_SECONDS)
        result["status"] = getattr(response, "status", response.getcode())
        body = read_response_prefix(response)
        payload = json.loads(body)
        for field in ("ip", "city", "region", "country", "org"):
            result[field] = payload.get(field)
    except urllib.error.HTTPError as exc:
        result["status"] = exc.code
        result["error"] = f"HTTPError: {exc.reason}"
        read_response_prefix(exc)
    except Exception as exc:
        result["error"] = f"{exc.__class__.__name__}: {exc}"

    return result


def build_report(opener: UrlOpener = urllib.request.urlopen) -> dict[str, Any]:
    return {
        "generated_at": now_utc(),
        "timeout_seconds": REQUEST_TIMEOUT_SECONDS,
        "body_prefix_bytes": BODY_PREFIX_BYTES,
        "runner": runner_metadata(),
        "egress": probe_egress(opener=opener),
        "results": probe_all(opener=opener),
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe public venue reachability.")
    parser.add_argument("--out", required=True, help="Path to write the JSON report.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    write_report(Path(args.out), build_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
