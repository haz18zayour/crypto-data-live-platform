---
title: Macro and flows panel — honest lag, never a single number
branch: feat/prd-008-macro-flows
assumptions:
  - claim: FRED's real publication-date metadata (not a naive realtime_start default, which stamps every observation as published "today") can be read reliably via output_type=4, fred/series last_updated, or release dates.
    tripwire: Confirm live, against a real FRED response, which field actually carries the true publication date before any story commits to it as settled. A wrong assumption here silently stamps CPI as published today.
    acceptedBy: default
  - claim: The existing FRED_API_KEY (currently shared with the crypto-investing-signals project) will be replaced with a dedicated key for this product before this PRD ships.
    tripwire: FRED's 120 req/min limit is per-key. A burst from the other project can take every macro row on this board to UNAVAILABLE, and it will look like this project's own defect.
    acceptedBy: default
  - claim: A FRED value revised under the same observation date (a CPI seasonal-factor restatement, an M2 benchmark revision) is shown as a revision, not silently overwritten or flagged as non-determinism by PRD-002's golden-file harness.
    tripwire: Nobody has decided the mechanism yet. Swallowing a revision is exactly the quiet dishonesty this project exists to prevent — must be decided explicitly here, not left as an accidental side effect of however persist_datapoint's upsert happens to behave.
    acceptedBy: default
  - claim: SoSoValue's "only the most recent 1 month of history" constraint and its separate "limit max 300" parameter do not silently truncate or duplicate data when combined.
    tripwire: Live-probe the actual response shape and date range returned before a story commits to a specific backfill or pagination assumption.
    acceptedBy: default
---

# Macro and flows panel — honest lag, never a single number

## What this delivers

A fourth data category: seven FRED macro series (`VIXCLS`, `DFF`, `T10Y2Y`, `DFII10`,
`DTWEXBGS`, `CPIAUCSL`, `M2SL`) spanning daily, weekly, and monthly release cadences; ETF net
flows for BTC/ETH/SOL from SoSoValue (T+1, BNB `NOT_DEFINABLE`); stablecoin supply per-chain for
ETH/SOL/BSC from DefiLlama (BTC `NOT_DEFINABLE`); and Fear & Greed from `alternative.me`, shipped
explicitly labeled as that vendor's own composite, never as an independent signal.
`DTWEXBGS` renders as "Fed Broad Dollar Index," never as "DXY" — no free, official DXY feed
exists anywhere. Every macro row shows its **reference period** and **published date**
separately on its own face; no cell ever shows a single "N days lag" number, because live
research proved that number depends entirely on which of three disagreeing anchors you pick.

## Why (from research and this gate's own findings)

Three findings are load-bearing.

1. **"Lag" is not one number — live-probing FRED found three disagreeing anchors.** M2's
   apparent lag is 22, 52, or 87 days depending on whether you measure from the end of the
   reference period, the observation date FRED stamps, or the real publication date. The
   brief's own claim that `DTWEXBGS` lags "1-3 business days" was live-checked and found wrong —
   it is a **weekly** release (H.10) with an observed ~10-11 day lag just before each release,
   confirmed against this project's own earlier measurement in
   `project-documents/15_Services_and_Credentials.md`. The only honest fix is showing the
   reference period and the published date as two separate facts, never collapsing them into a
   single lag figure that depends on an implicit, undisclosed anchor choice.
2. **The frontend already has a type for this; the backend does not.** `web/src/datapoint.ts`
   declares optional `referencePeriod`/`publishedAt` fields on `Provenance`, and
   `web/src/data.ts:255` already computes staleness from `publishedAt` when present. But no
   migration, no `persist_datapoint` parameter, and no fetcher anywhere populates either field —
   confirmed by reading `supabase/migrations/20260908140000_create_datapoints.sql` directly
   (no `reference_period`/`published_at` columns exist) and `ingest/persist.py`'s insert column
   list (neither field is written). This PRD is not "reuse existing plumbing" as research first
   suggested; it requires a real, blast-radius migration to add both columns, wiring
   `persist_datapoint` to accept and store them, and wiring every new fetcher to populate them
   from real vendor metadata.
3. **SoSoValue and DefiLlama each have a real, asset-shaped gap, not a uniform one.** SoSoValue's
   ETF-flow API enum has no BNB entry at all (confirmed live) — a settled `NOT_DEFINABLE`, not a
   scraping problem to solve. DefiLlama's `/stablecoinchains` has no Bitcoin entry at all
   (confirmed live) — Bitcoin genuinely has no stablecoin-supply concept to track, a different
   settled absence from BNB's ETF gap. Each renders its own distinct reason; neither is
   interchangeable with the other, matching this project's established anti-collapse pattern.

## Approach

