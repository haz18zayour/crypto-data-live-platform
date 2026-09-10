# crypto-data-live-platform — session log

**Just arrived? Run `uf next`, then read the Handoff section at the bottom.** Those two are the whole picture.

Everything between the markers is generated from `.uf/events.ndjson` by `uf log`.
Do not hand-edit it — it is regenerated. The hand-written sections below it survive.

<!-- uf:generated:start -->

## ▶ Resume here

**PRD-003-corroboration — 6/7 stories passed**

Codex implements, a different vendor verifies read-only. It stops only for a blast-radius merge, a third failure, or a human criterion.

Owner: **`uf`.** Run the command; it drives the agents itself.

```
uf run PRD-003-corroboration
```

**Last handoff note:** 2026-09-10 — US-306 implementation evidence is ready for external verification: registry entries must explicitly choose a second-source corroboration block or an uncorroborated note; Coin Metrics-style upstream consolidation is preserved in the note; PRD-002 generated coverage rejects silence. US-306 tests: 4 passed; registry-focused tests: 24 passed; ruff/mypy and registry validation clean; deterministic regressions: 107 passed (6 integration deselected). Live PostgreSQL remains unreachable from this sandbox.

## Where this stands

| PRD | Stories | Passed | State |
|---|---|---|---|
| PRD-001-spine | 8 | 8 | **all green** |
| PRD-002-harness | 7 | 7 | **all green** |
| PRD-003-corroboration | 7 | 6 | 6/7 |

Spend to date: **$21.08** Claude · **65106k** Codex tokens.

## What happened


### 2026-09-07

- 11:42  researched PRD-001-spine — 0 sources (REJECTED) · $2.05
- 16:55  **PRD-001-spine** compiled — 10 stories
- 16:55  **PRD-001-spine** compiled — 10 stories
- 16:57  US-001 started, attempt 1 (codex)
- 17:02  US-001 — codex finished `8e18cc86`
- 17:03  US-001 **rejected** — 0/5 criteria, judged by claude
- 17:06  **PRD-001-spine** compiled — 10 stories
- 17:06  US-001 started, attempt 2 (codex)
- 17:07  US-001 — codex finished `1561e20d`
- 17:07  US-001 **rejected** — 0/6 criteria, judged by claude

### 2026-09-08

