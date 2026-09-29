---
title: History and charts — a value read against its own history, never a verdict
branch: feat/prd-009-history-charts
assumptions:
  - claim: SoSoValue's ETF flow history endpoint (etfs/summary-history) supports a meaningful backfill window and rate limit compatible with a one-time backfill job.
    tripwire: Research could not fetch SoSoValue's own docs and only found an unrelated third party's unverified "20 req/min" claim. Live-probe the actual response shape, date range, and real rate limit before any story commits to a specific backfill window or pagination approach.
    acceptedBy: default
  - claim: OKX's rubik long/short and taker-volume history endpoints support a UTC-aligned bar parameter the same way candles support bar=1Dutc.
    tripwire: Research flagged this as unverified. If no UTC-aligned option exists for the rubik endpoints, disclose the UTC+8 offset on the cell face rather than silently mixing UTC+8-bucketed history with UTC-bucketed FRED/Coin Metrics history on a shared time axis.
    acceptedBy: default
  - claim: Recomputing historical technical-indicator values from backfilled candles, seeded with a sufficient multiple of each indicator's own warm-up period, agrees with PRD-002's existing golden-file harness rather than diverging on early backfilled bars.
    tripwire: PRD-002 proved this for the live, fixed-N-bar case only. Confirm live that a sufficiently long seed window produces values matching what the live pipeline would have computed at that historical bar before shipping backfilled technical indicators.
    acceptedBy: default
  - claim: A single RPC/view returning at most N points per cell as one JSON array keeps every board-wide history read under PostgREST's default row-response cap.
    tripwire: Research's evidence for the cap and its configurability was search-results-only. Confirm the real current cap and the RPC's actual response size live at this board's ~150-indicator, multi-asset scale before assuming this avoids truncation.
    acceptedBy: default
  - claim: A workflow_dispatch backfill job, run per-indicator against Coin Metrics/FRED/SoSoValue's real rate limits, completes within a practical GitHub Actions wall-clock budget without its own scheduled workflow or Healthchecks check.
    tripwire: Unmeasured. If a backfill run risks timing out inside an existing ingest workflow's window, give it its own workflow_dispatch job with its own timeout rather than risk a silent timeout inside daily/medium/fast ingest.
    acceptedBy: default
---

# History and charts — a value read against its own history, never a verdict

## What this delivers

A sparkline and a plain min/max scale on every board cell that has enough history to draw one —
the value read against its own recent past, never against an arbitrary band, a percentile, or any
other externally-supplied judgement. Backfills the ~150 registered indicators that today mostly
have one or a handful of persisted rows (confirmed live, 2026-09-28: fast-tier derivatives have
300+ rows from natural accumulation; most PRD-006/007/008 daily-tier rows have exactly one).
Indicators without enough history yet — by cadence-appropriate threshold, not a universal one —
render an explicit "not enough history yet (n points since &lt;date&gt;)" state, never a
fabricated flat line.

## Why (from research and this gate's own findings)

Three findings are load-bearing.

1. **The brief's own assumption about DefiLlama was wrong, and correcting it removed a fifth
   absence case that didn't need to exist.** `/stablecoincharts/{chain}` — a different endpoint
   from the same already-integrated vendor — returns daily history back to 2017 for Ethereum,
   confirmed live. Stablecoin supply is fully backfillable. The real fifth honest-absence case is
   Solana on-chain history via Helius `getBlock`: a prior session measured a single hour of block
   scanning at ~2.5h wall-clock, making RPC-based backfill genuinely prohibitive, not merely
   inconvenient.
2. **Backfilling into `datapoints` as-is would silently make a historical value the board's
   "current" one.** `board_read`/`datapoints_read` pick the latest row per cell by `fetched_at`.
   A backfill row written today with a 2024 `source_timestamp` would win that ordering and become
   what the live board displays — confirmed as the single most likely first-implementation defect
   in this PRD by research's own gotcha analysis. This requires its own migration (an `origin`
   column, `board_read` filtered to `origin = 'live'`) applied to production, with explicit owner
   sign-off, **before any backfill job is allowed to write a single row** — the same blast-radius
   discipline this project applied to every prior migration, now gated at the story-dependency
   level rather than left to sequencing luck.
