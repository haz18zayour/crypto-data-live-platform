---
id: US-206
title: Live drift canary — validates shape, writes nothing
priority: 6
touches:
  - ingest/canary.py
  - .github/workflows/**
  - tests/test_canary.py
context:
  - AGENTS.md
  - project-documents/10_Technical_Architecture.md
---

As the owner, I want a scheduled job that fetches each vendor live and checks the response
still matches its model, so that a vendor changing its API is discovered by us rather than by a
wrong number on the page.

**This is the only mechanism in the PRD that can detect vendor drift.** Recorded fixtures
(US-204) replay forever and cannot notice a live change; they pin our parsing, not the vendor's
behaviour. Without this story, the "vendor contract" guarantee ships a test that can never fail
for the reason it was written.

It also carries the liveness role decided in `10_Technical_Architecture.md`: collection runs
daily, so a 6-hourly canary is what keeps failure-detection latency at ~6–8h instead of ~26h.

## Acceptance criteria

- [test: the canary validates each registered vendor endpoint against its model] Coverage comes from the registry, so a newly registered vendor is checked without anyone remembering to add it
- [test: the canary writes no datapoints] Asserted against the database — it is a liveness and shape check, not a collection run
- [test: a shape mismatch fails the canary and names the vendor and field] Not a generic failure
- [test: the canary pings the heartbeat on success and the failure endpoint on failure] Same discipline as the collect job
- [test: one vendor failing does not prevent the others being checked] A partial table is the failure mode this project exists to prevent
- [integration: the canary runs against live vendors and reports per-vendor status] Hits the real endpoints and produces a per-vendor result
- [cmd: python -c "import sys; t=open('.github/workflows/canary.yml').read(); seg=t.split('cron:').pop(1); cron=seg.split(chr(39)).pop(1); minute=cron.split().pop(0); print('cron:', cron, '-> minute', minute); sys.exit(0 if minute != '0' else 1)"] The canary cron minute is offset from the top of the hour, where GitHub's scheduler is most loaded

## Notes for the implementer

- Roughly 20 seconds of work: one cheap request per vendor, validate, report. No pagination, no
  computation, no writes.
- Use a **separate** Healthchecks check from the collect job, so silence in one is
  distinguishable from silence in the other.
- Do not use a `[ci:]` criterion — `uf` commits and verifies in one step and never pushes, so
  CI has nothing to report on the commit being judged. Query the GitHub API from a `[cmd:]`
  gate instead, as US-008 does.