- 07:19  US-001 started, attempt 3 (codex)
- 07:23  US-001 — codex finished `0b57517e`
- 07:24  US-001 **rejected** — 5/6 criteria, judged by claude · $0.17
- 07:27  **PRD-001-spine** compiled — 10 stories
- 07:30  **PRD-001-spine** compiled — 10 stories
- 07:35  ⏸ **gate opened** — US-001 has failed 3 times — is the story wrong?
- 07:37  ▶ gate answered **rewrite-criteria** — Criteria were genuinely wrong and have been rewritten. C1 regenerated reachability.json locally during verification, overwriting the artifact produced on the GitHub runner - the criterion meant to prove the probe runs destroyed the evidence the story exists to produce, which is why C4 saw github_actions:false. Local and CI evidence are now separate committed files, plus a new criterion asserting the CI file carries its own github_run_id so a local regeneration cannot satisfy it. Attempts 1-2 were consumed by codex 404ing on gpt-5.5 (implementer never ran, $0, 0 tokens), not by the spec. All criteria verified passing by hand: CI success on HEAD cf7fc94, 8/8 venues with real HTTP status, 5 tests passing.
- 07:37  ⏸ **gate opened** — US-001 has failed 3 times — is the story wrong?
- 07:43  **PRD-001-spine** compiled — 10 stories
- 07:46  ▶ gate answered **skip** — US-001 no longer exists. Per the earlier G5 answer (rewrite-criteria) it was replaced by US-011, which carries the corrected criteria: local and CI evidence are separate committed files, and a new criterion asserts the CI artifact carries its own github_run_id so a local regeneration cannot satisfy it. requireCi is now true so the verifier receives a real CI conclusion instead of being asked to trust the artifact's self-reported field. Skipping refers only to the retired US-001 identity; the work itself is intact and US-011 is pending with 0 attempts.
- 07:46  US-011 started, attempt 1 (codex)
- 07:49  US-011 — codex finished `646c0341`
- 07:49  US-011 **rejected** — 0/7 criteria, judged by claude
- 08:20  **PRD-001-spine** compiled — 9 stories
- 08:21  US-002 started, attempt 1 (codex)
- 08:35  US-002 — codex finished `a6b88c65` · 2156k tok
- 08:35  US-002 **rejected** — 0/5 criteria, judged by claude
- 12:35  US-002 started, attempt 2 (codex)
- 12:39  US-002 failed — interrupted while running — the process stopped before a verdict
- 12:39  US-002 started, attempt 2 (codex)
- 12:39  US-002 — codex finished `9d4549ee` · 740k tok
- 12:41  US-002 **PASSED** — 5/5 criteria, judged by claude · $1.05
- 12:41  US-002 — codex finished `76a3a7fc` · 287k tok
- 12:42  US-002 failed — interrupted while verifying — the process stopped before a verdict
- 12:42  US-002 started, attempt 3 (codex)
- 12:42  US-002 **PASSED** — 5/5 criteria, judged by claude · $0.65
- 12:44  US-002 — codex finished `0523b7d3` · 283k tok
- 12:45  US-002 **PASSED** — 5/5 criteria, judged by claude · $0.66
- 12:45  US-003 started, attempt 1 (codex)
- 12:52  US-003 — codex finished `b4a35340` · 910k tok
- 12:53  US-003 **PASSED** — 5/5 criteria, judged by claude · $0.20
- 12:53  US-004 started, attempt 1 (codex)
- 12:54  US-004 failed — interrupted while running — the process stopped before a verdict
- 12:54  US-004 started, attempt 1 (codex)
- 13:01  US-004 — codex finished `3a31e43b` · 1249k tok
- 13:02  US-004 **PASSED** — 5/5 criteria, judged by claude · $0.19
- 13:05  US-005 started, attempt 1 (codex)
- 13:08  US-004 — codex finished `72efd0a9` · 1977k tok
- 13:08  US-004 **rejected** — 0/5 criteria, judged by claude
- 13:10  US-005 failed — interrupted while running — the process stopped before a verdict
- 13:10  US-004 started, attempt 3 (codex)
- 13:13  US-004 — codex finished `ad6b4095` · 319k tok
- 13:14  US-004 **PASSED** — 5/5 criteria, judged by claude · $0.29
- 13:14  US-005 started, attempt 1 (codex)
- 13:21  US-005 — codex finished `e0d490ad` · 2341k tok
- 13:23  US-005 **rejected** — 1/5 criteria, judged by claude · $0.32
- 13:29  US-005 — codex finished `c110cf02` · 1850k tok
- 13:30  US-005 **rejected** — 1/5 criteria, judged by claude · $0.34
- 13:32  **PRD-001-spine** compiled — 9 stories
- 13:33  **PRD-001-spine** compiled — 9 stories
- 13:33  US-006 started, attempt 1 (codex)
- 13:42  US-006 — codex finished `d26603d0` · 1615k tok
- 13:45  US-006 **PASSED** — 6/6 criteria, judged by claude · $0.35
- 13:47  **PRD-001-spine** compiled — 9 stories
- 18:01  **PRD-001-spine** compiled — 9 stories

### 2026-09-09

