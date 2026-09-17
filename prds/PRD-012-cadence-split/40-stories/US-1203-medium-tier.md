---
id: US-1203
title: Medium tier — ingest-medium.yml, native 8-hourly schedule, its own dedicated heartbeat
priority: 3
touches:
  - .github/workflows/ingest-medium.yml
context:
  - AGENTS.md
  - prds/PRD-012-cadence-split/30-spec.md
  - .uf/config.json
  - project-documents/15_Services_and_Credentials.md
---

As the owner, I want the medium tier's 4 registry entries (OKX funding rate, one per asset)
collected on their own native 8-hourly GitHub Actions schedule, independent of the daily and
fast tiers, so a 15-30 minute schedule drift (immaterial against this tier's 43200s/57600s
freshness bounds) never has to share a workflow file with tiers that have tighter or looser
needs.

## Acceptance criteria

- [test: ingest-medium.yml's cron fires every 8 hours, offset away from :00/:05 per GitHub's own top-of-hour-congestion guidance] Matches the practice ingest.yml already follows
- [test: a run triggered by this workflow calls the shared entrypoint with --tier medium] Uses US-1201's filter, does not reimplement it
- [test: this tier has its own dedicated Healthchecks.io check, distinct from the daily tier's, the fast tier's, and contract-canary's] Per Healthchecks.io's own documented "one check per job" practice, cited in research
- [integration: a real scheduled run against all live medium-tier vendors persists exactly the 4 medium-tier rows and the heartbeat pings once] End to end, the actual cron entry point
- [ci: the ingest-medium workflow run completes successfully on the pushed commit] The actual scheduled job, not a local approximation
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- New Healthchecks.io check needed (e.g. `HEALTHCHECK_URL_INGEST_MEDIUM`) — well within the
  20-check free tier alongside the existing checks. Provisioning a new check is a manual
  Healthchecks.io dashboard step plus a new repo secret, not a code path.
- The `[integration:]` criterion here is not exercised by the automated pipeline by default —
  same caveat as US-1202.
