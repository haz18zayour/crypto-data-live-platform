---
id: US-501
title: The web suite has never been gated — make it run
priority: 1
agent: claude
touches:
  - .uf/config.json
  - .github/workflows/uf-verify.yml
  - scripts/gates-cover-web.mjs
  - web/src/gates.test.ts
context:
  - AGENTS.md
  - project-documents/25_PRD_Acceptance_Protocol.md
---

As the owner, I want the browser tests to actually run in the gates and in CI, because right now
they never have and every guard has been reporting success by skipping.

Measured 2026-09-13:

```
$ test -f package.json && echo YES || echo NO
NO
$ cd web && npm test
Test Files  4 passed (4)
     Tests  13 passed (13)
```

`.uf/config.json` runs its `typecheck` and `test` gates behind `f.existsSync('package.json')`.
`.github/workflows/uf-verify.yml` guards every Node step behind `test -f package.json`. Both
look at the **repository root**. `package.json` has lived in `web/` since US-009.

So thirteen tests have passed only when a human ran them by hand, and in the meantime every
gate and every CI job has come back green by doing nothing. Nothing is broken — they pass — but
**this is the product's own failure mode occurring inside its own harness**, and it is not a
coincidence that it went unnoticed for four PRDs: that is exactly what silent absence does.

Every other story in this PRD is a web story. Until this is fixed, no criterion in PRD-005 means
anything at all.

`npm --prefix web run <script>` is verified to work from the repository root:

```
$ npm --prefix web run typecheck
> tsc -b --pretty false
exit=0
```

**Blast radius.** This touches `.github/workflows/**`. G4 does not fire on its own; it is run
manually before merge.

## Acceptance criteria

- [cmd: node scripts/gates-cover-web.mjs] Executes every gate declared in .uf/config.json and fails unless the web typecheck and the web test run really happened
- [cmd: npm --prefix web test] The 13 browser tests pass when invoked from the repository root
- [test: the gate-coverage script fails when the web project is absent from the gate commands] The script is not a rubber stamp, and this is what proves it
- [test: every node step in the CI workflow guards on the web manifest and none guards on a root manifest] Asserted against the parsed workflow YAML, not against its source text
- [cmd: uv run pytest -q --no-header] The Python suite still passes

## Notes for the implementer

- The gate-coverage script must **run** the gate commands and inspect their real output, not
  read `.uf/config.json` and pattern-match the strings. A gate that claims to run vitest and
  silently does not is the entire subject of this story; a checker that reads the claim rather
  than the behaviour reproduces the bug one level up.
- Parse the workflow with the `yaml` package already in `web`'s dependencies and assert against
  the parsed object. A regex over the file text is how "the registry records X" got satisfied
  twice this project by a comment plus a grep.
- Do not add a root `package.json` to make the existing root guards accidentally true. That
  fixes the symptom by moving the project, and leaves the guards still asserting the wrong
  thing.
- `npm --prefix web test` from the root is the invocation to standardise on. It is measured to
  work.
- Leave the `continue-on-error` integration step alone. Its behaviour is deliberate and belongs
  to a different decision.
