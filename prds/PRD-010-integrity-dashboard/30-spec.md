---
title: Integrity dashboard — the self-audit that actually audits
branch: feat/prd-010-integrity-dashboard
assumptions:
  - claim: Soda Core's freshness syntax runs correctly against Postgres the way dbt source freshness does.
    tripwire: UNVERIFIED, sourced from search-result summaries. Irrelevant under the chosen pure-SQL-views approach (Option C rejected); record only in case a future story reconsiders it.
    acceptedBy: default
  - claim: alternative.me's Fear & Greed index updates at most once per day, so day-to-day repetition of the same integer is expected and should be declared expected_constant rather than flagged frozen.
    tripwire: UNVERIFIED — our fetcher's exact update granularity was not confirmed live. Check fetched_at spread on already-persisted rows before setting the registry declaration; do not assume daily without checking.
    acceptedBy: default
  - claim: No current fetcher rounds a value on the vendor side in a way that makes real movement read as bit-for-bit identical, and no float64 TA-Lib recomputation produces a spurious last-ULP difference that makes a genuinely frozen value read as changed.
    tripwire: UNVERIFIED in both directions. Spot-check a real indicator's persisted history for either failure mode before committing to exact `=` equality; if found, document a per-indicator epsilon rather than picking one silently during implementation.
    acceptedBy: default
---

# Integrity dashboard — the self-audit that actually audits

## What this delivers

A second, independent read of the board's own honesty: a frozen-value badge on any cell whose
current value has stopped changing while still reporting OK (the exact failure a range check
cannot see, since a stuck value sits comfortably inside normal bounds), a per-source freshness
rollup computed from real data age rather than from whether a scheduled job happened to run, and a
build-time coverage gate that fails when a registry indicator lacks real UI/test wiring — not just
a mapping-key placeholder.

## Why (from research and this gate's own findings)

Four findings are load-bearing.

1. **A range check cannot see a frozen value, because the value never leaves its normal band.**
   42.0°C reads as healthy on every existing check this project has; the only way to catch a vendor
   silently repeating its last response is to look at whether the value moves at all, over real
   distinct observations — never over repeated fetches, since a re-fetch of the same
   `source_timestamp` updates the existing row in place rather than inserting a new one
   (`persist.py`'s upsert key is `(indicator_key, asset, source_vendor, source_timestamp)`).
2. **Some values are legitimately constant, and a naive global threshold would itself become a
   judgement about the market.** OKX funding rate clamps to 0.01% for many consecutive 8-hour
   intervals in a calm market; Fear & Greed and monthly macro series repeat by design. The registry
   must let an indicator declare "constant runs are expected here" explicitly, with a reason, rather
   than have the detector guess.
3. **~70% of the board is TA-Lib-derived, and a naive per-indicator frozen check would certify most
   of it healthy during exactly the failure this PRD exists to catch.** A frozen daily close makes
   Wilder/EMA-smoothed outputs (RSI, EMA, Bollinger, MACD, ATR) converge smoothly toward a constant
   rather than repeat identically bar to bar — they never trip an identical-value check on
   themselves. Detection has to run on the root price/rate series a technical indicator is actually
   computed from, then propagate to every indicator that depends on it.
4. **The integrity panel can share the exact failure mode it audits.** It reads through the same
   `datapoints` table, the same PostgREST layer, and the same browser poll/cache as the board it is
   checking. If any of those layers serves stale data, the panel can report "all green" from old
   data — the same silent-staleness failure this whole PRD exists to catch, just one layer up. The
   panel needs its own server-clock "computed at T" stamp, checked against the browser's own clock.

A fifth finding shapes the coverage story specifically: **a gate phrased as "every indicator has
wiring" can be satisfied by a placeholder** (a golden file copied from another indicator, an
`it.todo`, a `// @ts-expect-error`) that proves a key exists in a mapping without proving anything
is actually asserted. The coverage test has to check substance — a real, unique-per-indicator
golden fixture and a named test that exists — or this PRD reproduces the "self-audit that doesn't
audit" its own title warns against.

