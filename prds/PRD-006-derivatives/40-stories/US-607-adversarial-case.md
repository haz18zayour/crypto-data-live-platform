---
id: US-607
title: The adversarial case — a funding-interval change drives its own datapoint's derived interval, not a hardcoded assumption
priority: 7
touches:
  - tests/test_okx_derivatives_fetcher.py
  - prds/PRD-006-derivatives/50-evidence/
context:
  - AGENTS.md
  - prds/PRD-006-derivatives/10-research.md
  - project-documents/25_PRD_Acceptance_Protocol.md
---

As the owner, I want direct proof that this PRD's specific guarantee holds — an instrument's
recorded funding interval reflects its actual current cadence, never an assumption — because
research found a 2026-published practitioner guide making exactly this mistake in print, and a
green test suite proves nothing about a bug the suite's own author didn't think to write a test
for.

Per `25_PRD_Acceptance_Protocol.md`, every PRD's acceptance demonstration needs "an adversarial
case chosen to attack this PRD's specific guarantee" — not a general regression test, a
deliberate attempt to break the one thing this PRD exists to get right.

## Acceptance criteria

- [test: a synthetic funding-rate-history response with a genuine interval change (e.g. three consecutive 8h-spaced settlements, then a switch to 1h-spaced) produces a derived interval matching the newest gap, not the oldest, not an average, and not a hardcoded 8h] The exact scenario OKX's own escalation ladder produces, and the exact bug the 2026 practitioner guide made
- [test: the derived interval for two different assets in the same run can differ] Proves the derivation is per-instrument, not a single value computed once and applied everywhere
- [test: the persisted datapoint's source_field text names the derived interval explicitly] Verifiable by reading the row, not by trusting the code that wrote it — matches this project's provenance-on-the-face discipline
- [human: the owner reads a persisted funding-rate datapoint's provenance detail on the live page and confirms the interval shown matches OKX's actual current settlement cadence for that instrument] The demonstration item the acceptance protocol calls for, not a machine check

## Notes for the implementer

- If a real funding-interval change is observed live in OKX's actual settlement history during
  this story's build window, capture that as the primary evidence (committed alongside the
  synthetic test, not instead of it) — matching how PRD-003's `divergence.png` used a real
  measured case. If none occurs in the window, the synthetic fixture is the adversarial case on
  its own; do not delay this story waiting for a live occurrence that may not happen for weeks.
- This story does not change any production code by itself unless the tests above find a
  defect in US-601's derivation logic — if they pass against the existing implementation
  unmodified, that is the demonstration succeeding, not a sign the story did nothing.
- The `[human]` criterion is the one this framework will not let any agent judge for you. Do not
  attempt to satisfy it with an automated check; leave it for the G6 gate.
