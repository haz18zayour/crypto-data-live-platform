# 05 · Product roadmap

The ordered PRD list. This IS the backlog — `uf run` walks `prds/` in this order.

**Shape of the plan:** PRD-001 is a thin *vertical slice* — schema, registry, one fetcher, one
deployed page, one dead-man's-switch — so the whole spine is proven in production before any
breadth is added. Every later PRD adds one panel to a page that already works.

| PRD | Title | Why it is here | Depends on | Status |
|---|---|---|---|---|
| **PRD-001** | **Spine: reachability spike + registry + provenance schema + one live indicator, deployed** | Settles the one open architectural question (which venues are reachable from the target compute) **before** anything is built on the answer. Then proves the entire path end to end with a single indicator: fetch → status → provenance → Postgres → page → freshness visible → Healthchecks alerts on silence. The riskiest assumptions die first | — | planned |
| **PRD-002** | Determinism and contract harness | Golden-file tests pinning indicator output to fixed bars; VCR/cassette tests per vendor; warm-up-boundary tests; a `source_timestamp`-in-the-future assertion. Directly defends F5 (uptime-dependent values) and F11 (wrong field). Comes *before* breadth so every later indicator inherits the harness | 001 | planned |
| **PRD-003** | Spot OHLCV + technical indicators (BTC/ETH/SOL/BNB) | RSI, EMA stack, MACD, StochRSI, Bollinger, ATR, OBV via TA-Lib. Wilder smoothing explicit; population vs sample stdev settled; unclosed-candle exclusion enforced via OKX `confirm` | 002 | planned |
| **PRD-004** | Derivatives panel | Funding (**settled** series, never `premiumIndex`), open interest, long/short ratio, taker ratio. Per-venue funding interval recorded so cross-venue comparison and annualisation are correct | 002 | planned |
| **PRD-005** | On-chain panel — and honest absence | Coin Metrics MVRV, exchange flows, active addresses for **BTC + ETH**; MVRV/addresses/supply also free for **BNB**. For **SOL**: network activity and staking are BUILT from the free public RPC (verified live: epoch, cumulative tx count, circulating supply) while valuation and exchange flows render `NOT_DEFINABLE` — no vendor sells SOL realized-cap at any price, and a self-curated exchange-label set would recreate the wrong-data failure. See `research/R8`. This PRD is as much about displaying absence correctly as about displaying data | 002 | planned |
| **PRD-006** | Macro and flows panel | FRED series with **release lag surfaced on the face of each value**; stablecoin supply (DefiLlama); ETF net flows (SoSoValue, T+1); Fear & Greed labelled as a composite. `DTWEXBGS` labelled as a broad-dollar index, not "DXY" | 002 | planned |
| **PRD-007** | The single page | Layout of all panels on one screen: 4 assets × all indicators, staleness legible at a glance, three kinds of unavailability visually distinct. The product's actual thesis lives or dies here | 003–006 | planned |
| **PRD-008** | History and charts | Backfill; per-indicator sparklines and distribution context (so a value can be read against its own history rather than an arbitrary band) | 007 | planned |
| **PRD-009** | Integrity dashboard | Frozen-value detection, per-source freshness SLA rollup, coverage generated from the registry so an uncovered indicator is a build error. The self-audit that actually audits | 007 | planned |

Status: `planned` → `researching` → `specced` → `running` → `shipped`

---

## Ordering rationale

1. **The unknown goes first.** PRD-001 opens with the reachability spike because the compute
   location is genuinely undecided (R7 §C1) and every subsequent PRD assumes an answer.
2. **Data model early** — the `datapoints` schema and `asset_match` CHECK constraint are the
   least reversible things in the project.
3. **Auth before anything behind auth** — Cloudflare Access is configured in PRD-001, before
   a dashboard exists to expose.
4. **The test harness precedes breadth.** PRD-002 before 003–006 so twenty indicators inherit
   determinism and contract tests instead of retrofitting them onto twenty call sites.
5. **First shippable slice as early as possible** — PRD-001 ends with a real page, in
   production, showing one real number with its provenance.

## Out of scope for v1

Confirmed by the owner at gate G1, 2026-09-07. Restated from `01_Problem_Statement.md`
because this list is the cheapest thing to write and the most expensive to skip.

- **No composite score.** No summing, averaging or weighting into one number — the specific
  mechanism that inverted the prior system.
- **No buy / sell / hold signal**, conviction rating, entry zone, or ranking of coins.
- **No portfolio allocation, position sizing, or P&L.**
- **No backtesting or calibration engine.**
- **No trade execution; no exchange keys with trading permissions — ever.**
- **No alerts, email, Telegram or push.** The page is pulled, not pushed. *(The one exception
  is the Healthchecks.io dead-man's-switch, which alerts on pipeline silence — infrastructure
  liveness, not market content.)*
- **No multi-user, billing, or public access.**
- **No LLM-generated narrative** over the data.
- **No mobile-native app.** Responsive web only.
- **No fifth coin.** BTC, ETH, SOL fixed; **BNB** pinned in config (one line to change).
- **No migration or maintenance of `crypto-investing-signals`.** Mined for research; otherwise
  left running and untouched.
- **No paid data subscription in v1.** SOL's on-chain column ships empty and honest.

A signal layer may be built later as a **separate product consuming this one**. Keeping the
trustworthy layer separate from the layer that was measured to be wrong is the entire point.
