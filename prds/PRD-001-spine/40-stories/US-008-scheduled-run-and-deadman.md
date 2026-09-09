---
id: US-008
title: Scheduled run with a dead-man's-switch on silence
priority: 8
touches:
  - .github/workflows/ingest.yml
  - ingest/heartbeat.py
  - tests/test_heartbeat.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
  - project-documents/10_Technical_Architecture.md
---

As the owner, I want the ingestion job to run on a schedule and to be watched by something
that is not itself, so that if it stops running I find out from an alert rather than from a
gap in a chart weeks later.

The prior system's self-hosted runner exited 0 during a self-update and simply stopped. It
cost 24 hours of data. **A process cannot report that it is no longer running** — only the
absence of an expected signal can.

## Acceptance criteria

- [test: the heartbeat is pinged only after a successful persist] A run that fetched nothing, or failed to write, does not ping
- [test: a failed run pings the failure endpoint rather than staying silent] Explicit failure and silence are different signals and must reach the monitor differently
- [test: heartbeat failure does not fail the run] Monitoring is not allowed to become a source of outages
- [ci: ingest] The scheduled workflow is green on the pushed commit
- [cmd: python -c "import sys; t=open('.github/workflows/ingest.yml').read(); seg=t.split('cron:').pop(1); cron=seg.split(chr(39)).pop(1); minute=cron.split().pop(0); print('cron:', cron, '-> minute', minute); sys.exit(0 if minute != '0' else 1)"] The cron minute is offset from the top of the hour, where GitHub's scheduler is most loaded and most likely to drop a run
- [human] With the schedule paused deliberately, Healthchecks.io raises an alert within its grace period

## Notes for the implementer

- Cadence: every 6 hours, at an offset minute (e.g. `17 */6 * * *`). GitHub documents that
  scheduled workflows can be delayed or dropped entirely under load, and that load peaks on
  the hour — so never schedule at minute 0.
- Ping URL comes from `HEALTHCHECKS_PING_URL`. Append `/fail` for the failure signal.
- The `[human]` criterion is a gate: only the owner can confirm the alert actually arrived.
  Do not attempt to self-certify it, and do not simulate it with a mock.
- Budget note: ~4 runs/day at a couple of minutes each is roughly 240 of the 2,000 free
  GitHub Actions minutes per month on a private repo. A materially faster cadence is a cost
  decision, not a free one.
- Do not add a second always-on process, a WebSocket listener, or a self-hosted runner. A
  resident listener on a small shared machine is what starved the prior system's scheduled
  jobs and was reverted.