**One generic FRED fetcher driven by a series registry.** A pydantic registry row per series
(`series_id`, display name, release cadence, reference-period semantics, disclosure text) feeds
one fetcher that calls FRED's `series/observations` endpoint per row. Adding or removing a macro
row becomes a registry config change, not a new fetcher — matching how PRD-006/007 scaled to
four assets each. `"."` (FRED's missing-observation marker) never becomes `0`; the fetcher walks
back to the last real observation and the cell's face shows *that* observation's own reference
period, never today's date dressed up as fresh. The real published-at date is read from FRED's
own publication metadata (confirmed live before being written into a story as settled fact per
the assumption above), not from a naive `realtime_start` default.

**Database migration adds `reference_period` and `published_at` columns to `datapoints`,**
nullable for backward compatibility with every existing row from PRD-001/006/007.
`persist_datapoint` accepts both as optional keyword arguments. This is blast radius
(`**/migrations/**` per `.uf/config.json`) and needs G4 review before merge, same as every prior
schema change in this project.

**A revision to the same observation date is disclosed, not swallowed.** When a fetch returns a
different value for an observation date already persisted, the new row's `source_field` states
"revised from `<old value>`" rather than silently overwriting the prior figure — a decision this
gate makes explicitly rather than leaving to however the existing upsert-by-identity logic
happens to behave.

**`ingest/fetchers/sosovalue.py` and `ingest/fetchers/defillama_stablecoins.py`** are two new,
thin fetchers following the same `Ok | Stale | Unavailable | Error` discipline as every existing
fetcher. SoSoValue's per-ticker money fields are parsed as `Decimal`/`StrictStr`, never `float`
— the API returns long-decimal strings (e.g. `-55066297.0000000000000000`) that would drift
PRD-002's determinism golden files under float rounding. `ingest/fetchers/alternative_me.py`
calls the keyless Fear & Greed endpoint; the persisted `source_field` names `alternative.me`'s
own six sub-weights and explicitly notes "surveys 15%, currently paused" — the disclosure lives
on the cell's own face, not in a code comment, so a verifier can grep for it.

**All rows persist on PRD-012's daily/slow tier.** Nothing here changes intraday; T+1 ETF flows
and monthly macro releases gain nothing from a faster cadence, and putting them on the fast tier
would burn SoSoValue's 100,000-request monthly quota for zero new data.

## Data model changes

**Real, and blast radius.** A new migration adds `reference_period text` and
`published_at timestamptz`, both nullable, to `public.datapoints`. No existing row's meaning
changes; every pre-PRD-008 indicator continues to render exactly as before with both new columns
`null`.

## Out of scope

Restated from `00-brief.md` and confirmed at G1: BTC dominance; SP500/NASDAQCOM/SOFR/FEDFUNDS;
BNB ETF flows or stablecoin supply (both settled `NOT_DEFINABLE`); a global stablecoin-supply
total; CoinMarketCap's Fear & Greed Index; Google Trends, X/Twitter sentiment, Reddit sentiment,
LunarCrush, Santiment real-time endpoints; CME futures basis, exchange reserve aggregates,
Coinbase premium; news headlines or sentiment scores; any new panel layout; any composite, score,
signal, or cross-indicator judgement, permanently.

## The adversarial case

**Render the macro panel and read the staleness gradient at a glance**: same-day rows (VIX,
DFF, T10Y2Y, DFII10) next to `DTWEXBGS`'s real ~10-day weekly-release lag next to CPI's ~5-6 week
lag and M2's ~3-4 week lag (from period-end) — each showing its own reference period and
published date, none implying same-day freshness it doesn't have, and none collapsed into a
single "N days" figure. A second, cheap case: grep the entire rendered board and its source code
for the literal string "DXY" — it must never appear as a label, only (if at all) inside an
explanatory disclosure distinguishing `DTWEXBGS` from ICE's proprietary DXY. A third case: force
the Fear & Greed cell and confirm `alternative.me`'s own name and composite-methodology
disclosure (including "surveys 15%, currently paused") render on the cell's face, not as an
unlabeled number.

## Stories

| Story | Title | Depends on |
|---|---|---|
| US-801 | Database migration — reference_period and published_at columns on datapoints, nullable, backward compatible | — |
| US-802 | FRED fetcher — series registry, real published-date metadata, "." never becomes 0, revision disclosed not swallowed | US-801 |
| US-803 | Seven FRED rows registered — VIXCLS, DFF, T10Y2Y, DFII10, DTWEXBGS, CPIAUCSL, M2SL, each with correct release-cadence staleness thresholds | US-802 |
| US-804 | SoSoValue ETF-flow fetcher — BTC/ETH/SOL, Decimal money parsing, BNB declared NOT_DEFINABLE | US-801 |
| US-805 | DefiLlama stablecoin-supply fetcher — per-chain ETH/SOL/BSC, BTC declared NOT_DEFINABLE | US-801 |
| US-806 | Fear & Greed fetcher — alternative.me, composite disclosure and paused-survey-weight on the cell's face | US-801 |
| US-807 | One ingest run persists all four new fetchers alongside the existing board — pipeline and heartbeat integration, daily tier | US-803, US-804, US-805, US-806 |
| US-808 | The adversarial case — the staleness gradient read at a glance, the DXY-string grep, and the Fear & Greed disclosure demonstration | US-807 |
