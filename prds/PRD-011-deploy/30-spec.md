---
title: Deploy behind Cloudflare Access
branch: feat/prd-011-deploy
assumptions:
  - claim: Cloudflare Workers' free plan serves static assets and Access-gated requests without a practical request cap a single owner opening one page occasionally would hit.
    tripwire: UNVERIFIED — research could not fetch a current pricing/limits page for this specific combination. Confirm live via the Cloudflare dashboard's own usage display after deployment.
    acceptedBy: default
  - claim: sb_publishable_... Supabase keys (the legacy anon key's successor) work in this app's current Authorization Bearer header pattern the same way the legacy JWT key does.
    tripwire: UNVERIFIED and recalled, not fetched — non-JWT publishable keys may be intended only for the apikey header. Confirm live before any future story migrates off the legacy key.
    acceptedBy: default
  - claim: Supabase's legacy anon/service-role key deprecation lands at, or close to, the vendor's currently-stated end-of-2026 date.
    tripwire: A vendor's own timeline, not something this project controls. Check Supabase's current status before treating the deadline as fixed.
    acceptedBy: default
---

# Deploy behind Cloudflare Access

## What this delivers

The existing web app, reachable at a real URL, open to the owner and closed to everyone else.
Cloudflare Access gates every hostname (production and previews) behind a one-time-PIN login
to the owner's own email, with a one-week session. A scheduled, unauthenticated probe of the
real production hostname is the durable proof this stays true over time — the one control in
this project that lives in a dashboard instead of the repo, watched the same way every other
silent-failure class in this project is watched.

## Why (from research and this gate's own findings)

Two findings are load-bearing.

1. **The obvious path ships the product publicly.** Cloudflare Pages' one-click "Enable access
   policy" toggle — the default path in Cloudflare's own documentation — protects only the
   preview-deployment subdomain, never the real production `pages.dev` domain or a custom
   domain. Confirmed directly from Cloudflare's own docs, not a search snippet. Anyone
   reaching for the obvious toggle ships this dashboard open to the internet by default.
2. **Access protects the page, not the data.** The browser holds `VITE_SUPABASE_ANON_KEY` and
   calls Supabase's REST/RPC endpoints directly; Access sits in front of the Worker's own
   hostname, not `*.supabase.co`. Confirmed at G1: this is an accepted, explicitly-recorded
   limit for this PRD (the data is public market data, RLS already scopes `anon` to read-only
   grants), not something this PRD silently glosses over. A future PRD (a Worker-side proxy
   keeping the Supabase key server-side) is the real fix if that gap ever needs closing.

## Approach

**Workers static assets, not Pages.** `wrangler.jsonc` serves `web/dist` with
`not_found_handling: "single-page-application"` (this app has one route). Cloudflare Access
protects the Worker at scope "all traffic" — one dashboard setting covers every hostname,
unlike Pages' fragile two-Access-app, wildcard-deletion procedure.

**A dedicated deploy workflow, gated on tests passing.** `deploy-web.yml` triggers on push to
`main` (this project's actual integration branch), runs `npm run typecheck` and `npm run test`
inside `web/`, and only then runs `wrangler deploy`. A red suite never reaches production, and
the workflow run itself is durable evidence, unlike a dashboard-driven Git integration with no
CI record. `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` are new GitHub repo secrets the
owner provides once their Cloudflare account/Zero Trust org exists; `VITE_SUPABASE_URL` and
`VITE_SUPABASE_ANON_KEY` (already used locally) become GitHub secrets baked into the build at
deploy time, the same values already in `.env.local`.

**A `.node-version` file pins the build's Node version explicitly**, since Cloudflare's own
build-image documentation disagrees with its own known-issues page about the default (12.18.0
vs 22.16.0), and this project's Vite 7 / TypeScript 5.9 toolchain will not build on the older
image.

**Cloudflare Access configuration itself is dashboard/account-level work the owner performs
directly** (team domain, one-time-PIN identity provider, the Worker's Access policy at scope
"all traffic", 1-week session) — this project has no credentials to automate that account setup,
and the owner has confirmed they will handle it. The code-side stories (Worker config, CI
workflow, local build verification) do not block on this; the live-verification stories do.

**A scheduled, unauthenticated production-hostname probe is the durable safety net.** Access
configuration is the one control in this project that lives entirely in a dashboard, is not
diffable, and is documented by Cloudflare itself as something people get wrong. A canary
(extending the existing `canary.yml` pattern or a new small workflow) makes a real HTTP request
to the real deployed hostname on a schedule and asserts it is redirected toward Cloudflare
Access's login rather than returning the real page — the only thing that can catch dashboard
drift, per this project's own established lesson that a criterion which only exists as a
deselected integration test never actually runs.

## Data model changes

None. This PRD deploys the existing frontend and adds CI/infrastructure configuration; it does
not touch `datapoints`, any view, RPC, or migration.

## Out of scope

Restated from `00-brief.md` and confirmed at G1: no change to how the browser reads Supabase
data (anon key stays client-side; a Worker-proxied read path is a real, separate future PRD);
no Supabase legacy-anon-key migration (tracked as an assumption with a hard external deadline);
no custom domain (`*.workers.dev` accepted for a single-user tool); no change to the existing
ingestion pipeline or its own Healthchecks dead-man's-switch; no WebSocket/push functionality.

## The adversarial case

**An unauthenticated request to the real production hostname must never return the real page.**
Proven against the actual deployed hostname, not a preview URL or a mocked response — this is
exactly the class of failure ("looks protected, isn't") research found built into the obvious
Cloudflare path. **A broken build must never reach production**: a deliberately failing
typecheck or test run in the deploy workflow must be shown to block the `wrangler deploy` step,
not merely assumed from the workflow's own ordering. **The canary must be the thing that would
actually catch a real regression**, not a one-shot check run once and forgotten — proven by
confirming it runs on a real schedule and by demonstrating what it reports when pointed at an
intentionally-unprotected URL versus the real, protected one.

## Stories

| Story | Title | Depends on |
|---|---|---|
| US-1106 | Worker scaffold — wrangler.jsonc serving web/dist as an SPA, .node-version pinned, local build verified | — |
| US-1107 | Deploy workflow — deploy-web.yml gated on typecheck+test, triggers on push to main, builds with the real VITE_* secrets | US-1106 |
| US-1103 | First live deploy and Cloudflare Access configuration — owner completes account/dashboard setup, provides CI secrets, applies Access at scope "all traffic" | US-1107 |
| US-1104 | The Access drift canary — a scheduled, unauthenticated probe of the real production hostname asserting a redirect to Access login | US-1103 |
| US-1105 | The adversarial case — a broken build is proven blocked from deploy, the live hostname is proven to reject unauthenticated access, and the owner confirms they can actually open the real dashboard through Access | US-1107, US-1103, US-1104 |
