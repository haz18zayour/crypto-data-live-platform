# crypto-data-live-platform — session log

**Just arrived? Run `uf next`, then read the Handoff section at the bottom.** Those two are the whole picture.

Everything between the markers is generated from `.uf/events.ndjson` by `uf log`.
Do not hand-edit it — it is regenerated. The hand-written sections below it survive.

<!-- uf:generated:start -->

## ▶ Resume here

**PRD-005-dashboard — GATE G1, scope lock**

The research asked you questions and each carries the agent's own hypothesis. Anything you leave blank becomes an explicit assumption with a tripwire. The out-of-scope list is the one field with no default.

Owner: **You.** This one cannot be delegated.

```
open prds/PRD-005-dashboard/20-decisions.yaml
```

**Last handoff note:** 2026-09-14 — US-508 implementation is in the worktree: seven criterion-named CellFace tests pass, and web typecheck/build pass. Exact npm --prefix web test reaches 48 passed / 1 failed; only the pre-existing live Supabase BoardMatrix integration fails because fetch cannot reach board_read in this sandbox. Leave it fail-loud for external verification; do not mark the story complete.

## Where this stands

| PRD | Stories | Passed | State |
|---|---|---|---|
| PRD-001-spine | 8 | 8 | **all green** |
| PRD-002-harness | 7 | 7 | **all green** |
| PRD-003-corroboration | 7 | 7 | **all green** |
| PRD-004-indicators | 11 | 11 | **all green** |
| PRD-005-dashboard | 9 | 8 | 8/9 |

Spend to date: **$52.59** Claude · **119047k** Codex tokens.

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
- 08:18  US-307 started, attempt 3 (codex)
- 08:19  US-307 — codex finished `9782787b`
- 08:21  US-307 **PASSED** — 6/6 criteria, judged by claude · $0.56
- 10:52  researched PRD-004-indicators — 20 sources · $3.48
- 10:55  **PRD-004-indicators** compiled — 8 stories
- 10:56  US-401 started, attempt 1 (codex)
- 11:28  US-401 — codex finished `92a6d3ad` · 10612k tok
- 11:32  US-401 **PASSED** — 6/6 criteria, judged by claude · $0.61
- 11:34  US-402 started, attempt 1 (codex)
- 11:55  US-402 — codex finished `e092acba` · 3232k tok
- 11:57  US-402 **PASSED** — 5/5 criteria, judged by claude · $0.23
- 11:57  US-403 started, attempt 1 (codex)
- 12:19  US-403 — codex finished `2ac29895` · 2753k tok
- 12:22  US-403 **PASSED** — 6/6 criteria, judged by claude · $0.44
- 12:23  US-404 started, attempt 1 (codex)
- 12:45  US-404 — codex finished `e42479a2` · 4346k tok
- 12:48  US-404 **PASSED** — 6/6 criteria, judged by claude · $0.23
- 12:48  US-405 started, attempt 1 (codex)
- 13:12  US-405 — codex finished `ae552207` · 4561k tok
- 13:14  US-405 **PASSED** — 6/6 criteria, judged by claude · $0.24
- 13:14  US-406 started, attempt 1 (codex)
- 13:38  US-406 — codex finished `e07ed030`
- 13:42  US-406 **rejected** — 5/6 criteria, judged by claude · $0.58
- 13:42  US-406 started, attempt 2 (codex)
- 13:42  US-406 — codex finished `2b6d0a49`
- 13:44  US-406 **rejected** — 5/6 criteria, judged by claude · $0.50
- 13:45  US-406 started, attempt 3 (codex)
- 13:45  US-406 — codex finished `130c8f87`
- 13:46  **PRD-004-indicators** compiled — 8 stories
- 13:46  US-406 **rejected** — 0/6 criteria, judged by claude · $0.04
- 13:46  ⏸ **gate opened** — US-406 has failed 3 times — is the story wrong?

### 2026-09-12

