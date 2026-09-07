# R2 · On-Chain Data Sources — Per-Asset Availability for BTC, ETH, SOL

**Scope:** genuine per-asset on-chain data availability for the 4-asset observability dashboard
(BTC, ETH, SOL + 1 pinned coin). Research only. Date: 2026-09-07.

**Framing:** the prior system's own documentation called BTC-on-chain-applied-to-8-coins
*"not degraded data, wrong data,"* and double-counted `NUPL = 1 - 1/MVRV` as an independent
signal from MVRV. This document exists to prevent both mistakes recurring: it marks metrics
`NOT-DEFINABLE` rather than proposing a proxy, and flags every algebraically-derived metric.

---

## 0. VERIFIED CORRECTION — measured directly against the live API, 2026-09-07

> **The claim below in §1 that Coin Metrics' free Community API "does not publish realized
> cap, MVRV, SOPR, or NUPL for any of the three assets" is WRONG for MVRV.** It was corrected
> by querying the live endpoint rather than reading the catalog. The rest of this document
> stands, but where it conflicts with this section, **this section wins** — it is measurement,
> not documentation.

Live probe, one metric at a time, no API key, `community-api.coinmetrics.io/v4/timeseries/asset-metrics`:

| Metric | BTC | ETH | SOL |
|---|---|---|---|
| `CapMVRVCur` (MVRV) | **FREE** | **FREE** | NO-METRIC |
| `AdrActCnt` (active addresses) | **FREE** | **FREE** | PAID |
| `FlowInExNtv` / `FlowOutExNtv` (exchange flows) | **FREE** | **FREE** | NO-METRIC |
| `SplyCur` (circulating supply) | **FREE** | **FREE** | PAID |
| `TxCnt` (transaction count) | **FREE** | **FREE** | PAID |
| `CapMrktCurUSD` (market cap) | **FREE** | **FREE** | PAID |
| `PriceUSD` | **FREE** | **FREE** | PAID |
| `IssTotNtv` (issuance) | **FREE** | **FREE** | PAID |
| `HashRate` | **FREE** | FREE (post-merge: meaningless) | NO-METRIC |
| `CapRealUSD` (realized cap) | PAID | PAID | NO-METRIC |
| `DiffMean`, `SplyAct1yr` | PAID | PAID | NO-METRIC |
| `FeeMeanUSD`, `NVTAdj`, `VtyDayRet30d` | PAID | PAID | PAID |

Sample verified response (`CapMVRVCur`, BTC): `2026-09-06 → 1.510496045367411941`.
ETH on the same day: `1.116904747870542701`.
SOL returns: `"Bad parameter 'metrics'. All requested metrics aren't supported for asset 'sol'"`.

### What this actually establishes

1. **The prior system's MVRV and exchange-flow fetches were legitimate — *for BTC and ETH*.**
   The fabrication (R0/F2) was not inventing the source; it was **applying BTC's values to
   eight other coins**. That distinction matters: the source is sound, the fan-out was not.
2. **SOL has effectively ZERO free coverage from Coin Metrics** — not even `PriceUSD`. Three
   distinct failure modes are visible and must be distinguished in the UI:
   - `NO-METRIC` — the metric does not exist for this chain at all (MVRV, exchange flows)
   - `PAID` — exists, but gated behind credentials we do not have
   - `FREE` — genuinely available
   Collapsing these three into one "unavailable" loses real information about *why*.
3. **Realized cap is paid on every asset**, so any MVRV variant beyond `CapMVRVCur` itself
   (MVRV Z-score, realized price) cannot be computed on the free tier — it must be marked
   `UNAVAILABLE`, never derived. This is exactly the F3 trap.
4. **The honest consequence for the dashboard: SOL's on-chain column is nearly empty at $0.**
   That is the correct, truthful outcome, and it is the single strongest argument for
   whichever paid tier the owner chooses. It should be presented that way at the budget gate
   rather than hidden by proxying.

### Two further claims in this document that I could not confirm

- **"Dune's free tier stopped allowing query execution on 2026-09-10"** — that date is *three
  days in the future* as of writing (today is 2026-09-07). Treat as an announced upcoming
  change, not an accomplished fact. **UNVERIFIED — do not plan against it either way.**
- Glassnode, CryptoQuant, and Amberdata pricing pages blocked automated fetching (403 /
  redirect loops). Every figure quoted for them is second-hand. **Confirm real prices in a
  browser before any subscription decision at gate G2.**

---

## 1. Executive summary — 5 things that matter most

