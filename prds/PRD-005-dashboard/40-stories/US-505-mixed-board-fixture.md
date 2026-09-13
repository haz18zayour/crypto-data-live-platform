---
id: US-505
title: The mixed board, before any pixels exist to flatter it
priority: 5
agent: claude
touches:
  - web/src/fixtures/mixedBoard.ts
  - web/src/fixtures/mixedBoard.test.ts
  - scripts/no-fixture-in-bundle.mjs
context:
  - AGENTS.md
  - project-documents/25_PRD_Acceptance_Protocol.md
---

As the owner, I want a board carrying every state at once available before the design work
starts, because a page that looks calm when everything works is worth very little.

The acceptance protocol names this PRD's adversarial case: **force a mixed board — OK, STALE,
NOT_DEFINABLE, FETCH_FAILED — and read it at a glance.** Today the real board is 44 OK cells and
one historical error, so designing against reality means designing against the one case that
does not matter.

A natural `STALE` cannot be waited for. `freshness_stale_seconds` is 172800 against a 24-hour
collection cadence, so a cell only goes stale once collection has **already been broken for two
days**. Waiting is not a test plan.

This story comes before the headline and the matrix deliberately. **The mixed board is the
design target and the all-green board is the degenerate case**, and building the fixture
afterwards would mean building it to fit a design that was drawn from the easy case.

The fixture must never reach production. US-009 established a bundle scan as the machine check
for exactly this shape of risk, and the same approach applies here.

## Acceptance criteria

- [test: the fixture contains at least one cell in each of OK STALE NOT_DEFINABLE and FETCH_FAILED] The four states the adversarial case names, present simultaneously
- [test: the fixture has the same 48-cell shape the live board model produces] A fixture with a different shape tests a page that does not exist
- [test: the fixture passes through the real board model rather than being a hand-built render tree] Otherwise it proves the fixture renders, not that the board does
- [test: the fixture cells carry real provenance including vendor and source timestamp] A mixed board with hollow provenance cannot exercise US-508
- [test: the fixture board is reachable only when import.meta.env.DEV is true] Guarded at the module boundary, asserted
- [cmd: node scripts/no-fixture-in-bundle.mjs] Builds the app and fails if a fixture sentinel string appears anywhere in the output bundle
- [cmd: npm --prefix web test] The browser suite passes

## Notes for the implementer

- Give the fixture cells values that are obviously synthetic when read — a stale BTC close of
  11111.11 is unmistakable, 79111.80 is not. If a screenshot of the fixture ever gets mistaken
  for the live board, the numbers should be what gives it away.
- The `NOT_DEFINABLE` cells in the fixture must carry a declared reason, the same way US-504's
  real ones do.
- Include at least one `PAYWALLED` cell too. It is one of the four absence reasons and nothing
  on the live board produces it yet, so the fixture is the only place its rendering can be seen
  before a later PRD needs it.
- The sentinel for the bundle scan should be a string that exists only in the fixture module and
  would survive minification, so the scan cannot pass by accident.
