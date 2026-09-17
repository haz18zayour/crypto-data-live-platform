---
title: Split cadence — daily collect, fast derivatives, and the 6h canary
branch: feat/prd-012-cadence-split
assumptions:
  - claim: GitHub-hosted runners already receive a fresh IP per job run today, so splitting the collect workflow into tiers does not introduce new multi-IP rate-limit exposure that does not already exist for the single combined job.
    tripwire: If a future vendor's rate limiter is ever found to key off something other than the request's source IP, this finding does not automatically transfer to that vendor — re-verify per vendor rather than assuming it generalizes.
    acceptedBy: default
  - claim: The fast tier's own wall-clock budget (checkout, uv install, 12 OKX calls, writes, heartbeat ping) fits comfortably inside a 5-minute cadence with real headroom, not just on paper.
    tripwire: Must be verified with a real timed dry run before the story is accepted, per the wall-clock-vs-rate-limit lesson from the Helius/PRD-007 incident. If the real run does not fit with headroom, successive 5-minute runs will start overlapping or queueing.
    acceptedBy: default
  - claim: cron-job.org's account and repository_dispatch PAT are provisioned before any fast-tier story starts.
    tripwire: project-documents/15_Services_and_Credentials.md explicitly marks cron-job.org as N/A until this PRD — it has never been provisioned. A story failing on missing cron-job.org configuration or a missing GH_DISPATCH_PAT secret is a provisioning gap, not a code defect. Check this first.
    acceptedBy: default
---

# Split cadence — daily collect, fast derivatives, and the 6h canary

## What this delivers

The single `ingest` workflow, which currently collects every registered indicator on one
uniform 6-hourly cron regardless of that indicator's own real update cadence, splits into three
cadence tiers sharing one Python entrypoint: a **fast** tier (12 entries: OKX open interest,
long/short ratio, taker ratio — all on 300s freshness bounds) triggered externally by
cron-job.org every 5 minutes via `repository_dispatch`, a **medium** tier (4 entries: OKX funding
rate, 28800s bounds) on native GitHub Actions schedule, and the existing **daily** tier (54
entries: technical indicators, Coin Metrics, Validators.app staking, 86400s bounds), also on
native schedule. The already-existing `contract-canary` workflow (built in US-206, 6-hourly,
writes nothing) is confirmed unchanged. Separately, `sol_active_addresses`'s registry entry gets
its declared freshness fields corrected to match its real weekly schedule (set in PRD-007), fixing
a live mismatch discovered during this PRD's own G1 verification, not something this PRD's
cadence-split logic itself introduces or depends on.

## Why (from research and this gate's own findings)

Three findings are load-bearing.

1. **The brief's own stated risk was wrong; the real risk already caused a production incident
   in this codebase.** The brief worried that splitting collection across separate CI runner IPs
   would multiply vendor rate-limit exposure. Research found this premise false — GitHub-hosted
   runners already get a fresh IP per job run today, for the single combined job, so splitting
   changes nothing about IP diversity. The real risk research surfaced instead is a repeat of
   PRD-007's Helius incident: a tightened cadence's wall-clock budget colliding with the
   scheduler's own timeout, which nobody had checked for the *new* fast-tier job specifically.
2. **GitHub Actions cron cannot hold a 5-minute cadence against a 450-second freshness bound.**
   GitHub's own docs confirm scheduled runs are delayed under load, clustering "at the start of
   every hour"; independent measurement found ~1-in-10 runs land 5+ minutes late and ~1-in-50
   land 15+ minutes late, with community reports of 60+ minute peak delays. The fast tier's own
   `freshness_stale_seconds: 600` cannot absorb that without frequent false-STALE reads
   indistinguishable from a real vendor outage. cron-job.org, already an adopted trigger pattern
   in this project's architecture doc, documents 4-40 second dispatch delay — two orders of
   magnitude tighter — but was never actually provisioned (`15_Services_and_Credentials.md` marks
   it "N/A until PRD-012" verbatim).
3. **`sol_active_addresses` already has a live cadence-vs-contract mismatch, discovered during
   this gate, not anticipated by the brief.** Its registry entry declares `86400`/`172800`
   (daily/2-day) freshness fields, but its real dedicated schedule
   (`sol-active-addresses.yml`, built in PRD-007's US-707 for Helius's credit budget) only runs
   weekly. The cell currently reads `STALE` against its own declared contract for roughly 5 of
   every 7 days. This PRD corrects the declared fields to match the real schedule — it does not
   change the schedule itself, which is a separate, already-settled owner decision.

## Approach

