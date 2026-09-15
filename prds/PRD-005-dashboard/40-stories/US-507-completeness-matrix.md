---
id: US-507
title: The completeness matrix — 48 cells, none of them blank
priority: 7
agent: claude
touches:
  - web/src/BoardMatrix.tsx
  - web/src/BoardMatrix.test.tsx
  - web/src/CellFace.tsx
  - web/src/styles.css
  - web/src/App.tsx
  - web/src/data.ts
context:
  - AGENTS.md
  - project-documents/20_Design_System.md
  - project-documents/11_Data_Model.md
---

As the owner, I want the matrix itself: indicators down, assets across, every cell carrying a
state, so reading a column tells me how complete an asset is and reading a row tells me how
complete an indicator is.

This is the story that replaces the single BTC daily close the page has shown since US-009, and
it is where `board_read` finally gets consumed.

**Native `<table>`, laid out with `table-layout: fixed`.** A dense 12 × 4 grid is exactly the
layout that invites `display: grid` on the table element, and doing that silently strips the row
and column association a screen reader depends on. `role="grid"` is not the way out either — it
obliges the full roving-tabindex keyboard contract, which is strictly more work than keeping
semantics that come free.

**Colour is not the only channel.** `20_Design_System.md` says status is the only thing allowed
to be chromatic, and taken literally that is a WCAG 1.4.1 Level A failure: roughly 8% of men
have a colour vision deficiency, and a status grid whose only cue is a coloured dot is the most
common dashboard accessibility failure there is. Every state carries **a glyph, a word and a
hue**. The design system's intent survives — chroma still means something is notable — it just
stops being load-bearing alone. US-509 corrects the document.

The five faces, from the design system:

| State | Reads as | Feels |
|---|---|---|
| OK | the value | normal |
| STALE | value plus age, dimmed | uneasy |
| UNAVAILABLE / NOT_DEFINABLE | `n/a` plus the declared reason | settled |
| UNAVAILABLE / PAYWALLED | `requires paid tier` | actionable |
| ERROR / FETCH_FAILED | `unavailable` plus the reason | alarming |

## Acceptance criteria

- [test: the matrix renders as a table element with a row header per family and a column header per asset] Queried by ARIA role, so a div pretending to be a table fails
- [test: 48 data cells render and every one has non-empty text content] The bound is 48 and zero blanks; a grid that renders 45 and drops three must fail
- [test: every cell carries a state word and a glyph in addition to its colour class] Remove the stylesheet and the board is still readable
- [test: no cell renders 0 or an empty string for an absent value] Non-negotiable 1 of the design system
- [test: a NOT_DEFINABLE cell and a FETCH_FAILED cell render with different words glyphs and classes] The distinction the whole page exists to make
- [test: the page issues one request to board_read and does not fetch per cell] Asserted on the fetch mock call count
- [test: rendering the mixed fixture produces all five faces at once] The adversarial case, in a test
- [integration: the assembled page loads 48 cells from the live board_read endpoint] Real Supabase, real anon key, no mocked fetch — module-scoped tests cannot see wiring that was never done
- [cmd: npm --prefix web test] The browser suite passes
- [cmd: npm --prefix web run typecheck] The project typechecks

## Notes for the implementer

- Keep `fetchLatestCorroboration` and the corroboration panel working. PRD-003's divergence
  display is proven behaviour and must not regress into a rewrite.
- One honest limitation: jsdom resolves ARIA roles from the element, not from CSS, so the
  role-based assertions above will **not** catch a `display: grid` applied to the table. That
  gap is closed by US-509's real-browser pass. Do not treat the green test as proof the
  semantics survived.
- The cell is a component with one job — turn one board cell into one face. Every state goes
  through it, including OK, so there is no path where a value renders without passing the
  absence logic.
- The integration criterion uses the real `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`, which
  Vite loads from `.env.local`. It must **fail** when they are absent, not skip. A test that
  skips itself when the thing it tests is unavailable is how a suite stays green through an
  outage.
- Do not sort the rows by status. A grid that reorders itself when something breaks makes the
  broken cell harder to find the second time, not easier.
