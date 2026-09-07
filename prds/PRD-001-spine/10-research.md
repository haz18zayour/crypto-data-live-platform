# PRD-001 · Research — Spine

**Date:** 2026-09-07.
**How this was produced:** `uf research PRD-001-spine` was attempted and **failed on an
account rate limit** — the subprocess wrote only `You've hit your session limit`, which `uf`
correctly rejected as 0 citations. This file was then authored by hand, as the framework
permits ("re-run, or write it yourself with real sources"), from:

- the eight product-level research tracks in `project-documents/research/R0`–`R7` (~90 cited
  sources), and
- **direct live measurement of every endpoint named below**, performed in this session on
  2026-09-07. Every URL in §7 was actually fetched; nothing here is recalled.

---

## 1. The question this PRD exists to settle

Which venue endpoints are reachable **from the compute that will actually run ingestion**, and
can a single value travel the full path — fetch → status → provenance → Postgres → deployed
page → visible freshness → alert-on-silence — without any step being able to lie?

Everything else in the roadmap assumes an answer to the first half. `R7 §C1` documents why:
the prior system's 24-hour silent outage traces back through
`Binance → HTTP 451 from US IPs → self-hosted runner → a supervised process → it exited 0`.
The prior repo says so in its own workflow file:
`# runs-on self-hosted because Binance is unreachable from GitHub-hosted runners;`

**This cannot be answered from here.** All measurement below ran from Lebanon, where Binance
responds normally. Reachability from a US IP is not testable from a non-US IP. It must be
measured **on the runner**, and that is the first story.

---

## 2. Measured findings — spot OHLCV venues

All fetched live, 2026-09-07.

| Venue | Endpoint | Closed-candle flag? | Notes |
|---|---|---|---|
| **OKX** | `/api/v5/market/candles` | **YES — `confirm`, last field** | The decisive advantage |
| Coinbase Exchange | `/products/BTC-USD/candles` | no | Returns the forming bucket with no marker |
| Kraken | `/0/public/OHLC` | no | Returned ~720 daily candles (from 2024-09-17); depth is limited |

### 2.1 The unclosed-candle trap, demonstrated

OKX `BTC-USDT`, `bar=1D`, newest first — the final element of each row is `confirm`:

```
["1788796800000","78833.9","79036.7","78808.9","79021.2", … ,"0"]   <- STILL FORMING
["1788710400000","79717.9","80555.4","78682"  ,"78834.1", … ,"1"]   <- closed
["1788624000000","79800.5","80197.6","79199"  ,"79718"  , … ,"1"]   <- closed
```

`confirm = "0"` means the candle is incomplete; `"1"` means final. **R3 flagged the exact
0/1 semantics as UNVERIFIED because the docs page is JS-rendered — this measurement resolves
it.** The newest daily candle is genuinely partial, and every indicator computed over it is
wrong in a way that silently repairs itself by the next day, which is the hardest kind of bug
to notice.

Coinbase and Kraken return the same forming bucket with **no flag at all**. Filtering it out
there requires computing the expected close time and comparing against a trusted clock —
inference, where OKX gives fact.

**Recommendation: OKX is the primary spot source for the spine**, with `confirm = "1"` as a
hard filter, and Coinbase retained as the cross-check venue. This is a data-integrity choice,
not a preference — and it independently removes Binance from the critical path, dissolving
the 451 chain in §1.

### 2.2 The funding-rate field trap, re-verified

| Endpoint | Value | What it is |
|---|---|---|
| `fapi/v1/premiumIndex` → `lastFundingRate` | `0.00002925` | still moving; for a **future** settlement |
| `fapi/v1/fundingRate` (last settled) | `0.00003113` | what was actually charged |

The prior system used the first (`binance_futures.py:12,42`). See `R0 §1b / F11`. Not needed
for PRD-001, but the registry schema this PRD defines **must** be able to record *which field*
of *which endpoint* produced a value, or F11 becomes unpreventable rather than merely undone.

### 2.3 Coin Metrics free tier — measured per asset

Probed one metric at a time; three distinct outcomes, which must stay distinguishable
(`R7 §C4`):

| | BTC | ETH | BNB | SOL |
|---|---|---|---|---|
| `CapMVRVCur` | FREE | FREE | FREE | **no such metric** |
| `AdrActCnt`, `SplyCur`, `TxCnt`, `PriceUSD` | FREE | FREE | FREE | PAID |
| `FlowInExNtv` / `FlowOutExNtv` | FREE | FREE | no such metric | no such metric |
| `CapRealUSD` | PAID | PAID | PAID | no such metric |

Live sample: BTC `CapMVRVCur` = `1.510496…` (2026-09-06), ETH = `1.116905…`.
SOL returns `"All requested metrics aren't supported for asset 'sol'"`.

Not consumed by PRD-001 — but it is the evidence that `UNAVAILABLE` needs a **reason**, not
just a null.

---

## 3. Design inputs carried in from R5 (data-integrity track)

### 3.1 Status must be structural, not a convention

```sql
CREATE TYPE datapoint_status AS ENUM ('OK','STALE','UNAVAILABLE','ERROR');
```

with a discriminated union in both languages so **no code path yields a bare number**:
`Ok(value, source_timestamp) | Stale(value, source_timestamp) | Unavailable(reason) | Error(reason)`.
In TypeScript an exhaustive `switch` with a `never` fallthrough makes an unhandled status a
compile error. A fetcher that never runs cannot produce `Ok` — its absence is a missing row,
never a `0.0`. This is the direct structural fix for `R0/F1`.

