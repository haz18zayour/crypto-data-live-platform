---
id: US-508
title: Provenance on the face of the cell, without a click
priority: 8
touches:
  - web/src/CellFace.tsx
  - web/src/CellFace.test.tsx
  - web/src/CellDetail.tsx
  - web/src/styles.css
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
  - project-documents/20_Design_System.md
---

As the owner, I want to see where a number came from and when, without clicking anything,
because a value whose source I have to go looking for is a value I end up trusting by habit.

Non-negotiable 3 of the design system: **provenance is visible without a click** — the vendor,
and the source timestamp. Non-negotiable 2: **a stale value is shown, never shown as current**,
with its age on the face of it.

Both are already enforced at the database layer. `datapoints` carries `source_vendor`,
`endpoint`, `source_field`, `fetched_at` and `source_timestamp` on every row, and the
`value_iff_ok` and `reason_required` constraints make a value without provenance unstorable.
This story is about the last few centimetres, where all of that either reaches the eye or
quietly does not.

The distinction worth holding onto: `fetched_at` is when *we* asked, `source_timestamp` is what
the *venue* said the bar closed at. They are different questions and the second one is the one
that matters. PRD-001 stored a Hong Kong day close as a UTC one and passed six of six criteria;
a human reading a timestamp is what caught it. Putting that timestamp where a human will read it
is not decoration.

Full detail — endpoint, source field, fetch time, corroboration — goes one interaction deeper.

## Acceptance criteria

- [test: every OK and STALE cell shows its vendor and its source timestamp with no interaction] Asserted on the initial render, before any click or hover
- [test: a STALE cell shows its age in the same glance as its value] Age on the face, per non-negotiable 2
- [test: the timestamp shown is source_timestamp and not fetched_at] Given a cell where the two differ, the venue time is the one on the face
- [test: an ERROR cell shows its reason and shows no number at all] Absence never becomes a value
- [test: a cell with a reference period distinct from its publication date shows both] The lagged-series rule, ahead of the macro panel that will need it
- [test: opening a cell reveals endpoint source field and fetch time] The detail exists; it is just not the first thing
- [test: the detail view can be opened and closed by keyboard alone] It is part of the page, not a mouse feature
- [cmd: npm --prefix web test] The browser suite passes

## Notes for the implementer

- Timestamps render in UTC with the zone shown. This project has already been bitten once by a
  timestamp that looked right in the wrong zone, and localising it to the viewer would recreate
  exactly the ambiguity that cost PRD-001 a day.
- Vendor and timestamp must survive the dense layout. If they do not fit, the answer is a
  smaller type scale or a tighter row, not hiding them behind a hover — a hover does not exist
  on a phone and does not exist for a keyboard.
- `title` attributes are not provenance. They are invisible to touch, unreliable for screen
  readers, and cannot be screenshotted at the checkpoint.
- The lagged-series criterion has no live data behind it yet. Drive it from a fixture cell; the
  macro panel arrives in PRD-008 and should find this already working.
- **Routed to the default implementer, not Claude.** Every criterion here is behavioural; US-509 does the visual pass.
  Every story in this PRD was routed to Claude at first because the design skills are Claude-only;
  that put the whole PRD through one quota and the quota became the bottleneck. Only US-507 and
  US-509 actually need those skills.
