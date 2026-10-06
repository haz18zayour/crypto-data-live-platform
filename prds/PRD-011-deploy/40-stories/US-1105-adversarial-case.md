---
id: US-1105
title: The adversarial case — a broken build is proven blocked from deploy, and the owner confirms they can open the real public dashboard
priority: 5
touches:
  - .github/workflows/deploy-web.yml
context:
  - AGENTS.md
  - project-documents/25_PRD_Acceptance_Protocol.md
  - prds/PRD-011-deploy/10-research.md
  - prds/PRD-011-deploy/20-decisions.yaml
---

As the owner, I want this PRD's one remaining hard claim proven directly, not just asserted by
the individual stories' own narrower checks — the same adversarial discipline every prior PRD
in this project has closed with.

**Amended 2026-10-06:** Cloudflare Access is out of scope for this PRD (owner decision — the
page is public by choice). The two Access-rejection criteria this story originally had are
dropped; the build-gate proof is unaffected (it has nothing to do with Access) and remains in
full scope. The final `[human]` criterion is replaced with the public equivalent.

## Acceptance criteria

- [test: deliberately introducing a failing typecheck or test into a throwaway branch/PR and confirming deploy-web.yml's deploy step does not run (or the workflow fails before reaching it)] The gate is real, proven by breaking it on purpose, not assumed from the workflow's own step ordering
- [human] The owner opens the real deployed public URL (`https://crypto-data-live-platform.zayourhassan-1.workers.dev`) directly, no login, and confirms the real live dashboard renders — the same board this project has been running locally, now reachable from anywhere
- [cmd: uv run pytest -q] The full offline suite stays green
- [cmd: npm --prefix web test && npm --prefix web run typecheck] The full web suite and typecheck stay green

## Notes for the implementer

- The `[human]` criterion is the one this framework will not let any agent judge. Do not attempt
  to satisfy it with an automated check; leave it for the G6 gate.
- The deliberately-failing-build criterion must actually be run and shown to block deploy, not
  merely inferred from the YAML's `needs:`/ordering — reviewers of prior PRDs' gates in this
  project have accepted "the workflow is structured this way" as insufficient before; prove it.
