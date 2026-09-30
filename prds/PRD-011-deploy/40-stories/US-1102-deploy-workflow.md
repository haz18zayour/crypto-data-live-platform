---
id: US-1102
title: Deploy workflow — deploy-web.yml gated on typecheck+test, triggers on push to main, builds with the real VITE_* secrets
priority: 2
touches:
  - .github/workflows/deploy-web.yml
context:
  - AGENTS.md
  - prds/PRD-011-deploy/10-research.md
  - prds/PRD-011-deploy/20-decisions.yaml
---

As the owner, I want a broken build to be structurally incapable of reaching production, so
that a red test suite never ships — confirmed at G1: deploy only after tests pass, with the
workflow run itself standing as evidence, unlike a dashboard-driven Git integration with no CI
record.

## Acceptance criteria

- [test: .github/workflows/deploy-web.yml triggers on push to the main branch] Matches G1's decision that main is production
- [test: the workflow runs npm --prefix web run typecheck and npm --prefix web test (or the equivalent) before any deploy step, and the deploy step is declared with a dependency (needs:, or same-job ordering) on those succeeding] Deploy is structurally gated, not merely ordered by convention
- [test: the workflow's build step passes VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY from GitHub Actions secrets into the Vite build, matching the same variable names already used in .env.local] The deployed bundle gets real, working Supabase configuration
- [test: the workflow's deploy step uses CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID from GitHub Actions secrets, never a hardcoded or committed credential] No credential ever lands in the repo
- [test: the workflow does not run on pushes to any branch other than main] Confirms research's gotcha that wrangler-action deploys whatever branch triggered it unless pinned — a feature-branch push must never become "production"
- [cmd: uv run pytest -q] The full offline suite stays green (this story does not touch Python code, but the gate must still pass)

## Notes for the implementer

- `.uf/config.json`'s `blastRadius` lists CI workflows — this story is blast radius and G4
  applies before merge.
- This story cannot be verified end-to-end against a real Cloudflare deploy yet, since the
  owner's account/API token do not exist until US-1103. Its own criteria are about the
  workflow's structure and gating logic, checkable by reading the YAML and by the dry-run
  validation US-1101 already proved — do not attempt a real deploy here.
- The four new secrets this workflow reads (`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`,
  `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`) do not exist in this repo yet. Reference them
  by name in the workflow; do not invent placeholder values, and do not attempt to set them
  yourself — that is the owner's own action in US-1103.