- 09:14  US-005 started, attempt 3 (codex)
- 09:17  US-005 failed — interrupted while running — the process stopped before a verdict
- 09:17  US-005 started, attempt 3 (codex)
- 09:24  US-005 — codex finished `7df21196` · 1073k tok
- 09:25  US-005 **rejected** — 0/6 criteria, judged by claude
- 09:25  **PRD-001-spine** compiled — 9 stories
- 09:26  ⏸ **gate opened** — US-005 has failed 3 times — is the story wrong?
- 09:27  ▶ gate answered **rewrite-criteria** — The approach was wrong, and it has been rewritten. The tests shelled out to psql, which is absent on Windows (FileNotFoundError WinError 2) and only passed in CI because that workflow apt-installs postgresql-client - so the defect was invisible where it was written. Migrations now run through psycopg[binary], a wheel on every platform, already required by US-007, in a single transaction. Re-identifying as US-012 because answering this gate does not restore attempts: run.ts opens it whenever attempts >= maxAttempts without consulting a prior answer.
- 09:27  **PRD-001-spine** compiled — 9 stories
- 09:27  US-012 started, attempt 1 (codex)
- 09:46  US-012 — codex finished `5555fa9e` · 3193k tok
- 09:46  US-005 — codex finished `77d5fdca` · 8172k tok
- 09:48  US-005 failed — interrupted while verifying — the process stopped before a verdict
- 09:48  US-012 failed — interrupted while verifying — the process stopped before a verdict
- 09:48  US-012 started, attempt 1 (codex)
- 09:54  US-012 — codex finished `4eecdfc6` · 1060k tok
- 09:55  US-012 **PASSED** — 6/6 criteria, judged by claude · $0.37
- 09:59  US-007 started, attempt 1 (codex)
- 10:11  US-007 — codex finished `ccd48a1b` · 1562k tok
- 10:13  US-007 **PASSED** — 7/7 criteria, judged by claude · $0.32
- 10:15  US-008 started, attempt 1 (codex)
- 10:26  US-008 — codex finished · 1689k tok
- 10:27  US-008 **rejected** — 0/6 criteria, judged by claude
- 10:28  **PRD-001-spine** compiled — 9 stories
- 10:28  **PRD-001-spine** compiled — 9 stories
- 10:29  US-008 started, attempt 2 (codex)
- 10:36  US-008 — codex finished `cb4babf6` · 1171k tok
- 10:38  US-008 **rejected** — 4/6 criteria, judged by claude · $0.66
- 10:42  **PRD-001-spine** compiled — 9 stories
- 10:42  US-008 started, attempt 3 (codex)
- 10:47  US-008 — codex finished `b978451e` · 726k tok
- 10:49  US-008 **awaiting your judgement** — 5/6 criteria, judged by claude · $0.53
- 10:49  ⏸ **gate opened** — US-008: With the schedule paused deliberately, Healthchecks.io raises an alert within its grace period
- 10:53  **PRD-001-spine** compiled — 8 stories
- 16:01  ▶ gate answered **met** — Owner verified the full alert path on 2026-09-09, using a separate TEST check so the live monitor was not disturbed. Healthchecks generated a DOWN alert on silence ('success signal did not arrive on time, grace time passed') and the email was actually delivered to zayourhassan.1@gmail.com. The live crypto-data-ingest check separately shows ping #1 received at 13:39 local (10:39 UTC) via HTTPS GET from 168.62.197.25 - an Azure IP, i.e. the GitHub-hosted runner - with user-agent python-httpx/0.28.1, and status new -> up. Both halves proven: the heartbeat reaches Healthchecks from CI, and silence reaches the owner by email. This is the direct defence against the prior system's 24h silent outage, where a self-hosted runner exited 0 and nothing reported it.
- 16:01  👤 you judged US-008 **met** — Owner verified the full alert path on 2026-09-09, using a separate TEST check so the live monitor was not disturbed. Healthchecks generated a DOWN alert on silence ('success signal did not arrive on time, grace time passed') and the email was actually delivered to zayourhassan.1@gmail.com. The live crypto-data-ingest check separately shows ping #1 received at 13:39 local (10:39 UTC) via HTTPS GET from 168.62.197.25 - an Azure IP, i.e. the GitHub-hosted runner - with user-agent python-httpx/0.28.1, and status new -> up. Both halves proven: the heartbeat reaches Healthchecks from CI, and silence reaches the owner by email. This is the direct defence against the prior system's 24h silent outage, where a self-hosted runner exited 0 and nothing reported it.
- 16:01  US-009 started, attempt 1 (codex)
- 16:17  US-009 failed — interrupted while running — the process stopped before a verdict
- 16:17  US-009 started, attempt 1 (codex)
- 16:44  US-009 failed — interrupted while running — the process stopped before a verdict
- 16:44  US-009 started, attempt 1 (codex)
- 16:57  US-009 failed — interrupted while running — the process stopped before a verdict
- 16:57  US-009 started, attempt 1 (codex)
- 17:17  US-009 — codex finished `842003aa` · 4759k tok
- 20:43  US-009 failed — interrupted while verifying — the process stopped before a verdict
- 20:43  US-009 started, attempt 1 (codex)
- 20:46  US-009 — codex finished `65914c96` · 549k tok
- 20:48  US-009 **PASSED** — 9/9 criteria, judged by claude · $1.11
- 21:02  researched PRD-002-harness — 16 sources · $3.54
- 21:05  **PRD-002-harness** compiled — 7 stories
- 21:05  US-201 started, attempt 1 (codex)
- 21:16  US-201 — codex finished `2afd1c31` · 1841k tok
- 21:17  US-201 **PASSED** — 6/6 criteria, judged by claude · $0.18
- 21:18  US-202 started, attempt 1 (codex)
- 21:25  US-202 — codex finished `76f3ae8f` · 1186k tok
- 21:26  US-202 **PASSED** — 5/5 criteria, judged by claude · $0.18
- 21:26  US-203 started, attempt 1 (codex)
- 21:32  US-203 — codex finished `be4ba804` · 1007k tok
- 21:33  US-203 **PASSED** — 5/5 criteria, judged by claude · $0.16
- 21:33  US-204 started, attempt 1 (codex)
- 21:41  US-204 — codex finished `bc488b58` · 1275k tok
- 21:42  US-204 **PASSED** — 5/5 criteria, judged by claude · $0.19
- 21:43  US-205 started, attempt 1 (codex)
- 21:52  US-205 — codex finished `9eb90b10` · 1509k tok
- 21:54  US-205 **PASSED** — 5/5 criteria, judged by claude · $0.28
- 21:54  US-206 started, attempt 1 (codex)
- 22:12  US-206 — codex finished `568db0e7` · 3207k tok
- 22:14  US-206 **PASSED** — 7/7 criteria, judged by claude · $0.31
- 22:14  US-207 started, attempt 1 (codex)
- 22:19  US-207 — codex finished `15667825` · 726k tok
- 22:21  US-207 **PASSED** — 6/6 criteria, judged by claude · $0.25