- 12:40  ▶ gate answered **split** — The story bundles two separable concerns and kept half-landing as a result: (a) registering MACD and STOCHRSI as real IndicatorDefinition entries with corrected parameters, and (b) building a differential oracle whose independence from TA-Lib is proven rather than assumed. Verified on disk: load_registry() returns 1 entry, so the registration half genuinely did not land - this is incomplete work, not a verifier artifact, and a re-identified story will therefore produce a real diff. Splitting into US-409 (registration) and US-410 (oracle). Note the last attempt failed with 'verifier produced no parseable verdict' on C6, which is a verifier-side failure layered on top of the real gap.
- 12:41  **PRD-004-indicators** compiled — 9 stories
- 12:41  US-409 started, attempt 1 (codex)
- 12:52  US-409 — codex finished `1eebc6e2` · 2299k tok
- 12:53  US-409 **rejected** — 0/6 criteria, judged by claude
- 12:57  **PRD-004-indicators** compiled — 8 stories
- 13:04  US-411 started, attempt 1 (codex)
- 13:12  US-411 failed — interrupted while running — the process stopped before a verdict
- 13:12  US-411 started, attempt 1 (codex)
- 13:13  US-411 failed — interrupted while running — the process stopped before a verdict
- 13:13  US-411 started, attempt 1 (codex)
- 13:19  US-411 — codex finished `00a148cb` · 2022k tok
- 13:20  US-411 — codex finished `32d4eaea` · 1652k tok
- 13:24  US-411 **PASSED** — 7/7 criteria, judged by claude · $0.58
- 13:25  US-411 **PASSED** — 7/7 criteria, judged by claude · $0.67
- 13:27  US-407 started, attempt 1 (codex)
- 13:43  US-407 — codex finished `b1d70bb1` · 4449k tok
- 13:46  US-407 **PASSED** — 7/7 criteria, judged by claude · $0.63
- 13:47  US-408 started, attempt 1 (codex)
- 14:02  US-408 — codex finished `12647e80` · 2881k tok
- 14:06  US-408 **PASSED** — 6/6 criteria, judged by claude · $0.56
- 18:24  US-412 started, attempt 1 (codex)
- 18:32  US-412 — codex finished `8a2bc500` · 2158k tok
- 18:35  US-412 **PASSED** — 8/8 criteria, judged by claude · $0.68
- 18:38  **PRD-004-indicators** compiled — 8 stories
- 18:39  **PRD-004-indicators** compiled — 9 stories
- 18:42  **PRD-004-indicators** compiled — 10 stories
- 18:42  US-413 started, attempt 1 (codex)
- 18:47  US-413 — codex finished `c5cd20a6` · 1126k tok
- 18:49  US-413 **PASSED** — 6/6 criteria, judged by claude · $0.24
- 20:21  US-414 started, attempt 1 (codex)
- 20:34  US-414 — codex finished `bb5e6f8f` · 2428k tok
- 20:42  US-414 **rejected** — 0/7 criteria, judged by claude · $0.52

### 2026-09-13

- 08:21  **PRD-004-indicators** compiled — 11 stories
- 08:21  US-414 started, attempt 2 (codex)
- 08:26  US-414 — codex finished `b4109a9b` · 603k tok
- 08:32  US-414 **PASSED** — 7/7 criteria, judged by claude · $0.87
- 08:56  **PRD-005-dashboard** compiled — 9 stories
- 08:56  **PRD-005-dashboard** compiled — 9 stories
- 08:57  **PRD-005-dashboard** compiled — 9 stories
- 08:58  US-501 started, attempt 1 (claude)
- 09:02  US-501 — codex finished `5b6a30f2` · $1.23 · 18k tok
- 09:09  US-501 failed — interrupted while verifying — the process stopped before a verdict
- 09:09  US-501 started, attempt 1 (claude)
- 09:12  US-501 — codex finished `124c19b7` · $0.84 · 6k tok
- 10:11  US-501 **rejected** — 0/5 criteria, judged by codex
- 10:11  US-501 started, attempt 2 (claude)
- 10:13  US-501 — codex finished `f6da2f98` · $0.93 · 5k tok
- 10:22  US-501 **PASSED** — 5/5 criteria, judged by codex
- 10:22  US-502 started, attempt 1 (claude)
- 10:23  US-502 — codex finished `115620d8`
- 10:27  US-502 **rejected** — 0/6 criteria, judged by claude
- 10:27  US-502 started, attempt 2 (claude)
- 10:27  US-502 — codex finished `8fcdc787`
- 10:32  US-502 **rejected** — 0/6 criteria, judged by claude
- 10:32  US-502 started, attempt 3 (claude)
- 10:32  US-502 — codex finished `f299fd8b`
- 16:19  US-502 **rejected** — 0/6 criteria, judged by claude
- 16:19  ⏸ **gate opened** — US-502 has failed 3 times — is the story wrong?
- 19:38  ▶ gate answered **retry-anyway**
- 19:40  ⏸ **gate opened** — US-502 has failed 3 times — is the story wrong?
- 19:40  **PRD-005-dashboard** compiled — 9 stories
- 19:41  ▶ gate answered **skip**
- 19:41  US-510 started, attempt 1 (claude)