## Approach

**Registry gains two declarations, both required, neither defaulted.** Every `IndicatorDefinition`
gains a frozen-detection declaration — either `frozen_after_observations: <int>` (the number of
consecutive distinct-`source_timestamp` OK rows with an identical value before flagging) or
`expected_constant: <reason>` (an explicit exemption, e.g. funding rate clamped near zero, Fear &
Greed's bounded daily integer) — and every TA-Lib-derived entry gains `derives_from: <indicator
key>` naming the root series it is computed from, so frozen detection runs once on the root and
propagates to every dependent. Entries with a wall-clock `source_timestamp` (DefiLlama stablecoin
supply, validators.app — confirmed live to set `source_timestamp = fetched_at` /
`datetime.now(UTC)`) gain `freshness_unmeasurable: <reason>`, so the rollup never reports a green
SLA state it cannot actually measure. A coverage test fails the build if any entry lacks its
required frozen declaration, or if a TA-Lib entry lacks `derives_from`, or if `derives_from` names
a key that does not exist in the registry.

**A read-only integrity view/RPC, outside the ingest path.** Two things are computed per
indicator/asset/vendor, purely from already-persisted `datapoints` rows and the registry's own
declarations — nothing is written back into the write path that ingest already owns:
- **Freshness state** — `source_timestamp` age versus the registry's existing
  `freshness_warn_seconds`/`freshness_stale_seconds`, or `unmeasurable` for entries carrying
  `freshness_unmeasurable`. Computed at read time from data age, never from whether a scheduled
  workflow ran — a dropped GitHub Actions run shows up as ageing data instead of being invisible.
- **Frozen state** — for a root indicator (no `derives_from`), the latest
  `frozen_after_observations` consecutive *distinct-`source_timestamp`* OK rows compared for
  bit-identical value; for a dependent indicator, its declared root's own frozen state. An entry
  with `expected_constant` is never flagged, regardless of how long its value has held.

No new `datapoint_status` enum value. The view is additive and lives entirely outside `persist.py`,
so a stopped ingest pipeline cannot silently stop its own audit the way an ingest-time detector
would. This view is a genuine migration (new SQL objects in the production database) and follows
this project's established blast-radius discipline: written, reviewed, and applied to production
with the owner's explicit sign-off before any story built on top of it can be judged met.

**Every integrity read carries a server-clock `computed_at` stamp.** The frontend compares it
against its own clock and renders a distinct "integrity check itself is stale" state rather than
silently trusting a green panel that is itself old — the panel's answer to its own blind spot.

**The frozen badge lives on the cell, not buried on a separate page.** A cell whose value (or whose
declared root, if the cell is derived) is currently flagged frozen shows a small badge —
"unchanged since &lt;date&gt;" — without downgrading the cell away from OK. The market value itself
is untouched; the integrity fact is additive, exactly like every other honest-absence state this
project already renders.

**A per-source freshness rollup**, aggregating the same view by vendor, shows each source's real
data age against its threshold. Healthchecks.io's own up/grace/down status is explicitly not pulled
into this rollup in v1 — Postgres-computed data age is the ground truth, and Healthchecks remains
its own separate, independent dead-man's-switch, unchanged.

**Coverage becomes a compiler error, not a convention.** A codegen step (run in CI, checked for
currency by a pytest) emits a literal `IndicatorKey` union from `registry.yaml`, so `web/src/`'s
per-key UI wiring — written as `{[K in IndicatorKey]: ...}` mapped types — fails `tsc -b` when a
key is missing. The coverage pytest goes further than "the key exists in a mapping": it asserts
each key's golden fixture hash is unique (catching a copy-pasted placeholder) and that a named test
referencing that key actually exists.

## Data model changes

**Real, and blast radius.** A migration adds one or more SQL views/functions (frozen state,
freshness rollup, the `computed_at`-stamped integrity read) reading `public.datapoints` and taking
the registry's per-indicator declarations as parameters or a companion reference table. No existing
column, constraint, or `datapoint_status` value changes; the migration is purely additive and must
be applied to production with the owner's explicit sign-off before any UI or test built on top of
it can be judged met — the same discipline PRD-009's `origin` column and `history_read` RPC
followed.

`registry.yaml`/`ingest/registry.py`'s `IndicatorDefinition` gains three new optional-but-validated
fields: `frozen_after_observations: int | None`, `expected_constant: str | None` (mutually
exclusive with the former; exactly one required), `derives_from: str | None` (required for every
`talib_function`-carrying entry, validated against existing keys), and `freshness_unmeasurable: str
| None`. None of this is a database migration — it is a repo-tracked config change enforced by a
coverage test, exactly like every other registry field this project already requires.

## Out of scope

Restated from `00-brief.md` and confirmed at G1: no new `datapoint_status` enum value; no adoption
of dbt or Soda Core as a second toolchain; no fix to the two wall-clock-stamped fetchers'
underlying `source_timestamp` semantics (their rollup state moves from a false green to an honest
`unmeasurable` — re-plumbing their real observation-time semantics is separate future work); no
Healthchecks.io Management API integration in v1; no cross-indicator or cross-asset integrity
comparison — this project's permanent no-composite-score rule applies to the integrity layer
exactly as it does to market data.

## The adversarial case

**A real frozen sequence, injected into a throwaway schema, must trip the flag** — not a fixture
that could never occur in production (the upsert key means "N identical rows" only ever happens
over distinct advancing `source_timestamp`s with an unchanging value, never over repeated fetches
of the same timestamp). **A derived indicator's frozen root must propagate**: freeze a root series,
confirm at least one of its TA-Lib-derived dependents (which would never trip its own independent
identical-value check, since Wilder/EMA smoothing keeps moving toward the frozen input) shows the
badge via its declared `derives_from` link. **A wall-clock-stamped fetcher must never show green**:
confirm DefiLlama stablecoin supply or validators.app renders `unmeasurable` on the freshness
rollup, never a false-comfort OK. **A stale integrity read must be visible as stale**: force the
browser's clock check against an old `computed_at` and confirm the panel shows its own staleness
rather than silently trusting old data. **The coverage gate must reject a placeholder**: attempt to
satisfy it with a copy-pasted golden fixture or an `it.todo` and confirm the build still fails —
proving the gate checks substance, not presence.

## Stories

| Story | Title | Depends on |
|---|---|---|
| US-1008 | Registry schema extension — `frozen_after_observations`/`expected_constant`, `derives_from` for every TA-Lib entry, `freshness_unmeasurable` for the two wall-clock fetchers, enforced by a coverage test | — |
| US-1002 | Integrity migration — frozen-state and freshness views/RPC computed outside the ingest path, root-only frozen detection with dependent propagation via `derives_from`, applied to production before any story below runs | US-1008 |
| US-1003 | Integrity read carries a server-clock `computed_at` stamp; the frontend compares it against its own clock and renders a distinct stale-panel state | US-1002 |
| US-1004 | The cell-level frozen badge — "unchanged since &lt;date&gt;" on any cell whose value or declared root is currently flagged, OK status unchanged | US-1002 |
| US-1005 | The per-source freshness rollup panel — real data age vs. threshold per vendor, wall-clock-stamped sources rendered `unmeasurable`, never green | US-1002 |
| US-1006 | Coverage codegen — a literal `IndicatorKey` TypeScript union generated from `registry.yaml`, per-key UI wiring as exhaustive mapped types, a pytest asserting the generated file is current and every key has a real, uniquely-hashed golden fixture and a named test | US-1008 |
| US-1007 | The adversarial case — a real frozen sequence trips the flag, a derived indicator inherits its root's frozen state, a wall-clock fetcher never shows green, a stale integrity read is visible as stale, and the coverage gate rejects a placeholder | US-1002, US-1003, US-1004, US-1005, US-1006 |
