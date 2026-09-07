---
id: US-001
title: Reachability spike — measure venue access from the actual runner
priority: 1
touches:
  - scripts/probe_venues.py
  - .github/workflows/reachability-spike.yml
  - prds/PRD-001-spine/50-evidence/US-001/**
context:
  - AGENTS.md
  - prds/PRD-001-spine/10-research.md
  - project-documents/research/R7-cross-track-synthesis.md
---

As the owner, I want a recorded table of HTTP statuses per venue, observed from the compute
that will actually run ingestion, so that the compute location is decided by measurement
rather than by assumption.

This is the first story in the project because every later PRD assumes an answer. The prior
system's worst outage — 24 hours of silent data loss — traces directly to this fact going
unmeasured: Binance returns HTTP 451 to US IPs, which forced a self-hosted runner, which was
a supervised process, which exited 0 and stopped without telling anyone.

**A 451 is a finding, not a failure.** The story succeeds either way; what must not happen is
proceeding without knowing.

## Acceptance criteria

- [cmd: python scripts/probe_venues.py --out prds/PRD-001-spine/50-evidence/US-001/reachability.json] The probe runs and writes its result file
- [test: probe records an http status for every configured venue] Every venue in the list appears in the output, including ones that errored — a venue must never be silently omitted
- [test: probe records a transport failure as a result rather than raising] A DNS or timeout failure produces a row with a null status and an error string, so an unreachable venue is distinguishable from an unattempted one
- [ci: reachability-spike] The probe workflow is green on the pushed commit, proving it executed on a GitHub-hosted runner rather than on the owner's machine
- [cmd: python -c "import json,sys; d=json.load(open('prds/PRD-001-spine/50-evidence/US-001/reachability.json')); ks=set(r.get('venue') for r in d.get('results')); need={'okx','coinbase','kraken','binance_spot','binance_futures','bybit','coinmetrics','alternative_me'}; sys.exit(0 if need<=ks else 1)"] The evidence file covers all eight required venues
- [cmd: python -c "import json,sys; d=json.load(open('prds/PRD-001-spine/50-evidence/US-001/reachability.json')); n=sum(1 for r in d.get('results') if isinstance(r.get('http_status'), int)); print('venues with a real HTTP status:', n); sys.exit(0 if n>=6 else 1)"] At least six venues returned an actual HTTP status code — a run in which every venue errored is a broken probe, not a reachability finding

## Notes for the implementer

Probe exactly these, one unauthenticated GET each, recording venue name, URL, HTTP status,
latency in ms, and the first 200 bytes of the body:

| venue | URL |
|---|---|
| `okx` | `https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D&limit=1` |
| `coinbase` | `https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400` |
| `kraken` | `https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=1440` |
| `binance_spot` | `https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1` |
| `binance_futures` | `https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1` |
| `bybit` | `https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT` |
| `coinmetrics` | `https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=CapMVRVCur` |
| `alternative_me` | `https://api.alternative.me/fng/?limit=1` |

- The workflow must run on `ubuntu-latest` (GitHub-hosted). Running it on anything else
  defeats the purpose of the story.
- Set a short per-request timeout (10s) and **never** let one venue's failure abort the run —
  a partial table is the failure mode this whole project exists to prevent.
- Record the runner's public egress region if obtainable, since that is what the result is
  actually about.
- Do **not** add retries. A retry masks an intermittent block, and the question here is
  categorical, not statistical.
- **`urllib.request.urlopen`'s second positional parameter is `data`, not `timeout`.** Calling
  `urlopen(request, 10)` raises `TypeError: message_body should be a bytes-like object`, which
  a broad `except` will happily record as the "result" for every venue — producing a complete,
  well-formed report in which nothing was ever measured. Pass `timeout=` by keyword.
- Catch network errors narrowly. A bare `except Exception` around the request turns a
  programming error into a data point, which is the failure mode this whole product exists to
  prevent.
- The diff must not include any fetcher, schema or application code. This story produces a
  script, a workflow and an evidence file — nothing else.
