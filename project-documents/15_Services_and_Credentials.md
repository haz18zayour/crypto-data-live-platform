# 15 · Services and credentials

**Every row here is work only the owner can do** — an agent cannot create an account, accept
terms, or pay. Doing all of it in one sitting beats discovering it at 2am when a story halts.

Sourced from `research/R0`–`R8`, plus the US-011 reachability measurement. **v1 target cost: $0/mo.**

## Status key

`READY` key in `.env.local` · `PENDING` account exists, key not issued · `TODO` nothing yet ·
`N/A` not used by this product

---

## Core — needed before PRD-001 runs

| Service | Why | Env var(s) | Free tier? | Status |
|---|---|---|---|---|
| GitHub | repo, Actions scheduling, `gh` for the verifier's CI check | `gh auth login` (already done) | 2,000 Actions min/mo (private repo) | **READY** — repo exists, `gh` authenticated |
| Cloudflare | Pages hosting **+ Access (Zero Trust)** for single-user auth | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | yes — Access free up to 50 users | **TODO** |
| Supabase | Postgres for `datapoints` | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (ingest only), `VITE_SUPABASE_ANON_KEY` (browser) | 500 MB DB, 5 GB egress | **TODO** |
| Healthchecks.io | **dead-man's-switch** — alerts on job *silence*. The single highest value-per-effort defence (R5 §1) | `HEALTHCHECKS_PING_URL` | 20 checks | **TODO** |
| cron-job.org | independent second trigger via `repository_dispatch`, offset from the GH Actions cron | `GH_DISPATCH_PAT` (fine-grained, this repo, Actions: R/W) | yes | **TODO** — owner has used this before |

> `SUPABASE_SERVICE_ROLE_KEY` bypasses RLS. It must never reach the client bundle or any
> `VITE_`-prefixed variable. Any story touching it is blast-radius and needs gate G4.

No domain registrar row: `*.pages.dev` is sufficient for a single-user private dashboard.
Add one later if wanted — it is not a v1 dependency.

---

## Data sources — v1 ($0)

| Source | Provides | Key? | Notes | Status |
|---|---|---|---|---|
| Coinbase Exchange / Kraken public REST | spot OHLCV cross-check | none | Both reachable from US runners (200). Neither flags a closed candle | N/A — no key |
| OKX public REST | **primary** spot OHLCV, BTC/ETH/SOL/BNB | none | The only venue that explicitly flags a **closed candle** (`confirm`) (R3), and reachable from US runners (200). Both reasons point the same way | N/A — no key |
| ~~Binance `fapi`~~ → **OKX** | funding (settled), OI, long/short ratio | none | **Measured 2026-09-08: Binance returns 451 and Bybit 403 from a GitHub-hosted US runner; OKX returns 200.** Derivatives therefore come from OKX, or PRD-004 runs on non-US compute. Whichever venue: use the **settled** funding series, **never** a `premiumIndex`-style moving pre-settlement field (R0/F11) | N/A — no key |
| Coin Metrics community API | MVRV, exchange flows, active addresses, supply | none | **Measured 2026-09-07**, per asset: MVRV/addresses/supply/tx/mktcap/price free for **BTC, ETH, BNB**; exchange flows free for **BTC, ETH only** (no such metric for BNB); **SOL returns nothing, not even price** (R2 §0) | N/A — no key |
| alternative.me | Fear & Greed | none | Display as a *composite of other inputs*, never as an independent signal (R4) | N/A — no key |
| Solana public RPC | SOL network activity: epoch, cumulative tx count, supply, staking | none | **Verified live 2026-09-07**: `api.mainnet-beta.solana.com` returns `getEpochInfo` and `getSupply` free. Covers the SOL gap Coin Metrics leaves, for activity metrics only — not valuation (R8) | N/A — no key |
| DefiLlama | stablecoin supply, chain TVL incl. Solana | none | Verified live; free, no key | N/A — no key |
| FRED | DXY-proxy, VIX, yield curve, SOFR, M2, CPI | **`FRED_API_KEY`** | Free, 120 req/min. **Release lag must be displayed**: SOFR/VIX same-day, M2 3–4 wks, CPI 5–6 wks. No true DXY exists on FRED — `DTWEXBGS` is a *broader* index and must be labelled as such (R0/F12) | **TODO** — free registration |
| SoSoValue | BTC/ETH spot ETF net flows | likely key on Demo tier | Best programmatic option; Farside is HTML-only and 403s automated fetch. All T+1 (R4) | **TODO** — verify Demo tier terms |

## Deliberately NOT used — and why

Recording these so they are not "rediscovered" later (R4, R0/F9):

| Source | Reason |
|---|---|
| Google Trends / pytrends | **pytrends is archived/dead.** No official replacement. Do not substitute another scraper |
| X / Twitter API | **No free tier since Feb 2026** |
| Reddit API | Free tier now requires weeks-long manual approval |
| CryptoCompare / CCData | **Retired its free tier entirely, May 2026** — the prior system's news source is gone |
| CoinMarketCap Fear & Greed | Duplicates alternative.me's construct — repeats the "counted twice" failure (R0/F3) |
| 4chan /biz/ thread counts | Prior system's own docs record its validity as *unvalidated*. Availability is not a reason to display a number |
| Glassnode / CryptoQuant | Deferred. The only thing they buy is SOL's on-chain column (R7 §C3); revisit at G2 if the empty panel proves annoying. **Confirm prices in a browser — their pricing pages blocked automated fetch, so every quoted figure is second-hand** |

## Conditional — not used in v1

Resend/Postmark, Stripe, Twilio, OAuth providers, R2/S3, Turnstile, Sentry, PostHog, Upstash,
Algolia, Anthropic/OpenAI: **all N/A.** No alerts, no email, no billing, no LLM narrative, no
multi-user — per the G1 out-of-scope list.

---

## Environments

| | Local | Preview | Production |
|---|---|---|---|
| Secrets | `.env.local` (gitignored) | Pages env vars | Pages env vars + GH Actions secrets |
| Database | shared Supabase project | same | same |
| Domain | `localhost:5173` | `*.pages.dev` | `*.pages.dev` behind Cloudflare Access |

## Before the first PRD runs

- [ ] `.env.example` lists every variable above with **no real values**
- [ ] `.env.local` gitignored and filled
- [ ] Cloudflare account + Access policy restricted to `zayourhassan.1@gmail.com`
- [ ] Supabase project created; anon key and service-role key noted separately
- [ ] Healthchecks.io check created; ping URL saved
- [ ] `FRED_API_KEY` issued
- [ ] `GH_DISPATCH_PAT` fine-grained, this repo only, `Actions: Read and write`, expiry recorded
- [ ] every `TODO` above resolved or explicitly marked `N/A`
- [ ] `uf doctor` clean

## Cost envelope

| Service | Plan | Monthly |
|---|---|---|
| GitHub, Cloudflare Pages + Access, Supabase, Healthchecks.io, cron-job.org | Free | **$0** |
| All v1 data sources | Free | **$0** |
| **v1 total** | | **$0** |
| *Deferred:* CryptoQuant / Glassnode — buys SOL on-chain only | — | *~$29–109, revisit at G2* |
