---
id: US-1204
title: Fast tier — ingest-fast.yml, repository_dispatch-only trigger, cron-job.org provisioned and firing every 5 minutes, real timed dry run proves the wall-clock budget fits with headroom
priority: 4
touches:
  - .github/workflows/ingest-fast.yml
  - project-documents/15_Services_and_Credentials.md
context:
  - AGENTS.md
  - prds/PRD-012-cadence-split/10-research.md
  - prds/PRD-012-cadence-split/30-spec.md
  - .uf/config.json
---

As the owner, I want the fast tier's 12 registry entries (OKX open interest, long/short ratio,
taker ratio, 4 assets each) collected every 5 minutes via cron-job.org's tighter dispatch
timing, not GitHub Actions' own schedule, so this tier's 450-second freshness-stale bound is not
routinely and falsely tripped by GitHub's own documented top-of-hour scheduling congestion.

`project-documents/15_Services_and_Credentials.md` marks cron-job.org as "N/A until PRD-012" —
it has never been provisioned. This is a provisioning dependency, not a code concern: check this
first if this story appears broken.

## Acceptance criteria

- [test: ingest-fast.yml has no schedule: trigger — only repository_dispatch (type ingest-fast) and workflow_dispatch] The whole point: GitHub Actions supplies compute, not the clock, for this tier
- [test: a run triggered by this workflow calls the shared entrypoint with --tier fast] Uses US-1201's filter, does not reimplement it
- [test: this tier has its own dedicated Healthchecks.io check, distinct from every other tier's and contract-canary's] Per Healthchecks.io's own documented practice
- [integration: a real dispatched run against all live fast-tier vendors persists exactly the 12 fast-tier rows and the heartbeat pings once] End to end, the actual dispatch entry point
- [integration: a real timed run of the full fast-tier pipeline (checkout, uv install, all 12 OKX calls, writes, heartbeat ping) completes with real, measured headroom under 5 minutes, not an estimate] The specific tripwire this story exists to prove — matches the wall-clock-vs-rate-limit lesson from the Helius/PRD-007 incident
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- **Provision a cron-job.org account and a fine-grained GitHub PAT (`GH_DISPATCH_PAT`, this
  repo, Actions: read/write) before starting this story's live/integration criteria.** Configure
  a cron-job.org job firing every 5 minutes against this repo's `repository_dispatch` API
  endpoint with `event_type: ingest-fast`. This is a manual prerequisite, not a discoverable code
  path — update `project-documents/15_Services_and_Credentials.md`'s cron-job.org row from "N/A
  until PRD-012" to provisioned once done.
- The timed-dry-run criterion is the one this story exists for. Do not accept an estimate in
  place of a real measured run — this is exactly the class of assumption that broke US-707's
  original design before it was caught by actually running the fetch.
- `.github/workflows/**` is listed in `.uf/config.json`'s `blastRadius` — this story creates a
  new workflow file, which is blast radius, and G4 applies.
