---
title: On-chain panel — and honest absence
branch: feat/prd-007-onchain
assumptions:
  - claim: Coin Metrics' Community API rate limit (~1.6 req/s per IP, no key) is sufficient for a daily batch of BTC/ETH/BNB across up to 3 metrics if calls are serialized with backoff.
    tripwire: Any 429 must surface as FETCH_FAILED, never a silent retry that drops the row. This is a per-IP limit, not per-key, so it cannot be monitored via a dashboard between runs — a naive concurrent implementation at batch start will 429.
    acceptedBy: default
  - claim: Validators.app's mandatory account and API token is provisioned before any SOL-staking story starts.
    tripwire: A story failing on missing Validators.app credentials is a provisioning gap, not a code defect — check this first, don't assume the story itself is broken.
    acceptedBy: default
  - claim: Solana vote-transaction classification must be done client-side, against each fetched block's transaction data — there is no RPC-level filter.
    tripwire: Any code or test that passes a votes parameter to getBlock, or assumes one exists, is testing a nonexistent API surface. No such parameter has ever existed, and a 2022 feature request for one was closed not planned.
    acceptedBy: default
---

# On-chain panel — and honest absence

## What this delivers

A third data category on the board: **MVRV, active addresses, and exchange flows** for
BTC/ETH/BNB from Coin Metrics' free tier, and a **built** SOL network-activity + staking column
from the public Solana RPC and Validators.app. SOL's MVRV and exchange-flow cells render
`NOT_DEFINABLE` — permanently, on principle, not as a gap to fill later. No new UI: PRD-005's
board model already generalized once for PRD-006's derivatives; this proves it a second time.

## Why (from research and this gate's own live probes)

Three findings are load-bearing.

1. **The prior system's defect was fan-out, not fabrication.** `research/R2-onchain-sources.md`
   confirmed BTC/ETH MVRV and exchange flows are genuinely free on Coin Metrics — the prior
   system's mistake was stamping BTC's methodology onto eight other coins, not inventing the
   source. This PRD fetches what each chain genuinely has and marks the rest as settled absence.
2. **BNB's coverage was live-probed at this gate, not assumed from the roadmap.** Research
   flagged BNB coverage as still unconfirmed after its own pass; probing
   `community-api.coinmetrics.io` directly (2026-09-15, the same method R2 used for SOL) found
   MVRV/active-addresses/supply/tx-count genuinely `FREE`, but exchange flows return
   `bad_parameter` — `NO-METRIC`, not merely unconfirmed. The roadmap never called this out.
   BNB's exchange-flow cell renders `NOT_DEFINABLE` with that specific, now-confirmed reason.
3. **Solana has no RPC-level vote filter, and never has.** `getBlock`'s only parameters are
   `commitment`, `encoding`, `transactionDetails`, `maxSupportedTransactionVersion`, `rewards`.
   A 2022 feature request for a `votes: bool` parameter was explicitly closed "not planned," and
   that repository is now archived. Any story assuming a filter parameter exists would fail
   against an API surface that was never built. Vote/non-vote classification must inspect each
   fetched transaction's top-level instructions for the vote program address
   (`Vote111111111111111111111111111111111111111`) client-side.

## Approach

