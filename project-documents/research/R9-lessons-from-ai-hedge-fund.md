# R9 · Lessons from `ai-hedge-fund`

**Source:** `C:\Users\zayou\OneDrive\Desktop\Projects\cool gits\ai-hedge-fund` (virattt's AI
Hedge Fund), read directly 2026-09-08. **Method:** direct reading of `hedge_fund/data/*`.

**Why this repo is worth mining:** it is a mature, independently-built financial data layer
that solved the same problems this project faces — and it reached the **same conclusion about
silent failure** from a completely different direction. That convergence is the strongest
evidence available that the design in `11_Data_Model.md` is right.

Scope note: its investor agents, LLM layer, portfolio and backtesting are **out of scope
here** (no signals, no scoring — G1). Only the data layer transfers.

---

## 1. The convergent finding — fail-loud, stated independently

`hedge_fund/data/protocol.py`, verbatim:

> **Contract: empty list / None means the data genuinely doesn't exist. Infrastructure
> failures (auth, rate limits, network, server errors) must RAISE — a provider that silently
> returns empty on failure poisons backtests, because missing data is indistinguishable from
> "no signal".**

This is `R0/F1` reached independently. Our prior system's funding rate reported `0.0` for
months because a fetcher never ran; theirs frames the identical hazard as "silent empties
poison backtests". Two projects, different data, different authors, same conclusion.

**What this adds to our design:** they distinguish *"genuinely absent"* from *"failed to
fetch"* at the **protocol boundary**, not merely in the storage layer. Our `Ok | Stale |
Unavailable | Error` union already encodes this, and `Unavailable(NOT_DEFINABLE)` vs
`Error(FETCH_FAILED)` is exactly their distinction. **Keep it.**

## 2. Point-in-time correctness — a trap we had only half-covered

> **get_financial_metrics must be point-in-time: return only data that was publicly filed by
> *end_date*, not data whose fiscal period ended by then.**

and, from their contract test:

> **Point-in-time: get_financial_metrics filters on `filing_date` (when the data became
> public), not `report_period` (which leaks 3-6 weeks of future into a backtest).**

**This generalises directly to us, and sharpens `R0/F11` and `R4`:**

| Our case | The "report period" trap | The correct field |
|---|---|---|
| Funding rate | `premiumIndex.lastFundingRate` — an estimate for a *future* settlement | the settled rate, `source_timestamp` in the past |
| M2 | the month the figure *describes* | the date it was **released** (3–4 weeks later) |
| CPI | the reference month | the release date (5–6 weeks later) |
| ETF flows | the flow date | T+1 publication |
| Daily candle | the forming bar | the **closed** bar (`confirm == "1"`) |

Every one of these is the same bug: **the timestamp a value describes is not the timestamp at
which it became knowable.** Our schema already carries `source_timestamp` and `fetched_at`;
this says we need the distinction to be *enforced*, not merely available.

**Concrete requirement generated:** for any indicator whose publication lags its reference
period, the registry records **both** — a `reference_period` and a `published_at` — and the UI
displays the lag on the face of the value. This is stronger than the current
`10_Technical_Architecture.md` note that release lag "must be displayed", because it names the
field that makes it checkable.

## 3. The `Protocol` abstraction — worth adopting

`protocol.py` defines a `@runtime_checkable Protocol` that every provider satisfies
structurally — no inheritance:

> Any class with these methods can be used as a data provider throughout the pipeline. No
> inheritance required — Python's structural typing handles the rest.

**Adopt this for our fetchers.** One `Fetcher` Protocol returning our status union means OKX,
Coin Metrics, FRED and the Solana RPC are interchangeable at the type level, and mypy
enforces it. It also makes the cassette/contract tests generic across providers.

## 4. Caching semantics — the subtlety worth copying

`cached.py`:

> **only successful responses are cached, and errors from the wrapped client propagate
> (fail-loud preserved).**

A cache that stores failures turns one transient outage into a persistent wrong value — and a
cache wrapper that swallows errors silently undoes the fail-loud protocol above it. Their
wrapper is a decorator that **preserves** the failure semantics of what it wraps.

Directly relevant to `R0/F6`: our prior system loaded cached OHLCV **without checking
`expires_at`**, so stale-but-structurally-valid data produced confident output.

**Requirement:** any cache layer we add must (a) cache only `Ok`, never `Unavailable`/`Error`,
and (b) return `Stale` rather than `Ok` once past the freshness budget.

## 5. Contract tests — a concrete template for PRD-002

`test_client_contract.py` is exactly the harness PRD-002 calls for, and it needs **no API
key** — HTTP is stubbed. Its test list is worth copying as a checklist:

| Their test | What it pins | Our equivalent |
|---|---|---|
| `test_network_error_raises` | infra failure never becomes empty data | fetcher returns `Error`, never `Ok(0.0)` |
| `test_http_*` | status-code handling per class | 451/403 → `Error` with the code in detail |
| `test_financial_metrics_filters_on_filing_date` | point-in-time correctness | `source_timestamp` is never in the future |
| `test_follows_next_page_url_to_the_end` | pagination completeness | full candle range retrieved |
| `test_mid_walk_*` | **partial failure part-way through pagination** | a partial fetch is `Error`, not a short series |
| `test_no_next_page_url_means_single_request` | no spurious extra calls | rate-limit discipline |

**`test_mid_walk_*` is the one we would not have thought of.** A paginated fetch that fails on
page 3 of 5 returns a *shorter but structurally valid* series — which then silently produces a
wrong indicator over an incomplete window. That is a genuine new hazard for our OHLCV
fetching, and it belongs in PRD-002's harness.

## 6. What we deliberately do NOT take

- Investor agents, LLM commentary, portfolio construction, risk models, backtesting — all
  excluded at G1, and their presence in that repo is not an argument for ours.
- Their disk-cache-in-`~/.hedge-fund` design: we persist to Postgres with provenance columns
  instead, because our product's purpose is the audit trail, not fast reruns.

## 7. Requirements this generates

1. Fetchers satisfy one `Fetcher` `Protocol`, returning the status union — never a bare value.
2. Registry records `reference_period` *and* `published_at` where they differ; the UI shows
   the lag.
3. A cache, if added, caches only successes and downgrades to `STALE` past its budget.
4. PRD-002's contract harness covers, per provider: network error, HTTP error classes,
   pagination completeness, **mid-pagination failure**, and no-spurious-request.

## 8. Sources

| File | What it established |
|---|---|
| `hedge_fund/data/protocol.py` | The fail-loud contract, verbatim; the `Protocol` abstraction; point-in-time requirement |
| `hedge_fund/data/cached.py` | Cache-only-successes, propagate-errors semantics |
| `hedge_fund/data/test_client_contract.py` | The contract-test checklist, incl. mid-pagination failure |
| `README.md` | Scope and status of the project |
