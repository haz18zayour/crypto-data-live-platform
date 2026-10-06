# 01 · Problem statement

## The problem

Indicator data for crypto assets fails **silently**. It does not throw; it returns a number,
and the number is wrong. Measured, in the owner's previous system
(`crypto-investing-signals`, 96 PRDs, live in production for ~9 months):

| Failure | Evidence |
|---|---|
| A fetcher was never called before the pipeline ran | funding rate, open interest and L/S ratio scored a confident `0.0` for months |
| BTC's on-chain series was applied to 8 other coins | the project's own doc: *"not degraded data, **wrong data**"* |
| A "second" indicator was an algebraic restatement of the first | NUPL computed as `1 − 1/MVRV`; whale accumulation derived from exchange flow. Both carried independent weight. Dropped in PRD-092 |
| An indicator was inverted against reality | `spx_correlation`, over 1,394 days: bearish readings preceded **+0.789%** next-day BTC against a **+0.091%** base rate. Dropped in PRD-095 |
| Sources were chosen by availability, not validity | Reddit → 4chan /biz/, LunarCrush → Google Trends, CryptoPanic → CryptoCompare. The doc records their correlation validity as *unvalidated* |

The compounding cost: with roughly half the composite weight resting on contrarian inputs, a
simulated **−40% drawdown scored +5.94** against **+6.4** at an all-time high. A frozen
calibration over 140 configurations returned `corr(calibrate, test) = −0.518` — calibration
skill *anti-predicted* out-of-sample skill, so no amount of re-weighting could recover it.

**None of this was visible while it was happening.** There was no surface on which a wrong
number looked different from a right one. That absence — not the modelling — is the problem
this product solves.

## Who has it

One person: the owner, allocating his own capital across BTC, ETH, SOL and one manually
pinned fourth asset (**BNB**). Not a team, not customers, not a market. A single operator who needs to
trust his instruments before he trusts anything built on them.

## How it is solved today

He does not. The previous system still emails signals four times a day, and its own README
warns the reader not to trust them. The current workaround is manual spot-checking against
TradingView, exchange UIs and block explorers — episodic, unrecorded, and impossible to
perform across ~25 indicators × 4 coins at any useful frequency.

## Why now

The signal work is halted, not by a missing feature but by an absent foundation. A five-seat
council voted 5/5 on 2026-09-03 that the entry score must carry zero allocation weight; the
open remediation items are all data-integrity items (PRD-092 integrity, PRD-097 fail-closed
semantics, PRD-087 self-audit). Re-approaching the signal problem without first being able to
*see* each input, per coin, with its provenance, is a guarantee of repeating it.

## What success looks like in 90 days

**Every indicator on the page states where it came from, when it was last updated, and
whether that is stale — and any indicator that cannot be honestly sourced for a given coin
renders as `UNAVAILABLE` rather than as a number.**

The observable test: pick any cell on the page at random; within five seconds, know its
source, its age, and whether it is real for *that* coin. Zero proxied values presented as
native. Zero indicators derivable from another indicator already on the page.

## Explicitly NOT solving

Confirmed at gate G1 by the owner on 2026-09-07.

- **No composite score.** No summing, averaging or weighting of indicators into a single
  number. This is the specific mechanism that inverted the previous system.
- **No buy / sell / hold signal.** No conviction rating, no entry zones, no ranking of coins
  against each other.
- **No portfolio allocation, position sizing, or P&L.**
- **No backtesting or calibration engine.**
- **No trade execution, and no exchange keys with trading permissions — ever.**
- **No alerts, email, Telegram or push** in v1. The page is pulled, not pushed.
- **No multi-user support, no billing, no accounts or login.** Single operator. **Amended
  2026-10-06:** the deployed page itself is reachable publicly, by the owner's explicit choice
  (Cloudflare Access was dropped from PRD-011's scope) — it displays the same read-only market
  data regardless of who loads it, so public reachability carries no data-exposure risk beyond
  what the product already shows. This is a change to *who can open the URL*, not to the
  single-operator, no-accounts nature of the product itself.
- **No LLM-generated narrative or commentary** over the data.
- **No mobile-native app.** Responsive web only.
- **More than four coins.** BTC, ETH, SOL fixed; BNB pinned in config, changeable in one line.
- **Migrating or maintaining `crypto-investing-signals`.** It is mined for research and
  otherwise left alone.

A signal layer may be built later, as a separate product that *consumes* this one. Keeping
the trustworthy layer separate from the layer that was wrong is the point.
