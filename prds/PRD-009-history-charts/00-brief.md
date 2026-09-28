# PRD-009 · History and charts

**In one to three sentences:** Give every cell on the board a per-indicator sparkline and
distribution context — a value read against its own history, not an arbitrary band, and never a
score or judgement about whether that history is "good." Backfill the indicators that currently
have only one or a handful of persisted rows, since a sparkline over a single point is not a
sparkline.

**Depends on:** PRD-005 (the dashboard — cells and the board model already exist to attach this
to). Reads history that PRD-001 through PRD-008's fetchers already know how to produce; adds no
new vendor.

**Roughly:** 6–9 stories.

---

## Why this PRD is shaped this way

Confirmed live against the production database, 2026-09-28: `datapoints` rows accumulate
naturally every time the pipeline runs (unique per `indicator_key, asset, source_vendor,
source_timestamp`), but accumulation is wildly uneven across categories. Fast-tier derivatives
(`open_interest`, `taker_ratio`, 5-minute cadence) already have 300+ historical rows each. Most
daily-tier rows added by PRD-006 through PRD-008 (MVRV, active addresses, ETF net flow, every
macro series) have exactly **one** row — they only started being collected days ago. A sparkline
over one point is not a sparkline; a distribution context over one point is meaningless. This is
the central scope question research must settle: how far back can each vendor actually backfill,
and does every indicator get a sparkline on day one, or do sparse-history rows ship with an
honest "not enough history yet" state instead of a fake flat line.

## What research must settle before this PRD is spec'd

- **Per-vendor backfill depth and shape.** OKX's `history-candles`/`funding-rate-history`, Coin
  Metrics' `asset-metrics` time-range queries, FRED's `series/observations` (already a time
  series by construction), SoSoValue's `summary-history`, and DefiLlama's `stablecoinchains` (a
  current-snapshot endpoint with **no** history parameter, confirmed live in PRD-008) each behave
  differently. Confirm which of this board's ~150 registered indicators can be backfilled at all,
  how far back per vendor's real rate limits, and which (DefiLlama's stablecoin supply is the
  leading candidate) structurally cannot be backfilled beyond "since we started collecting" — a
  fifth honest-absence case alongside NOT_DEFINABLE/UNAVAILABLE/PAYWALLED/FETCH_FAILED.
- **Storage: reuse `datapoints` as-is, or a dedicated history table.** `datapoints` already
  accumulates every distinct `source_timestamp` per the unique index added in PRD-003. Confirm
  whether a sparkline query (N most recent rows per indicator/asset) performs acceptably against
  the existing table at real scale, or whether a rollup/materialized view is needed — this is a
  read-pattern question, not a new write path.
- **What "distribution context" means without becoming a signal.** AGENTS.md's rule is absolute:
  no composite score, no ranking, no judgement. A raw sparkline of past values is pure display. A
  percentile badge, a z-score, or a "this is unusually high" label crosses into interpretation the
  project has explicitly ruled out everywhere else. Research must find and cite genuine prior art
  for showing "this value against its own recent range" as a **visual scale, not a verdict** (e.g.
  a min/max axis under the sparkline, not a colored badge) — and G1 must confirm the exact
  mechanism before any story is written, since this is the one part of this PRD closest to the
  project's hardest line.
- **Backfill as a one-time job vs. an ongoing part of the pipeline.** Confirm whether backfill
  runs once per newly-registered indicator (a manual/triggered job) or needs to be re-triggered
  whenever a new indicator is added to the registry going forward.

## Explicitly NOT in this PRD

- **Any score, percentile rank, z-score, "overbought/oversold" label, or colored significance
  badge on a value relative to its own history.** Permanent, project-wide rule — this PRD adds a
  visual scale, never a verdict.
- **Cross-indicator or cross-asset comparison charts.** One indicator's own history only; not
  "RSI vs MVRV" or "BTC vs ETH."
- **Any new vendor.** This PRD only asks existing fetchers for more of what they already return.
- **Candlestick or OHLC charting.** Sparklines are single-value-over-time; full OHLC charting (if
  ever wanted) is a materially bigger UI surface and not implied by the roadmap line.

## The adversarial case

**A newly-registered indicator with exactly one persisted row renders honestly** — no sparkline
drawn from a single point, no fabricated flat line, an explicit "not enough history yet" state
distinct from NOT_DEFINABLE/UNAVAILABLE. Second: **pick one indicator whose real historical value
swung from one extreme to the other** (a real drawdown or spike already in the data) and confirm
the sparkline and its scale reflect that swing accurately against real numbers pulled directly
from the vendor, not the persisted rows alone — an independent cross-check that backfill wrote
the correct historical values, not just *a* value per slot.

## Phase checklist

- [x] `00-brief.md`
- [ ] `10-research.md` — `uf research PRD-009-history-charts`
- [ ] `20-decisions.yaml` — **GATE G1**
- [ ] `30-spec.md`
- [ ] `40-stories/*.md`
- [ ] `uf compile PRD-009-history-charts`
- [ ] **GATE G2** — approve the estimate
- [ ] `uf run`
- [ ] merge to `main`
- [ ] `uf learn`
