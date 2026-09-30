---
id: US-1105
title: The adversarial case — a broken build is proven blocked from deploy, the live hostname is proven to reject unauthenticated access, and the owner confirms they can actually open the real dashboard through Access
priority: 5
touches:
  - .github/workflows/deploy-web.yml
context:
  - AGENTS.md
  - project-documents/25_PRD_Acceptance_Protocol.md
  - prds/PRD-011-deploy/10-research.md
---

As the owner, I want this PRD's two hardest claims proven directly, not just asserted by the
individual stories' own narrower checks — the same adversarial discipline every prior PRD in
this project has closed with.

## Acceptance criteria

- [test: deliberately introducing a failing typecheck or test into a throwaway branch/PR and confirming deploy-web.yml's deploy step does not run (or the workflow fails before reaching it)] The gate is real, proven by breaking it on purpose, not assumed from the workflow's own step ordering
- [integration: an unauthenticated HTTP request to the real production hostname, made independently of US-1104's own canary code, confirms the same redirect-to-Access behavior] A second, independent confirmation of the core claim, not a re-run of the same script
- [human] The owner opens the real deployed URL themselves, completes the one-time-PIN login, and confirms the real live dashboard renders — the same board this project has been running locally, now reachable from anywhere the owner opens it
- [cmd: uv run pytest -q] The full offline suite stays green
- [cmd: npm --prefix web test && npm --prefix web run typecheck] The full web suite and typecheck stay green

## Notes for the implementer

- The `[human]` criterion is the one this framework will not let any agent judge. Do not attempt
  to satisfy it with an automated check; leave it for the G6 gate.
- The deliberately-failing-build criterion must actually be run and shown to block deploy, not
  merely inferred from the YAML's `needs:`/ordering — reviewers of prior PRDs' gates in this
  project have accepted "the workflow is structured this way" as insufficient before; prove it.
- If US-1103's real deploy or Access configuration has not happened by the time this story
  runs, say so plainly — the live criteria here cannot be satisfied by inference from the
  earlier stories' offline/dry-run checks alone.
