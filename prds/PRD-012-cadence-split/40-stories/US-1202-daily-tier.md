---
id: US-1202
title: Daily tier — ingest.yml moves from every-6-hours to once-daily, keeping its existing per-vendor pacing and heartbeat
priority: 2
touches:
  - .github/workflows/ingest.yml
context:
  - AGENTS.md
  - prds/PRD-012-cadence-split/30-spec.md
  - .uf/config.json
---

As the owner, I want the daily tier's 54 registry entries (technical indicators, Coin Metrics,
Validators.app staking) collected once a day instead of every 6 hours, so this genuinely-daily
data stops being refetched with an identical value five times a day for no benefit, while its
own generous freshness bounds (86400s/108000s+) stay honestly met.

`ingest.yml`'s current `cron: '17 */6 * * *'` runs the full 71-row registry every 6 hours. This
story narrows it to the 54 daily-tier rows only, on a once-daily cron, keeping the existing
17-minute-past-the-hour offset (GitHub's own recommendation to avoid top-of-hour congestion,
already followed by this workflow).

## Acceptance criteria

- [test: ingest.yml's cron fires once per day, not every 6 hours] The core change this story makes
- [test: a run triggered by this workflow calls the shared entrypoint with --tier daily] Uses US-1201's filter, does not reimplement it
- [test: the daily tier's own heartbeat still pings success only when the run itself completed, independent of individual cell failures] Matches the existing pattern, unchanged by the cadence narrowing
- [integration: a real scheduled run against all live daily-tier vendors persists exactly the 54 daily-tier rows and the heartbeat pings once] End to end, the actual cron entry point
- [ci: the ingest workflow run completes successfully on the pushed commit] The actual scheduled job, not a local approximation
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- This story narrows `ingest.yml`'s scope; it does not rename the file or change its trigger
  types (`schedule`, `repository_dispatch: [ingest]`, `workflow_dispatch`, `push`) beyond the
  cron expression itself.
- The `[integration:]` criterion here will not be exercised by the automated pipeline's own
  attempts (pytest's default addopts excludes it) — per this project's own recorded lesson, this
  criterion is unverified until someone runs it manually with real credentials. Do not treat an
  automated "met" judgement on this criterion as proof it actually ran.
