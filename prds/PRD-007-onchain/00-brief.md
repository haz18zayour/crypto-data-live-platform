# PRD-007 · On-chain panel — and honest absence

**In one to three sentences:** Add on-chain data — MVRV, exchange flows, active addresses — for
BTC and ETH from Coin Metrics' free tier, genuinely free-to-confirm fields for BNB, and a
**built** (not bought) network-activity/staking column for SOL from the public RPC. SOL's
valuation and exchange-flow cells render `NOT_DEFINABLE`, on principle, because no vendor at
any price currently sells genuine SOL realized-cap or reliably-labeled SOL exchange flows.

**Depends on:** PRD-002 (determinism and contract harness). Inherits PRD-003's corroboration
requirement structurally, same as PRD-006.

**Roughly:** 7–9 stories.

---

## Why this PRD is shaped this way

`research/R2-onchain-sources.md` measured this directly against Coin Metrics' live API rather
than trusting its catalog, and found something the prior system got exactly backwards:

> *"The prior system's MVRV and exchange-flow fetches were legitimate — for BTC and ETH. The
> fabrication was not inventing the source; it was applying BTC's values to eight other coins."*

The source was sound. The fan-out — one chain's methodology stamped onto every asset — was the
defect. This PRD is the fix applied correctly: **fetch what each chain genuinely has, and mark
what it doesn't as settled absence, never a proxy.**

R2's live probe against Coin Metrics' free Community API, one metric at a time, no key:

| Metric | BTC | ETH | SOL |
|---|---|---|---|
| MVRV (`CapMVRVCur`) | FREE | FREE | **NO-METRIC** |
| Active addresses | FREE | FREE | PAID |
| Exchange flows | FREE | FREE | **NO-METRIC** |
| Circulating supply | FREE | FREE | PAID |
| Realized cap | PAID | PAID | NO-METRIC |

