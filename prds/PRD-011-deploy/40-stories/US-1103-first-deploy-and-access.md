---
id: US-1103
title: First live deploy — owner completes Cloudflare account/dashboard setup, provides CI secrets; the app is live at a real, public URL
priority: 3
touches:
  - wrangler.jsonc
context:
  - AGENTS.md
  - prds/PRD-011-deploy/10-research.md
  - prds/PRD-011-deploy/20-decisions.yaml
---

As the owner, I want the app actually live at a real Cloudflare Workers URL, so that PRD-011's
brief is real rather than only structurally ready.

**Amended 2026-10-06:** the owner explicitly decided the page may be public — Cloudflare Access
is out of scope for this PRD entirely (see `20-decisions.yaml`'s `amendments:` entry). This
story's scope is now exactly its first two original criteria: real account setup, and a real
live deploy.

This story is almost entirely account/dashboard work only the owner can do — there is no
credential in this project that could automate a Cloudflare account into existing.

## Acceptance criteria

- [human] The owner has: (1) a Cloudflare account, (2) a Cloudflare API token scoped for Workers deploys added as the `CLOUDFLARE_API_TOKEN` GitHub repo secret, (3) the account id added as `CLOUDFLARE_ACCOUNT_ID`, (4) `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` already present as GitHub repo secrets
- [integration: pushing to main triggers deploy-web.yml (US-1107), and the workflow's real run — not a dry run — completes successfully, producing a real reachable *.workers.dev URL that serves the real app (not a blank page)] The Worker is actually live, not just configured

## Notes for the implementer

- Do not attempt to create a Cloudflare account or API token yourself — you have no credentials
  for this.
- This story has no files to touch — it is pure verification once the owner's setup exists.
- Already satisfied as of 2026-10-06: `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` provisioned
  and verified valid; `deploy-web.yml` run 37474353014 succeeded; the live URL
  (`https://crypto-data-live-platform.zayourhassan-1.workers.dev`) returns HTTP 200 with the
  real app's HTML, confirmed by curling it directly. See
  `prds/PRD-011-deploy/50-evidence/US-1103/verdict.json`.
