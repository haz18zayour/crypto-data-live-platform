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

> **Amended 2026-10-06** (see `20-decisions.yaml`'s `amendments:` entry): the owner explicitly
> decided the deployed page may be public. Cloudflare Access is dropped from this PRD's scope
> entirely — no Access policy, no drift canary, no login verification. The research and
> rationale below predate that decision and are kept for the record (they explain why Workers
> was chosen over Pages regardless, and what "public" already meant for the data even before
> this amendment), but no remaining acceptance criterion may require Access.

## What this delivers

The existing web app, reachable at a real, public URL. No login. The data path was already
public-readable before this amendment (the anon key ships in the bundle; see finding 2 below),
so a public page does not newly expose anything decision 1 at G1 had not already accepted.

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

**Cloudflare Access is out of scope (2026-10-06 amendment).** The owner's own account/API-token
setup (Cloudflare account, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`) was still required
and completed — that part of the original plan stands, since it is how the deploy workflow
authenticates to Cloudflare regardless of whether Access is ever applied. No Access policy is
configured on top of it.

## Data model changes

None. This PRD deploys the existing frontend and adds CI/infrastructure configuration; it does
not touch `datapoints`, any view, RPC, or migration.

## Out of scope

Restated from `00-brief.md` and confirmed at G1, plus the 2026-10-06 amendment: **Cloudflare
Access in full** (no policy, no login, no drift canary — owner decision, page is public by
choice); no change to how the browser reads Supabase data (anon key stays client-side; a
Worker-proxied read path is a real, separate future PRD); no Supabase legacy-anon-key migration
(tracked as an assumption with a hard external deadline); no custom domain (`*.workers.dev`
accepted); no change to the existing ingestion pipeline or its own Healthchecks dead-man's-switch;
no WebSocket/push functionality.

## The adversarial case

**A broken build must never reach production.** A deliberately failing typecheck or test run in
the deploy workflow must be shown to block the `wrangler deploy` step, not merely assumed from
the workflow's own ordering — this is the one protection from the original plan that has nothing
to do with Access and remains fully in scope.

## Stories

| Story | Title | Depends on |
|---|---|---|
| US-1106 | Worker scaffold — wrangler.jsonc serving web/dist as an SPA, .node-version pinned, local build verified | — |
| US-1107 | Deploy workflow — deploy-web.yml gated on typecheck+test, triggers on push to main, builds with the real VITE_* secrets | US-1106 |
| US-1103 | First live deploy — owner completes Cloudflare account/dashboard setup, provides CI secrets; the app is live at a real, public URL | US-1107 |
| US-1105 | The adversarial case — a broken build is proven blocked from deploy, and the owner confirms they can open the real public dashboard | US-1107, US-1103 |
