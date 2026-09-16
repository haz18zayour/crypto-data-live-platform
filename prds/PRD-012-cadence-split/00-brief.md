# PRD-012 · Split cadence — daily collect, fast derivatives, and the 6h canary

**In one to three sentences:** The roadmap's original framing (owner decision 2026-09-09) assumed
almost every source publishes once a day or slower, so the existing every-6-hours `ingest` job
wastefully refetches identical values, while a cheap, no-write `canary` every 6h would make a
failure visible in ~6–8h instead of 24h+grace. That framing predates PRD-006, which added 16
genuinely fast-cadence entries (12 at 5 minutes, 4 at 8 hours) alongside the 55 truly-daily ones.
This PRD must resolve cadence **per tier**, not with one global daily job, or it silently breaks
the freshness contracts PRD-006 already shipped.

**Depends on:** PRD-001 (the `ingest` job and heartbeat exist). PRD-002 (determinism and contract
harness — the existing `contract-canary` workflow, built in US-206, already does the 6-hourly
no-write shape-check half of this design and does not need to be rebuilt).

**Roughly:** 2–4 stories — this is smaller than a typical PRD now that half the original design
(the canary) already exists, but the cadence-tier split needs care, not a blind cron change.

---

## What already exists, confirmed by reading the current repo, not assumed from the roadmap

- `.github/workflows/canary.yml` (`contract-canary`, built in US-206, predates this PRD) already
  runs every 6 hours (`cron: '23 */6 * * *'`), pings every registered vendor endpoint for a real
  shape-check, writes zero datapoints, and pings a dedicated heartbeat
  (`HEALTHCHECK_URL_CONTRACT_CANARY`) on both success and failure. This is the "canary" half of
  the original PRD-012 design. **It does not need to be built — only confirmed still correct.**
- `.github/workflows/ingest.yml` (the job that actually writes datapoints) currently runs on
  `cron: '17 */6 * * *'` — every 6 hours, for every registered indicator, regardless of that
  indicator's own real update cadence. This is the actual problem this PRD exists to fix.
- `.github/workflows/sol-active-addresses.yml` (built in PRD-007's US-707, once the 2.5-hour SOL
  fetch was found to need its own schedule) currently runs weekly (`cron: '43 3 * * 0'`) —
  already a precedent for a registry entry getting its own dedicated, non-uniform cadence.

## The real distribution this PRD must design against (read directly from `ingest/registry.yaml`)

| `expected_update_interval_seconds` | Count | What it covers |
|---|---|---|
| 300 (5 min) | 12 | OKX open interest, long/short ratio, taker ratio — 3 families × 4 assets |
| 28800 (8h) | 4 | OKX funding rate — 1 family × 4 assets |
| 86400 (1 day) | 54 | Technical indicators (TA-Lib), Coin Metrics MVRV/active-addresses/exchange-flow, Validators.app staking |
| ~2.6M (weekly, `sol_active_addresses` only) | 1 | Already split onto its own schedule (PRD-007) |

**A single global "daily collect" job would immediately violate the 5-minute and 8-hour tiers'
own `freshness_warn_seconds`/`freshness_stale_seconds` contracts** (600s/450s and
43200s/57600s respectively) — those cells would read `STALE` within minutes to hours of a daily
job's first run, a regression PRD-006 explicitly built corroboration and freshness bounds to
prevent. This PRD is not free to assume the roadmap's original "almost everything is daily"
premise still holds; it must re-derive the real design from the registry as it exists today.

## What research must settle before this PRD is spec'd

- **Confirm the fast (5 min) and medium (8h) tiers still need their current cadence**, or whether
  OKX's real update frequency for open interest / long-short ratio / taker volume / funding rate
  has changed since PRD-006 shipped (live-probe, don't assume the registry's existing numbers are
  still correct — they were set by PRD-006's own research, not this PRD's).
- **Whether GitHub Actions' cron scheduling can reliably hit a 5-minute cadence** at all — GitHub
  Actions' own documented behavior is that scheduled workflows can be delayed under load and are
  not guaranteed to fire at the exact scheduled minute, especially for high-frequency crons. If a
  5-minute cadence is not reliable via GitHub Actions cron, this PRD needs a different mechanism
  for the fast tier (e.g. `cron-job.org`, already used elsewhere in this project's stack per
  `AGENTS.md`) or a documented, honest degradation of the freshness bound.
- **Whether splitting collection into multiple jobs (fast/medium/daily) multiplies Coin Metrics'
  and Helius's per-IP/per-account rate limits into a problem** — each job is a separate CI runner
  with a separate IP, so a naive split could cause each vendor's rate limiter to see the *same*
  total call volume from *different* apparent sources within a short window, which is not
  necessarily safer than one job pacing all calls together. Confirm this doesn't quietly violate
  a budget PRD-006/007 already proved safe under a single combined job.
- **Whether the existing `contract-canary` workflow needs any changes at all**, or whether this
  PRD's only real canary-side work is confirming it still passes with the newer vendors (Coin
  Metrics, Helius, Validators.app) wired in — which PRD-007 already fixed in
  `fix(PRD-007): three real live-discovered defects...` (commit `c09efc0`).

## Explicitly NOT in this PRD

- **Rebuilding the contract-canary.** It already exists, already runs every 6h, already writes
  nothing, already pings a heartbeat. This PRD confirms it, does not replace it.
- **Changing `sol-active-addresses.yml`'s cadence.** That schedule was a direct, already-verified
  owner decision from PRD-007 (US-707), driven by Helius's credit budget, not this PRD's cadence
  logic. Out of scope unless a future PRD revisits SOL's budget specifically.
- **Any new indicator, vendor, or panel.** This PRD only changes *when* existing registered
  indicators are collected, never *what* is collected.
- **A composite freshness score or health dashboard** — that's PRD-010 (integrity dashboard),
  not this PRD. This PRD only fixes the collection cadence itself.

## The adversarial case

**Force a fast-tier cell (e.g. `btc_open_interest`) stale by simulating a missed collection
window, and confirm it reads `STALE` within its existing 450-second freshness-warn bound — not
24 hours later** because a global daily job silently absorbed it into the slow tier. A second
case: confirm the contract-canary's own 6-hourly heartbeat still fires correctly once the main
collect job's cadence changes, proving the two schedules are genuinely independent, not
accidentally coupled through a shared trigger or shared credential rate limit.

## Phase checklist

- [x] `00-brief.md`
- [ ] `10-research.md` — `uf research PRD-012-cadence-split`
- [ ] `20-decisions.yaml` — **GATE G1**
- [ ] `30-spec.md`
- [ ] `40-stories/*.md`
- [ ] `uf compile PRD-012-cadence-split`
- [ ] **GATE G2** — approve the estimate
- [ ] `uf run`
- [ ] merge to `main`
- [ ] `uf learn`