### 2026-09-10

- 05:47  researched PRD-003-corroboration — 9 sources · $2.85
- 05:50  **PRD-003-corroboration** compiled — 7 stories
- 05:51  US-301 started, attempt 1 (codex)
- 06:06  US-301 — codex finished `7b949311` · 2473k tok
- 06:09  US-301 **PASSED** — 6/6 criteria, judged by claude · $0.75
- 06:09  US-302 started, attempt 1 (codex)
- 06:26  US-302 — codex finished `6065ec4b` · 1983k tok
- 06:27  US-302 **PASSED** — 6/6 criteria, judged by claude · $0.29
- 06:27  US-303 started, attempt 1 (codex)
- 06:35  US-303 — codex finished `3d82c879` · 1184k tok
- 06:37  US-303 **PASSED** — 5/5 criteria, judged by claude · $0.13
- 06:37  US-304 started, attempt 1 (codex)
- 06:51  US-304 — codex finished `328e28ef` · 1672k tok
- 06:54  US-304 **rejected** — 6/7 criteria, judged by claude · $0.49
- 06:54  US-304 started, attempt 2 (codex)
- 06:59  US-304 — codex finished `6ce69cec` · 410k tok
- 07:02  US-304 **PASSED** — 7/7 criteria, judged by claude · $0.47
- 07:06  US-305 started, attempt 1 (codex)
- 07:16  US-305 failed — interrupted while running — the process stopped before a verdict
- 07:16  US-305 started, attempt 1 (codex)
- 07:24  US-305 — codex finished `2e16ba55` · 2169k tok
- 07:27  US-305 — codex finished `93143f4b` · 1925k tok
- 07:28  US-305 **PASSED** — 5/5 criteria, judged by claude · $0.47
- 07:29  US-306 started, attempt 1 (codex)
- 07:30  US-305 **PASSED** — 5/5 criteria, judged by claude · $0.36
- 07:30  US-306 failed — interrupted while running — the process stopped before a verdict
- 07:30  US-306 started, attempt 1 (codex)
- 07:47  US-306 — codex finished `282ad541` · 2159k tok
- 07:51  US-306 **PASSED** — 5/5 criteria, judged by claude · $0.33
- 07:51  US-306 — codex finished `1c76e217` · 2697k tok
- 07:51  US-306 failed — interrupted while verifying — the process stopped before a verdict
- 07:51  US-306 started, attempt 2 (codex)
- 07:53  US-306 **PASSED** — 5/5 criteria, judged by claude · $0.33
- 07:54  US-307 started, attempt 1 (codex)
- 07:55  US-306 — codex finished `488bceeb`
- 07:56  US-306 **PASSED** — 5/5 criteria, judged by claude · $0.27
- 07:57  US-307 failed — interrupted while running — the process stopped before a verdict
- 07:57  US-307 started, attempt 1 (codex)
- 08:14  US-307 — codex finished
- 08:14  US-307 — codex finished `6705162b`
- 08:15  US-307 **rejected** — 0/6 criteria, judged by claude
- 08:15  US-307 **rejected** — 0/6 criteria, judged by claude

