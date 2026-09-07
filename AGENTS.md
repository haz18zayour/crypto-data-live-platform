# crypto-data-live-platform

<!--
Written by a person, kept short. Generated agent instructions measurably do not help —
they cost tokens on every invocation and slightly reduce success rates, while
human-written context improves them. When an agent learns something worth keeping it
writes a proposal to `.uf/proposals/`; you fold in the ones that are actually true.

An empty section is better than an invented one.
-->

**Stack:** Python 3.12 (`uv`, httpx, pydantic, TA-Lib) ingestion · Supabase Postgres ·
Vite + React + TypeScript + Tailwind on Cloudflare Pages, behind Cloudflare Access ·
GitHub Actions `schedule:` + cron-job.org `repository_dispatch` triggers ·
Healthchecks.io dead-man's-switch.
See `project-documents/10_Technical_Architecture.md`.

> **Compute location is UNDECIDED** until PRD-001's reachability spike runs. Binance returns
> HTTP 451 to US IPs, which is what forced the prior system onto a self-hosted runner that
> later died silently. Do not assume GitHub-hosted runners can reach every venue — measure it.

**This product's one rule above all others:** it displays market data and **makes no
judgement about it**. No composite score, no signal, no ranking. A wrong number must look
different from a right one — that is the whole product. If a value cannot be honestly sourced
for an asset, it renders `UNAVAILABLE` with a reason, never a proxy and never `0`.

## How work happens here

This product runs on `uf`. Read `CYCLE.md` for the loop, `SKILLS.md` for which skill to fire
at which phase, `KNOWLEDGE.md` for what we already know.

Work is organised as **PRDs** in `prds/PRD-00N-<slug>/`, walked in the order set by
`project-documents/05_Product_Roadmap.md`. Each PRD compiles to `spec.lock.json`, then runs
story by story: one agent implements in a fresh context, a **different vendor** verifies in
a read-only sandbox and must cite a file, line or test name per criterion.

**You cannot mark your own work complete.** Produce the evidence the criteria name — the
tests, the screenshots, the passing commands — and leave it where it can be found. Do not
write a summary claiming success; nobody reads it and the verifier ignores it.

## Conventions

<!-- Add the real ones as you discover them. -->

## Gotchas

<!-- Things that cost an afternoon. Also run `uf learn` so other products inherit them. -->

## Blast radius

Changes to these need human review before merge (mirrored in `.uf/config.json`):

- authentication and session handling
- RLS policies
- payments
- database migrations
- CI workflows and deploy configuration
