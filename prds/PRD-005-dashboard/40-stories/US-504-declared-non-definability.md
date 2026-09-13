---
id: US-504
title: Declared non-definability, so a settled gap reads settled
priority: 4
agent: claude
touches:
  - ingest/registry.yaml
  - ingest/registry.py
  - tests/test_registry_not_definable.py
  - web/src/board.ts
  - web/src/board.test.ts
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
  - project-documents/20_Design_System.md
---

As the owner, I want an absence that will never be filled to say so, with its reason, because
otherwise the only way to make it stop nagging is to stop trusting the page.

US-503 made every gap alarming. That is the right default and the wrong final answer for
`daily_close`, which is declared BTC-only on purpose. Three of the 48 cells are permanently
empty by design and should read as **settled**, not as three things that are broken.

`definable_for` cannot carry this. It is per-key and names the assets a key *does* cover; it
says nothing about the assets it does not, and it cannot distinguish "deliberately excluded"
from "nobody has written this yet". That ambiguity is the whole problem.

So the declaration is explicit: a `not_definable` block on the family's existing entry, naming
the assets and the reason — one registry edit, not 45. A reason is mandatory. An unexplained
`NOT_DEFINABLE` is indistinguishable from a shrug, and in six months nobody will remember which
it was.

**Blast radius.** `**/registry*`. G4 does not fire on its own; it is run manually before merge,
together with US-502's migration.

## Acceptance criteria

- [test: the parsed registry entry for btc_daily_close declares ETH SOL and BNB not definable each with a non-empty reason] Read from the parsed IndicatorDefinition, never from the YAML text
- [test: a not_definable entry with a missing or empty reason is rejected by the registry model] The reason is load-bearing, so the schema has to require it
- [test: the board model renders those three cells as NOT_DEFINABLE carrying the declared reason unchanged] The words the registry chose are the words the page shows
- [test: with the declaration removed those three cells return to NOT_FETCHED] Proves the declaration is doing the work and the cells are not settled for some unrelated reason
- [test: an asset listed in both definable_for and not_definable is rejected] A contradiction in the registry must be a load error, not a race between two code paths
- [test: registry coverage still passes across all 45 entries] The PRD-002 invariant holds
- [cmd: uv run pytest -q --no-header] The Python suite passes
- [cmd: npm --prefix web test] The browser suite passes

## Notes for the implementer

- The reason is prose for a human reading the page, not an enum. `daily_close` is BTC-only
  because this board declares it so, and that is what it should say — do not invent a
  chain-level justification that is not true.
- Declare nothing else as not definable in this story. Every other gap on the board today is a
  real gap and must keep drawing the eye.
- `ingest/registry.py` is the schema; extend the pydantic model so an unparseable declaration
  fails at load, not at render.
- The web side reads the same registry file that Python does. Do not introduce a second
  hand-maintained list of exclusions for the browser.