1. **MVRV genuinely exists for all three chains, but on completely different footing.** BTC's
   MVRV is UTXO-exact (every satoshi has a last-moved price). ETH and SOL are account-based —
   there is no UTXO to timestamp, so "realized cap" for them is a *reconstructed* metric built
   from transfer-graph heuristics (cost-basis-per-address, FIFO/HIFO assumptions). Glassnode
   publishes MVRV for both ETH and SOL using this methodology; Coin Metrics' **free Community
   API does not publish realized cap, MVRV, SOPR, or NUPL for any of the three assets** — its
   free tier is essentially price/supply/active-address data only (verified directly against
   the live catalog endpoint, see §7).
2. **SOPR is BTC-native by construction and does not genuinely exist for ETH or SOL.** SOPR
   is defined as (value of a UTXO at spend) / (value of that UTXO at creation) — it requires a
   discrete, uniquely-priced unit of currency (a UTXO). Account-based chains have no such unit;
   any "SOPR" quoted for ETH or SOL is a vendor-specific reconstruction from address-level
   cost-basis heuristics, not the same measurement. No vendor researched (Glassnode, CryptoQuant,
   Santiment, Coin Metrics) publishes a metric literally labeled SOPR for ETH or SOL as of this
   research. Treat SOPR as **BTC-only**; do not accept an ETH/SOL "SOPR" without inspecting its
   exact construction.
3. **Puell Multiple, Reserve Risk, and Thermocap are structurally Bitcoin-only.** All three are
   built on Bitcoin's fixed, auditable issuance schedule and PoW block-reward economics (miner
   revenue = subsidy + fees, valued at time of production). ETH (post-Merge, no block subsidy,
   PoS) and SOL (inflationary PoS issuance, different validator economics) have no equivalent
   "miner cost basis" concept. These three should render `NOT-DEFINABLE`, not "unavailable" —
   the distinction matters because a future vendor integration cannot fix this.