3. **Every vendor's history endpoint behaves differently, and the differences are exactly where a
   real defect would hide.** OKX's candles go back years; its funding history is only ~3 months;
   its open-interest history lives on a *separate* endpoint from the live snapshot with its own
   units to reconcile. FRED's `output_type=4` initial-release semantics hit the same
   ~2000-vintage-date cap PRD-008 already broke once, and must be chunked. Coin Metrics returns an
   empty response — not an error — outside its entitlement window, so a naive backfill would
   silently record a falsely-short history. Each of these is a real, vendor-specific recipe, not a
   generic "fetch more history" function.

## Approach

**One migration first, gating everything else.** `datapoints` gains an `origin` column
(`'live'` or `'backfill'`, default `'live'`). `board_read` and `datapoints_read` are rebuilt to
filter to `origin = 'live'`, so a backfilled row can never appear as the board's current value
regardless of its `fetched_at`. This migration is written, reviewed, and applied to production —
with the owner's explicit sign-off, per this project's established manual-migration-apply
discipline — before any other story in this PRD may run. No later story's acceptance criteria may
be judged met by a codex sandbox alone; each backfill story's own live-write criterion is
meaningless until this lands.

**A shared backfill entry point, not per-vendor scripts.** `ingest/backfill.py` exposes one
`workflow_dispatch`-triggered entry point taking an `indicator_key` (or `--all`), dispatching to a
per-registry-row backfill recipe. Every write goes through the existing
`persist_datapoint`/`persist_board` path with `origin='backfill'`, idempotent through the
pre-existing unique index on `(indicator_key, asset, source_vendor, source_timestamp)` — a
re-run never duplicates a row it already wrote. A coverage test (mirroring PRD-002's registry
coverage discipline) fails the build if any registry entry has neither a backfill recipe
reference nor an explicit `not_backfillable: <reason>` declaration — so a future PRD's new
indicator cannot silently ship with permanent "not enough history" and nobody notice.

**Per-vendor backfill recipes, each carrying its own real constraint:**
- **OKX** — candles backfill deep (years) and technical indicators are recomputed from them with
  a seed window sized to several multiples of each indicator's own TA-Lib warm-up period, not
  just the plotted window. Funding-rate history is shallow (~3 months, measured live) and ships
  honestly bounded to what the vendor actually returns. Open interest history comes from a
  *different* endpoint (`open-interest-history`) than the live snapshot (`public/open-interest`);
  both persist with their own `endpoint`/`source_field` so a viewer (and the verifier's live
  cross-check) can tell which wrote which row. Long/short ratio and taker volume backfill at
  `period=1D`; the live cells stay at their existing `5m` cadence — the resulting sparkline plots
  on a real time axis so the density change between sparse-historical and dense-recent points is
  visible, never resampled away.
- **Coin Metrics** (MVRV, active addresses, exchange flows) — backfill queries `catalog-v2` for
  each metric's real `min_time` first and asserts the entitlement window before treating an empty
  response as "no history," never as an error.
- **FRED** — backfill uses the same initial-release (`output_type=4`) semantics as the live
  fetcher, chunked into `realtime_start` windows that stay under the vintage-date cap PRD-008
  already found and fixed for the live case.
- **SoSoValue, DefiLlama (`/stablecoincharts/{chain}`), alternative.me** — each gets a thin
  recipe reusing its existing fetcher's parsing/schema discipline against the new historical
  endpoint or parameter.
- **Solana on-chain history, validators.app** — both declare `not_backfillable` with their real,
  distinct reasons (RPC block-scan cost; no known history endpoint), proving the coverage test
  accepts a genuine declared absence as well as a genuine recipe.

**A single history-read RPC returns at most N points per cell as one JSON array,** ordered by the
existing unique index, rather than a board-wide row-per-point query that risks PostgREST's
response cap at ~150 indicators × 4-5 assets. The sparkline component reads this array directly;
no client-side history assembly across pages.