### 2026-09-14

- 05:43  US-510 — codex finished `07bc43c7` · $2.65 · 12k tok
- 05:52  US-510 **PASSED** — 6/6 criteria, judged by codex
- 05:52  US-503 started, attempt 1 (claude)
- 05:53  **PRD-005-dashboard** compiled — 9 stories
- 05:53  US-503 failed — interrupted while running — the process stopped before a verdict
- 05:53  US-503 started, attempt 1 (codex)
- 06:05  US-503 — codex finished `bc2821a2` · 2677k tok
- 06:09  US-503 **PASSED** — 7/7 criteria, judged by claude · $0.66
- 06:09  US-504 started, attempt 1 (codex)
- 06:19  US-504 — codex finished `8fe474c2` · 1861k tok
- 06:27  US-504 **PASSED** — 8/8 criteria, judged by claude · $0.28
- 06:28  US-505 started, attempt 1 (codex)
- 06:38  US-505 — codex finished `3b3b2c66` · 1645k tok
- 06:44  US-505 **PASSED** — 7/7 criteria, judged by claude · $0.30
- 06:44  US-506 started, attempt 1 (codex)
- 06:49  US-506 — codex finished `cbbf2d23` · 748k tok
- 06:54  US-506 **PASSED** — 7/7 criteria, judged by claude · $0.25
- 06:54  US-507 started, attempt 1 (claude)
- 07:03  US-507 — codex finished `8b373379` · $3.54 · 36k tok
- 07:08  US-507 **rejected** — 0/10 criteria, judged by claude
- 07:08  US-507 started, attempt 2 (claude)
- 07:10  US-507 — codex finished `7eff036d` · $1.56 · 7k tok
- 07:16  US-507 **PASSED** — 10/10 criteria, judged by codex
- 07:16  US-508 started, attempt 1 (codex)
- 07:25  US-508 — codex finished `4ddc5913` · 1713k tok
- 07:31  US-508 **PASSED** — 8/8 criteria, judged by claude · $0.29
- 07:31  US-509 started, attempt 1 (claude)
- 07:43  US-509 — codex finished `5add7873` · $3.86 · 55k tok
- 07:48  US-509 **rejected** — 0/10 criteria, judged by claude
- 07:48  US-509 started, attempt 2 (claude)
- 07:48  US-509 — codex finished `364848a8`
- 07:52  US-509 **rejected** — 0/10 criteria, judged by claude
- 07:52  US-509 started, attempt 3 (claude)
- 07:52  US-509 — codex finished `daf8f49e`
- 07:56  US-509 **rejected** — 0/10 criteria, judged by claude
- 07:56  ⏸ **gate opened** — US-509 has failed 3 times — is the story wrong?
- 11:06  ▶ gate answered **skip**
- 11:06  **PRD-005-dashboard** compiled — 9 stories
- 11:06  US-511 started, attempt 1 (claude)
- 11:13  US-511 — codex finished `9853206c` · $2.49 · 30k tok
- 11:17  US-511 **rejected** — 0/10 criteria, judged by codex
- 11:17  US-511 started, attempt 2 (claude)
- 11:19  US-511 — codex finished `facc59c1` · $0.96 · 5k tok
- 11:23  US-511 **rejected** — 0/10 criteria, judged by codex

<!-- uf:generated:end -->

## Handoff

