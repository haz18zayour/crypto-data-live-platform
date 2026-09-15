---
id: US-707
title: One ingest run persists all three data categories — pipeline and heartbeat integration
priority: 7
touches:
  - ingest/pipeline.py
  - ingest/heartbeat.py
  - tests/test_persist_board.py
  - tests/test_heartbeat.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want the on-chain entries persisted by the same scheduled run that already
persists the technical board and the derivatives panel, so this PRD does not repeat US-414's
gap (a working computation with no path to the database) or PRD-006's structural near-miss
(entries a persistence filter excludes by construction).

`persist_board` was already generalized in PRD-006 to accept results keyed by registry entry
regardless of `talib_function`. This story extends the same shape to the on-chain entries — no
new filter, no new branch, one persistence path for all three data categories.

## Acceptance criteria

- [test: persist_board accepts on-chain results alongside technical and derivatives results, without an on-chain-specific branch inside it] One persistence path, not three
- [test: a single ingest run writes rows for the technical board, the derivatives panel, and every on-chain entry] Every registered cell, one run, one heartbeat ping
- [test: one on-chain metric's fetch failure does not prevent any other cell — technical, derivatives, or on-chain — from persisting] Matches the per-cell failure isolation established for every prior data category on this board
- [test: the heartbeat still pings success only when the run itself completed, independent of individual cell failures] A single ERROR-status row is not a pipeline failure; a run that raised before completing is
- [integration: a real scheduled run against all live vendors persists all three data categories and the total row count matches the full registry] End to end, the actual cron entry point
- [cmd: uv run pytest -q --no-header -o addopts=] The full offline suite stays green
- [ci: the ingest workflow run completes successfully on the pushed commit] The actual scheduled job, not a local approximation

## Notes for the implementer

- Do not add a second scheduled job. Same reasoning as PRD-006's equivalent story: PRD-012 (not
  yet built) is where a deliberate cadence split gets decided, with its own reasoning — doing it
  accidentally here would pre-empt that.
- Coin Metrics' per-IP rate limit and Helius's per-account rate limit are independent of each
  other and of OKX's — pacing one vendor's calls does not protect against exceeding another's.
  Verify the full run's total call count against each vendor's own documented limit, not just
  the previous data categories' already-proven pacing.
- `.github/workflows/ingest.yml` and `.uf/config.json`'s `blastRadius` both list
  `.github/workflows/**` — if this story needs to touch the workflow file (e.g. to add new
  secrets for Coin Metrics/Helius/Validators.app), that is blast radius and G4 applies.
