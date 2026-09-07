# 10 · Technical architecture

Derived from `research/R0`–`R7`. Where this document conflicts with a single research track,
`R7-cross-track-synthesis.md` explains why — the tracks could not see each other.

---

## Stack

| Layer | Choice | Why | Alternative rejected |
|---|---|---|---|
| Ingestion language | **Python 3.12** (`uv`, pydantic, httpx, structlog) | Mature TA/data ecosystem; owner already fluent — 223 files of prior art. Cadence is minutes-to-months, so V8 isolate speed is irrelevant (R6 §6) | TypeScript-on-Workers — would unify the language but forces a rewrite of the one part with a mature ecosystem, to win latency this product does not need |
| Indicator computation | **TA-Lib** (C library) as the computation engine, golden-file pinned | Canonical Wilder implementations; the RSI/ATR smoothing ambiguity that diverges 5–10 points in trends (R3) is settled by using the reference implementation rather than re-deciding it. Windows wheels/MSI available since v0.6.5 | `pandas-ta` — original is heading to archival (R3); `pandas-ta-classic` fork is maintained but adds a maintenance bet for no correctness gain. Retained as fallback only |
| Database | **Supabase Postgres** (direct :5432, not the :6543 pooler) | Row count over 3 years is low single-digit millions — a non-event for Postgres (R6 §3). Free tier's 7-day pause is dodged by daily ingest writes | TimescaleDB / ClickHouse / DuckDB+Parquet — all unwarranted at this volume; each adds an operational surface for zero benefit |
| Frontend | **Vite + React + TypeScript + Tailwind** | Owner's existing stack; the discriminated-union render pattern (R5 §2.1) needs a real type system to enforce exhaustiveness at compile time | — |
| Charts | **Lightweight Charts** (Apache-2.0, attribution logo required) primary; **uPlot** for dense sparkline panels | Purpose-built for financial series; uPlot handles the many-small-panels case at lower bundle cost (R6 §4) | Recharts/visx — fine for dashboards, weak on candlesticks and dense series |
| Hosting (frontend) | **Cloudflare Pages** | Free tier generous; owner already deploys here | — |
| Auth | **Cloudflare Access (Zero Trust)** free tier | Single user. Auth stays entirely at the edge; no service-role key can reach the browser because the browser never holds one; no email infrastructure (R6 §5) | Supabase magic link — what the prior system used; more moving parts and an email dependency for one user |
| Scheduling / compute | **UNDECIDED — blocked on the reachability spike.** See "The open decision" below | — | — |
| Dead-man's-switch | **Healthchecks.io** free tier (20 checks) | ~30 min of work; the single highest value-per-effort defence available (R5 §1). Directly addresses the 24h silent outage | Relying on the job to report its own failure — which is precisely what failed |

---

## The open decision — compute location

**This is the one architectural question the research could not close, and it must not be
guessed.** Full reasoning in `R7 §C1`.

The prior system's worst outage traces back through a chain that starts with a data-source
choice:

```
Binance chosen as primary source
  -> Binance returns HTTP 451 to US IPs
    -> GitHub-hosted runners (US) unusable
      -> self-hosted runner on Fly.io Frankfurt
        -> a long-lived process the owner must supervise
          -> exited 0 on self-update, stopped silently
            -> 24h of data lost before anyone noticed
```

The prior repo states this in its own workflow file: `# runs-on self-hosted because Binance is
unreachable from GitHub-hosted runners;` with `primary_region = 'fra'`.

**R3 independently recommends Coinbase/Kraken as primary spot OHLCV with OKX as cross-check**
— on data-quality grounds, because OKX is the only venue found that explicitly flags a closed
candle. That recommendation, taken up, dissolves the chain above: no Binance, no 451, no
self-hosted runner, no silent-death failure mode.

