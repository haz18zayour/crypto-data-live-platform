---
id: US-001
title: <one specific, buildable thing>
priority: 1

# Files this story is expected to change. The verifier uses this to detect a story that
# claimed success while changing nothing, so it must be honest and narrow.
touches:
  - src/**

# Resolved and INLINED into the prompt at compile time. A path that does not exist FAILS
# the build — an agent pointed at a missing file does not error, it silently proceeds
# without the context and never tells you.
context:
  - AGENTS.md
  - project-documents/10_Technical_Architecture.md
  # - project-documents/20_Design_System.md
  # - kb:08-auth-and-identity/README.md
---

As a <user>, I want <capability> so that <outcome>.

Specific enough that a fresh agent can build it without asking a question, and a different
agent can prove it was built.

## Acceptance criteria

<!--
EVERY criterion declares how it will be proven. There is no default — a criterion with no
method is a compile error, by design. "Typecheck passes" as free text was the previous
pipeline's most common criterion: asserted dozens of times, machine-checked never.

  [cmd: <shell>]        exit 0 is met; stdout and exit code are captured as evidence
  [test: <name>]        a named test that must exist and pass
  [integration: <name>] a test driving the ASSEMBLED system through its public entry
                        point. At least one per PRD, or compile fails.
  [browser: <path>]     a screenshot that must exist on disk and be non-empty
  [ci: <check>]         a named CI check green on the pushed commit
  [human]               a person decides — becomes a gate, never an agent judgement
-->

- [cmd: npm run typecheck] The project typechecks with no errors
- [test: <names the behaviour this story adds>] A test covers the new behaviour
- [integration: <the assembled system does something observable>] A test drives the real entry point end to end
- [browser: 50-evidence/US-001/screen.png] The screen renders the new state
- [human] It reads well to a person

## Notes for the implementer

<!-- Gotchas, the specific file to touch, anything the diff should NOT include. -->