**One shared entrypoint, filtered by tier.** `ingest/pipeline.py`'s existing `run_all_assets`/
`run_pipeline`/`run_scheduled_board` machinery already reads every registered indicator from
`ingest/registry.yaml`; this PRD adds a `--tier {fast,medium,daily}` filter (or equivalent
programmatic parameter) that restricts a run to only the registry rows whose
`expected_update_interval_seconds` matches that tier's own value (`300` for fast, `28800` for
medium, `86400` for daily — no new registry field, the discriminator already exists). No
fetch/write/heartbeat logic is duplicated across tiers; a fix to shared pipeline logic needs one
change, not three.

**Three workflow files, one shared script.** `ingest-fast.yml` drops `schedule:` entirely and
triggers only on `repository_dispatch` (type `ingest-fast`) plus `workflow_dispatch` as a manual
fallback, matching the naming convention already used by `canary`/`ingest`/`sol-active-addresses`.
`ingest-medium.yml` keeps a native `schedule:` cron (8-hourly, offset away from `:00`/`:05` per
GitHub's own recommendation and the existing `ingest.yml`'s own `17 */6 * * *` precedent).
`ingest.yml` itself is renamed/repurposed as the daily tier, keeping its existing offset cron
but moved to once-daily instead of every 6 hours. Each gets its own dedicated Healthchecks.io
check and Grace Time, following the vendor's own documented "one check per job" practice — well
within the 20-check free tier alongside the existing `HEALTHCHECK_URL_CONTRACT_CANARY` and
`sol-active-addresses` checks.

**cron-job.org fires the fast tier's `repository_dispatch` every 5 minutes**, using a
fine-grained PAT scoped to this repo's Actions read/write (`GH_DISPATCH_PAT`, per
`15_Services_and_Credentials.md`'s own documented shape) — provisioned as part of this PRD, not
assumed to already exist. A real timed dry run of the fast tier's full wall-clock budget
(checkout + `uv` install + 12 OKX calls + writes + heartbeat) happens before this criterion is
accepted, not estimated on paper, per the assumption above.

**`sol_active_addresses`'s freshness fields are corrected** to values that actually fit a weekly
schedule (e.g. `expected_update_interval_seconds` reflecting the real ~7-day cadence, with
`freshness_warn_seconds`/`freshness_stale_seconds` sized with real headroom above that, not the
current daily/2-day values) — a small, isolated registry change, verified by confirming the cell
no longer reads `STALE` immediately after a normal weekly run completes.

## Data model changes

None. This PRD changes *when* existing registered indicators are collected and corrects one
entry's declared freshness fields to match an already-existing schedule; it adds no new column,
migration, indicator, or vendor.

## Out of scope

Restated from `00-brief.md`, confirmed at G1: rebuilding the contract-canary workflow (already
exists, unchanged); changing `sol-active-addresses.yml`'s own weekly schedule (only its
registry-declared freshness fields are corrected here); any new indicator, vendor, or panel; any
composite freshness score or health dashboard (PRD-010); resolving whether continuous 5-minute
automated polling violates OKX's usage-pattern terms beyond the numeric rate limit (flagged
`UNVERIFIED` by research at the primary-source level — the fast tier's acceptance criteria must
not assume this is settled).

## The adversarial case

**Force a fast-tier cell (e.g. `btc_open_interest`) stale by simulating a missed collection
window, and confirm it reads `STALE` within its existing 450-second freshness-warn bound — not
hours or days later** because a coarser tier silently absorbed it. **A second case, directly
guarding against the blind spot research flagged**: confirm the daily tier's own `--tier` filter
does not silently drop a row that belongs to it — i.e., that the union of fast + medium + daily
tier runs, over one full cycle, writes exactly the same 71-row set the single combined job used
to write, with no row falling through a filter gap or landing in the wrong tier. A third,
cheaper case: confirm `contract-canary`'s own 6-hourly heartbeat still fires correctly once the
main collect workflow's shape changes, proving the two schedules are genuinely independent, not
accidentally coupled through a shared trigger, secret, or credential rate limit.

## Stories

| Story | Title | Depends on |
|---|---|---|
| US-1201 | Registry tier filter — one shared entrypoint accepts `--tier {fast,medium,daily}`, partitioning by `expected_update_interval_seconds` with no row dropped or duplicated | — |
| US-1202 | Daily tier — `ingest.yml` moves from every-6-hours to once-daily, keeping its existing per-vendor pacing and heartbeat | US-1201 |
| US-1203 | Medium tier — `ingest-medium.yml`, native 8-hourly schedule, its own dedicated heartbeat | US-1201 |
| US-1204 | Fast tier — `ingest-fast.yml`, `repository_dispatch`-only trigger, cron-job.org provisioned and firing every 5 minutes, real timed dry run proves the wall-clock budget fits with headroom | US-1201 |
| US-1205 | `sol_active_addresses` registry freshness fields corrected to match its real weekly schedule | — |
| US-1206 | The adversarial case — forced fast-tier staleness read, full-cycle row-count reconciliation across all three tiers, and confirmed canary/collect schedule independence | US-1202, US-1203, US-1204, US-1205 |
