---
id: US-503
title: The board model — 48 cells from the registry, absence is alarming
priority: 3
touches:
  - web/src/board.ts
  - web/src/board.test.ts
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
  - project-documents/20_Design_System.md
---

As the owner, I want the grid's shape to come from the registry rather than from whatever the
database happened to return, because a grid built from the response can only ever show me what
arrived.

**This is the story the whole PRD turns on.** Everything visual downstream is a rendering of
whatever this model decides, so an error here is invisible and permanent.

The registry has 45 entries. The grid is 12 indicator families across 4 assets — **48 cells**.
The three without entries are `daily_close` for ETH, SOL and BNB.

The tempting rule is "no registry entry, therefore not definable, therefore render it calm and
grey". **That rule re-creates US-412 exactly.** The EMA stack was in the spec, was never
registered, and coverage was blind to it precisely because coverage is generated *from* the
registry. Under the tempting rule a forgotten indicator becomes the most reassuring thing on
the page — the page would lie, in the one direction it exists to prevent.

So the default inverts: **a cell with no registry entry is `NOT_FETCHED` and reads as a
problem.** Only an explicit declaration makes an absence settled, and that declaration is
US-504.

Deriving the axes: the asset comes from the entry's `definable_for`, and the family comes from
stripping the lowercased asset prefix off the key — `bnb_bollinger_upper` gives `BNB` plus
`bollinger_upper`. **The strip is asserted, not defaulted.** A key that does not begin with its
own asset raises. Splitting the key alone works today and, the first time it does not, files a
cell quietly under the wrong row.

## Acceptance criteria

- [test: the board model built from the parsed registry and the four assets yields exactly 48 cells] Counted from the model, with 48 written as families times assets rather than as a literal
- [test: every one of the 48 cells carries a state and none is undefined or empty] No cell may be blank, at the model layer, before any rendering exists
- [test: a family with no registry entry for an asset yields NOT_FETCHED and never NOT_DEFINABLE] The US-412 regression, asserted directly
- [test: a registry key that does not begin with its own lowercased asset throws] Feed a deliberately malformed entry; a silent fallback must fail this
- [test: a cell whose registry entry exists but whose board row is missing is also NOT_FETCHED] Registered but unfetched and unregistered are both absences and neither is settled
- [test: the model maps OK STALE UNAVAILABLE and ERROR rows onto their cells without altering the value] The model arranges, it does not compute
- [cmd: npm --prefix web test] The browser suite passes

## Notes for the implementer

- The family list is derived, not hand-written. A hard-coded array of twelve names is a second
  source of truth that will drift from the registry the first time an indicator is added, which
  is the same class of bug as US-412.
- Do not let a missing row become `0`, `null` rendered as empty, or a dropped cell. Non-negotiable
  1 in `20_Design_System.md`: never render zero for absence.
- No fetching in this module. It takes parsed rows and a parsed registry and returns a model.
  Keeping it pure is what lets every later story test the hard cases without a network.
- `48` in the tests should be computed from the registry, so that adding an indicator family
  later fails loudly in one place rather than silently passing a stale literal.
- **Routed to the default implementer, not Claude.** A pure TypeScript model with behavioural criteria; no design skill applies.
  Every story in this PRD was routed to Claude at first because the design skills are Claude-only;
  that put the whole PRD through one quota and the quota became the bottleneck. Only US-507 and
  US-509 actually need those skills.