**The sparkline itself is a scale, never a verdict.** A line, the last point visually marked, and
min/max *value labels with their own dates* at the axis ends — no shaded band, no percentile
marker, no colour keyed to position in the range. The time window is fixed per cadence tier and
printed as text (e.g. "90d" / "7d") next to the chart, since two cells' "range" can silently cover
different spans when backfill depth differs by vendor (funding ~3 months vs. candles years).
Below a cadence-tiered minimum point count (≥7 points and ≥2 distinct values for daily-or-faster
series; a lower bar for monthly series so CPI/M2 can ever draw), the cell shows
"not enough history yet (n points since &lt;date&gt;)" instead of a line — a fact about how long
this board has been collecting, never conflated with `NOT_DEFINABLE`/`UNAVAILABLE`/`PAYWALLED`/
`FETCH_FAILED`, which are facts about the vendor or the fetch.

## Data model changes

**Real, and blast radius.** A migration adds `origin text not null default 'live'` to
`public.datapoints`, and rebuilds `board_read`/`datapoints_read` to filter to `origin = 'live'`.
No existing row's meaning changes — every pre-PRD-009 row defaults to `'live'` and continues to
render exactly as before. This migration must be applied to production, with owner sign-off,
before any backfill story's own live-write criterion can be judged met.

## Out of scope

Restated from `00-brief.md` and confirmed at G1: any score, percentile rank, z-score,
overbought/oversold label, or colour-coded significance badge on a value relative to its own
history; cross-indicator or cross-asset comparison charts; any new vendor (every backfill source
is an existing vendor's own additional endpoint); candlestick or full OHLC charting; Solana
on-chain history backfill via Helius (declared `not_backfillable`, not attempted); validators.app
historical backfill (declared `not_backfillable`, no known history endpoint); a downsampled or
materialized rollup table; client-side vendor fetching for history.

## The adversarial case

**A newly-registered indicator with exactly one persisted row renders honestly** — no sparkline
drawn from a single point, an explicit "not enough history yet" state distinct from every other
absence reason on the board. **A cross-vendor seam check, not a same-endpoint replay**: pick one
indicator whose real historical data already contains a genuine swing (a real drawdown or spike),
and confirm the backfilled sparkline's values on a date *within the overlap between backfilled and
live data* match a fresh, independent live call to the vendor's *live* endpoint for that same
date/value — not simply re-running backfill's own endpoint and parameters against itself, which
would prove nothing about a splice at the seam (research's own blind-spot finding).

## Stories

| Story | Title | Depends on |
|---|---|---|
| US-901 | Database migration — `origin` column on datapoints, `board_read`/`datapoints_read` filtered to `origin='live'`, applied to production before any backfill runs | — |
| US-902 | History-read RPC — at most N points per cell as one JSON array, ordered by the existing unique index | US-901 |
| US-903 | Backfill job infrastructure — shared `workflow_dispatch` entry point, idempotent writes, and a coverage test requiring every registry entry to declare a recipe or `not_backfillable: <reason>` (Solana on-chain, validators.app declared not_backfillable here) | US-901 |
| US-904 | OKX backfill recipes — candles (deep, TA-Lib warm-up reseeded), funding (shallow, honestly bounded), open-interest history (separate endpoint, distinct provenance), long/short and taker volume at 1D | US-903 |
| US-905 | Coin Metrics backfill recipe — MVRV/active addresses/exchange flows via `catalog-v2` `min_time`, empty response never treated as no-history | US-903 |
| US-906 | FRED backfill recipe — chunked initial-release (`output_type=4`) vintages matching live semantics | US-903 |
| US-910 | SoSoValue, DefiLlama (`/stablecoincharts`), and alternative.me backfill recipes (re-identified from US-907, which exhausted all 3 attempts on codex's own account usage quota outage without producing any diff) | US-903 |
| US-908 | Sparkline component — min/max value labels with dates, real time axis with raw points, cadence-tiered minimum-history threshold, explicit insufficient-history state | US-902 |
| US-909 | The adversarial case — sparse-history honesty, and a cross-vendor seam check proving no splice at the backfill/live boundary | US-904, US-905, US-906, US-910, US-908 |