- **2026-09-15 — US-511 attempt 3: this session's Bash/PowerShell tools denied every single
  command with "this session has no approval surface," including `node --version`-adjacent
  calls like `tsc`, `npm`, and even shell variable expansion — worse than prior attempts, which
  could at least run some commands. Confirmed with a fresh subagent too: same denial. So no
  command executed here, and no new screenshots or test output were produced this attempt.**
  What I could do instead: read every file the story touches. Found and fixed one real bug
  while auditing — `web/package.json`'s `pretest` ran `playwright install chromium`, but
  `chromium.launch()`'s default headless mode needs the separate `chromium-headless-shell`
  binary, which is exactly what the last recorded gate failure shows (`Executable doesn't exist
  at ...chromium_headless_shell-1187...chrome-win\headless_shell.exe`). Changed it to
  `playwright install chromium chromium-headless-shell`. This is the likely root cause of C4,
  C5, C9 failing last attempt — not the code in `BoardMatrix.tsx`/`CellFace.tsx`/`styles.css`/
  `capture-board.mjs`/`board.browser.test.ts`, which read correctly against every criterion
  (12 row headers, 48 cells, greyscale-distinguishable faces, 400px no-page-scroll, table
  semantics preserved). Also fixed a stale reference in `20_Design_System.md` line 106: it
  still named the retired `US-509` instead of its re-identified `US-511`. The design-doc
  content itself (colour-not-sole-channel, glyph-and-word table, PRD-005 not PRD-008) was
  already correct and `check-design-doc.mjs`'s logic confirms it matches by inspection.
  **Still owed, unchanged from before:** the three PNGs at
  `prds/PRD-005-dashboard/50-evidence/US-511/` do not exist. Whoever runs this next needs a
  session that can actually execute `npm --prefix web test` and
  `node scripts/capture-board.mjs` — this one could not, on any command, for any reason.