<!-- uf:generated:end -->

## Handoff

- 2026-09-10 — US-306 implementation evidence is ready for external verification: registry entries must explicitly choose a second-source corroboration block or an uncorroborated note; Coin Metrics-style upstream consolidation is preserved in the note; PRD-002 generated coverage rejects silence. US-306 tests: 4 passed; registry-focused tests: 24 passed; ruff/mypy and registry validation clean; deterministic regressions: 107 passed (6 integration deselected). Live PostgreSQL remains unreachable from this sandbox.
- 2026-09-10 — US-305 implementation and tests are ready for external verification. Missing Coinbase target-day bars, including the real older-latest-candle shape, persist the primary value and a reasoned NOT_CORROBORATED record with no divergence fields; HTTP errors remain Error outcomes and only those trigger corroboration failure policy. Targeted US-303-305 tests: 20 passed (1 live deselected); Ruff and scoped mypy clean; non-network/non-DB regressions: 92 passed (3 live deselected). Live PostgreSQL fixtures are unreachable from this sandbox; full-project mypy has 8 pre-existing test errors outside touched files.
- 2026-09-10 — US-304 implementation is ready for external verification: midpoint divergence is assessed against the per-indicator registry tolerance, the first tolerance/status written for a datapoint pair is immutable on rerun, and the live entry point fetches/persists both peer venues behind the US-303 timestamp gate. Targeted tests: 7 passed with live deselected; changed-file ruff/mypy and registry validation clean; deterministic regressions: 93 passed. The fail-loud live integration test could not connect to Supabase from this sandbox.
- 2026-09-10 (session): PRD-003 at 3/7, all first attempt. Both venues verified live and
  aligned — OKX 78,300.70, Coinbase 78,283.98, both on a genuine 00:00 UTC boundary
  asserted **independently per venue**, **2.1 bps apart** against the measured 25 bps
  tolerance. US-301 is **blast radius**: it extends the unique identity with
  `source_vendor` (two venues previously collided and the second write silently UPDATEd
  the first) and adds a `corroborations` table. **Manual G4 owed before merge — the
  migration is written but NOT applied to `public`.**
  Bullets below prefixed with a bare date are Codex's per-story sandbox notes, not
  session state.
- 2026-09-10 — US-303 implementation is ready for external verification: timestamp validation rejects each source independently when off UTC midnight or future, unequal timestamps return a TIMESTAMP_MISMATCH carrying both timestamps without invoking comparison, and equal timestamps invoke the comparison callback. Targeted tests: 7 passed; mypy and ruff clean; deterministic non-network/non-Postgres regressions: 90 passed. Full suite: 93 passed, with existing live socket and Postgres checks failing loud because this sandbox cannot reach them. Git commit was not possible because the sandbox denies writes to .git.
- 2026-09-10 — US-302 implementation is ready for external verification: Coinbase is decoded into named strict fields, asserts its own UTC-midnight buckets, excludes the live bucket, and stores bucket-end timestamps. Targeted tests: 10 passed (live deselected); unaffected non-DB regressions: 69 passed. The fail-loud live test is present but this sandbox blocks sockets with WinError 10013; existing real-Postgres fixtures are likewise unreachable here.
- 2026-09-10: **PRD-002 complete, 7/7, every story first attempt**, merged to `main`. The
  harness now guards PRD-004 onward: exactly-N-bar slices, goldens with an external oracle,
  `extra='forbid'` + strict vendor models, recorded shapes, truncation/gap/duplicate detection,
  a live drift canary at `23 */6 * * *`, and coverage generated from the registry so a new
  indicator cannot ship without a golden and a model. Next is **PRD-003 cross-source
  corroboration**, then PRD-004 indicators, then PRD-005 the dashboard.
