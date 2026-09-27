# US-1206-C3 canary/collect schedule independence evidence

Checked in-repo on 2026-09-27.

The contract canary and collect jobs have independent schedules and triggers:

- `.github/workflows/canary.yml` keeps `schedule: '23 */6 * * *'`, `repository_dispatch` type `canary`, and `workflow_dispatch`.
- `.github/workflows/ingest.yml` runs daily collect only at `schedule: '17 0 * * *'`, `repository_dispatch` type `ingest`, and `workflow_dispatch`.
- `.github/workflows/ingest-medium.yml` runs medium collect at `schedule: '37 */8 * * *'` and `workflow_dispatch`.
- `.github/workflows/ingest-fast.yml` has no native `schedule`; it runs on `repository_dispatch` type `ingest-fast` and `workflow_dispatch`.

The canary does not share the collect heartbeat secret:

- `canary.yml` uses `HEALTHCHECK_URL_CONTRACT_CANARY`.
- `ingest.yml` uses `HEALTHCHECKS_PING_URL`.
- `ingest-medium.yml` maps `HEALTHCHECKS_PING_URL` from `HEALTHCHECK_URL_INGEST_MEDIUM`.
- `ingest-fast.yml` maps `HEALTHCHECKS_PING_URL` from `HEALTHCHECK_URL_INGEST_FAST`.

The canary's command is still non-persisting contract validation:

- `canary.yml` runs `uv run python -m ingest.canary`.
- The collect workflows run `uv run python -m ingest.heartbeat --tier daily|medium|fast`.

