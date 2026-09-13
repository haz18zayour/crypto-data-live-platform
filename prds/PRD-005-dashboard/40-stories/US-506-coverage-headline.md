---
id: US-506
title: The coverage headline — the one line that is the product
priority: 6
agent: claude
touches:
  - web/src/CoverageHeadline.tsx
  - web/src/CoverageHeadline.test.tsx
  - web/src/coverage.ts
context:
  - AGENTS.md
  - project-documents/20_Design_System.md
---

As the owner, I want the top of the page to tell me how much of the board is real before I look
at a single number, because that is the question I open the page to answer.

From `20_Design_System.md`:

> The page's primary object is coverage, not values. That line is the product. Everything below
> it is detail.

The shape, with the four absence reasons kept separate rather than lumped into one "missing"
count:

```
44 of 48 indicators OK   ·   1 stale   ·   3 unavailable
                                            3 not definable · 0 paywalled · 0 fetch failed
```

**The denominator is 48 and it comes from the registry.** A headline that counts the rows the
database returned can only ever say that everything it received is fine. "44 of 44" is
technically true, completely useless, and precisely the reassuring lie this page exists to
prevent.

The four absence reasons stay distinct because they demand different responses. Three not
definable is settled and needs nothing. One fetch failed is someone's afternoon.

## Acceptance criteria

- [test: the headline denominator equals the cell count of the board model and not the number of rows returned] Given a board model missing rows, the denominator must not shrink
- [test: on the mixed fixture the headline reports the correct count for each of the five states] Counted against the fixture, whose composition US-505 fixes
- [test: the per-state counts sum to the denominator] An arithmetic invariant, so no cell can be counted twice or dropped
- [test: the three absence reasons are reported separately and are never summed into one figure] not definable, paywalled and fetch failed each appear with their own number
- [test: a board with every cell OK still shows the denominator and the zero counts] The calm case must look like a measurement, not like an absence of information
- [test: the headline is announced to assistive technology as a single status region] Read as one statement rather than as scattered numbers
- [cmd: npm --prefix web test] The browser suite passes

## Notes for the implementer

- Put the counting in a plain function in `web/src/coverage.ts`, separate from the component, so
  the arithmetic invariant can be tested without rendering anything.
- Do not round, bucket or express this as a percentage. "97% complete" hides which cell is
  missing, and which cell it is is the entire point.
- The word for a zero count is `0`, shown, not omitted. A row that disappears when its count is
  zero makes absence invisible again.
- `font-variant-numeric: tabular-nums` on the figures so they do not shift width when the board
  refetches.