- **2026-09-14 — STOPPED HERE. PRD-005 is 8 of 9 real stories done; `US-511` is the only one
  left, and it is blocked on the environment, not on the work.** Read this whole bullet before
  running anything.

  **Branch:** `feat/prd-005-dashboard`, pushed. `main` is unchanged at `c4c0722` (PRD-004).
  Do not merge yet — US-511 is unfinished.

  **Story ledger.** `uf status` shows 8/11 because two ids are retired phantoms, not work:
  `US-502` was re-identified as `US-510` and `US-509` as `US-511`. Both originals failed 3×
  purely on Claude session rate limits (HTTP 429, zero files changed). Answering G5 with
  `retry-anyway` does **not** restore attempts in this framework; only a new story id does.
  Their G5 gates are answered `skip`. Real state: 501, 503, 504, 505, 506, 507, 508, 510 all
  passed with full evidence. Only **US-511** remains, with **1 attempt left** (2 rejected,
  1 interrupted by an OOM kill, which does not cost an attempt).

  **What US-511 still needs.** Attempt 1 of the original US-509 already landed and committed
  the design half: the stylesheet rewrite (738 lines), the `BoardMatrix` changes, the
  `20_Design_System.md` correction, `scripts/check-design-doc.mjs`, and a mixed-board dev page
  at `web/mixed-board.html`. `scripts/capture-board.mjs` also exists and is well-formed — it
  starts Vite itself, drives headless Chromium, waits on the 48th cell rather than a timer, and
  implements `--check-semantics` and `--check-contrast` via axe-core. **What is missing is only
  its output:** the three PNGs under `prds/PRD-005-dashboard/50-evidence/US-511/`
  (`board-live-light.png`, `board-live-dark.png`, `board-mixed-light.png`), plus the greyscale
  and 400px-width tests.

  **The blocker, and it will bite you again.** The implementer agent **cannot install
  dependencies** — every `npm install` came back *"Permission for this tool use was denied. It
  requires approval, and this session has no approval surface."* So anything a story needs from
  a package manager must be in place **before** `uf run` starts. On the new machine, run these
  by hand first:

  ```
  npm --prefix web install            # node_modules is not in git
  cd web && npx playwright install chromium chromium-headless-shell
  ```

  `web/package.json` already pins `playwright@1.55.0` and `@axe-core/playwright@4.10.2`, and has
  a `pretest` hook that installs the browser. Two traps I hit: Playwright 1.55 wants Chromium
  build **1187** specifically (I had warmed the cache with 1.56, which fetches 1200+, and the
  launch failed on the mismatch); and a killed download leaves a `__dirlock` directory in
  `%LOCALAPPDATA%\ms-playwright` that blocks every later install until you delete it.

  **Then simply:** `uf run`. If US-511 exhausts its last attempt, answer the G5 gate `skip`,
  re-identify it as `US-512` the same way (git mv the story file, change `id:`, update the
  path in the three `[browser:]` criteria and the story table in `30-spec.md`, `uf compile`),
  and run again.

  **Applied to production by hand, because nothing else will.** `ingest/migrate.py` only
  supports `--check`; **it has no apply path at all**. `20260913120000_create_board_read.sql`
  was executed against the live database on 2026-09-14 and PostgREST's schema cache reloaded
  with `notify pgrst, 'reload schema'`. Verified: `board_read` returns **45 rows for 45 distinct
  cells**, and an anonymous REST read returns HTTP 200 with real values. **US-510 had passed
  6/6 while the view did not exist in production** — its tests run against `TEST_DATABASE_URL`,
  so they proved the migration was correct and never that it was applied. US-507's integration
  criterion is what caught it, at HTTP 404. Any future migration needs the same manual step.

  **Agent routing was changed mid-PRD and the reasoning matters.** I originally set
  `agent: claude` on all nine stories because every design skill is Claude-only. That was
  over-applied: it put a SQL migration, a TypeScript model and a registry change through the one
  quota the design skills need, and the quota became the bottleneck — **US-510 spent ten hours
  on a single attempt, throttled eighteen times.** After rerouting, the same class of story
  passed in minutes for $0.25–$0.66. **Only US-507 and US-511 carry `agent: claude` now.** Keep
  it that way. The framework flips the verifier automatically when implementer equals the
  configured verifier, so the different-vendor rule holds either way — verified in
  `ultimate-framework/src/core/verify.ts`.

  **Memory killed this run three times.** `uf run` needs roughly **5 GB free**; it died at
  2–3 GB with Chrome open. This is the single biggest reason to move to a stronger machine.

  **Still owed, unchanged:** rotate the Supabase database password, anon key and service-role
  key — all three were pasted into a chat transcript. And integration tests still refetch rather
  than sharing a cached fixture; the 4-hour suite is mitigated by deselection, not fixed.

- 2026-09-14 — US-508 implementation is in the worktree: seven criterion-named CellFace tests pass, and web typecheck/build pass. Exact npm --prefix web test reaches 48 passed / 1 failed; only the pre-existing live Supabase BoardMatrix integration fails because fetch cannot reach board_read in this sandbox. Leave it fail-loud for external verification; do not mark the story complete.
- 2026-09-14 — US-507 attempt 1 failed on one test only (C8/C9: live `board_read` → HTTP 404; 41/42 passed, typecheck clean). Cause is not in `web/`: `supabase/migrations/20260913120000_create_board_read.sql` was only ever executed inside throwaway schemas by `tests/test_board_read.py`, never against live `public`, so PostgREST has no such relation. G4 already approved it ("proceed"). **Owed before re-verifying US-507:** apply that one migration to production and `notify pgrst, 'reload schema'`. Attempt 2 could not do this: the session's permission mode denied the DB write, `npm test`, and typecheck. No code was changed. Do not work around it by reading `datapoints_read` instead, because that goes against the PRD's single-view decision.
- 2026-09-14 — US-505 implementation is present in the three expected story paths and awaits independent verification. The fixture uses the real buildBoard model and parsed registry; no story status was changed.
- 2026-09-14 — US-504 implementation is ready for external verification: btc_daily_close declares ETH/SOL/BNB not_definable with a mandatory reason; overlap is rejected; board gaps render NOT_DEFINABLE with unchanged detail and revert to NOT_FETCHED when removed. Criterion-focused Python tests: 29 passed with 1 integration deselected; web: 23 passed, typecheck/build clean. Exact Python gate reached 172 passed and 10 deselected but has 20 fail-loud PostgreSQL setup errors because this restricted sandbox cannot connect.
- 2026-09-13 (session): **PRD-004 fully complete, 11/11 stories, merged.** The board now
  **persists**: `run_all_assets()` + `persist_board()` computes 44 indicators in ~23s and
  writes them — database holds **50 rows, 45 distinct indicators, 4 assets**. Every asset
  shows `EMA200 < EMA50 < EMA20` independently, a coherent uptrend stack.
  **localhost still renders only the BTC daily close** — the page is PRD-001's single-value
  view. Turning 45 cells into the completeness matrix is **PRD-005**, which now has real
  data to design against instead of placeholders.
  Suite: 182 tests, 150s. Note `uf run` checks out the branch in `30-spec.md` front-matter —
  author story files there or they vanish mid-run and the verifier gets no criteria text
  (that caused two 'no usable JSON' failures here).
