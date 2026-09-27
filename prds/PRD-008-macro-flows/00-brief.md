# PRD-008 · Macro and flows panel

**In one to three sentences:** Add a fourth data category — macro (FRED), stablecoin supply
(DefiLlama), and ETF net flows (SoSoValue) — with every value's real release lag surfaced on its
own face, never presented as "live" when it isn't. Fear & Greed ships labeled explicitly as
`alternative.me`'s own composite, never as an independent signal. `DTWEXBGS` ships labeled as a
broad-dollar index, never as "DXY" — no free, official DXY feed exists at all.

**Depends on:** PRD-002 (determinism and contract harness). Inherits PRD-003's corroboration
requirement structurally where a second source genuinely exists (dominance, some macro
cross-checks); most rows here have exactly one credible free source and ship `uncorroborated`,
same pattern as PRD-006/007.

**Roughly:** 6–9 stories.

---

## Why this PRD is shaped this way

`project-documents/research/R4-macro-and-sentiment-sources.md` (2026-09-07, ~20 citations) already
did the adversarial legwork this gate would otherwise have to redo. Three findings are load-bearing:

1. **"Macro" lag varies by two orders of magnitude, and that variance is the actual story.**
   SOFR/DFF/VIX/T10Y2Y/SP500/NASDAQCOM update same-day-to-next-day. `DFII10` (real yields) and
   `DTWEXBGS` lag 1–3 business days. **CPI lags ~5–6 weeks and M2 lags ~3–4 weeks** — both must
   render with their real release lag on the cell's own face, never implying same-day freshness.
   This is the single most important discipline this PRD adds: a "macro" panel that hides which
   of its rows are days old and which are over a month old is exactly the kind of quiet dishonesty
   this project exists to prevent.
2. **No free, official DXY feed exists anywhere.** The only free proxy is FRED's `DTWEXBGS` — a
   26-currency Fed-published broad dollar index, methodologically different from ICE's proprietary
   6-currency DXY. R4 is explicit that displaying this as "DXY" would be a labeling lie; it must
   read as its own real name (Fed Broad Dollar Index) with the DXY-adjacent context disclosed, not
   substituted.
3. **ETF flows are T+1 everywhere, and Fear & Greed has zero published predictive-validity
   evidence.** Farside is the free de facto standard but is an unofficial HTML scrape with no API;
   SoSoValue has a genuine free Demo API and is R4's recommendation. Every ETF flow number is
   "yesterday's flow," never live — issuers report after market close. Fear & Greed
   (`alternative.me`) is a backward-looking composite of six sub-weights (two of which — BTC
   dominance and Google Trends — duplicate data this board could show elsewhere), with **no**
   published evidence it predicts anything; R4's own history flags that CoinMarketCap runs a
   second, different Fear & Greed, and showing both would reproduce this project's own
   documented "counted twice" failure. Only one composite ships, labeled as exactly what it is.

## What R4 already ruled out, and why this PRD does not reopen it

R4 judged sentiment sources adversarially and found almost the entire category does not clear the
bar for a $0-budget, non-judgemental dashboard:

- **Google Trends / pytrends** — pytrends has been archived/dead since April 2025; the official
  API is gated alpha with no public access. Any scraped substitute repeats the exact fragility
  that pushed the prior system onto 4chan thread counts.
- **X/Twitter sentiment** — no free tier since Feb 2026; the academic evidence that exists is for
  generic researcher-scraped text, not any purchasable feed.
- **Reddit sentiment** — technically free but gated behind weeks-long manual OAuth approval;
  operationally impractical, and no source-specific validity evidence exists anyway.
- **LunarCrush / Santiment** — the real-time parts are paywalled at the $0 tier, and no
  vendor-specific predictive-validity evidence exists to justify paying for them here.
- **CoinMarketCap's second Fear & Greed Index** — a duplicate construct under a less-transparent,
  proprietary methodology; showing it alongside `alternative.me`'s would recreate the exact
  double-counting failure this project has already identified and removed once before.