- 2026-09-10: PRD-002 is 4/7 with every story passing first attempt — US-201 bar-slice
  contract, US-202 goldens, US-203 response models, US-204 recorded shapes. Verified by hand,
  not just by green ticks: a 2-bar or 500-bar slice is **rejected** where the contract says 1,
  and the OKX model refuses an added field, a renamed field, a number-for-string and a null,
  each naming the field. Remaining: US-205 truncation, US-206 live drift canary, US-207
  registry-generated coverage.
- 2026-09-10: PRD-001 is merged to `main` and PRD-002 (determinism + contract harness) is
  running on `feat/prd-002-harness`, currently US-201. **Operating protocol agreed with the
  owner: run autonomously inside a PRD, stop hard between PRDs** and prove the PRD works
  against real services before starting the next — see `project-documents/25_PRD_Acceptance_Protocol.md`.
  The proof must include an adversarial case attacking that PRD's specific guarantee; for
  PRD-002 that is passing a longer bar slice and showing it **rejected**, not silently
  different.
- 2026-09-10: PRD-002's research **corrected the architecture doc**. TA-Lib settles the
  *formula*, not history-independence: EMA/RSI/ATR/ADX and ~18 others carry an "unstable
  period", so the same bar over 500 vs 5000 bars of history differs **at the final bar**.
  Pinning `(bars, window)` is therefore not determinism — the contract is **exactly N bars**.
  Do not re-introduce the weaker claim.
- 2026-09-09: The four Codex bullets below are the implementer's sandbox notes, not session
  state. Codex runs without network or `.git` access, so its "cannot reach GitHub/Postgres"
  lines are normal, not a fault.

_One bullet before you stop, newest at the top: what you were thinking that no file
records — the approach already tried and rejected, why something is half-written, the
question you were about to ask. `uf next` reads the top bullet and shows it._

## Notes

_Durable observations about this product. Newest at the top. Reusable lessons go to
`uf learn` instead, and several already have._

- **Green criteria are not proof, and this repo has the counter-example.** US-006 passed 6/6,
  verified by a different vendor, while storing a Hong Kong day close as a UTC one — 78,834.1
  instead of 79,111.8. OKX's default `bar=1D` is aligned to **UTC+8**; UTC days need
  `bar=1Dutc`. Caught only because a human read a timestamp. Four of six PRD-001 defects came
  from criteria nobody had written.
- **Credentials are live and verified** (`.env.local`, gitignored): Supabase project
  `jsfyvxzuvxdnqhrqloux`, PostgreSQL 17.6 via the **session pooler** — the direct connection is
  IPv6-only without the paid add-on, so it fails from GitHub runners. FRED key reused from
  `crypto-investing-signals`. Healthchecks `crypto-data-ingest` proven end to end, including a
  real DOWN email. Cloudflare / cron-job.org / SoSoValue are deliberately `N/A` until the PRDs
  that need them.
- **Reachability is measured, not assumed** (`50-evidence/US-011/reachability-ci.json`, run
  34341379190): from a GitHub US runner, OKX/Coinbase/Kraken/CoinMetrics/alternative.me all
  return 200; **Binance 451 and Bybit 403**. That is why OKX is primary and why no self-hosted
  runner exists — the prior system's 24h outage traced to exactly that chain.
- **The machine runs out of memory and kills `uf run` mid-verification.** Repeated
  "interrupted" statuses are usually this, not flakiness. Check free RAM and committed memory
  before assuming a story is broken; ~5 GB free is comfortable. Recovery is automatic and does
  not cost an attempt.
- **SOL's on-chain column is genuinely thin and that is correct.** Coin Metrics' free tier has
  nothing for SOL — not even price — while BTC/ETH/BNB get MVRV, addresses, supply and flows.
  SOPR/MVRV are **not definable** on an account-based chain, at any price. Render
  `NOT_DEFINABLE`, never a proxy.
- **Macro release lag is measured, not estimated.** FRED, 2026-09-08: `DFF` 5 days behind,
  `DTWEXBGS` 11, **`M2SL` 69**. R4 had guessed 3–4 weeks for M2. A lagged series carries
  `reference_period` *and* `published_at`, and freshness is judged against publication.
- **The dashboard was moved earlier at the owner's request** — the designed page is now PRD-005,
  right after the indicators, so ~32 real cells exist to design against. Later panels add rows
  to a grid that is already designed. Its stories must set `agent: claude`; every design skill
  (`open-design:apple-hig` and friends) is Claude-only and Codex cannot invoke them.