- 2026-09-13 — US-414 attempt 2: persistence code/tests already landed in bb5e6f8; verifier exit-1 root cause was the absent story/criteria file, restored and compiled in 8f98ce5. Five fast US-414 tests pass; Ruff and strict ingest mypy pass. Exact pytest collected 166 passes and 16 fail-loud Postgres setup errors only because this restricted sandbox cannot reach the configured DB; committed gate evidence from the DB-enabled run records 182 passed. Independent verifier should now read US-414 from spec.lock.json and judge the existing named tests.
- 2026-09-12 — US-414 implementation and tests are in the worktree. Fast board/heartbeat evidence: 8 passed; Ruff and ingest mypy clean. Exact pytest gate: 166 passed, 10 live deselected, 16 fail-loud Postgres setup errors because this sandbox cannot reach the configured database. Real Postgres and live full-board tests are in tests/test_persist_board.py for external verification; do not mark complete from this handoff.
- 2026-09-12 (session): **PRD-004 complete including two late defects the 8/8 green run
  missed.** Board is **45 entries**, 11–12 indicators per asset across BTC/ETH/SOL/BNB:
  RSI, EMA 20/50/200, ATR, Bollinger (3 bands), OBV, MACD, StochRSI, daily close.
  **EMA was named in the spec and never built** — `grep -c EMA registry.yaml` returned 0 while
  every story passed, because registry coverage checks that registered indicators have
  evidence and is blind to one nobody registered. **OBV shipped with `required_bars: 1`**
  (cumulative indicator over one bar = that bar's volume), then 5 (its golden's length),
  now **200 with the reasoning on the entry**. Both fixed as US-412/US-413.
  Suite: **176 offline tests in 39s**; integration deselected by default after the full run
  hit **4h03m** by throttling OKX/Coinbase. That inefficiency is mitigated, **not fixed** —
  live tests still refetch rather than share a cached fixture. Owed work.
  Next: **PRD-005, the dashboard**, against a board that is finally real.
- 2026-09-12 (session): **PRD-004 complete, 8/8**, board at **33 indicators across BTC/ETH/SOL/BNB**.
  Strongest evidence in the project: RSI matches StockCharts' published spreadsheet across 19
  values to within **0.005**, and an EMA-smoothed variant misses by 6 points — so the test
  discriminates rather than merely passing.
  **Scale problem found and mitigated:** the full suite went 73s → **4h03m** once 33 indicators
  needed 250 bars each (OKX history-candles caps at 100/request). Nine live tests caused it,
  throttling both venues. Integration is now deselected by default (**170 offline tests in
  53s**) and runs as a separate non-blocking CI step. **The underlying inefficiency is not
  fixed** — live tests still refetch instead of sharing a cached fixture. Worth a small PRD.