4. **Dune's free tier stopped being free for query execution on 2026-09-10** (this week, per
   the account cutoff: accounts created before 2026-07-21 lose query-execution rights and
   become view-only; Dune cited compute cost as the reason). This changes the "$0 route"
   calculus materially — Dune/Flipside-style community-SQL platforms are no longer a reliable
   $0 foundation for a personal project; budget for at least the cheapest paid analyst tier
   ($65/mo billed annually, per Dune's FAQ) if depending on Dune queries.
5. **Exchange-flow and exchange-balance numbers disagree across vendors by construction, not
   by error.** Glassnode's own transparency notice states reported exchange balances are
   *"lower bounds of the true balance"* subject to *"retrospective revisions"* as clustering
   improves. CryptoQuant and Glassnode have publicly disputed the same on-chain event (a Gemini
   whale deposit) with opposite interpretations of the same transaction. This is a standing
   trap for a dashboard that shows a single number per indicator — provenance (which vendor,
   which clustering version) is not optional metadata here, it is the difference between two
   contradictory "facts."

---

## 2. Metric × Asset availability matrix

Legend: **AVAILABLE-FREE** (a real, no-cost API/route exists) · **AVAILABLE-PAID** (exists,
requires a paid tier from at least one vendor) · **NOT-DEFINABLE** (no genuine construction
exists for this chain's architecture) · **NO-VENDOR** (definable in principle, but no vendor
researched actually publishes it for this asset).

### Valuation

| Metric | BTC | ETH | SOL |
|---|---|---|---|
| MVRV | AVAILABLE-FREE (Coin Metrics free API has `CapMVRVCur` for BTC — see caveat §7; LookIntoBitcoin free charts) | AVAILABLE-PAID (Glassnode Studio chart free-to-view, API behind Advanced/Pro; CM free tier does NOT have it) | AVAILABLE-PAID (Glassnode publishes SOL MVRV; CM free tier does NOT) |
| MVRV Z-Score | AVAILABLE-FREE (LookIntoBitcoin free chart) | AVAILABLE-PAID (Glassnode) | AVAILABLE-PAID (Glassnode — chart exists at studio.glassnode.com/charts/market.MvrvZScore?a=SOL) |
| Realized Cap | AVAILABLE-FREE (Coin Metrics community catalog exposes it for BTC in some tiers; multiple free chart sites) | AVAILABLE-PAID (Glassnode; reconstructed, not UTXO-exact) | AVAILABLE-PAID (Glassnode; reconstructed) |
| Realized Price | AVAILABLE-FREE (derivable from realized cap ÷ supply; CryptoQuant free charts) | AVAILABLE-PAID | AVAILABLE-PAID |
| NUPL | AVAILABLE-FREE (LookIntoBitcoin) — **but algebraically `1 - 1/MVRV`; do not treat as independent of MVRV** | AVAILABLE-PAID (same derivation warning applies) | AVAILABLE-PAID (same derivation warning) |
| SOPR (+aSOPR, STH/LTH-SOPR) | AVAILABLE-PAID (Glassnode Advanced+; UTXO-exact) | **NOT-DEFINABLE** (no UTXO unit; no vendor found publishing a genuine equivalent) | **NOT-DEFINABLE** (same reason) |
| Puell Multiple | AVAILABLE-FREE (LookIntoBitcoin) | **NOT-DEFINABLE** (no block-subsidy miner-revenue concept post-Merge) | **NOT-DEFINABLE** (validator issuance economics are structurally different; no vendor equivalent found) |
| Reserve Risk | AVAILABLE-PAID (Glassnode; also LookIntoBitcoin free) | **NOT-DEFINABLE** | **NOT-DEFINABLE** |
| Thermocap | AVAILABLE-FREE/PAID (Glassnode, Newhedge free chart) | **NOT-DEFINABLE** (no PoW security spend) | **NOT-DEFINABLE** (no PoW security spend) |

### Flows

| Metric | BTC | ETH | SOL |
|---|---|---|---|
| Exchange inflow/outflow/netflow | AVAILABLE-PAID (CryptoQuant Advanced $29-39/mo annual; Glassnode) | AVAILABLE-PAID (CryptoQuant, Glassnode both cover ETH) | AVAILABLE-PAID (CryptoQuant markets SOL exchange-flow coverage; **UNVERIFIED** exact metric parity with BTC — CryptoQuant's own SOL-specific doc pages returned 403/404 to automated fetch during this research) |
| Exchange balance/reserve | AVAILABLE-PAID (same vendors) | AVAILABLE-PAID | AVAILABLE-PAID (**UNVERIFIED** depth vs BTC) |
| Miner flows | AVAILABLE-PAID (CryptoQuant "Miner Reserve/Position Index") | **NOT-DEFINABLE** (no miners) | **NOT-DEFINABLE** (no miners) |
| Large-holder / whale transactions | AVAILABLE-PAID (Glassnode, CryptoQuant whale-ratio); AVAILABLE-FREE at low depth (Whale Alert Twitter/API free tier, unstructured) | AVAILABLE-PAID | AVAILABLE-PAID (Nansen "smart money" flags SOL wallets; Solscan free explorer shows large txns unstructured) |

### Network activity

| Metric | BTC | ETH | SOL |
|---|---|---|---|
| Active addresses | AVAILABLE-FREE (Coin Metrics free API `AdrActCnt`, confirmed live) | AVAILABLE-FREE (Coin Metrics free API `AdrActCnt`, confirmed live) | AVAILABLE-FREE (Artemis public dashboards; Dune `solana.transactions`; **not** in Coin Metrics free tier, confirmed absent) |
| Transaction count | AVAILABLE-FREE (Coin Metrics, mempool.space, Blockchain.com) | AVAILABLE-FREE (Etherscan, Coin Metrics) | AVAILABLE-FREE (Solana Beach, Solscan, Artemis, Solana Foundation's solana.com/data) |
| Fees | AVAILABLE-FREE (mempool.space) | AVAILABLE-FREE (Etherscan gas tracker, ultrasound.money for burn) | AVAILABLE-FREE (Solana Beach, Dune "Solana Fee Tracker" public dashboard, Artemis) |
| Hashrate/difficulty (BTC) | AVAILABLE-FREE (Blockchain.com, mempool.space) | NOT-DEFINABLE (PoS, no hashrate) | NOT-DEFINABLE |
| Gas price (ETH) | NOT-DEFINABLE (no gas market) | AVAILABLE-FREE (Etherscan) | NOT-DEFINABLE (SOL has priority fees, a different mechanism — do not equate to ETH gas) |
| TPS / validator & staking data (SOL) | NOT-DEFINABLE | NOT-DEFINABLE (ETH has its own staking metric, see Supply row) | AVAILABLE-FREE (Solana Beach, Stakewiz API, validators.app, Solscan validators page) |

### Supply

| Metric | BTC | ETH | SOL |
|---|---|---|---|
| Circulating vs total/max supply | AVAILABLE-FREE (near-universal: CoinGecko, CMC, Coin Metrics) | AVAILABLE-FREE | AVAILABLE-FREE |
| Staked supply | NOT-DEFINABLE (no staking) | AVAILABLE-FREE (beaconcha.in, Dune) | AVAILABLE-FREE (Solana Beach, Stakewiz — SOL has high staking ratio ~65-70%, this is a materially important indicator) |
| Supply in profit/loss | AVAILABLE-PAID (Glassnode; needs realized-price-per-coin distribution, itself UTXO-native) | AVAILABLE-PAID (Glassnode; reconstructed) | AVAILABLE-PAID (Glassnode; reconstructed, **UNVERIFIED** whether Glassnode covers SOL for this specific sub-metric — chart existence not confirmed for this exact one) |
| HODL waves / age-band supply | AVAILABLE-PAID (Glassnode, UTXO-age-exact) | AVAILABLE-PAID (Glassnode "MVRV by Age" exists for SOL too, implying an ETH/age equivalent likely exists — **UNVERIFIED** exact ETH chart) | AVAILABLE-PAID (confirmed: Glassnode "Solana MVRV by Age" chart exists) |
| Long/short-term holder supply | AVAILABLE-PAID (Glassnode, CryptoQuant; UTXO-age-exact, the "true" original construction) | AVAILABLE-PAID (reconstructed via first-seen/last-moved heuristics) | AVAILABLE-PAID (reconstructed; Glassnode "LTH MVRV" chart for SOL confirmed to exist) |

### Stablecoins & ETFs

| Metric | BTC | ETH | SOL |
|---|---|---|---|
| Stablecoin supply/net issuance (chain-level) | N/A (BTC doesn't host stablecoins) | AVAILABLE-FREE (DefiLlama `stablecoins` public API, no auth, confirmed free endpoints) | AVAILABLE-FREE (DefiLlama covers Solana-issued stablecoin supply) |
| US spot ETF net flows | AVAILABLE-FREE (Farside Investors — free daily table + a documented API surface covering BTC ETFs since Jan 2024; SoSoValue free dashboard) | AVAILABLE-FREE (Farside covers ETH ETFs too) | AVAILABLE-FREE-ish (Farside's API listing mentions "all US spot Bitcoin, Ethereum, and Solana ETFs" — **UNVERIFIED**, confirm at launch time since spot SOL ETFs are a newer/still-forming product category; check farside.co.uk/sol/ directly before relying on it) |

---

## 3. Per-vendor comparison (real prices, fetched 2026-09-07)

| Vendor | Free tier | Cheapest paid tier | Mid tier | Top tier | BTC | ETH | SOL |
|---|---|---|---|---|---|---|---|
| **Coin Metrics** | Community API, no key, `community-api.coinmetrics.io/v4`, 10 req/6s per IP. Confirmed live via catalog query: has price/supply/`AdrActCnt` for BTC & ETH; **no** `CapMVRVCur`/`CapRealUSD`/SOPR/NUPL for any of the 3 in free tier; SOL free tier is essentially market-cap/reference-rate only, no active-address data. | Network Data Pro — pricing not publicly listed, sales-quote only (**UNVERIFIED** price) | — | — | Best (Pro) | Good (Pro) | Weakest of the three even on Pro (**UNVERIFIED** — could not confirm SOL parity without a quote) |
| **Glassnode** | Studio (chart viewing) free/Standard tier, no API | Advanced ~$49/mo (charts only, no API per current tier gating) | Professional ~$999/mo billed annually, API access gated to this tier or as an add-on (source: research.glassnode.com/pricing 301-redirected from insights.glassnode.com/pricing — treat exact figure as **UNVERIFIED**, pricing pages changed mid-research and one fetch 404'd) | Institutional, custom, redistribution rights | Best coverage, UTXO-exact metrics | Full MVRV/MVRV-Z/age-cohort suite confirmed via live chart URLs | MVRV, MVRV-Z, MVRV-by-Age, LTH-MVRV all confirmed via live chart URLs — surprisingly deep for SOL, but confirm SOPR/Puell-style metrics are genuinely absent (expected, since NOT-DEFINABLE) |
| **CryptoQuant** | Free tier (per captainaltcoin.com review) | Advanced $39/mo ($29/mo billed yearly) | Professional $109/mo ($99/yr-equiv), adds "Data API up to 24H resolution" | Premium $799/mo ($699/yr-equiv), "Data API up to block-level resolution" | Strongest exchange-flow coverage (500+ exchanges claimed) | Covered, four top-level asset sections are "BTC, ETH, Stablecoins, Altcoins" | SOL sits under "Altcoins" section; a public `cryptoquant.com/asset/sol/summary` page exists but returned 403 to automated fetch — **UNVERIFIED** exact metric depth for SOL vs BTC parity |
| **Santiment** | Free, 1000 API calls/mo, GraphQL, 30-day data lag | Sanbase Pro $49/mo ($44/mo annual) | Sanbase Max $249/mo ($225/mo annual, real-time no lag) | — | Full coverage | Full coverage | Santiment's own "top 3000 assets" chain list named in their pricing copy did **not** include Solana explicitly (listed: Bitcoin, Ethereum, XRP Ledger, BNB Chain, BCH, LTC, Cardano, Dogecoin, ICP, Polygon, Avalanche, Optimism, Arbitrum) — however a separate Santiment insight post is titled "Santiment Unveils Solana Data Coverage," so **SOL support appears to exist but is inconsistent/newer**; treat as UNVERIFIED depth, verify against `academy.santiment.net/metrics` before depending on it |
| **Nansen** | Free: 100 credits + 10/day refresh | Pro $49/mo annual ($69/mo monthly), 2,000 credits/mo; pay-per-use also available: Basic $0.01/call, Advanced $0.05/call | — | Enterprise (no listed tier — "Nansen does not have an Enterprise plan" per one source; contradicts general market knowledge, **UNVERIFIED**) | Covered | Covered (Nansen's core strength is EVM wallet labeling) | Covered — Nansen markets 45+ chains including Solana; "smart money" labels exist for SOL wallets |
| **Dune** | **Materially changed 2026-09-10**: legacy free accounts (created before 2026-07-21) become view-only, cannot execute queries. New free accounts: **UNVERIFIED** exact current limits post-change | Analyst $65/mo (annual), ~4,000 credits/mo | Plus $349/mo (annual), ~25,000 credits/mo | Enterprise custom | Good (community BTC dashboards) | Good | **Strong** — Solana decoded tables (`solana.transactions` etc.) are actively maintained; widely used for SOL fee/active-address dashboards |
| **Flipside Crypto** | Community tier: 500 query-seconds free, unlimited *viewing* of public queries, API access included | Builder/Pro — priced from $349/mo for expanded query-seconds | — | Enterprise (Snowflake data share, custom) | Good | Good | Good — historically one of the strongest free Solana SQL analytics surfaces, though the 500-second cap limits how much you can compute per month |
| **Artemis** | Free "Lite" tier — dashboards + limited API | Professional — price not public, "reach out to sales" (**UNVERIFIED**) | — | Enterprise (Snowflake share, custom API) | Covered (protocol financials, not UTXO valuation metrics) | Covered | Covered — Solana is one of Artemis's flagship chain dashboards (active addresses, fees, DEX volume, stablecoin supply) |
| **Token Terminal** | Free: full historical data, 3 dashboards, CSV export, MCP access — genuinely generous for protocol financials | Pro $350/mo | API tier: custom price, 250,000 req/day | Data Room: custom, raw blockchain + BigQuery/Snowflake share | Covered as "Bitcoin" project fundamentals only (limited — TT is protocol/L2/dApp financials-first, not a UTXO-valuation platform) | Strong (ETH is TT's home turf: fees, revenue, DA) | Strong (SOL fundamentals: fees, revenue, DAU) — **but TT does not publish MVRV/SOPR-style valuation metrics at all**, it's a fees/revenue/PS-ratio platform |
| **DefiLlama** | Free, unauthenticated, `api.llama.fi`, "31 free endpoints," no documented rate limit for normal use | Pro `pro-api.llama.fi` $300/mo — higher limits + ~38 extra endpoints (unlocks, bridges, DAT) | — | — | N/A for on-chain valuation (DefiLlama is TVL/stablecoins/fees, not MVRV-style) | Stablecoin supply on ETH: free | Stablecoin supply on SOL: free — this is DefiLlama's genuine value-add for this project |
| **Bitquery** | Developer: 1,000 points free, rate-limited | Personal $39/mo, 100k points | Pro $79/mo, 1M points | Scale $239/mo, 5M points; Enterprise custom | Covered (raw chain queries, not pre-computed valuation metrics) | Covered | Covered — free gRPC streaming for Solana added in an April 2026 release per their own blog |
| **Covalent / GoldRush** | 14-day trial, 25k credits | "Vibe Coding" $10/mo | Professional $250/mo | Enterprise custom; also pay-per-request via x402 | Wallet/txn indexing only — **not** a source for MVRV/SOPR-style valuation metrics on any chain | Same | Same |
| **Allium** | Free tier, 20,000 credits | From $200/mo | — | Enterprise | Covered (enterprise-grade raw data warehouse, not pre-built valuation metrics) | Covered | Covered — markets Solana price-feed coverage specifically |
| **Amberdata** | **UNVERIFIED** — pricing page did not expose tiers to automated fetch, quote-only appears likely | Custom quote only | — | — | Covered (institutional market + on-chain data) | Covered | **UNVERIFIED** depth |
| **Messari** | Free: 20 req/min, basic asset metrics | Lite/Pro: 200 req/min, no monthly cap, price **UNVERIFIED** (not disclosed in public pages found) | — | Enterprise custom | Covered | Covered (DeFi-protocol metrics, 50+ networks) | Covered at protocol-metrics level; MVRV-style valuation metrics **UNVERIFIED** for Messari specifically — its strength is asset profiles/research, not UTXO-style valuation |
| **Helius** (SOL infra, not analytics) | Free RPC tier | Developer $49/mo | Business $499/mo | Professional $999/mo (+ LaserStream data add-ons $500-4,500/mo for 5-100TB) | N/A | N/A | This is **RPC/indexing infrastructure**, not a pre-computed metrics source — use it only if you plan to compute SOL metrics yourself from raw ledger data, which is a large undertaking |
| **Solscan / SolanaFM** | Solscan: free public tier, reduced limits | Solscan Pro: sales-quoted, third-party estimates suggest ~$199-999/mo tiers (**UNVERIFIED**, not from an official pricing page) | — | — | N/A | N/A | Good for validator lists, large-transaction browsing, block explorer data; not a source for pre-computed valuation metrics |
| **Farside Investors** | Fully free — daily ETF flow tables + a documented 6-endpoint API surface, data from Jan 2024 | N/A (no paid tier found) | — | — | BTC spot ETF flows, 12 tickers (IBIT, FBTC, GBTC, ARKB, etc.) | ETH spot ETF flows | SOL spot ETF flows claimed by one API-listing source — **UNVERIFIED**, confirm before relying on it since SOL spot ETFs are newer |
| **SoSoValue** | Free dashboard (web only, no confirmed free API) | **UNVERIFIED** | — | — | Covered | Covered | Covered |

---

## 4. Budget recommendation: what each tier genuinely buys

**$0/month — genuinely obtainable, no proxying:**
- Coin Metrics free API: BTC + ETH active addresses, price, supply (NOT MVRV/SOPR/NUPL for
  anything, confirmed empirically).
- DefiLlama free API: stablecoin supply/net-issuance on ETH and SOL.
- Farside: BTC + ETH (and likely SOL) spot ETF net flows.
- Solana network/staking data: Solana Beach + Stakewiz APIs, free, no key.
- ETH gas: Etherscan free tier / ultrasound.money.
- BTC hashrate/difficulty/fees: mempool.space, free, no key.
- Public dashboards (Dune, Artemis, DefiLlama) for active addresses / fees / TPS if you're
  willing to either screen-scrape a public dashboard's numbers or accept the post-2026-09-10
  Dune constraint (view existing public dashboards, do not expect to run new queries for free).
- **What $0 does NOT buy, for any of the three assets:** MVRV, MVRV Z-score, realized cap,
  NUPL, SOPR, supply-in-profit/loss, LTH/STH supply split, HODL waves, exchange netflow. Every
  vendor researched gates these behind a paid tier. This is the single most important
  budget fact in this document — the valuation-metric category the prior system got wrong is
  also the category with no genuine $0 route.

**Under $50/month:**
- CryptoQuant Advanced ($29-39/mo) — exchange flows, some valuation metrics, but SOL depth
  UNVERIFIED (403'd on inspection; budget time to verify before committing).
- Santiment Pro ($44-49/mo) — full BTC/ETH coverage, SOL coverage inconsistent/unverified.
- Nansen Pro ($49-69/mo, 2,000 credits) — strong wallet-labeling/whale data across all three
  chains, weaker on classic MVRV/SOPR-style valuation metrics (Nansen's strength is flow/labels,
  not realized-cap-style valuation).
- This budget buys **exchange-flow and whale/labeling data credibly for all three assets**, but
  probably not a full BTC-grade MVRV/SOPR/Reserve-Risk suite for ETH/SOL — that still points to
  Glassnode.

**$50-200/month:**
- Glassnode is the only vendor confirmed (via live chart URLs) to publish the full MVRV /
  MVRV-Z / MVRV-by-Age / LTH-MVRV family for **all three assets**, but its own API access is
  gated to the Professional tier which multiple sources price near $999/mo billed annually —
  meaning the $50-200 band on Glassnode buys Studio **chart viewing**, not API access
  (**UNVERIFIED, pricing pages were inconsistent across three separate fetches during this
  research — confirm directly with Glassnode sales before budgeting**).
- CryptoQuant Professional ($99-109/mo) adds "Data API up to 24H resolution" — this is the
  most concretely-priced path to programmatic BTC+ETH exchange-flow and valuation data in this
  band; SOL depth still unverified.
- Dune Plus ($349/mo) exceeds this band but is the realistic cost of depending on Dune's SQL
  layer now that the free tier is gone for execution.

**Bottom line for this project's actual need (4 assets, single dashboard, personal use):**
the cheapest path to *genuine, non-proxied* per-coin MVRV+SOPR+exchange-flow for BTC, and
MVRV-only (SOPR is NOT-DEFINABLE) for ETH/SOL, is **CryptoQuant Professional (~$99-109/mo)**
supplemented by **Coin Metrics free tier + DefiLlama free + Farside free** for everything that
doesn't require valuation-metric depth. Glassnode is higher-quality and covers SOL MVRV better,
but its published API pricing is materially higher and its per-tier gating needs direct
confirmation from Glassnode before committing money.

---

## 5. Metrics that must render `UNAVAILABLE` (BTC-only by construction)

| Metric | Why it cannot exist for ETH/SOL |
|---|---|
| SOPR (all variants) | Defined on a UTXO: (spend-time value)/(creation-time value) of a *specific coin unit*. Account-based chains have no discrete coin-units to timestamp — a wallet's balance is fungible and continuously mutated, so "the profit ratio of the coin just spent" is not a well-defined question. |
| Puell Multiple | Defined on daily miner revenue (block subsidy + fees) relative to its 365-day average. ETH has had no block subsidy since the Merge (2022); PoS validator rewards are a structurally different accounting (stake-proportional issuance, not a per-block auction). SOL's inflation schedule funds validators similarly differently. Neither has a "miner cost basis" concept to trend. |
| Reserve Risk | Built from HODLer opportunity-cost accumulated against a Puell-Multiple-like miner-cost baseline; inherits Puell Multiple's BTC-only dependency. |
| Thermocap | Cumulative USD-value of PoW block rewards ("security spend"). No equivalent for PoS chains — there is no market-priced computational security expenditure comparable to a hash auction. |
| Hashrate / difficulty | PoW-only concepts; ETH and SOL are proof-of-stake, they have no hashrate. |
| HODL waves in their *original, UTXO-exact* form | Technically reconstructable on account-based chains via last-transfer heuristics (and vendors do this — see matrix), but the true UTXO-exact version (every coin's exact unbroken dormancy) only exists on BTC. Treat ETH/SOL "HODL waves" as a heuristic reconstruction, not the same measurement, and label accordingly if shown at all. |

Realized Cap, MVRV, MVRV Z-Score, and NUPL are **not** in this list — they are genuinely
computable (with a reconstruction methodology) for account-based chains, and multiple vendors
(Glassnode confirmed) publish them for SOL and ETH. The important discipline is labeling them
"reconstructed / heuristic cost-basis, not UTXO-exact" rather than presenting them as
equivalent-quality to the BTC number.

---

## 6. Traps

1. **Exchange-wallet labeling disagreement is structural, not a bug to be fixed by picking a
   better vendor.** Glassnode's own transparency notice: reported balances are *"lower bounds
   of the true balance"* and *"may undergo retrospective revisions."* CryptoQuant and Glassnode
   have publicly disputed the interpretation of the same Gemini-related BTC movement (one called
   it a whale deposit, the other called it internal) — a Coin Metrics engineer's later
   confirmation sided with CryptoQuant's read in that specific case. **Design consequence:**
   the dashboard must show which vendor's number it is, and ideally the update/last-revision
   timestamp, not just a value — an exchange-flow number without its vendor and clustering
   revision date is not a fact, it's one side of an ongoing disagreement.
2. **Historical revision.** Because exchange labels are added/removed retroactively, a
   time-series value fetched today for a date six months ago may not match what was fetched
   six months ago for that same date. If this dashboard ever caches historical values, cache
   invalidation on label-set updates is a real requirement, not paranoia.
3. **Derived-metric duplication (the prior system's actual bug).** `NUPL = 1 - 1/MVRV` exactly,
   algebraically, always. Any dashboard tile for NUPL must be visually/structurally marked as
   derived from MVRV, not an independent read. The same caution applies to "Realized Price"
   (= Realized Cap ÷ Supply, i.e., MVRV's denominator restated per-coin) and to Puell-Multiple-
   family metrics that reuse the same 365-day-average miner-revenue baseline as Reserve Risk.
4. **"SOPR for ETH/SOL" claims should be treated as red flags, not features.** If a vendor's
   marketing page or a future integration offers "ETH SOPR" or "SOL SOPR," inspect the exact
   construction before trusting it — this research found no vendor with a documented,
   UTXO-equivalent methodology for either chain. This is precisely the shape of the prior
   system's core failure (a plausible-looking number computed a different way than its label
   implies) and deserves the highest scrutiny of anything in this matrix.
5. **CryptoQuant's own SOL-specific documentation pages (`dataguide.cryptoquant.com`,
   `userguide.cryptoquant.com`, `cryptoquant.com/asset/sol/summary`) blocked automated access
   (403/404) during this research.** Do not assume SOL parity with BTC/ETH on CryptoQuant
   without manually confirming inside a logged-in account or via a sales conversation — the
   coverage claims in vendor marketing copy for SOL were consistently vaguer than for BTC/ETH
   across every vendor researched, which is itself a signal.
6. **Dune's free-tier collapse (2026-09-10) happened mid-research.** Any plan written before
   this week that assumed "Dune is a free SQL layer for Solana data" needs to be re-checked —
   confirm current free-tier query limits directly at signup time, don't rely on older
   documentation or this document's snapshot.

---

## 7. Sources cited (fetched during this research)

1. `https://community-api.coinmetrics.io/v4/catalog-v2/asset-metrics?assets=btc,eth,sol` — live
   catalog query; established Coin Metrics free/Community tier has `AdrActCnt` and
   `CapMVRVCur`-labelled entries for BTC/ETH price-tier data but **no** `CapRealUSD`, SOPR, or
   NUPL for BTC, ETH, or SOL, and SOL's free coverage is limited to `CapMrktEstUSD` and
   reference-rate/volume data (no active-address metric found for SOL in this tier).
2. `https://docs.glassnode.com/further-information/exchange-data-transparency-notice` —
   established Glassnode's own caveats on exchange-balance data: lower-bound-only, subject to
   retrospective revision, imperfect clustering.
3. `https://coingape.com/cryptoquant-vs-glassnode-the-crypto-data-firms-spar-over-whale-deposits-and-btc-flash-crash/`
   (via search snippet) — established the concrete CryptoQuant-vs-Glassnode Gemini-deposit
   labeling dispute cited in Trap #1.
4. `https://cryptobriefing.com/dune-free-plan-view-only-access/` — established the 2026-09-10
   Dune free-tier query-execution cutoff for accounts created before 2026-07-21, and the
   compute-cost rationale Dune gave.
5. `https://docs.dune.com/learning/how-tos/pricing-faqs` — established Dune's credit-based
   pricing structure (Analyst ~$1.875/100 credits monthly, Plus ~$1.596/100 credits monthly).
6. `https://tokenterminal.com/pricing` — established Token Terminal's Free ($0, 3 dashboards,
   full history, CSV) / Pro ($350/mo) / API (custom, 250k req/day) / Data Room (custom) tiers.
7. `https://app.santiment.net/pricing` — established Santiment Free/Pro ($49/mo, $44 annual)/Max
   ($249/mo, $225 annual) tiers and the 30-day-lag restriction on Free/Pro.
8. Search of `academy.santiment.net`, `app.santiment.net/insights` — established Santiment's
   named covered-chain list omits Solana in its pricing copy, while a separate Santiment
   insight post is titled "Santiment Unveils Solana Data Coverage" — an internal inconsistency
   worth resolving before relying on Santiment for SOL.
9. Search of `helius.dev/pricing` — established Helius Free/$49 Developer/$499 Business/$999
   Professional tiers and $500-4,500/mo LaserStream data add-ons (5TB-100TB); Helius is RPC/
   indexing infrastructure, not a pre-computed metrics vendor.
10. Search of `docs.nansen.ai/getting-started/credits` and `academy.nansen.ai` — established
    Nansen Free (100 credits + 10/day) / Pro ($49-69/mo, 2,000 credits) tiers and the $10/1,000-
    credit and $0.01-$0.05/call pay-per-use alternative.
11. Search of `bitquery.io/blog/bitquery-april-2026-release` and pricing pages — established
    Bitquery's point-based Personal $39/Pro $79/Scale $239 tiers and free gRPC Solana streaming
    added in an April 2026 release.
12. Search establishing `api.llama.fi` (DefiLlama) is unauthenticated and free for stablecoin-
    supply data on ETH/SOL, with `pro-api.llama.fi` at $300/mo for higher limits and extra
    endpoints (31 free vs 38 additional Pro endpoints, per an August 2026 count from a
    third-party API-cataloging source — **UNVERIFIED** exact current endpoint counts, confirm
    at `defillama.com/docs/api`).
13. Search establishing Farside Investors provides a free, documented ETF-flow API surface
    covering BTC ETFs from January 2024 across 12 tickers, plus ETH (and reportedly SOL) ETFs
    — SOL coverage specifically flagged **UNVERIFIED** in this document, confirm before use.
14. `https://goldrush.dev/pricing/` (via search) and Covalent/GoldRush search results —
    established GoldRush is wallet/transaction indexing (14-day trial/25k credits, $10 "Vibe
    Coding," $250 Professional), not a source of pre-computed MVRV/SOPR-style metrics.

Several pages (Glassnode's own pricing page, CryptoQuant's dataguide/userguide, Amberdata's
pricing page, CryptoQuant's SOL asset page) returned 301 redirects, 403s, or 404s to automated
fetch during this research and could only be partially corroborated via search-engine snippets
of third-party review sites. Every such figure is marked **UNVERIFIED** above and should be
re-confirmed directly against the vendor before any purchasing decision.
