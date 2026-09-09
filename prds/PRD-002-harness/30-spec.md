---
title: Determinism and contract harness
branch: feat/prd-002-harness
assumptions:
  - claim: TA-Lib is not yet a dependency, so the unstable-period hazard is preventable rather than present.
    tripwire: Any story adding TA-Lib must add the autouse fixture asserting the default unstable period in the same commit.
    acceptedBy: default
  - claim: The canary's live shape check can ride along in the PRD-012 6h canary job.
    tripwire: If PRD-012 is deprioritised, this PRD ships its own scheduled job rather than dropping the check.
    acceptedBy: default
  - claim: Exact float equality is workable for goldens because inputs are fixed and the code is deterministic.
    tripwire: Any cross-platform float discrepancy — then introduce a tolerance and record why.
    acceptedBy: default
---

# Determinism and contract harness

## What this delivers

The machinery every later indicator inherits, built before there are twenty of them to
retrofit. Three guarantees, each enforced by a mechanism rather than a convention.

## Why (from research)

`10-research.md` corrected the brief on a load-bearing point, so the shape of this PRD changed:

1. **TA-Lib settles the formula, not history-independence.** EMA, RSI, ATR, ADX, CMO, DX,
   KAMA, T3 and ~14 others carry an *unstable period* — the same bar computed over 500 bars of
   history differs from the same bar over 5000, **at the final bar**, converging rather than
   snapping. Pinning `(bars, window)` is therefore **not** determinism. The contract must be
   *exactly N bars*.
2. **Cassettes cannot detect vendor drift.** They replay the recording forever. The brief's
   guarantee 2 was structurally impossible as written; detecting drift needs a live check.
3. **A self-generated golden blesses the bug.** US-006 passed 6/6, verified by a different
   vendor, while storing a Hong Kong day close. A golden produced by the code under test would
   have made that permanent.

## Approach

Extend PRD-001's existing test idiom — `httpx.MockTransport`, committed JSON goldens, pydantic
— plus one live drift canary. Rejected: a full `pytest-regressions` + `pytest-recording` +
Hypothesis stack, which drags pandas and numpy into an ingestion package that has neither. See
`20-decisions.yaml`.

## Data model changes

One additive registry field: `required_bars`. No `datapoints` schema change, so **not**
blast-radius.

## Out of scope

New indicators, assets or vendors; cross-source corroboration (PRD-003); UI; adopting pandas,
numpy or new test frameworks; backfilling or repairing gaps in any form.

## Stories

| Story | Title | Depends on |
|---|---|---|
| US-201 | Bar-slice contract — exactly N bars, or an error | — |
| US-202 | Golden-file determinism, with an externally-computed oracle | US-201 |
| US-203 | Vendor response models that reject a reshape | — |
| US-204 | Parsing pinned against recorded vendor shapes | US-203 |
| US-205 | A truncated fetch is an error, never a shorter series | US-203 |
| US-206 | Live drift canary — validates shape, writes nothing | US-203 |
| US-207 | Integrity coverage generated from the registry | US-201 |