**Two new fetcher modules.** `ingest/fetchers/coinmetrics.py` — the first non-OKX vendor this
project integrates — calls Coin Metrics' `/v4/timeseries/asset-metrics` directly via `httpx`,
serialized with backoff to respect the ~1.6 req/s per-IP ceiling (no key required). A malformed
or `forbidden`/`bad_parameter` response maps to `Error(FETCH_FAILED)` or the appropriate
`Unavailable` reason (`PAYWALLED` for a credential-gated metric like `CapRealUSD`,
`NOT_DEFINABLE` for one the asset genuinely doesn't have), never a default. `ingest/fetchers/
solana_rpc.py` calls Helius's free-tier JSON-RPC (`getBlock`, chosen over QuickNode because its
rate-limit documentation was directly cited and current, not found via a secondary aggregator),
fetches a day's blocks, and classifies vote vs. non-vote transactions client-side per the
corrected finding above — counting non-vote transactions and unique fee-payer signers as SOL's
built "active addresses" analog. `ingest/fetchers/validators_app.py` calls Validators.app's
token-gated REST API for SOL validator/stake data.

**Registry entries, by family, all following `btc_daily_close`'s established `not_definable`
precedent** (a deliberate board-scope reason, not literally "impossible in the universe" — the
same wording pattern already used for daily close being "intentionally BTC-only on this board"):

- `mvrv`: BTC/ETH/BNB from Coin Metrics; SOL `not_definable` — *"No vendor sells genuine SOL
  realized-cap or MVRV at any price; Solana is account-based with no UTXO to anchor a cost-basis
  methodology to, and no open-source implementation exists."*
- `active_addresses`: BTC/ETH/BNB from Coin Metrics; SOL from the Solana RPC build (a different
  vendor and methodology under the same family label — each cell's own provenance names its
  actual source, honoring this board's transparency rule even when a family spans two vendors).
- `exchange_flow`: BTC/ETH from Coin Metrics; BNB `not_definable` — *"Coin Metrics' free tier
  has no exchange-flow metric for BNB (confirmed live, 2026-09-15: bad_parameter on both
  FlowInExNtv and FlowOutExNtv)"*; SOL `not_definable` — *"Solana's exchange-wallet labeling
  ecosystem is materially less mature than Ethereum's; even mature vendors with a decade of
  BTC/ETH labeling publicly disagree with each other on the same flow events. A self-curated
  Solana label set would produce a confidently-wrong number, not a lesser one."*
- `staking`: SOL from Validators.app; BTC `not_definable` — *"Proof-of-work has no staking
  concept"*; ETH/BNB `not_definable` — *"Out of scope for this PRD's on-chain panel; SOL staking
  is research R8's specific build recommendation, not a general staking feature."*

**Persistence extends the existing daily run again.** `persist_board` was already generalized in
PRD-006 to accept results keyed by registry entry regardless of `talib_function`; on-chain
entries slot into the same shape. One heartbeat call, three data categories, one failure surface.

## Data model changes

**None**, same as PRD-006. No new column, no migration. Every absence reason is expressed
through the existing `not_definable` / `uncorroborated` registry blocks and the existing
`UNAVAILABLE`/`ERROR` status vocabulary.

## Out of scope

Restated from `00-brief.md`, confirmed at G1: SOL MVRV and exchange flows (permanently
`NOT_DEFINABLE`, not a gap to fill); BNB exchange flows (confirmed `NO-METRIC`, not merely
unconfirmed); NUPL, MVRV Z-score, realized price, or any other MVRV-derived metric (the exact
"algebraically-derived value double-counted as a second signal" trap the prior system fell
into); any exchange-flow vendor beyond Coin Metrics' free tier; any RPC-level "vote filter" —
classification is client-side only; any new panel layout; any composite, score, signal, or
cross-indicator judgement, permanently.

## The adversarial case

**Render BTC, ETH, BNB and SOL's on-chain columns side by side and read the difference at a
glance**: MVRV and exchange-flow `OK` for BTC/ETH, exchange-flow `NOT_DEFINABLE` for BNB with
its own distinct reason, MVRV and exchange-flow `NOT_DEFINABLE` for SOL with a different reason
again, active-addresses and staking `OK` for SOL sourced from a completely different vendor than
the other three assets' cells in the same rows. This is the direct test of R2's central
complaint about the prior system: collapsing `NO-METRIC`, `PAID`, and genuinely `OK` into one
blank cell destroys the information the owner actually needs. A second, cheaper case: force a
Coin Metrics `PAID`-tier request (`CapRealUSD`) and confirm it renders `PAYWALLED`, never
silently substituting the free-tier `CapMVRVCur` in its place.

## Stories

| Story | Title | Depends on |
|---|---|---|
| US-701 | Coin Metrics fetcher — MVRV, BTC only, rate-limit handling proven against real data | — |
| US-702 | MVRV registered across BTC/ETH/BNB; SOL declared NOT_DEFINABLE | US-701 |
| US-703 | Active addresses (Coin Metrics) registered across BTC/ETH/BNB | US-701 |
| US-704 | SOL active addresses — built from Helius RPC, vote transactions classified client-side | US-701 |
| US-705 | Exchange flows (Coin Metrics) — BTC/ETH only; BNB and SOL each NOT_DEFINABLE with distinct, confirmed reasons | US-701 |
| US-706 | SOL staking — Validators.app; BTC/ETH/BNB each NOT_DEFINABLE with distinct reasons | — |
| US-707 | One ingest run persists all three data categories — pipeline and heartbeat integration | US-702, US-703, US-704, US-705, US-706 |
| US-708 | The adversarial case — the four-asset on-chain column read at a glance, plus a forced PAYWALLED cell | US-707 |
