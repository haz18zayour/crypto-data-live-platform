# 05 · Product roadmap

The ordered PRD list. This IS the backlog — `uf run` walks `prds/` in this order. Ids are written plain, not bold — `uf next` requires the cell to start with `PRD-NNN` and bold markers make the whole roadmap invisible to it.

**Shape of the plan:** PRD-001 is a thin *vertical slice* — schema, registry, one fetcher, one
deployed page, one dead-man's-switch — so the whole spine is proven in production before any
breadth is added. Every later PRD adds one panel to a page that already works.

| PRD | Title | Why it is here | Depends on | Status |
|---|---|---|---|---|
| PRD-001 | **Spine: reachability spike + registry + provenance schema + one live indicator, deployed** | Settles the one open architectural question (which venues are reachable from the target compute) **before** anything is built on the answer. Then proves the entire path end to end with a single indicator: fetch → status → provenance → Postgres → page → freshness visible → Healthchecks alerts on silence. The riskiest assumptions die first | — | planned |
| PRD-002 | Determinism and contract harness | Golden-file tests pinning indicator output to fixed bars; VCR/cassette tests per vendor; warm-up-boundary tests; a `source_timestamp`-in-the-future assertion. Directly defends F5 (uptime-dependent values) and F11 (wrong field). Comes *before* breadth so every later indicator inherits the harness | 001 | planned |
| PRD-003 | **Cross-source corroboration** | The only defence in this roadmap against mistakes we have not thought of. Every other check enforces something someone predicted; this one catches a wrong number because a second, independent venue disagrees. Fetch the same quantity from 2+ venues, compare within tolerance, and treat divergence as a finding rather than picking a winner. Placed here so every indicator built afterwards inherits the pattern | 002 | planned |
| PRD-004 | Spot OHLCV + technical indicators (BTC/ETH/SOL/BNB) | RSI, EMA stack, MACD, StochRSI, Bollinger, ATR, OBV via TA-Lib. Wilder smoothing explicit; population vs sample stdev settled; unclosed-candle exclusion enforced via OKX `confirm` | 002 | planned |
| PRD-005 | The single page | **The dashboard you actually want.** Moved ahead of the remaining panels at the owner's request: the completeness matrix needs rows, not every row. After PRD-004 there are ~32 real cells across 4 assets — enough for the layout, the coverage header and the NOT_DEFINABLE / PAYWALLED / FETCH_FAILED distinction to be real rather than theoretical. Later panels add rows to a grid that is already designed. Apple-grade; stories MUST set `agent: claude` (see 20_Design_System.md) | 004 | shipped |
| PRD-006 | Derivatives panel | Funding (**settled** series, never `premiumIndex`), open interest, long/short ratio, taker ratio. Per-venue funding interval recorded so cross-venue comparison and annualisation are correct | 002 | shipped |
| PRD-007 | On-chain panel — and honest absence | Coin Metrics MVRV, exchange flows, active addresses for **BTC + ETH**; MVRV/addresses/supply also free for **BNB**. For **SOL**: network activity and staking are BUILT from the free public RPC (verified live: epoch, cumulative tx count, circulating supply) while valuation and exchange flows render `NOT_DEFINABLE` — no vendor sells SOL realized-cap at any price, and a self-curated exchange-label set would recreate the wrong-data failure. See `research/R8`. This PRD is as much about displaying absence correctly as about displaying data | 002 | researching |
| PRD-008 | Macro and flows panel | FRED series with **release lag surfaced on the face of each value**; stablecoin supply (DefiLlama); ETF net flows (SoSoValue, T+1); Fear & Greed labelled as a composite. `DTWEXBGS` labelled as a broad-dollar index, not "DXY" | 002 | planned |
| PRD-009 | History and charts | Backfill; per-indicator sparklines and distribution context (so a value can be read against its own history rather than an arbitrary band) | 005 | planned |
| PRD-010 | Integrity dashboard | Frozen-value detection, per-source freshness SLA rollup, coverage generated from the registry so an uncovered indicator is a build error. The self-audit that actually audits | 005 | planned |
| PRD-011 | Deploy to Cloudflare Workers | Moved out of PRD-001. The data path is already in production via GitHub Actions; the page is a single-user read-only viewer that localhost exercises identically. **Amended 2026-10-06:** Cloudflare Access was dropped from scope by owner decision — the deployed page is public, since it is read-only market data with nothing to protect. The service-role bundle scan did NOT move with it — it runs locally in PRD-001 | 005 | shipped |
| PRD-012 | Split cadence: daily collect + 6h canary | Owner decision 2026-09-09. Almost every source publishes once a day or slower, so 6-hourly collection refetches identical values; but daily-only collection hides a failure for 24h+grace — the prior system's exact blind spot. Splits into a daily `collect` job and a 20-second `canary` every 6h that pings sources and the heartbeat and writes no datapoints. Failure visible in ~6–8h, data honest at daily, owner contacted only on breakage. Small; fold into PRD-002 if convenient | 001 | planned |

Status: `planned` → `researching` → `specced` → `running` → `shipped`

---

## Ordering rationale

1. **The unknown goes first.** PRD-001 opens with the reachability spike because the compute
   location is genuinely undecided (R7 §C1) and every subsequent PRD assumes an answer.
2. **Data model early** — the `datapoints` schema and `asset_match` CHECK constraint are the
   least reversible things in the project.
3. ~~Auth before anything behind auth~~ — **superseded 2026-10-06:** PRD-011 dropped Cloudflare
   Access from scope entirely; the deployed page is public by owner decision (see the
   out-of-scope amendment above). No auth layer exists or is planned.
4. **The test harness precedes breadth.** PRD-002 before 003–006 so twenty indicators inherit
   determinism and contract tests instead of retrofitting them onto twenty call sites.
5. **Corroboration precedes breadth.** PRD-003 comes before the panels because it is the
   only check that does not require predicting the failure. The OKX `bar=1D` bug — a Hong
   Kong day close stored as a UTC one, 0.35% off, caught only because a human looked at the
   number — would have been caught automatically by comparing OKX against Coinbase.
6. **First shippable slice as early as possible** — PRD-001 ends with a real page, in
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
- **No multi-user, billing, accounts or login.** **Amended 2026-10-06:** the deployed page
  itself is reachable publicly by the owner's explicit choice (PRD-011 dropped Cloudflare
  Access from scope) — it is still single-operator, read-only, and shows the same honest data
  to anyone who loads it.
- **No LLM-generated narrative** over the data.
- **No mobile-native app.** Responsive web only.
- **No fifth coin.** BTC, ETH, SOL fixed; **BNB** pinned in config (one line to change).
- **No migration or maintenance of `crypto-investing-signals`.** Mined for research; otherwise
  left running and untouched.
- **No paid data subscription in v1.** SOL's on-chain column ships empty and honest.

A signal layer may be built later as a **separate product consuming this one**. Keeping the
trustworthy layer separate from the layer that was measured to be wrong is the entire point.
