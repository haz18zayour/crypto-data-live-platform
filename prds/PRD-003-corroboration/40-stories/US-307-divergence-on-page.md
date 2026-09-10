---
id: US-307
title: Divergence reaches the page
priority: 7
touches:
  - web/**
  - tests/test_page_divergence.py
context:
  - AGENTS.md
  - project-documents/20_Design_System.md
---

As the owner, I want to see when two venues disagree, so that the check I paid for is one I can
actually act on.

**This is the PRD's adversarial case.** A divergence that is measured, stored, and never
displayed is a check that exists only in the database — and the whole argument for this PRD was
that the `bar=1D` defect went unnoticed because nothing put it in front of a human.

## Acceptance criteria

- [test: a value whose divergence exceeds tolerance renders visibly differently from one inside tolerance] Not a subtle tint — legibly different
- [test: both venue values and the divergence in bps are shown, not just a warning] "These two disagree" without the numbers is not actionable
- [test: an uncorroborated value is visually distinct from a corroborated one] Absence of disagreement is not agreement
- [test: NOT_CORROBORATED renders as its own state, distinct from both] Per `20_Design_System.md`: never a blank cell
- [test: no averaged or combined value is displayed anywhere] The page must not resolve what the pipeline deliberately did not
- [browser: prds/PRD-003-corroboration/50-evidence/US-307/divergence.png] A screenshot showing a beyond-tolerance divergence with both values

## Notes for the implementer

- Keep it plain. PRD-005 owns the designed dashboard; this story makes divergence **visible**,
  not beautiful.
- Colour carries status and nothing else (`20_Design_System.md`). A divergence is a status.
- Reuse the exhaustive-switch discipline from US-009 so a new corroboration state is a compile
  error rather than a silently unhandled case.