None of this needs re-litigating at G1 unless new evidence has emerged since 2026-09-07 — this
gate's job is to confirm R4 still holds (a quick live spot-check, same method PRD-007 used for
BNB coverage), not repeat the full adversarial pass from scratch.

## What research must settle before this PRD is spec'd

- **FRED API key provisioning and the exact series list** — R4 names the series (`DTWEXBGS`,
  `VIXCLS`, `T10Y2Y`, `DFF`/`FEDFUNDS`, `SOFR`, `DFII10`, `CPIAUCSL`, `M2SL`, `SP500`,
  `NASDAQCOM`) and their lags from FRED's own series pages, but the roadmap line only explicitly
  names "FRED series" — confirm at G1 exactly which subset ships in this PRD versus a future one
  (a macro panel with 10 rows is a bigger scope jump than PRD-006/007's per-PRD story counts).
- **SoSoValue's free Demo API's exact current rate limit and response shape** — R4 flags this as
  "beta," confirmed to exist via search but not independently fetched directly (403'd to the
  research tool). Live-probe it the same way R2 live-probed Coin Metrics for PRD-007, before
  committing a required-fields shape to a story.
- **DefiLlama's stablecoin endpoint shape for the specific chains/assets this board tracks** —
  R4 confirms the API exists free and keyless but did not enumerate the exact response fields
  needed for BTC/ETH/SOL/BNB-relevant stablecoin supply.
- **Whether BTC dominance (CoinGecko or CoinMarketCap) ships in this PRD at all** — the roadmap
  line does not mention it, but R4 recommends CoinGecko's free Demo API as the single provider if
  it does ship. Confirm scope: is dominance in PRD-008, a future PRD, or permanently out?

## Explicitly NOT in this PRD

- **Google Trends, X/Twitter sentiment, Reddit sentiment, LunarCrush, Santiment real-time
  endpoints** — see "What R4 already ruled out" above. Not a gap to fill; a deliberate,
  evidence-based omission.
- **CoinMarketCap's Fear & Greed Index** — duplicate of `alternative.me`'s, omitted on the same
  category-collapse grounds R2 already established for MVRV derivatives in PRD-007.
- **CME futures basis, exchange reserve aggregates, Coinbase premium** — R4 found no free, keyless
  API for these; CryptoQuant/Coinglass paid tiers are out of scope for a $0-budget dashboard
  unless the owner explicitly opts in at a future G1.
- **News headlines and any accompanying "sentiment score"** (CryptoPanic, Marketaux, NewsAPI) —
  R4's own recommendation is headlines-with-timestamps only, never a bundled score; even that is
  optional and not named in the roadmap line, so treat as out of scope unless G1 says otherwise.
- **Any composite, score, signal, or cross-indicator judgement** — permanent, project-wide.
- **No new panel layout** — PRD-005's board model already generalized twice (PRD-006, PRD-007);
  this is the fourth data category proving the same pattern again, not new UI.

## The adversarial case

**Render the macro panel and read the staleness gradient at a glance**: same-day rows (VIX,
SOFR, S&P 500) next to `DTWEXBGS`'s 1–3 day lag next to CPI's ~5–6 week lag and M2's ~3–4 week
lag — each showing its own real "as of" date, none implying same-day freshness it doesn't have.
A second case, direct and cheap: confirm `DTWEXBGS` never renders as "DXY" anywhere in the UI,
copy, or source_field — grep the whole board for the literal string "DXY" and confirm it appears
only in an explanatory disclosure ("not the same as ICE's proprietary DXY"), never as a label. A
third case: force the Fear & Greed cell and confirm it renders with `alternative.me`'s own name
and composite-methodology disclosure on its face, not as an unlabeled number.

## Phase checklist

- [x] `00-brief.md`
- [ ] `10-research.md` — `uf research PRD-008-macro-flows`
- [ ] `20-decisions.yaml` — **GATE G1**
- [ ] `30-spec.md`
- [ ] `40-stories/*.md`
- [ ] `uf compile PRD-008-macro-flows`
- [ ] **GATE G2** — approve the estimate
- [ ] `uf run`
- [ ] merge to `main`
- [ ] `uf learn`
