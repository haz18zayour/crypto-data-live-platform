---
id: US-1009
title: Coverage codegen — a literal IndicatorKey union generated from registry.yaml, exhaustive UI wiring, a substance-checking coverage test
priority: 2
touches:
  - scripts/generate_indicator_keys.py
  - web/src/registry.generated.ts
  - tests/test_registry_codegen.py
  - web/src/registry.ts
context:
  - AGENTS.md
  - prds/PRD-010-integrity-dashboard/10-research.md
  - prds/PRD-010-integrity-dashboard/20-decisions.yaml
---

As the owner, I want an indicator that is missing UI or test wiring to fail the build, so that
"every indicator is covered" is a compiler/test error rather than a convention someone can forget —
research found `web/src/registry.ts` currently loads `registry.yaml` at runtime via `?raw` +
`parse()`, making every indicator key a plain `string` to the TypeScript compiler today, so no
mapped-type exhaustiveness check can see a new key.

Research's own blind-spot finding: a coverage gate phrased as "every indicator has wiring" can be
satisfied by a placeholder — a golden file copied from another indicator, an `it.todo`, a
`// @ts-expect-error` — that proves a key exists in a mapping without proving anything real is
asserted. This story's coverage test must check substance, not presence, or it reproduces the exact
"self-audit that doesn't audit" failure this PRD's own title warns against.

## Acceptance criteria

- [test: a Python codegen script reads registry.yaml and emits web/src/registry.generated.ts containing a literal `export const INDICATOR_KEYS = [...] as const` and a derived `IndicatorKey` union type, covering every key currently in the registry] The generated file exists and is complete
- [test: a pytest asserts the committed registry.generated.ts is byte-identical to what the codegen script would produce from the current registry.yaml right now] A stale generated file is caught, not silently trusted
- [test: removing or renaming a key in a test copy of registry.yaml and regenerating changes the emitted union, proving the codegen actually reflects the registry rather than being hand-maintained] The generation is real, not a static file someone edits by hand
- [test: a pytest asserts every key in the generated union has a corresponding golden fixture file, and that at least two different indicators' golden fixtures are not byte-identical to each other] Catches a copy-pasted placeholder golden, not just its presence
- [test: a pytest asserts every key in the generated union is referenced by name in at least one test function across the test suite] Catches an `it.todo` or an empty test shell — the key must appear in something that actually runs
- [test: at least one existing UI mapping (e.g. the cell-detail or sparkline component's per-indicator configuration) is rewritten as `{[K in IndicatorKey]: ...}` and demonstrably fails tsc when a key is manually removed from the mapping in a throwaway diff] The compile-time exhaustiveness check is real, proven by breaking it on purpose
- [cmd: uv run pytest -q] The full offline suite stays green
- [cmd: npm --prefix web run typecheck] The exhaustive mapping compiles cleanly against the real, current registry

## Notes for the implementer

- Decide where codegen runs (a `npm run` pre-build step, a checked-in generated file verified by
  the pytest above, or both) and document the choice — either is acceptable as long as staleness is
  caught by a test, per the story's own criteria.
- "Demonstrably fails tsc when a key is manually removed" should be proven as part of the story's
  own evidence (e.g. a documented local repro), not asserted without having actually run it — this
  project's verification discipline requires showing the negative case actually fires, not assuming
  it would.
- This story does not require every existing UI file to be rewritten with the exhaustive mapping —
  pick the highest-value existing per-indicator UI mapping to convert as the proof, and leave a
  clear pattern for US-1004/US-1005 (and future stories) to follow for their own new per-indicator
  UI surfaces.