### 3.2 The one line that prevents the worst historical failure

```sql
CONSTRAINT asset_match CHECK (status <> 'OK' OR measured_on = asset)
```

Displaying BTC's number as SOL's becomes a **database error**. The prior system's *"not
degraded data, wrong data"* becomes structurally impossible rather than a discipline problem.

### 3.3 Freshness is two numbers, and frozen is a third check

`expected_update_interval` (how often the source publishes) is **not**
`freshness_budget_seconds` (how stale is tolerable). A daily-close indicator: interval 24h,
warn ~30h, hard `STALE` at 48h — survives one missed cycle, catches two.

Separately: a source can be *fresh* (`fetched_at` seconds ago) while **frozen** — returning an
identical payload forever. That is a distinct check comparing against the last N stored
values, and it is deliberately deferred to PRD-009; PRD-001 only needs the columns that make
it possible later.

### 3.4 Silence must be detected by something that is not the pipeline

Healthchecks.io free tier (20 checks). The job pings on success; the *absence* of a ping
raises the alarm. `R0/F8`: the prior runner exited 0 and stopped — a system that reports its
own failures cannot report that it is no longer running. ~30 minutes of work, and the highest
value-per-effort item in the entire research corpus.

---

## 4. Which single indicator should the spine carry?

Criteria: exercises provenance, has an unambiguous source timestamp, has a real staleness
budget, and demonstrates a genuine trap on day one.

**Recommendation: BTC daily close from OKX, `confirm = "1"` only.**

- `source_timestamp` = the candle's close time — unambiguous and checkable.
- `freshness_budget` = 26h warn / 48h stale — a real budget, not a placeholder.
- `measured_on` = `BTC` = `asset`, so the CHECK constraint is exercised in the happy path.
- It demonstrates the unclosed-candle trap immediately, and it is the foundation PRD-003
  builds every technical indicator on.

Rejected alternatives: **Fear & Greed** (fetched live, currently `71` / "Greed", updates
daily) — trivially easy but has no per-asset dimension, so it never exercises `measured_on`.
**Coin Metrics MVRV** — excellent provenance story, but daily-close-only and would make
PRD-001 depend on a second vendor before the path is proven once.

---

## 5. Reachability spike — exact shape

Runs **on the target runner**, not locally. For each row: one unauthenticated GET, record HTTP
status, latency, and the first 200 bytes of the body. Committed as evidence.

| Venue | Endpoint to probe |
|---|---|
| OKX | `/api/v5/market/candles?instId=BTC-USDT&bar=1D&limit=1` |
| Coinbase Exchange | `/products/BTC-USD/candles?granularity=86400` |
| Kraken | `/0/public/OHLC?pair=XBTUSD&interval=1440` |
| Binance spot | `/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1` |
| Binance futures | `/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1` |
| Bybit | `/v5/market/tickers?category=linear&symbol=BTCUSDT` |
| Coin Metrics | `/v4/timeseries/asset-metrics?assets=btc&metrics=CapMVRVCur` |
| alternative.me | `/fng/?limit=1` |

**A `451` on any row is a finding, not a failure.** The output is a committed table that
decides the compute row in `10_Technical_Architecture.md`. If OKX, Coinbase, Kraken and Coin
Metrics all return 200, GitHub-hosted runners are sufficient and no long-lived process is ever
needed — the outcome the whole architecture is shaped to reach.

---

## 6. What is still genuinely unknown

- **Reachability from a US runner.** Untestable from here. This is the spike.
- **Whether OKX/Bybit geo-block unauthenticated public market data by IP**, as distinct from
  restricting US *accounts* — routinely conflated, and the distinction decides PRD-004.
- **SOL on-chain buy-vs-build.** Research was launched and died on the same rate limit; it is
  a PRD-005 input and blocks nothing here.
- Cloudflare Access's exact free-tier user cap was reported as 50 by R6 but its official page
  did not render to the fetcher. **UNVERIFIED** — confirm in a browser before relying on it.
  It does not block this PRD; one user is far under any plausible cap.

---

## 7. Sources

Every URL below was fetched live in this session on 2026-09-07.

| Source | What it established |
|---|---|
| https://www.okx.com/api/v5/market/candles | The `confirm` flag exists and the newest daily candle returns `0` (forming) while older ones return `1` — resolves R3's UNVERIFIED note by measurement |
| https://api.exchange.coinbase.com/products/BTC-USD/candles | Returns daily candles with **no** closed-candle marker; forming bucket is indistinguishable |
| https://api.kraken.com/0/public/OHLC | Returns ~720 daily candles (from 2024-09-17); no closed-candle marker; limited history depth |
| https://fapi.binance.com/fapi/v1/premiumIndex | `lastFundingRate` = `0.00002925`, a moving pre-settlement estimate with `nextFundingTime` in the future |
| https://fapi.binance.com/fapi/v1/fundingRate | Last **settled** rate = `0.00003113` — a different number, confirming F11 |
| https://community-api.coinmetrics.io/v4/timeseries/asset-metrics | Per-asset free-tier matrix; BTC MVRV `1.5105`, ETH `1.1169`; SOL unsupported; realized cap paid everywhere |
| https://api.alternative.me/fng/ | Fear & Greed live (`71`, "Greed") with a `time_until_update` field — usable, but has no per-asset dimension |

Plus, in this repository: `project-documents/research/R0`–`R7`, which carry ~90 further
citations across the derivatives, on-chain, OHLCV/computation, macro/sentiment,
data-integrity and stack tracks.