**What remains unproven** is derivatives. Binance dominates funding/OI/liquidations, and
whether OKX and Bybit geo-block *unauthenticated public market-data endpoints by IP* — as
opposed to restricting US *accounts*, a different thing routinely conflated — was not
establishable. All verification for this project ran from Lebanon, where Binance `fapi`
responds normally; **reachability from a US IP cannot be tested from a non-US IP.**

**PRD-001 therefore begins with a reachability spike** that runs on the real target compute
and records, per venue and endpoint, the observed HTTP status. Until that table exists the
compute row above stays `UNDECIDED`, and the two candidate shapes are:

| | If venues are reachable from GitHub-hosted runners | If they are not |
|---|---|---|
| Trigger | GitHub Actions `schedule:` at off-peak minutes + cron-job.org `repository_dispatch` as an independent second trigger | Same |
| Compute | The GitHub-hosted runner itself | A **stateless** Fly.io machine in `fra`, started per run via the Machines API and stopped on exit — never resident |
| Residual risk | GH Actions cron is documented to delay and occasionally drop runs silently | Machine start failures — caught by the same dead-man's-switch |

Both shapes keep the dead-man's-switch and neither reinstates a supervised long-lived process.

---

## What "live" means here

**Provably fresh, not streaming.** Verified cadences of the actual sources (R7 §C2):

| Source | Genuine cadence |
|---|---|
| Spot OHLCV | seconds–minutes |
| Funding rate | 8h fixed (Binance); 1h–8h *dynamic* (OKX/Bybit) |
| On-chain (Coin Metrics) | one point per UTC day |
| Fear & Greed | daily |
| M2 | monthly, 3–4 week release lag |

Exactly one row moves faster than eight hours. A push layer would deliver real-time updates
for **price alone** while every other panel sat unchanged for hours — and the prior system
already measured the cost of that choice: a resident WebSocket listener starved the scheduled
jobs and was reverted (R0/F10).

So the browser **polls** (TanStack Query, 30–60s). The product's value is that a stale number
announces itself, not that a fresh one arrives in 50ms. *The repository name invites the
opposite assumption and should not be allowed to drive the design.*

---

## Shape

```
                    TRIGGER (redundant, independent)
   GitHub Actions schedule:  ──┐        ┌── cron-job.org -> repository_dispatch
                               ▼        ▼
                      ┌──────────────────────────┐
                      │   INGEST (Python 3.12)   │
                      │                          │
                      │  registry.yaml  ← the single source of truth:
                      │    per indicator: vendor, endpoint, FIELD,
                      │    freshness budget, definable-for-assets
                      │            │             │
                      │            ▼             │
                      │  fetchers ── return Ok | Stale | Unavailable | Error
                      │            │    (never a bare float)
                      │            ▼             │
                      │  compute (TA-Lib, pure: f(bars, window))
                      │            │             │
                      │            ▼             │
                      │  integrity checks ── coverage generated FROM registry
                      └────────────┬─────────────┘
                                   │  ping on success
                                   ├──────────────► Healthchecks.io ── alerts on SILENCE
                                   ▼
                      ┌──────────────────────────┐
                      │  SUPABASE POSTGRES       │
                      │  datapoints (long/narrow)│
                      │   value, status,         │
                      │   source_vendor, endpoint│
                      │   fetched_at,            │
                      │   source_timestamp,      │
                      │   measured_on, asset     │
                      │   CHECK(status!='OK'     │
                      │     OR measured_on=asset)│
                      └────────────┬─────────────┘
                                   │  polled, read-only
                                   ▼
                      ┌──────────────────────────┐
                      │  DASHBOARD (Vite/React)  │
                      │  Cloudflare Pages        │
                      │  behind Cloudflare Access│
                      │                          │
                      │  exhaustive switch on    │
                      │  status — UNAVAILABLE    │
                      │  renders "—", never "0"  │
                      └──────────────────────────┘
```

