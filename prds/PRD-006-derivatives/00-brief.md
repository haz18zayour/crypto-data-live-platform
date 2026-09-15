# PRD-006 · Derivatives panel

**In one to three sentences:** Add a second data category to the board — funding rate
(**settled**, never a live/predicted field), open interest, long/short ratio and taker
buy/sell ratio, for BTC/ETH/SOL/BNB perpetuals. Every entry records its venue's funding
**interval** explicitly, so cross-venue comparison and annualisation cannot silently assume
a uniform 8-hourly cadence that isn't there.

**Depends on:** PRD-002 (determinism and contract harness). Inherits PRD-003's corroboration
requirement structurally — US-306 already made "declare a second source or mark
uncorroborated" mandatory for every registry entry, not optional per-PRD.

**Roughly:** 6–8 stories.

---

## Why this PRD is shaped this way

`project-documents/11_Data_Model.md` names the exact failure this PRD exists to prevent:

> *"the prior system's funding rate, open interest and long/short ratio reported a confident
> `0.0` for months because a fetcher was never called."*

Derivatives data is also where `research/R1-derivatives-sources.md` found the most
vendor-specific traps in this project's entire research phase — three of them are load-bearing
for how this PRD must be built, not just background:

1. **"Funding rate" is two different numbers, and vendors blur them.** A ticker/live endpoint
   (Binance `premiumIndex`, OKX `public/funding-rate`) is easy to mistake for a locked
   prediction. This board renders **settled, realized** funding only — the same discipline
   PRD-004 already applied to OHLCV (`confirm`/closed-candle only). The live field is not fetched
   for display.
2. **Funding intervals are not uniform and are not fixed per instrument.** OKX and Bybit both
   run dynamic settlement — an instrument can be at 8h and switch to 1h when a rate hits its
   cap/floor. Annualizing by a flat "×3/day" assumption is the single most common bug in this
   space. Every funding datapoint must carry its own interval so annualisation is computed per
   entry, never assumed globally.
3. **Coin-margined vs USDT-margined is a silent unit-mixing trap.** Inverse-contract open
   interest is coin-denominated; linear is USD-denominated. This board's assets (BTC/ETH/SOL/BNB
   perpetuals) should standardize on one instrument type — decide which, and record it in the
   registry note the same way OHLCV records `bar=1Dutc` — rather than mixing conventions across
   entries.

## What research must settle before this PRD is spec'd

- **Which venue is primary**, and whether a second venue is reachable for corroboration. OKX is
  already integrated (spot close, OHLCV); confirm its perpetual-swap funding/OI/long-short
  endpoints are on the same reachable compute path the PRD-001 spike measured, and identify a
  genuinely reachable second venue for corroboration (R1 lists Binance and Bybit as free
  alternatives, but PRD-001 already found Binance returns HTTP 451 to US IPs — re-verify against
  whatever the actual deployment target turns out to be).
- **Long/short ratio and taker ratio history depth.** R1 flags that Binance's history endpoints
  for these are capped at a 30-day rolling window — confirm OKX's equivalent limits before
  committing to a backfill assumption.
- **Per-venue funding interval representation** — a fixed field, or a lookup that can change
  over an instrument's life (dynamic settlement means it genuinely can).

## Explicitly NOT in this PRD

- **No liquidation data.** R1's own finding: liquidation feeds are "mostly modeled, not
  measured" — Binance's stream is a 1-order/second snapshot, OKX's is a partially-reported
  7-day window, and Coinglass's heatmap is an explicit model, not observed data. This board
  makes no judgement call more consequential than what it already refuses to do with market
  data generally: a modeled estimate does not get to look like a measured value. Worth its own
  PRD, later, if the owner wants it at all — with its own explicit "this is estimated" labelling
  built in from the first story, not retrofitted.
- **No options data** (skew, IV, DVOL) — Deribit-only, thin SOL liquidity per R1, a materially
  different vendor integration. Separate PRD if wanted.
- **No basis / term structure** — requires combining spot + quarterly futures; not blocking for
  a first derivatives cut.
- **No new panel layout work.** The board model, coverage headline and completeness matrix
  built in PRD-005 already generalize to more rows; this PRD adds registry entries and
  fetchers, not new UI.
- **No composite score, signal, or cross-indicator judgement** — permanent, project-wide.

## The adversarial case

**Force an instrument through a funding-interval change** (or, if that can't be observed live
in the research window, construct the fixture case the way PRD-005's mixed board was
constructed) **and show the annualised figure is computed from the instrument's own recorded
interval, not a hardcoded ×3/day** — the exact bug R1 names as the single most common mistake
in this data category. A second, cheaper adversarial case if the first is impractical to
demonstrate live: show a `dapi`/inverse-style coin-denominated OI value is never silently
summed with a USD-denominated one.

## Phase checklist

- [x] `00-brief.md`
- [ ] `10-research.md` — `uf research PRD-006-derivatives`
- [ ] `20-decisions.yaml` — **GATE G1**
- [ ] `30-spec.md`
- [ ] `40-stories/*.md`
- [ ] `uf compile PRD-006-derivatives`
- [ ] **GATE G2** — approve the estimate
- [ ] `uf run`
- [ ] merge to `main`
- [ ] `uf learn`
