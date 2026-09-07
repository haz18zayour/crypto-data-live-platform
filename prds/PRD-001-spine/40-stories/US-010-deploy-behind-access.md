---
id: US-010
title: Deploy to Cloudflare Pages behind Access
priority: 10
touches:
  - .github/workflows/deploy.yml
  - web/**
context:
  - AGENTS.md
  - project-documents/10_Technical_Architecture.md
  - project-documents/15_Services_and_Credentials.md
---

As the owner, I want the page deployed and reachable only by me, so that the spine is proven
in production rather than on localhost.

The PRD is not finished until a real value is visible at a real URL. Everything before this
story is unfalsifiable in the way that matters.

## Acceptance criteria

- [ci: deploy] The deploy workflow is green on the pushed commit
- [cmd: npm --prefix web run build] The build the workflow runs also succeeds locally
- [test: the built bundle contains no service-role key and no secret-looking value] The production bundle is scanned for the service-role key and for any `SUPABASE_SERVICE` string
- [human] The deployed URL requires Cloudflare Access sign-in, and after signing in shows the BTC daily close with its source, age and freshness

## Notes for the implementer

- Deploy `web/` to Cloudflare Pages on push to the PRD branch, so a preview URL exists before
  merge.
- Cloudflare Access policy restricted to `zayourhassan.1@gmail.com`. Access is configured in
  the Cloudflare dashboard by the owner — an agent cannot create the account or accept terms.
  If the free tier does not cover it, that is the tripwire recorded in `20-decisions.yaml`:
  stop and report rather than falling back to an unprotected page.
- The bundle-scan criterion is not theatre. The prior system's standing security rule was that
  the service-role key must never reach the browser; this makes that rule machine-checked
  rather than remembered.
- The `[human]` criterion is a gate. Do not self-certify that the page looks right — produce
  the deployment and stop.
- This story must not change fetcher, schema or registry code. If something there needs
  fixing, it belongs to the story that owns it.