Three distinct failure modes, and R2 is explicit that collapsing them loses real information:
**`NO-METRIC`** (the chain has nothing to measure — SOL is account-based, no UTXO to anchor a
realized-cap methodology to, and no vendor researched — Glassnode, CryptoQuant, Messari,
Santiment — sells genuine SOL MVRV at any price); **`PAID`** (exists, gated behind credentials
we don't hold); **`FREE`** (genuinely available now). The board must show *why*, not just *that*.

## SOL, specifically — build, don't omit everything

`research/R8-solana-onchain-buy-vs-build.md` is the deeper dive the roadmap points to, and its
verdict is not a blanket "SOL has no on-chain data" — it's metric-class-specific:

- **Network activity (active addresses, tx count, staking/validators): BUILD, and it's cheap.**
  Free-tier Solana RPC (Helius or QuickNode, both confirmed with real $0 tiers) for daily
  non-vote transaction counts and unique signers, plus Validators.app (confirmed genuinely free,
  no paid tier exists at all) for staking/validator data. Days of effort, not weeks, $0/mo.
- **Realized cap / MVRV: OMIT.** Solana is account-based — no UTXO to inherit a cost basis from
  — so "realized cap" would mean reconstructing a full historical cost-basis ledger across ~6.5
  years of transfer history from scratch. No open-source implementation exists. R8's own words:
  *"not a weekend project, and arguably not a solo-maintainer project at all."*
- **Exchange flows: OMIT.** Solana's exchange-wallet labeling ecosystem is materially less
  mature than Ethereum's, and R8 found that even mature vendors with a decade of Bitcoin/Ethereum
  labeling *publicly disagree with each other* on the same flow events. A self-curated Solana
  label set would produce a confidently-wrong number, not a lesser-quality one — exactly this
  platform's defining failure mode, reapplied to a new chain.

## What research must settle before this PRD is spec'd

- **Does Coin Metrics' free tier genuinely cover BNB** the way the roadmap currently claims
  (MVRV/addresses/supply)? R2's live probe only tested BTC/ETH/SOL — BNB coverage is asserted
  in `05_Product_Roadmap.md` but not independently confirmed in either research doc found so far.
  Probe it the same way R2 probed SOL: live, one metric at a time, no assumptions from the
  catalog page.
- **Coin Metrics API key provisioning and rate limits** for the free Community tier at
  production scale (4 assets × 3 metrics × daily cadence) — R2 flagged pricing pages for
  Glassnode/CryptoQuant/Amberdata as blocked from automated fetching; confirm Coin Metrics'
  own free-tier request limits directly.
- **Solana RPC provider choice** — Helius vs. QuickNode, both confirmed free tiers in R8, but
  neither was load-tested against this project's actual daily batch shape. Pick one and record
  why, matching the OKX-primary decision pattern from PRD-006.
- **Vote vs. non-vote transaction filtering on Solana** — R8 flags this as "a filtering problem,
  not a scale-blocking problem" but could not reconfirm the current vote/non-vote split live.
  Confirm the RPC-level filter works as documented before committing required-fields to a story.

## Explicitly NOT in this PRD

- **SOL realized cap / MVRV.** No vendor sells it at any price (R8, confirmed against Coin
  Metrics, Santiment, and unconfirmed-leaning-absent on Glassnode/CryptoQuant). Renders
  `NOT_DEFINABLE`, permanently, unless a vendor ever publishes it — not a gap to revisit by
  building it ourselves.
- **SOL exchange flows.** Same reasoning: a self-curated label set would recreate the exact
  wrong-data failure this platform exists to prevent. `NOT_DEFINABLE`.
- **NUPL, MVRV Z-score, realized price, or any other MVRV-derived metric.** R2 flags these as
  the exact "algebraically-derived, double-counted as independent" trap the prior system fell
  into (`NUPL = 1 - 1/MVRV` presented as a second signal). If MVRV is on the board, its
  derivatives are not, unless a future PRD makes that case explicitly.
- **Any exchange-flow vendor beyond Coin Metrics' free tier** (Nansen, Arkham, CryptoQuant) —
  R2/R8 both flag these as unverified-pricing, four-figure-a-year territory; out of scope for a
  $0-budget dashboard unless the owner explicitly opts in at a future G1.
- **No new panel layout.** PRD-005's board model, coverage headline and completeness matrix
  already generalize — PRD-006 proved it with a second data category; this is the third.
- **No composite score, signal, or cross-indicator judgement** — permanent, project-wide.

## The adversarial case

**Render the SOL column next to BTC/ETH's and read the difference at a glance: MVRV and
exchange-flow cells `NOT_DEFINABLE` with the real reason, network-activity and staking cells
`OK` with real values, in the same row family others are `OK` for BTC/ETH.** This is the direct
test of R2's central complaint about the prior system — that collapsing three different kinds of
absence (`NO-METRIC`, `PAID`, and genuinely `OK`) into one blank cell destroys the information
the owner actually needs. A second, cheaper adversarial case if useful: force a Coin Metrics
`PAID`-tier metric request (e.g. `CapRealUSD`) and confirm it renders `PAYWALLED`, never silently
substituting the free-tier `CapMVRVCur` in its place.

## Phase checklist

- [x] `00-brief.md`
- [x] `10-research.md` — `uf research PRD-007-onchain`, 13 sources, $0.91
- [x] `20-decisions.yaml` — **GATE G1** — drafted; BNB coverage live-probed directly
      (research flagged it as still unconfirmed after its own pass) — MVRV/addresses/
      supply/tx-count FREE, exchange flows NO-METRIC, confirmed 2026-09-15
- [x] `30-spec.md`
- [x] `40-stories/*.md` — 8 stories
- [x] `uf compile PRD-007-onchain` — 62 criteria, digest `6d083edf76bb8fd5`
- [ ] **GATE G2** — approve the estimate
- [ ] `uf run`
- [ ] merge to `main`
- [ ] `uf learn`
