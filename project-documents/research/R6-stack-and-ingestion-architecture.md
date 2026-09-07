# R6 — Stack and Ingestion Architecture for a Single-User Crypto Observability Dashboard

Researched 2026-09-07. All prices/limits below were fetched live from vendor pages or vendor-adjacent sources during this session; anything not independently confirmed against an official page is marked **UNVERIFIED**.

---

## 1. Executive Summary

**Headline recommendation:** Keep the owner's existing stack almost unchanged — Python 3.12 + APScheduler ingestion, Supabase Postgres (port 5432, direct connection, no PgBouncer), Vite/React/TS on Cloudflare Pages — but swap the trigger mechanism for scheduled jobs from a self-hosted Fly.io runner or a bare GitHub Actions `schedule:` to **GitHub Actions `schedule:` as the primary trigger, fronted by `cron-job.org` (or a second scheduler) calling `repository_dispatch` as a backup path, with a Fly.io `shared-cpu-1x` machine used only as a stateless, on-demand worker that is invoked and shut down per run — never a long-lived background process.** This directly avoids both documented failure modes: no persistent WebSocket listener ever competes with scheduled jobs for CPU (failure 1), and there is no self-hosted runner process that can silently exit (failure 2) — GitHub-hosted runners are ephemeral VMs Cloudflare/GitHub manage, not a process the owner must supervise.

For storage: plain Supabase Postgres, no TimescaleDB/ClickHouse/DuckDB layer. The realistic 3-year row count for this dataset is in the **low single-digit millions**, which is a non-event for Postgres.

For frontend: Vite + React + TS on Cloudflare Pages (free tier is generous and already familiar), with **TradingView Lightweight Charts** as the primary charting library for candlesticks and dense sparklines, falling back to **uPlot** for extremely dense multi-series panels where Lightweight Charts' feature set doesn't fit.

