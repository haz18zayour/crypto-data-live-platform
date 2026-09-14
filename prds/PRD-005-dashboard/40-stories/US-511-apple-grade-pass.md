---
id: US-511
title: The Apple-grade pass, and the design document corrected
priority: 9
agent: claude
touches:
  - web/src/styles.css
  - web/src/BoardMatrix.tsx
  - web/src/CellFace.tsx
  - web/src/CoverageHeadline.tsx
  - web/package.json
  - scripts/capture-board.mjs
  - project-documents/20_Design_System.md
context:
  - AGENTS.md
  - project-documents/20_Design_System.md
---

**Re-identified from US-509.** All three US-509 attempts died on a Claude session rate limit —
HTTP 429, `You've hit your session limit`. Attempt 1 got a long way first and its work is
already committed: the stylesheet rewrite, the matrix changes, the design-document correction,
`scripts/check-design-doc.mjs` and a mixed-board dev page. **What is missing is the real-browser
half** — Playwright, the capture script, the three screenshots, and the greyscale and
narrow-width tests. Build on what is there rather than starting the design over.

As the owner, I want the page to look like something made deliberately, and I want a real
browser to prove the things jsdom cannot.

Two jobs, and they belong together because the second is what makes the first checkable.

**The design pass.** Apple-grade: restrained, dense, legible. Forty-eight cells on one screen
without it feeling like a trading terminal. Generous type scale, tight vertical rhythm, few
rules and borders. Colour carries meaning and nothing else carries colour — but never alone.
No decoration that could be mistaken for data: no sparkline flourishes on values with no
history, no gauges implying precision the source does not have. Dark and light both first-class,
the viewer's system setting decides.

**Use the skills.** `open-design-local:apple-hig`, `taste-skill`, `color-expert`,
`ui-ux-pro-max`, then `design-review` for the audit. They are the reason this story is routed to
Claude — Codex cannot invoke any of them, and a design story routed the default way ships a
competent generic page.

**The real browser.** US-507 noted an honest gap: jsdom resolves ARIA roles from the element,
not from CSS, so nothing in the suite so far would catch a `display: grid` applied to the table
and silently destroying row and column semantics. A headless Chromium closes it, and the same
script produces the screenshots the acceptance checkpoint needs.

**The document correction.** `20_Design_System.md` currently says status is the only thing
allowed to be chromatic, which taken literally is a WCAG 1.4.1 Level A failure. It also still
attributes this work to PRD-008, from before the roadmap moved it. Both get fixed, because a
design document that contradicts the design is worse than no document.

## Acceptance criteria

- [browser: prds/PRD-005-dashboard/50-evidence/US-511/board-live-light.png] The live board, light theme, captured from a real browser
- [browser: prds/PRD-005-dashboard/50-evidence/US-511/board-live-dark.png] The live board, dark theme
- [browser: prds/PRD-005-dashboard/50-evidence/US-511/board-mixed-light.png] The mixed fixture board, showing all five faces at once — the adversarial case, photographed
- [cmd: node scripts/capture-board.mjs --check-semantics] In a real browser, asserts the matrix resolves to an accessible table with 12 row headers 4 column headers and 48 cells
- [cmd: node scripts/capture-board.mjs --check-contrast] Fails on any axe-core violation of colour-contrast or of use-of-colour on the rendered board
- [test: every state face is distinguishable with colour removed] Rendered greyscale, the glyph and the word still separate all five states
- [test: the board is readable at 400px wide with no horizontal scrolling of the page body] The matrix may scroll inside its own container; the page may not
- [cmd: node scripts/check-design-doc.mjs] The design document no longer claims colour is the sole status channel, records the glyph-and-word rule, and names PRD-005 rather than PRD-008
- [cmd: npm --prefix web test] The browser suite passes
- [cmd: npm --prefix web run typecheck] The project typechecks

## Notes for the implementer

- Chromium is already downloaded to the local Playwright cache, so the install step should be
  fast. Pin the Playwright version rather than floating it.
- The capture script starts the dev server itself, waits for the board to render real rows, and
  shuts it down. A screenshot of a loading spinner satisfies the file checks and proves nothing,
  so wait on a cell being present, not on a timeout.
- Do not restyle the corroboration panel out of existence. PRD-003's divergence display is
  proven behaviour and its presence on the page is a requirement, not a leftover.
- Greyscale is the fastest honest test of whether colour is load-bearing. If two states become
  indistinguishable, the fix is a different glyph or a different word, not a stronger hue.
- Restraint is the brief. If a choice is between an effect and nothing, choose nothing — this
  page is read on the days something is wrong, and decoration costs legibility exactly then.