**The registry is the spine.** Adding an indicator is a row, never a migration (R0 §3b — the
prior schema was wide, one column pair per indicator, which is why integrity coverage was a
hand-maintained list that drifted). Integrity coverage is generated from the registry, so an
uncovered indicator is a build error rather than an oversight.

---

## Core schema decision

Long/narrow, provenance non-optional (R5 §2.2):

```sql
CREATE TYPE datapoint_status AS ENUM ('OK','STALE','UNAVAILABLE','ERROR');

CREATE TABLE datapoints (
  indicator_key   text  NOT NULL,
  asset           text  NOT NULL,   -- what we DISPLAY it as
  measured_on     text  NOT NULL,   -- what it was ACTUALLY computed on
  value           double precision, -- NULL unless OK/STALE
  status          datapoint_status NOT NULL,
  reason          text,             -- required for UNAVAILABLE/ERROR
  source_vendor   text  NOT NULL,
  endpoint        text  NOT NULL,   -- incl. the FIELD (F11)
  fetched_at      timestamptz NOT NULL,
  source_timestamp timestamptz,
  CONSTRAINT asset_match CHECK (status <> 'OK' OR measured_on = asset)
);
```

That CHECK constraint is the F2 defence: BTC's MVRV displayed as SOL's becomes a **database
error**, not a silent proxy. It is the single highest-leverage line in the schema.

`UNAVAILABLE` must further distinguish three reasons (R7 §C4) — `NOT_DEFINABLE` (SOPR on SOL:
account-based, no UTXO, not purchasable at any price), `PAYWALLED` (realized cap), and
`FETCH_FAILED`. One blank cell for all three destroys the information the owner most needs:
whether a gap is permanent, purchasable, or broken.

---

## Environments

| | Local | Preview | Production |
|---|---|---|---|
| URL | `localhost:5173` | `*.pages.dev` (per-branch) | Cloudflare Pages, behind Access |
| Database | Supabase project (same, read-only from app) | same | same |
| Secrets | `.env.local`, gitignored | Pages env vars | Pages env vars + GitHub Actions secrets |
| Ingestion | manual invoke | never scheduled | scheduled |

Single Supabase project. A second is not justified for one user, and divergence between two
databases is itself a silent-failure risk.

---

## Blast radius

Paths needing human review before merge (mirrored into `.uf/config.json`). Note these are
**product-specific** — there is no auth flow, no payments, no RLS surface of consequence:

- `**/registry*` — the indicator registry. Changing a definition retroactively changes the
  meaning of every stored value; this is the most dangerous file in the repo.
- `**/migrations/**` — schema, and especially the `asset_match` constraint.
- `**/fetchers/**` — endpoint or field changes silently alter what a number *is* (F11, F12).
- `.github/workflows/**` — the trigger layer; its silent failure cost 24h before.
- `**/status*`, `**/freshness*` — the fail-closed semantics themselves.

## Constraints

- **Budget: $0/mo for v1.** The paid-tier question reduces to a single row — SOL's on-chain
  column (R7 §C3). Everything else is genuinely free. Ship with SOL on-chain rendering
  `UNAVAILABLE — no free source`, which is a *truthful* display and precisely the product's
  purpose. Revisit only if the empty panel proves annoying in use.
- **GitHub Actions free minutes: 2,000/mo** (repo is private — verified). At ~3 min/run this
  allows ~22 runs/day. A 15-minute cadence would exceed it; cadence is a cost decision.
- **No secret may reach the browser.** The dashboard reads through the anon key against
  read-only views, or through Access-gated static JSON. No service-role key client-side, ever.
- **Determinism is a hard requirement**, not a nicety: indicator computation is a pure
  function of (bars, window), golden-file pinned. The prior system's values depended on
  process uptime (R0/F5).
- **Vendor churn is assumed, not exceptional.** Four sources broke or gated in nine months
  (R0 §3); CryptoCompare retired its free tier entirely in May 2026 and pytrends is archived
  (R4). Every fetcher is cassette-tested so a silent response-shape change fails loudly.