For "live": given the underlying cadences (minutes to months) and the scar tissue from a WebSocket listener causing CPU contention, **polling/revalidation (e.g., TanStack Query with a 30–60s interval, or Supabase Realtime's Postgres-changes feed consumed only by the browser, never by the ingestion worker) is correct — a self-hosted WebSocket push layer is not justified for a single viewer.**

For auth: **Cloudflare Access (Zero Trust) free tier**, not Supabase Auth magic link — it keeps auth entirely at the edge, requires no service-role key in the browser, and needs no email-sending infrastructure, at $0/mo for a single user (well under the 50-user free cap).

For language: **stay on Python** for ingestion. The TA/data ecosystem (pandas, numpy, ccxt, pandas-ta) and the owner's existing fluency outweigh the single-language argument for a low-frequency (minutes-to-months cadence) batch ingestion job — this is not a place where Workers' V8-isolate speed matters.

---

## 2. Scheduling Comparison

| Option | Free tier | Paid tier | Reliability characteristics | Cron/subrequest limits | Fit for this project |
|---|---|---|---|---|---|
| **GitHub Actions `schedule:`** | 2,000 min/mo (private repos, free personal account); unlimited on public repos | Actions minutes bundled with GitHub plans ($4/mo Team adds more, or pay $0.008/min Linux overage) | GitHub's own docs: *"The schedule event can be delayed during periods of high loads of GitHub Actions workflow runs. High load times include the start of every hour."* Under sufficiently high load "some queued jobs may be dropped" entirely — no run, no error. Community reports (2026) document delays from minutes up to several hours at peak times, and outright skipped runs. | Auto-**disables scheduled workflows in public repos after 60 days with no repository activity** (push/PR/release — not just cron runs) — a private-repo variant of this rule is reported by users though GitHub's own docs specifically scope it to public repos | Good baseline; must run at off-the-hour minutes (e.g. `:07`, `:23`) and must have an independent watchdog, because it *will* silently skip occasionally |
| **Cloudflare Workers Cron Triggers** | 5 triggers/account, 10ms CPU/invocation (HTTP), 10ms CPU for cron on free plan, **50 subrequests/invocation** | Workers Paid $5/mo: 250 triggers/account, up to 5 min CPU (HTTP)/30s–15min CPU (cron, depending on interval), **10,000 subrequests/invocation** (scalable to 10M) | Cloudflare-managed, no queueing/backlog issues like GH Actions; wall-clock cap is 15 min per cron invocation on both tiers | 50 subreq (free) is a hard wall for ~12 APIs called serially with retries — Paid tier's 10,000 removes this constraint entirely | Excellent *trigger* reliability, but ingestion logic in JS/TS on Workers means porting the Python signal engine — see §6 |
| **Supabase pg_cron + pg_net / scheduled Edge Functions** | pg_cron ships in Postgres extensions list; Edge Functions: 500,000 invocations free, then $2/million | Pro $25/mo unlocks larger compute, no pausing | **Free-tier projects pause after 7 days of inactivity** — a fatal flaw for a scheduler that must run unattended: a paused DB stops accepting pg_cron jobs and stops serving the dashboard until manually resumed | pg_net is async HTTP from inside Postgres — workable for pings, awkward for calling 12 different rate-limited/paginated APIs with real error handling | Not recommended as the *primary* orchestrator; fine as a secondary heartbeat/health-check inside the DB you already have |
| **Railway Hobby** | none (trial credit only) | **$5/mo includes $5 of usage credit** (i.e., effectively pay-as-you-go beyond that) | Always-on services supported; this is what the owner already ran successfully pre-scar-tissue | No native cron primitive documented on the pricing page — cron typically implemented as a scheduled restart of a script or via Railway's cron service type | Solid, known-good option; owner has already operated this |
| **Fly.io shared-cpu-1x** | Free allowances limited to certs/snapshots only; no general free compute confirmed on current pricing page | ~$1.94–$2.54/mo per `shared-cpu-1x-256mb` machine (region-dependent), pay-as-you-go | Fully controllable; supports `[[restart]] policy = "always"` and machines that start on-demand and stop — ideal as a stateless worker triggered by an external scheduler rather than a resident cron/process | N/A (self-managed) | Best used as **compute**, not as the **scheduler** — this is exactly the role it played before scar tissue 2 (self-hosted runner as scheduler was the mistake, not Fly itself) |
| **Render** | 750 free instance-hours/mo for web services (spin down after 15 min idle); **no free tier for Cron Jobs** | Cron Jobs bill per minute, from **$0.00016/min**, ~$1/mo minimum per cron service (UNVERIFIED exact rate — pulled from third-party aggregator, not render.com/pricing directly) | Managed cron primitive exists (`render.com/docs/cronjobs`) | N/A | Viable paid alternative to GH Actions, but adds a second billing relationship for marginal benefit here |
| **Koyeb** | Free Postgres only (0.25 vCPU/1GB, 5h/mo); no free compute confirmed for services | Pro from $29/mo, $10 included compute | Scale-to-zero and always-on both supported; no cron-specific pricing surfaced on the pricing page | UNVERIFIED subrequest/cron specifics | Not a natural fit; pricier entry point than Railway/Fly for this workload |
| **Hetzner CX22** | none | **≈€4.35–4.59/mo** for 2 vCPU / 4GB RAM / 40GB NVMe, 20TB egress | Full VM — you own cron (systemd timer or crontab) entirely; no vendor scheduling reliability question at all, but *you* are the watchdog | N/A (bare VM) | Cheapest raw compute by far; best paired with an external dead-man's-switch (e.g., Healthchecks.io/cron-job.org ping) since nothing above you enforces the schedule |
| **Val Town** | Free: 15-min cron granularity, 1-min max runtime, 100k runs/day | Pro $21/mo: 1-min granularity, 10-min max runtime, 1M runs/day | Managed, simple; runtime cap (1–10 min) may be tight for calling ~12 APIs with retries in one invocation | N/A | Good for lightweight single-purpose crons; less ideal as the single orchestrator for a 12-API fan-out job unless split into many small vals |
| **Deno Deploy** | 1M requests/mo, 20GiB egress, 10 active apps | Pro $20/mo | Cron/scheduled task support **not documented on the pricing page itself** — Deno Deploy does support `Deno.cron()` per its runtime docs (UNVERIFIED against pricing page; confirm via docs before relying on it) | UNVERIFIED | Would require a TypeScript rewrite of ingestion; not recommended given the Python ecosystem argument |
| **Modal** | $30/mo free compute credit, 100 containers | Team $250/mo | Native `modal.Cron`/`modal.Period` scheduling primitives, Python-native (matches owner's stack) | UNVERIFIED subrequest limits (not applicable — full outbound network access from a container) | Strong dark-horse candidate: Python-native scheduled functions with a real free tier; worth a spike if GH Actions delay ever becomes unacceptable |
| **Inngest** | Hobby free: 50k executions/mo, 500k events/mo, cron use case explicitly listed | Pro from $99/mo | Durable execution, step retries built in; cron support present but tier-specific caps for scheduled jobs not broken out separately on pricing page | UNVERIFIED | Better suited to event-driven fan-out than simple periodic polling; likely overkill here |
| **Trigger.dev** | Free: $5 credit/mo, 10 schedules max, 20 concurrent runs | Hobby $10/mo (100 schedules), Pro $50/mo (1,000+ schedules) | "Durable cron schedules without timeouts" — explicitly designed to avoid the GH Actions delay problem | Billed per-second compute + $0.000025/run | Legitimate alternative if the project outgrows GH Actions' timing slop; free tier's 10 schedules covers ~12 APIs only if consolidated into fewer jobs |
| **Upstash QStash** | Free: 1,000 msgs/day, 10 active schedules, 7-day max delay | Pay-as-you-go $1/100k msgs; Fixed 1M $180/mo | Schedule-a-webhook primitive, not a compute host — needs a receiving endpoint (Worker/Fly/etc.) | 10 schedules (free) is enough for this project's ~4 cadences if grouped, not if split per-API | Best used as the *reliable trigger* calling into a Fly/Worker endpoint that does the actual fan-out to 12 APIs, rather than as the compute layer itself |

### Ranked recommendation for the scheduling layer

1. **GitHub Actions `schedule:` as primary**, running the existing Python ingestion in-runner (no external compute host needed for the ingestion logic itself — GH-hosted runners have full Python + network access). Schedule at off-peak minutes, keep the repo "active" (a monthly trivial commit, or note the private-repo nuance) to dodge the 60-day disable rule.
2. **cron-job.org calling `repository_dispatch`** (as the owner already used) as an independent second trigger with a *different* minute offset — this catches the case where GH Actions' own cron event is delayed/dropped, since `repository_dispatch` triggers immediately via the REST API rather than going through the internal cron queue.
3. **A dead-man's-switch** (Healthchecks.io free tier or a simple Supabase row + separate cron-job.org check) that pages the owner if no successful ingestion row has landed within 1.5x the expected interval — this is the direct fix for scar tissue 2 (silent 24h data gap), independent of which scheduler is used.
4. Do **not** resurrect a persistent background process (self-hosted runner, WebSocket listener, or long-lived Fly machine) as the scheduler. If Fly.io compute is needed at all (e.g., for a long-running backfill), invoke it on-demand from GitHub Actions via the Fly Machines API and let it stop itself — never keep it resident.

---

## 3. Storage

### Free-tier limits (Supabase/Postgres, confirmed live from supabase.com/pricing)
- **Free plan:** 500 MB database (shared CPU, 500MB RAM), 5GB egress + 5GB cached egress/mo, 50,000 MAU, 200 concurrent Realtime connections, 500k Edge Function invocations/mo.
- **Free projects are paused after 7 days of inactivity** (Supabase docs: "Free Plan projects... paused if no activity for 7 consecutive days"; restorable from the dashboard, data intact). This matters for the *dashboard's* Supabase project even if ingestion runs elsewhere — daily scheduled writes from GitHub Actions will keep it "active" and prevent pausing, so this is a non-issue given the ingestion cadence.
- **Pro plan ($25/mo):** 8GB disk, 250GB egress, 100GB storage, 500 Realtime connections, no pausing.

### Row-count estimate (3 years, 4 assets, ~35 indicators, ~12 APIs)

| Category | # series | Cadence | Rows/series/3yr | Total rows (3yr) |
|---|---|---|---|---|
| Price/OHLCV (if stored at 5-min bars) | 4 (one per asset) | 5 min | ~315,360 | **~1,261,000** |
| Price/OHLCV (if stored at 1-min bars, worst case) | 4 | 1 min | ~1,576,800 | ~6,307,000 |
| Funding rates | 4 | 8-hourly | ~3,285 | ~13,000 |
| On-chain indicators | ~10 × 4 assets | daily | ~1,095 | ~43,800 |
| Macro indicators (mostly global, not per-asset) | ~10 | daily-equivalent | ~1,095 | ~11,000 |
| Remaining misc indicators (sentiment, dominance, etc.) | ~14 | daily | ~1,095 | ~15,300 |
| **Total (5-min price bars)** | | | | **~1.34 million rows** |
| **Total (1-min price bars, worst case)** | | | | **~6.4 million rows** |

At ~100–150 bytes/row (bigint id, smallint asset/indicator FK, timestamptz, float8 value, provenance columns, plus index overhead), the worst case (1-min price bars for 3 years) is roughly **0.6–1GB** — comfortably inside Supabase Pro's 8GB, and even tight-but-plausible on the 500MB free tier if older bars are downsampled or price history is capped at 1-year raw + rolled-up older data. The 5-min-bar scenario (~1.3M rows, ~150–250MB) fits the **free tier alone**, with room to spare for everything else.

**Conclusion: nothing beyond plain Postgres is remotely warranted.** This is not a "big data" problem — it is a few million narrow rows over three years for a single viewer. Any analytical database is solving a problem this project doesn't have.

### One line each on alternatives
- **TimescaleDB:** Purpose-built for exactly this shape of data (time-series, downsampling, continuous aggregates) but adds an extension/operational dependency for a dataset 2–3 orders of magnitude below where its compression and chunking advantages start to matter; Timescale Cloud's free tier (10GB) would work but is pure overhead here.
- **ClickHouse (Cloud):** No permanent free tier as of 2026 (30-day/$300 trial only, then $66/mo Basic) — disqualified on cost alone for a project this small, and its columnar OLAP design targets billions of rows, not millions.
- **DuckDB + Parquet on R2:** Excellent *read-path* fit (see below) but Parquet files are not naturally append-friendly for a scheduler writing every few minutes-to-hours; would require a rewrite-the-file-per-batch pattern, adding real complexity for zero benefit at this row count.
- **Turso/libSQL:** Free tier (5GB storage, 500M rows read/mo, 10M rows written/mo) is generous and would work, but offers no advantage over Postgres here and loses Supabase's Realtime/Auth/Storage bundle.
- **Cloudflare D1:** 500MB (free) / 10GB (paid) max DB size, 50 (free) / 1,000 (paid) queries per Worker invocation — workable size-wise but the per-invocation query cap is an awkward fit for a dashboard doing ad-hoc multi-indicator queries, and it fragments the stack away from the single Supabase project the owner already knows.
- **DuckDB-WASM over Parquet on R2, no database at all:** Technically the *read side* works well — DuckDB-WASM can run SQL directly against Parquet files over HTTP range requests served from R2 (confirmed free egress, 10GB storage free) with no backend query layer at all. But the *write side* (ingestion appending rows every few minutes to hours from 12 APIs) does not map cleanly onto immutable Parquet files without a compaction job, which reintroduces exactly the operational complexity Postgres avoids for free. **Verdict: not worth it at this scale** — the row count that would justify a Parquet/R2 architecture (tens to hundreds of millions of rows, high egress) doesn't exist here.

---

## 4. Frontend + Charting

### Cloudflare Pages free tier (confirmed via developers.cloudflare.com/pages/platform/limits)
500 builds/mo, 1 concurrent build, 20-min build timeout, 100 custom domains, 20,000 files/site (25MiB max/file), 100 projects/account. No documented bandwidth cap on the free tier (Cloudflare's model is unmetered static asset bandwidth). This is already what the owner used and remains the right choice — no reason to change.

### Charting comparison

| Library | Bundle size | Perf at 10k–100k pts | Candlesticks | License/attribution | Many small sparklines |
|---|---|---|---|---|---|
| **Lightweight Charts (TradingView)** | ~45KB gzipped, purpose-built canvas renderer | Excellent — designed for exactly this (financial time series, real-time updates) | Native, first-class | **Apache-2.0.** Confirmed via GitHub LICENSE + TradingView docs: **attribution IS required** — a link to tradingview.com must appear on any page using the library, satisfiable via the built-in `attributionLogo` chart option (small corner logo/link) rather than a separate notice. Not a blocker, just must not be disabled without providing equivalent attribution elsewhere. | Good but not primarily designed for many tiny multi-panel sparklines — one chart instance per panel adds up in DOM/canvas count |
| **ECharts** | ~1MB full bundle, tree-shakeable down significantly by importing only used chart types/components | Good, GPU/canvas-friendly, handles large series well | Supported via candlestick series type | Apache-2.0, no attribution requirement | Capable but heavier per-instance overhead; better suited to fewer, richer charts than many small ones |
| **uPlot** | **<50KB**, one of the smallest serious charting libs available | **Best-in-class** — explicitly built for huge point counts at 60fps, canvas-based | Possible but manual (no built-in candlestick series; must draw OHLC bars yourself) | MIT, no attribution | **Best fit for many small sparkline panels** given its tiny per-instance footprint and raw speed |
| **Recharts** | Moderate (React + D3-based, SVG) | Degrades past a few thousand points (SVG DOM nodes) | No native candlestick | MIT | Poor fit — SVG-per-point doesn't scale to dozens of dense panels |
| **visx** | Low-level primitives (D3 + React), size depends on what you compose | Depends entirely on implementation | DIY | MIT | More building-block than solution; more engineering effort than this project needs |
| **Observable Plot** | Moderate, SVG/Canvas hybrid | Good for exploratory/static charts, not optimized for live-updating dense series | No native candlestick | ISC | Better for one-off exploratory plots than a live dashboard |

**Recommendation:** **Lightweight Charts** as primary for the 4 main asset price/candlestick panels (its purpose-built financial-chart ergonomics — crosshair, time scale, price scale — save real engineering time, and the attribution logo is a one-line config, not a real cost). **uPlot** as the fallback/secondary for the ~25–35 smaller indicator sparkline panels, where its sub-50KB footprint and raw canvas speed matter more across many simultaneous chart instances than Lightweight Charts' financial-specific chrome.

### What "live" should mean
Given cadences of minutes (price) to months (macro), and given that **scar tissue 1 was directly caused by a persistent WebSocket listener contending for CPU with scheduled jobs on a shared-cpu-1x Fly machine**, a push layer is not justified here for a single viewer. The correct model is **polling/revalidation**: the dashboard fetches from Supabase on an interval (e.g., 30–60s via TanStack Query `refetchInterval`, or on tab focus) matched loosely to the fastest underlying cadence, not a persistent connection. This eliminates the exact class of background process that caused the prior incident, at zero cost to the single user's experience (nobody needs sub-second updates on 8-hourly funding or daily on-chain data).

**Supabase Realtime vs polling vs SSE:** Supabase Realtime (Postgres changes) is free up to 200 concurrent connections and would technically work, but it reintroduces a persistent connection from the client — for a *single browser tab*, this is materially the same risk profile (a long-lived socket) as scar tissue 1, just moved to the frontend instead of a backend worker. Since the frontend isn't sharing a CPU with the scheduler, this is lower-risk than the original incident, but it's still unnecessary complexity for data that changes at most every few minutes. **Recommend plain polling** — simplest, no additional infrastructure, and trivially observable/debuggable. SSE is a reasonable middle ground if the owner later wants push-without-websocket-complexity, but isn't needed at v1.

---

## 5. Auth

| Option | Cost | Complexity | Service-role key exposure risk |
|---|---|---|---|
| Supabase Auth (magic link) | Free | Requires email delivery setup (SMTP or Supabase's rate-limited default), session/JWT handling in the frontend, RLS policies in Postgres | Low if done correctly, but RLS misconfiguration is a recurring real-world failure mode; more moving parts than a single-user app needs |
| **Cloudflare Access (Zero Trust)** | **Free** — confirmed free tier covers up to 50 users (well above the 1 needed); paid tier is $7/user/mo if ever exceeded | Lowest — Access sits in front of Cloudflare Pages, authenticates via existing identity provider (Google/GitHub/one-time PIN) before the SPA ever loads, no code changes to the frontend | **Zero** — auth happens entirely at Cloudflare's edge before any request reaches the app; no service-role key, no JWT handling, no RLS dependency for the *page* itself (RLS on Supabase should still exist as defense-in-depth for the API calls the SPA makes directly) |
| Edge basic auth (Worker-checked password) | Free | Low, but weaker (no MFA, no SSO, password-in-header) | Zero exposure but weaker authentication guarantee |
| Bare Worker-checked token | Free | Low-moderate (hand-rolled token issuance/rotation) | Zero exposure but reinvents what Access already provides |

**Recommendation: Cloudflare Access.** For exactly one user, it is strictly lower-complexity than Supabase Auth magic link (no email infra, no session code in the SPA) and strictly more secure than basic auth or a hand-rolled token (supports real identity providers, short-lived edge-signed JWTs, device posture if ever wanted). It also cleanly satisfies "no service-role key may ever reach the browser" — the browser only ever needs the Supabase anon key plus RLS policies scoped to the single user, and Access is a completely separate gate in front of that.

---

## 6. Language Split: Python vs TypeScript for Ingestion

**Verdict: stay on Python.**

- The owner already has a working, battle-tested Python 3.12 + APScheduler + pydantic-settings + structlog ingestion engine. Rewriting ~12 API integrations in TypeScript to run on Workers buys "one language across the stack" but costs a full rewrite of working code, re-introduces the exact class of bugs already shaken out of the Python version, and Workers' constraints (10ms CPU free / 50 subrequests free, or paid-tier limits) are a worse fit for a job that needs to call 12 rate-limited external APIs with retries and backoff than a GitHub Actions runner or a plain VM with unrestricted execution time and outbound calls.
- TypeScript-on-Workers would mostly pay off if ingestion needed to be *low-latency* or *edge-distributed* — neither is true for data that updates every few minutes to months.
- The TA/data ecosystem argument (pandas, numpy, ccxt) is real and current: Python remains meaningfully more mature here in 2026, and the owner is fluent in it specifically. There is no forcing function to change.
- Frontend (Vite/React/TS) staying in TypeScript is correct regardless — that's a separate axis, and the two languages meeting only at the Supabase Postgres boundary (Python writes, TS/SQL reads) is a clean, well-understood seam.

---

## 7. Three Fully-Specified Stacks by Budget

### $0/mo
- **Ingestion:** Python 3.12 + APScheduler-style job list run as a single script inside **GitHub Actions `schedule:`** (private repo, within the free 2,000 min/mo — a 12-API fetch-and-write job running every 15–60 min for a handful of minutes per run stays well inside this budget). Backup trigger via **cron-job.org free tier** calling `repository_dispatch`.
- **Storage:** Supabase **Free** Postgres (500MB) — keep price history at 5-min bars (not 1-min) to stay comfortably inside the 500MB cap; daily writes from GH Actions prevent the 7-day pause.
- **Frontend:** Vite + React + TS on **Cloudflare Pages Free**.
- **Charts:** Lightweight Charts (Apache-2.0, attribution logo left on) + uPlot for sparklines.
- **Auth:** **Cloudflare Access Free** (1 of 50 free seats).
- **Watchdog:** A free Healthchecks.io check pinged at the end of each successful ingestion run; alerts via free email/Slack webhook if it misses its window.
- **What it buys:** A fully functional, reliably-alerting personal dashboard at literally $0/mo.
- **What it risks:** GitHub Actions' documented scheduling delay/occasional drop is the main residual risk — mitigated but not eliminated by the cron-job.org backup trigger and the watchdog (which at least makes failures loud, satisfying the "must loudly fail" requirement even on the free tier).

### ~$5–10/mo
- **Ingestion:** Same GitHub Actions primary trigger, but the actual fetch-and-write logic runs as a small always-on job dispatched to a **Railway Hobby ($5/mo)** service (or a Fly.io `shared-cpu-1x` machine at ~$2–2.50/mo, started on-demand via the Fly Machines API and stopped after each run) — giving headroom beyond GH Actions' runner constraints (e.g., longer backfills, no 2,000-min/mo ceiling to watch).
- **Storage:** Supabase Free still, or upgrade only if the 500MB cap is hit (unlikely per §3).
- **Frontend/Charts/Auth:** unchanged from the $0 tier.
- **Watchdog:** Healthchecks.io free tier still sufficient at this volume.
- **What it buys:** Removes GitHub Actions' compute/time constraints as a variable, and provides a real compute host if the owner wants to add heavier backfills or occasional larger jobs later.
- **What it risks:** Reintroduces a Railway/Fly service to operate — but as a **stateless, on-demand-invoked worker**, not a resident background process, this does not reproduce scar tissue 1 (which was specifically about a *persistent* listener contending for CPU).

### ~$25/mo
- **Ingestion:** Same as $5–10 tier.
- **Storage:** **Supabase Pro ($25/mo)** — removes the 7-day pause risk entirely (irrelevant here given active daily writes, but removes it as a variable permanently), 8GB disk (headroom for 1-min price bars if ever wanted), 250GB egress, no MAU/connection anxiety.
- **Frontend/Charts/Auth:** unchanged.
- **Watchdog:** unchanged, or upgrade to Healthchecks.io paid ($5/mo add-on, optional) for SMS alerting instead of just email/Slack.
- **What it buys:** Removes the one real ongoing constraint (Supabase free-tier size/pausing) and buys peace of mind and headroom, at a price point still trivial for a single-user tool.
- **What it risks:** Nothing new — this tier is strictly "pay to remove remaining free-tier anxieties," not a different architecture.

---

## 8. How This Design Avoids the Owner's Two Documented Failures

1. **Scar tissue 1 (WebSocket listener causing CPU contention on shared-cpu-1x, slowing jobs from <4min to 6+min):** This design has **no persistent listener process anywhere**. The Fly/Railway compute (if used at all) is invoked on-demand per scheduled run and exits — there is nothing resident to contend for CPU with itself. On the frontend, "live" is defined as polling, not a WebSocket, so no persistent socket exists there either. The only place anything resembles a long-lived connection is Supabase Realtime, which is optional, client-side only, and was explicitly evaluated and deprioritized in §4 precisely because it's the same risk shape.

2. **Scar tissue 2 (self-hosted Fly runner stopped silently after GitHub Actions self-update, losing 24h of data unnoticed):** This design does not use a self-hosted runner at all — GitHub-hosted runners are ephemeral, GitHub-managed VMs that cannot "silently exit and stay down" the way a self-hosted supervisor process can. The residual risk (GH Actions' own documented scheduling delays/drops) is answered with (a) a second independent trigger path (cron-job.org → `repository_dispatch`) at a different offset, and (b) an explicit **dead-man's-switch watchdog** (Healthchecks.io) that pages the owner the moment an expected ingestion run fails to check in — directly satisfying "must loudly fail if it does not run," which is the actual lesson from scar tissue 2 (the problem wasn't the outage, it was that nobody knew for 24 hours).

---

## 9. Sources Cited

- GitHub Actions schedule delay behavior — https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
- GitHub Actions 60-day scheduled workflow disable rule — https://docs.github.com/actions/managing-workflow-runs/disabling-and-enabling-a-workflow
- Cloudflare Workers pricing (CPU time, cron duration) — https://developers.cloudflare.com/workers/platform/pricing/
- Cloudflare Workers limits (subrequests, cron triggers per account) — https://developers.cloudflare.com/workers/platform/limits/
- Supabase pricing (Free/Pro limits, egress, MAU) — https://supabase.com/pricing
- Supabase free project pausing (7-day inactivity) — https://supabase.com/docs/guides/platform/free-project-pausing
- Railway pricing (Hobby $5/mo) — https://railway.com/pricing
- Fly.io pricing (shared-cpu-1x rates, free allowances) — https://fly.io/docs/about/pricing/
- Val Town pricing (cron intervals, runtime caps by tier) — https://www.val.town/pricing
- Upstash QStash pricing (free tier messages/schedules) — https://upstash.com/pricing/qstash
- Deno Deploy pricing (free tier requests/egress) — https://deno.com/deploy/pricing
- Inngest pricing (Hobby free tier executions/events) — https://www.inngest.com/pricing
- Trigger.dev pricing (free tier schedules, compute-second billing) — https://trigger.dev/pricing
- Cloudflare D1 limits (DB size, queries per invocation) — https://developers.cloudflare.com/d1/platform/limits/
- Turso pricing (free tier storage/rows) — https://turso.tech/pricing
- Cloudflare Pages limits (builds, files, projects) — https://developers.cloudflare.com/pages/platform/limits/
- Cloudflare R2 pricing (free storage/operations, free egress) — https://developers.cloudflare.com/r2/pricing/
- TradingView Lightweight Charts license (Apache-2.0 + attribution) — https://github.com/tradingview/lightweight-charts/blob/master/LICENSE
- Render cron job pricing and free-tier scope (third-party aggregation, **UNVERIFIED** exact per-minute rate against render.com/pricing directly) — https://render.com/pricing
- Koyeb pricing (Postgres free tier, Pro plan) — https://www.koyeb.com/pricing
- Hetzner CX22 pricing (third-party aggregation of hetzner.com published rates; **UNVERIFIED** direct against hetzner.com/cloud pricing table, which did not render pricing in fetch) — https://www.hetzner.com/cloud/
- ClickHouse Cloud pricing (no permanent free tier as of 2026) — third-party aggregation, **UNVERIFIED** against clickhouse.com directly
- Timescale Cloud pricing (10GB free tier) — third-party aggregation, **UNVERIFIED** against tigerdata.com/pricing directly
- Cloudflare Zero Trust/Access free tier (50-user cap) — third-party aggregation (controld.com, costbench.com, zerotrustcost.com) corroborating official Cloudflare "Teams under 50 users" free-tier framing; **UNVERIFIED** against a single official cloudflare.com pricing page (official page did not render tier details on fetch)
- Modal pricing (Starter $30/mo credit, native cron primitives) — third-party aggregation + https://modal.com/docs/guide/cron
