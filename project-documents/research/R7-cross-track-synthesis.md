# R7 · Cross-track synthesis — conflicts the individual research tracks could not see

**Date:** 2026-09-07. Written after R1–R6, from evidence that only appears when the tracks are
read against each other and against the prior repo. Every claim here was verified directly.

---

## C1 · The central conflict: Binance vs GitHub-hosted runners

**R6 recommended** running ingestion on GitHub Actions `schedule:` with GitHub-hosted runners,
explicitly to avoid the self-hosted runner that died silently (R0/F8).

**R1 recommended** Binance Futures `fapi` as the primary derivatives source — it is the
dominant venue for funding, OI and long/short ratio.

**R3 discovered** that Binance's public REST returns **HTTP 451** to US and other restricted
region IPs.

**These three cannot all be true at once.** GitHub-hosted runners run in US Azure regions.

### This is not speculation — the prior repo already hit it and documented it

`.github/workflows/*.yml` in `crypto-investing-signals` contains, verbatim:

```
# runs-on self-hosted because Binance is unreachable from GitHub-hosted runners;
```

and `fly.toml` pins `primary_region = 'fra'` (Frankfurt).

**So the causal chain behind the prior system's worst outage was:**

```
chose Binance as primary source
  -> GitHub-hosted runners return 451
    -> had to self-host a runner on Fly.io in Frankfurt
      -> that runner was a long-lived process the owner had to supervise
        -> it exited 0 on self-update and stopped silently
          -> 24 hours of data lost before anyone noticed   (R0/F8)
```

The infrastructure failure was **downstream of a data-source decision**. Any plan that keeps
Binance as primary re-creates the whole chain, and no amount of watchdog engineering removes
the root cause — it only detects it faster.

### Resolution

**R3 independently recommends Coinbase Exchange or Kraken as primary OHLCV, with OKX as a
cross-check** (OKX being the only venue found that explicitly flags a closed candle via a
`confirm` field). That recommendation was made on data-quality grounds, not infrastructure
grounds — and it happens to dissolve C1 completely:

> Drop Binance as the primary spot source, and GitHub-hosted runners become viable. The
> self-hosted runner — the single component that caused the worst outage — is then never
> needed at all.

**The fix for the data-quality problem is the same as the fix for the infrastructure problem.**
That convergence is the strongest architectural signal in this entire research effort.

### The unresolved remainder — and why it must be a spike, not an assumption

Spot OHLCV is solvable this way. **Derivatives are not obviously solvable this way**, because
Binance is genuinely dominant for funding/OI/liquidations, and the plausible alternatives
(OKX, Bybit) also restrict US persons — whether they *geo-block unauthenticated public market
data endpoints by IP* is a different question from whether they restrict US *accounts*, and
the two are frequently conflated.

**This could not be tested from here.** All verification in this document was performed from
the owner's machine in Lebanon, where Binance `fapi` responds normally (confirmed:
`premiumIndex` and `fundingRate` both returned live data on 2026-09-07). Reachability from a
US IP cannot be established from a non-US IP.

**Therefore the first PRD must include a reachability spike** that runs on the actual target
compute and records, per venue and per endpoint, the HTTP status observed. Concretely, for
each of Binance spot + fapi, Coinbase, Kraken, OKX, Bybit, Deribit and Coinglass: does an
unauthenticated public request from a GitHub-hosted runner return 200 or 451?

Until that table exists, the compute location is **undecided**, and any architecture document
claiming otherwise is guessing. This is exactly the class of assumption that, left untested,
becomes a silent failure three months later.

---

## C2 · "Live" is mostly a fiction at this data's cadence

Verified update cadences of the actual sources:

| Source | Genuine update cadence |
|---|---|
| Spot OHLCV | seconds to minutes |
| Funding rate | **8h** on Binance (fixed); 1h–8h and *dynamic* on OKX/Bybit (R1) |
| Open interest | minutes, but published in coarse buckets |
| Coin Metrics on-chain (MVRV, flows, addresses) | **daily close, one point per UTC day** |
| Fear & Greed | daily |
| M2 | monthly, with a **multi-week release lag** |

Only one row in that table moves faster than every eight hours. A WebSocket push layer would
therefore deliver real-time updates for **price alone**, while every other panel on the page
sat unchanged for hours — and the prior system already proved the cost of that choice
(R0/F10: a resident WebSocket listener starved the scheduled jobs and was reverted).

**Conclusion: "live" here means "provably fresh", not "streaming".** The product's value is
that a stale number *announces itself*, not that a fresh one arrives in 50ms. This is
consistent with R6's polling recommendation and should be stated plainly to the owner, because
the project's own name ("live platform") invites the opposite assumption.

---

## C3 · The budget question has a sharper answer than any single track gave

Combining the verified Coin Metrics matrix (R2 §0, measured) with R1's derivatives findings:

| | BTC | ETH | SOL |
|---|---|---|---|
| **Spot OHLCV + technicals** | free | free | free |
| **Derivatives** (funding, OI, L/S) | free, exchange APIs | free | free |
| **On-chain** (MVRV, flows, addresses) | **free** (Coin Metrics) | **free** (Coin Metrics) | **nothing — not even price** |

**The entire paid-tier question reduces to one row: SOL's on-chain column.** Everything else
on the board is genuinely obtainable at $0.

That reframes the decision the owner faces at G2. It is not "how much should I spend on data" —
it is "is SOL on-chain data worth ~$29–109/mo, given that BTC and ETH are free and SOL's
UTXO-derived metrics (SOPR, Puell, Reserve Risk) are **not definable at any price**?"

Presented that way, the honest v1 recommendation is **$0**: ship with SOL's on-chain panel
rendering `UNAVAILABLE — no free source`, which is a *truthful* display and exactly what the
product exists to do. Buy coverage later, if the empty panel actually proves annoying in use.
Paying to fill a panel before knowing whether it is looked at is the same reflex that produced
25 indicators nobody had validated.

---

## C4 · Three kinds of "unavailable" must be distinguished

Measured against Coin Metrics (R2 §0), a metric can be absent for three different reasons:

| Reason | Example | UI treatment |
|---|---|---|
| **NOT-DEFINABLE** — the metric has no meaning on this chain | SOPR/MVRV on SOL: account-based, no UTXO to timestamp | `n/a for this chain` — permanent, and *correct*, not a gap |
| **PAYWALLED** — exists, we lack credentials | `CapRealUSD` on BTC | `requires paid tier` — actionable |
| **FETCH-FAILED** — should exist, did not arrive | endpoint 500, timeout | `unavailable` + reason — alarming |

Collapsing these into one blank cell destroys the information the owner most needs: whether
the gap is permanent, purchasable, or broken. The prior system had no concept of any of them —
it emitted `0.0`.

---

## C5 · Two claims from the research agents that I corrected by measurement

Recorded so the corrections are not re-introduced later:

1. **"Coin Metrics' free API publishes no MVRV for any asset"** (R2 §1) — **false**.
   `CapMVRVCur` is free for BTC and ETH; BTC returned `1.5105` and ETH `1.1169` on
   2026-09-06. Full measured matrix in R2 §0. SOL genuinely has no such metric.
2. **"Dune's free tier stopped allowing query execution on 2026-09-10"** (R2) — that date is
   **in the future** relative to 2026-09-07. An announced change at best. Not planned against.

Both agents were otherwise sound. The lesson for this project's own operation: **a confident
research claim is not evidence, and the cost of checking was two `curl` calls.**
