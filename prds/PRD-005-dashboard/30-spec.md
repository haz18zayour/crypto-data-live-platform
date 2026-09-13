---
title: The single page — completeness first
branch: feat/prd-005-dashboard
assumptions:
  - claim: A single `board_read` view keeps the page bounded as history grows.
    tripwire: The view returns more than one row per (indicator_key, asset), or more rows than the registry has entries — the distinct-on ordering is wrong and the page is reading duplicated or stale cells.
    acceptedBy: default
  - claim: Deriving the family by stripping the asset prefix is safe because the strip is asserted.
    tripwire: Any registry key that does not begin with its own lowercased `definable_for` asset. The parser raises rather than filing the cell under the wrong row.
    acceptedBy: default
  - claim: 48 cells is the denominator, not 45.
    tripwire: A rendered grid with fewer than 48 cells, or any blank cell. "At least 45" passes on a grid that drops exactly the three cells the page exists to make visible.
    acceptedBy: default
---

# The single page — completeness first

## What this delivers

The page the owner actually asked for: **one screen where data completeness is the first thing
visible**, backed by the 45 real cells PRD-004 persisted. A coverage headline, then an
assets × indicators matrix in which **no cell is ever blank**, in which `NOT_DEFINABLE` reads as
settled and `FETCH_FAILED` draws the eye, built to Apple-grade direction.

## Why (from research)

Four findings changed the shape of this PRD.

1. **The web test suite has never been gated.** Both the `uf` gates and the CI workflow guard
   their Node steps on `package.json` at the repository root; it lives in `web/`. Thirteen tests
   across four files have passed only when run by hand since US-009 wrote them, and every guard
   reported success by skipping. That is this product's own failure mode inside its own harness,
   and every other story here is a web story, so it goes first.
2. **The denominator must come from the registry, not from the response.** A grid built from
   what the database returned can only show what arrived. A grid built from the registry can
   show what did not. That difference *is* the product.
3. **An unregistered cell must not render as `NOT_DEFINABLE`.** The tempting rule re-creates
   US-412 exactly — a forgotten indicator rendered as the calmest thing on the page. Absence is
   alarming unless the registry declares otherwise, with a reason.
4. **Colour cannot be the only status channel.** `20_Design_System.md` says it should be; taken
   literally that is a WCAG 1.4.1 Level A failure. Every state gets a glyph and a word as well
   as a hue, and the design document is corrected rather than left contradicting itself.

## Approach

One `board_read` view using `distinct on (indicator_key, asset)`, so the response stays at one
row per cell forever. The board model derives a 48-cell cross-product from the parsed registry,
defaults absence to `NOT_FETCHED`, and asserts the asset prefix rather than falling back. The
matrix is a native `<table>` laid out with `table-layout: fixed` — applying `display: grid` to a
table silently destroys row and column semantics and no test here would catch it. See
`20-decisions.yaml`.

**Every story sets `agent: claude`.** Every design skill in this environment is Claude-only, so
a story routed the default way ships a competent generic page. The framework flips the verifier
automatically when the implementer matches the configured verifier, so Codex still grades the
work and the different-vendor rule holds with the roles swapped.

## Data model changes

A new read-only view, `public.board_read`, and a `not_definable` block on one registry entry.
Both are **blast radius** (`**/migrations/**`, `**/registry*`), as is the workflow edit in
US-501 (`.github/workflows/**`). G4 does not fire on its own and is run manually.

No change to the `datapoints` table, its constraints, or RLS.

## Out of scope

Deployment and auth (PRD-011); charts, sparklines and history (PRD-009); frozen-value detection
and the SLA rollup (PRD-010); new indicators, venues or sources; any composite, score, signal or
ranking, permanently; any last-known-good fallback; averaging corroborated venues.

## The adversarial case

**Force a mixed board — `OK`, `STALE`, `NOT_DEFINABLE`, `FETCH_FAILED` at once — and read
completeness at a glance.** A natural `STALE` cannot be waited for: the stale budget is 48h
against a 24h cadence, so it only appears once collection has already been broken for two days.
US-504 builds the fixture that forces it, before any polish exists to flatter.

## Stories

| Story | Title | Depends on |
|---|---|---|
| US-501 | The web suite has never been gated — make it run | — |
| US-502 | `board_read` — one bounded query, latest row per cell | US-501 |
| US-503 | The board model: 48 cells from the registry, absence is alarming | US-501 |
| US-504 | Declared non-definability, so a settled gap reads settled | US-503 |
| US-505 | The mixed board, before any pixels exist to flatter it | US-503 |
| US-506 | The coverage headline — the one line that is the product | US-503 |
| US-507 | The completeness matrix — 48 cells, none of them blank | US-505, US-506 |
| US-508 | Provenance on the face of the cell, without a click | US-507 |
| US-509 | The Apple-grade pass, and the design document corrected | US-507, US-508 |
