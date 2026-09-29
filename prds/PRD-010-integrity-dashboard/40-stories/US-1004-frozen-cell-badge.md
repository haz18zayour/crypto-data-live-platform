---
id: US-1004
title: The cell-level frozen badge — "unchanged since <date>" on any cell flagged frozen (directly or via its declared root), OK status unchanged
priority: 3
touches:
  - web/src/CellDetail.tsx
  - web/src/data.ts
  - web/src/Sparkline.tsx
  - web/src/FrozenBadge.tsx
  - web/src/FrozenBadge.test.tsx
context:
  - AGENTS.md
  - prds/PRD-010-integrity-dashboard/10-research.md
  - prds/PRD-010-integrity-dashboard/20-decisions.yaml
---

As the owner, I want a frozen value flagged on the cell itself, not only on a separate page, so
that the integrity problem is visible exactly where the value is actually read — confirmed at G1:
the market value's OK status is never downgraded, since this project makes no judgement about the
number itself, only about whether the pipeline is honestly reporting it.

## Acceptance criteria

- [test: a cell whose own indicator is flagged frozen by US-1002's read renders a badge reading "unchanged since <date>" using the value's real source_timestamp, without changing the cell's OK status colour or icon] Direct case
- [test: a derived cell (its registry entry declares derives_from) whose declared root is flagged frozen renders the same badge, sourced from the root's frozen state, not from an independent check on the derived cell's own values] Propagated case
- [test: a cell whose indicator is not flagged frozen renders no badge] The negative case — no badge is not itself information a user must interpret as "definitely not frozen," it is simply absent when there is nothing to say
- [test: an indicator declaring expected_constant never renders the badge regardless of how long its value has held] The explicit exemption reaches the UI
- [cmd: npm --prefix web test] The web suite stays green
- [cmd: npm --prefix web run typecheck] Typecheck holds
- [browser: load the live board at http://localhost:5174, open a cell whose underlying data currently satisfies the frozen condition (or one manufactured via a short-lived test fixture against a throwaway schema if no live cell currently qualifies), and visually confirm the badge renders with a real date, with no colour or layout change implying a value judgement about the number] Real rendering, not just a passing unit test

## Notes for the implementer

- This story depends on US-1002's migration being applied to production (per that story's own
  gating) before the `[browser:]` criterion above can be judged against real data — if the
  migration has not yet landed in production, that specific criterion cannot be satisfied and
  should not be marked met by inference from the unit tests alone.
- Badge placement and visual weight should match this project's existing "provenance on the face
  of the cell, without a click" discipline from PRD-005/US-508 — additive information, not a
  reflow of the cell's primary value.
- Do not add any colour-coding tied to how long the value has been frozen, or any severity tiering
  beyond the binary flagged/not-flagged state the view already computes — that would reintroduce
  exactly the kind of judgement this project's one rule forbids.
