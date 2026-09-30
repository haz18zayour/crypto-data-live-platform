---
id: US-1104
title: The Access drift canary — a scheduled, unauthenticated probe of the real production hostname asserting a redirect to Access login
priority: 4
touches:
  - .github/workflows/deploy-canary.yml
context:
  - AGENTS.md
  - prds/PRD-011-deploy/10-research.md
  - prds/PRD-011-deploy/20-decisions.yaml
---

As the owner, I want an automated, recurring check confirming the deployed page still rejects
unauthenticated access, so that a Cloudflare dashboard misconfiguration — the one control in
this project that isn't diffable — cannot silently leave the page open without anyone noticing.

Research's own blind spot: Access configuration lives entirely in a dashboard, is known by
Cloudflare's own documentation to be fragile across re-toggles, and nothing in this repo
currently watches it. Confirmed at G1: a scheduled probe is in scope for this PRD.

## Acceptance criteria

- [test: a scheduled GitHub Actions workflow (new, or an addition to the existing canary.yml pattern) makes an unauthenticated HTTP request to the real deployed production hostname on a schedule] Recurring, not one-shot
- [test: the workflow asserts the response is a redirect toward Cloudflare Access's login (a 30x to a *.cloudflareaccess.com host, or Access's documented challenge response), and fails the workflow run if it instead receives a 200 with real page content] The actual regression this canary exists to catch
- [integration: run this canary once by hand against the real deployed production hostname (once US-1103's Access configuration is live) and confirm it reports success] Proven against the real hostname, not a mock — per this project's own established lesson that a criterion existing only as a deselected/simplified test never actually runs
- [test: the canary writes no datapoints and does not touch the existing ingest pipeline's own Healthchecks dead-man's-switch] Stays a pure infrastructure check, not conflated with data-pipeline monitoring

## Notes for the implementer

- This story depends on US-1103's Access configuration actually being live to run its real
  `[integration:]` criterion. If Access is not yet configured, the workflow and its structural
  tests can still be built and verified offline; say plainly that the live run is pending.
- Follow this project's existing `canary.yml` conventions (naming, scheduling style, how it
  reports failure) if one already exists for the ingestion pipeline, so this new check reads as
  part of the same family rather than a one-off script.
- Do not write anything to `datapoints` or reuse the ingestion pipeline's own dead-man's-switch
  for this — a page-availability check and a data-freshness check are different failure modes
  and must stay visibly distinct, per this project's own no-conflation discipline.
