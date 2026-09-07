# R0 · Lessons from `crypto-investing-signals`

**Source:** local audit of `C:\Users\zayou\OneDrive\Desktop\Projects\crypto-investing-signals`
(96 PRDs, 223 Python files, 1,244 passing tests, live ~9 months, last commit 2026-09-04).
**Method:** direct reading of the repo's own measured post-mortems — `REMEDIATION_PLAN.md`,
`VALIDATION_2026-09-03.md`, `COUNCIL_VERDICT_2026-09-03.md`,
`research-prd-097-fail-closed-2026-09-04.md`, `indicators-and-data-sources.md`, `README.md`,
`SESSION_HANDOFF.md`.
**Date:** 2026-09-07

This is the highest-value research input available, because it is not literature — it is
**measured failure on this owner's own data**. Every claim below is quoted from that repo.

---

## 1. The failures, and what each one teaches

| # | Failure | Measured evidence | Design consequence for THIS product |
|---|---|---|---|
| F1 | **A fetcher was never called** | `funding_rate`, `oi`, `ls_ratio` scored a confident `0.0` for months — `get_all_futures_data()` was not called before `run_signal_pipeline()` | "Never fetched" and "fetched, value is zero" must be **different states in the type system**, not the same float |
| F2 | **Wrong asset's data presented as native** | BTC on-chain applied to 8 coins. Repo's own words: *"not degraded data, wrong data"* | Every datapoint stores the **asset it was actually measured on**. If it differs from the asset displayed, it renders `UNAVAILABLE` — never a proxy |
| F3 | **Duplicate indicators counted as independent** | `nupl = 1 - 1/mvrv` (corr **0.92** with MVRV); `whale` derived from exchange flow; F&G counted twice as `fear_greed` + `fg_zscore` (corr **0.72**). Verdict: *"one variable voting four times across three categories"* | Maintain an explicit **derivation graph**. Any indicator computed from another on the page is labelled derived, not independent |
| F4 | **An inverted indicator ran for 1,394 days** | `spx_correlation` bearish readings preceded **+0.789%** next-day BTC vs a **+0.091%** base rate | Show the **raw value and its distribution**, not a score. Direction claims require measurement, and this product makes none |
| F5 | **Indicator values depended on process uptime** | ATR modifier, BB squeeze quantile and OBV normaliser were computed over whatever `ohlcv_cache` held, growing forever from a 500-bar seed. *"Same market, different score."* | Computation must be **deterministic and reproducible**: fixed window, fixed lookback, recomputable from stored bars. This is a testable property |
| F6 | **Stale-but-valid data produced confident output** | No freshness guard on `as_of_close`; cached OHLCV loaded without checking `expires_at`. *"Stale-but-structurally-valid OHLCV produces a confident HOLD"* | **Freshness is part of the value.** A value without a verified timestamp is not displayable |
| F7 | **The integrity check itself was decorative** | `_assess_data_quality` validated **exactly two rows** (`funding_rate/BTC`, `btc_mvrv/BTC`). Self-audit "passes with zero directional signals". Runs reported `clean` while indicators were silently zero | Integrity coverage must be **derived from the indicator registry**, so a new indicator is auto-covered and cannot be forgotten |
| F8 | **The scheduled job stopped silently** | Fly.io self-hosted GitHub runner exited 0 on self-update; the machine stopped. Cost 24h of signals before anyone noticed | **Dead-man's-switch.** Absence of a run must itself raise an alarm — a run cannot be trusted to report its own death |
| F9 | **Sources chosen by availability, not validity** | Reddit to 4chan /biz/; LunarCrush to Google Trends; CryptoPanic to CryptoCompare. Repo records validity as **"unvalidated"** | A source must earn its place. "It was the one that still worked" is not a reason to display a number |
| F10 | **Background process starved the scheduled jobs** | A WebSocket listener on `shared-cpu-1x` Fly pushed job time from under 4 min to 6+ min. Fully built, then **reverted** (PRD-061) | Do not add an always-on listener beside scheduled work on one small box. Argue for polling unless streaming is proven necessary |

---

## 1b. F11 — a defect found during THIS research, not present in any post-mortem