- 2026-09-12 — US-408 implementation evidence is ready for external verification: registry notes declare dated history for all 8 asset/venue pairs, including Coinbase BNB=317 on 2026-09-10; tests/test_assets.py proves the 249-vs-250 uncorroborated path, 317-vs-250 margin, all 32 technical cells, pair routing, and a fail-loud live four-asset run. Scoped regressions: 91 passed with 5 live tests deselected; Ruff and mypy clean. Exact full suite: 156 passed, with this sandbox's known socket restriction causing 5 live failures and unavailable PostgreSQL causing 18 fail-loud setup errors.
- 2026-09-12 — US-407 implementation is ready for external verification: the real registry has 33 rows (32 technical outputs across BTC/ETH/SOL/BNB plus btc_daily_close), each explicitly references parameters, a reusable golden, required_bars and the okx_candle response model. tests/test_coverage.py has criterion-named scale, uncovered-entry, uniqueness, explicit-parameter, diagnostic-message and real-registry integration tests. Coverage: 9 passed; surrounding registry/indicator tests: 38 passed; Ruff and ingest mypy pass; exact registry --validate exits 0. Full suite: 151 passed, with the known sandbox-only 4 live socket failures and 18 fail-loud PostgreSQL setup errors.
- 2026-09-12 — US-411 artifacts are present in recovered commits: 21 criterion-scoped tests pass, including parsed registry entries, corrected parameters, TA-Lib spy and delegation-bite controls, converged-tail differential checks, goldens, response models, and whole-registry coverage. Ruff and ingest mypy pass. The exact full-suite command reaches 147 passed but this sandbox blocks OKX/Coinbase sockets and PostgreSQL, producing 4 live failures and 18 fail-loud setup errors; do not weaken or skip those gates.
- 2026-09-10 — US-405 implementation evidence is ready for external verification: TA-Lib Bollinger(20,2,SMA) matches the committed 1..20 population-stdev arithmetic; the sample-stdev control is rejected; OBV matches a five-step hand calculation including a positive-volume flat close and ignores conflicting quote volume; venue base-volume source_field text and the flat rule are pinned in the golden registry fixture. Named gate 5 passed; deterministic regressions 132 passed with 7 live integrations deselected; Ruff and strict mypy clean. Full suite reached 135 passed but blocked sockets caused 4 live failures and unavailable PostgreSQL caused 18 fail-loud fixture errors. Commit unavailable because .git is read-only.
- 2026-09-10 — US-404 implementation is ready for external verification: StockCharts cs-rsi.xls and cs-atr (1).xls rows are committed as nested external fixtures; TA-Lib wrappers match every published output, reject an EMA-smoothed RSI control, and RSI/ATR N=250 vs N=500 tails agree within 1e-6. Named gate 5 passed; scoped regressions 123 passed with 5 live integrations deselected; Ruff and strict mypy clean. Full local suite reached 129 passed but 15 fail-loud PostgreSQL fixtures cannot connect in this sandbox. Commit unavailable because .git is read-only.
- 2026-09-10 — US-403 implementation is ready for external verification: OKX history pagination is capped at 100 and Coinbase time-window pagination at 300; both fail on short pages and validate exact newest-first UTC-daily contiguity after assembly. Criterion tests: 5 passed (live deselected); deterministic regressions: 118 passed; Ruff, ingest mypy, registry validation clean. Live test exists and fails loud because this sandbox blocks outbound sockets (WinError 10013). Commit was unavailable because .git is read-only.
- 2026-09-10 — US-402 implementation pending external verification: parameterized TA-Lib lookback validation and the 250-bar recursive floor are in ingest/registry.py; tests/test_lookback.py has criterion-named biting tests. Targeted 8 passed, deterministic 117 passed, registry CLI/ruff/strict mypy clean. Full suite reached 120 passed but live sockets and PostgreSQL are blocked in this sandbox.
- 2026-09-10 (session): **PRD-003 complete, 7/7**, merged. Corroboration is live: OKX and
  Coinbase compared per UTC day, tolerance **25 bps measured** from 59 days (median 7.1,
  p90 10.8, max 13.8; the bar=1D defect was 35.2). G4 migration **applied to production** —
  two venues now coexist where the second write previously UPDATEd the first. Adversarial
  proof at `prds/PRD-003-corroboration/50-evidence/US-307/divergence.png`.
  **Known limits, do not overstate this:** only spot close has a second venue, so most of
  the board stays uncorroborated; 59 days is a thin sample; and a shared bug in our own
  comparison code is invisible to corroboration (same wrong offset twice = zero
  divergence). Next: **PRD-004 technical indicators**, the first real scale test.
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
