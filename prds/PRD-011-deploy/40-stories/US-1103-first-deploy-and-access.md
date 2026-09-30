---
id: US-1103
title: First live deploy and Cloudflare Access configuration — owner completes account/dashboard setup, provides CI secrets, applies Access at scope "all traffic"
priority: 3
touches:
  - wrangler.jsonc
context:
  - AGENTS.md
  - prds/PRD-011-deploy/10-research.md
  - prds/PRD-011-deploy/20-decisions.yaml
---

As the owner, I want the app actually live at a real Cloudflare Workers URL with Access
protecting it, so that PRD-011's brief is real rather than only structurally ready.

This story is almost entirely account/dashboard work only the owner can do — there is no
credential in this project that could automate a Cloudflare account or Zero Trust org into
existing. Confirmed at G1: the owner does this directly.

## Acceptance criteria

- [human] The owner has: (1) a Cloudflare account with a Zero Trust org (team domain) created, (2) a Cloudflare API token scoped for Workers deploys added as the `CLOUDFLARE_API_TOKEN` GitHub repo secret, (3) the account id added as `CLOUDFLARE_ACCOUNT_ID`, (4) `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` added as GitHub repo secrets with the same real values already in `.env.local`
- [integration: pushing to main triggers deploy-web.yml (US-1107), and the workflow's real run — not a dry run — completes successfully, producing a real reachable *.workers.dev URL] The Worker is actually live, not just configured
- [human] The owner has applied Cloudflare Access to the deployed Worker at scope "all traffic" (per G1: one-time-PIN identity provider to the owner's own email, 1-week session) via the Cloudflare dashboard or API
- [integration: after Access is applied, the owner (or the implementer, if given a way to authenticate) opens the real deployed URL and confirms the real dashboard renders — the same board this project has been running locally throughout] Proves the deployed bundle is the real app, not a blank page from a missing VITE_* value (research's own flagged gotcha)

## Notes for the implementer

- Do not attempt to create a Cloudflare account, Zero Trust org, API token, or Access policy
  yourself — you have no credentials for this, and per G1 the owner does this directly. Your
  job in any automated attempt here is limited to confirming the GitHub Actions run succeeds
  once the owner says the secrets are in place, and to reporting clearly if something in the
  workflow itself (not the owner's account setup) is the blocker.
- If the owner's account/dashboard setup has not happened yet when this story runs, say so
  plainly and stop — do not fabricate a passing verdict by only checking the dry-run validation
  from US-1101 again. The criteria here are about a REAL live deploy and REAL Access
  protection, not a repeat of earlier stories' checks.
- This story has no files to touch — it is pure verification once the owner's setup exists.