**The prior system read the wrong funding-rate field, and no audit caught it.**

`signal-engine/signal_engine/fetchers/binance_futures.py:12,42`:

```python
_PREMIUM_INDEX_URL = f"{_FAPI_BASE}/fapi/v1/premiumIndex"
...
fapi_pair_to_coin[r["symbol"]]: float(r["lastFundingRate"])
```

`premiumIndex.lastFundingRate` is a **continuously-moving pre-settlement value** for the
*upcoming* funding window — not the rate that was actually charged. The settled series lives
at `/fapi/v1/fundingRate`. Measured live, 2026-09-07, BTCUSDT:

| Endpoint | Value | Meaning |
|---|---|---|
| `premiumIndex.lastFundingRate` | `0.00002925` | moving estimate for `nextFundingTime` (future) |
| `fundingRate` (last settled) | `0.00003113` | what was actually charged at the last settlement |

A **6.4% relative difference at a single instant**, on a value that keeps drifting until
settlement. Every historical funding reading in the prior system is therefore a snapshot of
an unsettled estimate taken at whatever moment the scheduler happened to fire — which also
means **it is not reproducible**: re-running the pipeline five minutes later yields a
different "historical" value for the same window. This compounds F5 (uptime-dependent values).

Note what this means about the audits: the prior system's own analysis concluded that funding
*"receives rich data"* and blamed the scoring bands. It was reading a real, richly-varying
number — just not the one it claimed to be reading. **No integrity check that verifies only
"is the value present and in range" can ever catch this class of bug.**

**Requirement generated:** every indicator's registry entry names its exact endpoint and the
exact field within the response, and a contract test asserts the semantic — for funding,
that `source_timestamp` is a *past settlement* time, never a future one. Any indicator whose
`source_timestamp` lies in the future is a build/runtime error, not a value.

## 1c. F12 — one indicator, two different underlying indices

`indicators-and-data-sources.md` records the macro DXY indicator as:

> DXY — 10-day trend | FRED API (`DTWEXBGS`) — **falls back to yfinance (`DX-Y.NYB`)** if FRED fails

These are **not the same index**:

- `DTWEXBGS` — Fed *Broad* Trade Weighted US Dollar Index, ~26 currencies, goods-and-services
  weighted, **published weekly with a release lag**.
- `DX-Y.NYB` — ICE US Dollar Index, **6 currencies** (EUR ~57.6%, JPY, GBP, CAD, SEK, CHF),
  **real-time intraday**.

Different constituents, different weights, different scale, different update cadence. The
value therefore **jumped discontinuously whenever the fallback engaged**, and a "10-day trend"
computed across a switchover mixed two incompatible series. Neither the label nor the stored
value recorded which one produced the number.

**Requirement generated:** a fallback source is a **different indicator**, not the same one.
Either it is recorded with its own `source_vendor`/`endpoint` and shown as a distinct series,
or there is no fallback. Silently substituting a different underlying instrument behind one
label is F2 (wrong data presented as native) in macro clothing.

---

## 2. The finding that most validates this project's scope

From `REMEDIATION_PLAN.md`, 2026-09-03 validation, point 3:

> **"Almost nothing is a fetch failure.** `spx_correlation` is the only one. `funding`, `oi`,
> `ls_ratio` and `active_addr` all receive **rich data** and quantise it to 3-8 distinct
> scores through bands set outside the observed distribution. The fix is mostly in
> `scoring/`, not `fetchers/`."

**The raw data was largely fine. The scoring layer destroyed it.** Bands were set outside the
observed distribution, so a live, richly-varying input collapsed into a handful of values —
and those values were then summed into a composite that ranked forward returns *backwards*
(lowest-scoring quintile +1.02% over 7 days, highest -0.53%, across 17,501 coin-days).

This is the strongest possible argument for the scope decided at G1: **show raw values with
their real distributions, and no scoring at all.** The layer being removed is precisely the
layer that was measured to be wrong.

---

## 3. Measured facts worth keeping (context, not scope)

