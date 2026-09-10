---
title: Cross-source corroboration
branch: feat/prd-003-corroboration
assumptions:
  - claim: Coinbase's 86400 buckets are UTC-aligned.
    tripwire: Their docs are silent on it. The 59-day measurement is evidence, not proof — a per-venue assertion that hour==minute==second==0 is mandatory and is its own criterion.
    acceptedBy: default
  - claim: 25 bps separates honest basis from real error for BTC-USDT vs BTC-USD.
    tripwire: More than two false positives in a month, or a real defect under 25 bps — either reopens the measurement with a larger sample.
    acceptedBy: default
  - claim: Corroboration defends against a wrong number at one source.
    tripwire: It does not defend against a wrong number in the code reading both. Same wrong offset applied twice gives exactly zero divergence and reports agreement.
    acceptedBy: default
---

# Cross-source corroboration

## What this delivers

The same quantity fetched from two independent venues, compared, with **disagreement surfaced
as a finding** — never averaged, never resolved in favour of a "primary".

## Why (measured, not argued)

US-006 passed 6/6, verified by a different vendor, storing **78,834.1** instead of **79,111.8**
because OKX's default daily bar is UTC+8. Measured 2026-09-10 across 59 UTC days, OKX
`BTC-USDT` 1Dutc vs Coinbase `BTC-USD`:

| | bps |
|---|---|
| median | 7.1 |
| p90 | 10.8 |
| max | 13.8 |
| **the defect** | **35.2** |

The error is 2.5× the worst honest disagreement. A threshold lives in that gap.

## Approach

**One row per venue.** Unique identity becomes
`(indicator_key, asset, source_vendor, source_timestamp)`; divergence is stored separately with
the tolerance that was in force at write time. Both venues are peers — the schema must not be
able to express a preference. See `20-decisions.yaml` for the three rejected shapes.

## Data model changes

**BLAST RADIUS — `**/migrations/**` and `ingest/persist.py`. Manual G4 review before merge,
because the framework's gate does not fire.**

The current upsert identity is `(indicator_key, asset, source_timestamp)`
(`ingest/persist.py:66-73`), so **two venues collide and the second write silently UPDATEs the
first**, losing a number with no error. The migration extends the identity and adds a
`corroborations` record holding `divergence_bps`, `tolerance_bps_at_write`, `status`, and the
two row ids.

PRD-002's contract and golden harness must be **re-run** against the new identity, not assumed.

## Out of scope

Averaging, medians, "primary wins", any silent reconciliation; a third venue; new indicator
families; automatic threshold tuning; UI redesign (PRD-005).

## The adversarial case

Feed two venues that disagree beyond tolerance and show the divergence **reaching the page** —
not averaged, not hidden, not silently preferring one.

## Stories

| Story | Title | Depends on |
|---|---|---|
| US-301 | Schema: two venues as peers, divergence stored with its tolerance | — |
| US-302 | Coinbase fetcher — fields by name, UTC alignment asserted per venue | — |
| US-303 | Timestamp equality gates the comparison | US-302 |
| US-304 | Divergence computed and stored against the registry tolerance | US-301, US-303 |
| US-305 | A missing bar at the second venue is NOT_CORROBORATED, not an error | US-304 |
| US-306 | Single-source indicators are marked uncorroborated, visibly | US-304 |
| US-307 | Divergence reaches the page | US-304 |