- **Drawdown-anchored exit logic**, calibrated 2021-23, frozen, tested 2024-26: 35/35
  drawdown episodes caught, median lag 5.0 days. Exit-rule-only turned $10,000 into
  **$28,210** vs **$12,117** buy-and-hold, beating buy-and-hold on 9 of 10 coins. This is the
  one validated edge in the old system, and it is explicitly **out of scope here** — recorded
  so it is not lost when the signal layer is revisited.
- The shipped engine was invested **1.9% of the time** and issued **92% of its signals in the
  two worst years, 4% in the two best**.
- **Free sources that ran reliably for ~9 months:** Binance public REST (OHLCV + futures
  fapi), CoinMetrics community API, alternative.me F&G, FRED.
- **Sources that broke or gated:** Reddit OAuth (broken at signup), LunarCrush (HTTP 402),
  CryptoPanic (free tier deprecated), CryptoCompare (later required a key). **Four vendor
  changes in nine months** — third-party churn must be a design assumption, not a surprise.

---

## 3b. The schema encoded the bug

`signal-engine/migrations/008_indicator_history.sql` stores indicators **wide** — one column
pair per indicator on a `(coin, date)` row:

```sql
ls_ratio_score  DOUBLE PRECISION,  ls_ratio_raw  DOUBLE PRECISION,
oi_score        DOUBLE PRECISION,  oi_raw        DOUBLE PRECISION,
google_trends_score ..., fourchan_score ..., news_sentiment_score ..., funding_rate_score ...
```

Two structural consequences, both of which caused real failures:

1. **Adding an indicator requires a migration.** This is why the integrity check covered only
   two hardcoded rows (F7) and why `spx_correlation` was absent from
   `_INDICATOR_HISTORY_COLUMNS` — coverage was a hand-maintained list that drifted from
   reality.
2. **There is no `status`, `source`, `fetched_at` or `source_timestamp` column anywhere.** A
   `NULL` therefore cannot distinguish *never fetched* from *unavailable* from *fetch errored*
   from *legitimately not applicable*. F1 is not merely a code bug — it is **encoded in the
   schema**, and no amount of application-layer care could have surfaced it.

**Consequence for this product:** store indicator observations **long/narrow** —
`(asset, indicator_id, observed_at, value, status, source_vendor, endpoint, fetched_at,
source_timestamp, measured_on_asset)` — so a new indicator is a row, never a migration, and
provenance and status are non-optional columns rather than an afterthought.

---

## 4. Requirements this generates

Each is written to become a testable acceptance criterion.

1. A stored datapoint carries: `source_vendor`, `endpoint`, `fetched_at`, `source_timestamp`,
   `measured_on_asset`, `status`.
2. `status` is an explicit enum — `OK | STALE | UNAVAILABLE | ERROR` — never inferred from a
   value. A missing value must be **not representable as a number**. (Defends F1, F6.)
3. `measured_on_asset != displayed_asset` implies `UNAVAILABLE`. No proxying, ever.
   (Defends F2.)
4. Every indicator declares its inputs; two indicators sharing a derivation are flagged as
   derived rather than independent. (Defends F3.)
5. Every indicator declares a freshness budget; exceeding it flips `status` to `STALE`, and
   the UI shows staleness without the user having to go looking. (Defends F6.)
6. Indicator computation is a pure function of (bars, window): same inputs, same output,
   enforced by a golden-file test. (Defends F5.)
7. Integrity-check coverage is generated from the indicator registry, so an uncovered
   indicator is a build error rather than an oversight. (Defends F7.)
8. Absence of a scheduled run raises an alarm that the run itself does not produce.
   (Defends F8.)

---

## 5. Sources

All local, all read directly on 2026-09-07.

| File | What it established |
|---|---|
| `README.md` | System Trust Status table — F1, F2; the "degraded / fabricated" language |
| `SESSION_HANDOFF.md` | F8 runner outage; F10 PRD-061 revert; standing constraints |
| `REMEDIATION_PLAN.md` | The 5,190 / 5,710-row analysis; F3, F5; "the fix is mostly in scoring/"; the money test |
| `research-prd-097-fail-closed-2026-09-04.md` | F6, F7; fail-closed vs fail-open design; `IndicatorScore` blast radius |
| `indicators-and-data-sources.md` | The 25-indicator inventory with sources and keys; F9 replacement-source history |
