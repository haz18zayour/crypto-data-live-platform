# R1 — Derivatives & Market Microstructure Data Sources (BTC / ETH / SOL)

Research date: 2026-09-07. Track scope: funding rates, open interest, liquidations, long/short & taker ratios, options metrics, basis/term structure. Assets: BTC, ETH, SOL (the 4th pinned coin's coverage varies by vendor and is called out where it matters).

---

## 1. Executive summary — the 5 things that actually matter

1. **"Funding rate" is two different numbers and vendors blur them.** Every venue's REST market-data endpoint (Binance `premiumIndex`, OKX `funding-rate`, Bybit `tickers`) surfaces a *live/current* field that is easy to mistake for a forecast. In practice Binance's `lastFundingRate` in `/fapi/v1/premiumIndex` is the **last settled** rate, refreshed continuously as the premium index moves toward the next settlement — it is not a locked prediction, and it is not the same object as `/fapi/v1/fundingRate` (pure settlement history). Deribit's `get_funding_rate_history` is explicit about this and returns `interest_1h`/`interest_8h` — genuinely realized. **Never treat a "current funding rate" ticker field as a completed historical data point without checking each vendor's own definition.** This is the exact class of bug (a fetcher silently returning a plausible-looking wrong number) that broke the owner's previous system.

2. **Funding intervals are not uniform, and naive comparison/annualization is silently wrong.** Binance is fixed at 8h for BTC/ETH/SOL. OKX defaults to 8h but runs some instruments at 1h/2h/4h and auto-shortens to hourly when a rate hits its cap/floor, applying an "8/N" normalization factor to the raw per-period number. Bybit does the same dynamic-interval switching. **Annualizing by multiplying a per-period rate by 3 (assuming 8h × 3/day) will be wrong for any instrument currently in a shortened interval**, and comparing raw per-period rates across venues without normalizing by interval-length is the single most common funding-rate bug.

3. **"Liquidation data" is mostly modeled, not measured, and this is the single biggest vendor-exaggeration risk in this track.** Binance killed its real-time public liquidation stream years ago; `/fapi/v1/allForceOrders` (public) is deprecated/non-functional, and the websocket liquidation stream now pushes only a **1-order-per-second snapshot per symbol**, not the full liquidation flow. OKX's public liquidation-orders feed has historically been capped at a **7-day window** and, per its own docs, liquidations are **partially reported** (large-notional threshold, not every event). Coinglass's popular "Liquidation Heatmap" is explicitly described in its own materials as a **modeled estimate of clustered liquidation risk built from open-interest snapshots and assumed leverage distributions — not confirmed exchange liquidation-engine output**. Coinglass's separate "Aggregated Liquidation History" endpoint aggregates the (already-sampled) exchange-pushed liquidation events, which is closer to real but still inherits each exchange's undercount. **Treat all liquidation numbers as directional/estimated unless a vendor explicitly documents raw event capture, and label them as such in the UI — do not present a liquidation figure with the same confidence as a funding rate.**

4. **Coin-margined vs USDT-margined is a silent unit-mixing trap.** Binance runs entirely separate API trees (`fapi` = USDⓈ-M, `dapi` = COIN-M) with separate open-interest, funding, and long/short-ratio endpoints and different notional conventions (USD-value vs contract-count). OKX and Bybit unify this under `instType`/`category` (`linear` vs `inverse`) but the response units still differ (coin-denominated OI for inverse contracts). Aggregating "total open interest" across instrument types without converting to a common USD basis silently produces a meaningless number — this is a structurally identical failure mode to the funding-rate score bug described in this project's brief.

5. **Free official exchange APIs cover funding, OI, and long/short ratios for BTC/ETH/SOL adequately for a single-user dashboard at $0.** The paid layer (Coinglass $29–$699/mo, Laevitas $50–$500/mo, Velo/Kaiko/Amberdata/CoinAPI enterprise-quoted) buys **cross-exchange aggregation, longer history retention, and options analytics (skew/IV/DVOL context)** — none of which is strictly required if the dashboard fetches Binance + Bybit + OKX + Deribit directly per-asset and does its own aggregation/normalization. Given this owner's stated failure mode (silent wrong zeros from an unvalidated fetcher), a **smaller number of directly-owned, well-tested exchange fetchers beats a single black-box paid aggregator** for the "provenance and staleness" requirement of this dashboard — you cannot show "where the number came from" if the number came from an undocumented aggregator model.

---

## 2. Indicator-by-indicator source recommendation

| Indicator | Recommended primary source(s) | Why | Cost |
|---|---|---|---|
| Perpetual funding rate (current, per-exchange) | Binance `fapi`/`dapi`, Bybit v5 `market/tickers`, OKX v5 `public/funding-rate` | Official, free, no key required, real-time | $0 |
| Funding rate history (realized) | Binance `/fapi/v1/fundingRate`, Bybit `/v5/market/funding/history`, OKX `/public/funding-rate-history`, Deribit `/public/get_funding_rate_history` | All four are explicit "settled" history, not predicted | $0 |
| OI-weighted / cross-exchange aggregated funding | Coinglass `fundingRate/oi-weight-ohlc-history` or compute yourself from the 3 exchange feeds | Coinglass is convenient; self-computed is auditable | $0 (self) or $29+/mo |
| Open interest, per exchange (USD + coin-margined) | Binance `/fapi/v1/openInterest` (+ `/futures/data/openInterestHist`, 30-day cap), Bybit `/v5/market/open-interest`, OKX `/public/open-interest` | Official, free; must convert dapi coin-margined OI to USD yourself | $0 |
| Open interest, aggregated across exchanges | Coinglass `coins-markets` / `open-interest` endpoints, or self-aggregate the 3 feeds | Same reasoning as funding | $0 (self) or $29+/mo |
| Liquidations (aggregated, "best effort") | Coinglass `futures/liquidation/aggregated-history` (explicitly labeled aggregation of exchange-pushed events) — clearly UI-labeled as estimated | Nothing free gives a trustworthy aggregate; exchange-native feeds are individually incomplete (see traps) | $0 tier exists but rate-limited; realistically $29+/mo for usable interval granularity |
| Long/short account ratio, top-trader position ratio | Binance `/futures/data/globalLongShortAccountRatio`, `/futures/data/topLongShortPositionRatio` (30-day history cap), Bybit `/v5/market/long-short-ratio` | Official, free | $0 |
| Taker buy/sell volume | Binance `/futures/data/takerlongshortRatio` | Official, free | $0 |
| Options: 25-delta skew, IV, DVOL, put/call | Deribit REST (`get_historical_volatility`, options `ticker` `mark_iv`/greeks), Deribit DVOL index | Deribit is the dominant BTC/ETH options venue; free public REST | $0 |
| Options: SOL specifically | Deribit now lists SOL options with matching futures expiries (added liquidity infrastructure in 2026) — verify live open interest before relying on it; treat thin-liquidity strikes with caution | Confirmed added, but depth is materially thinner than BTC/ETH — UNVERIFIED whether SOL 25-delta skew is tradable-liquid enough to be meaningful | $0 |
| Basis / term structure (perp vs spot, quarterly annualized) | Compute from Binance/Deribit/OKX spot index + quarterly futures mark price yourself; Laevitas/Amberdata packages this pre-computed | Official pieces are free and simple to combine; paid vendors save the computation, not the raw access | $0 (self) or $50+/mo |

---

## 3. Full per-vendor comparison

### Binance Futures (fapi = USDⓈ-M, dapi = COIN-M)
- Funding rate current: `GET /fapi/v1/premiumIndex` → `lastFundingRate` (last **settled** rate per Binance's own field description), `nextFundingTime`; weight 1 per symbol, 10 for full list. No API key required.
- Funding rate history: `GET /fapi/v1/fundingRate` — realized rate, `startTime`/`endTime`/`limit` (max 1000, default 100/200). Shares a 500 req/5min weight bucket with `fundingInfo`.
- Funding caps/floors/interval: `GET /fapi/v1/fundingInfo` → `fundingIntervalHours`.
- Open interest (live): `GET /fapi/v1/openInterest`. History: `GET /futures/data/openInterestHist` — **capped at latest 30 days**, `period` in 5m–1d.
- Long/short ratios: `GET /futures/data/globalLongShortAccountRatio`, `GET /futures/data/topLongShortAccountRatio`, `GET /futures/data/topLongShortPositionRatio` — all **capped at latest 30 days**, `limit` default 30 / max 500.
- Taker buy/sell volume: `GET /futures/data/takerlongshortRatio`.
- Liquidations: `GET /fapi/v1/allForceOrders` (public) and `GET /dapi/v1/allForceOrders` are **deprecated / no longer maintained and stopped accepting requests**; the liquidation-order **websocket streams now push only the latest single order as a snapshot at most once per 1000ms per symbol**, i.e. not a complete real-time feed of every liquidation.
- API key: not required for any public market-data endpoint above.
- Coin-margined vs USDT-margined: entirely separate API trees (`fapi` vs `dapi`); `dapi` OI/volume figures are contract-count / coin-denominated, not USD — must be converted.
- Coverage: BTC, ETH, SOL all fully covered on both fapi and dapi.
- Cost: $0.
- Gotcha confirmed: `openInterestHist` and both long/short-ratio history endpoints share the same **30-day rolling window** limitation — a dashboard needing longer history must snapshot and store it yourself from day one.

### Bybit v5
- Funding rate current + OI: `GET /v5/market/tickers` (`category=linear|inverse`) → `fundingRate`, `nextFundingTime`, `fundingIntervalHour`, `openInterest`, `openInterestValue`.
- Funding rate history: `GET /v5/market/funding/history` — settled rates, `limit` max 200 per call, no documented hard historical-depth ceiling in the fetched page.
- Open interest history: `GET /v5/market/open-interest`.
- Long/short ratio: `GET /v5/market/long-short-ratio`.
- Funding interval: **per-symbol and dynamic** — Bybit runs a "Dynamic Settlement Frequency" system that switches a contract to hourly settlement when funding hits its cap/floor, then reverts to 2h/4h/8h afterward. Annualizing a Bybit rate by a fixed multiplier without checking `fundingIntervalHour` first will misstate APR.
- Liquidations: no confirmed public REST liquidation-history endpoint with meaningful depth was found in official v5 docs during this research; Bybit's public liquidation feed is websocket-based and, like Binance, is understood to be a filtered/rate-limited push rather than a full audit trail — **UNVERIFIED**, flag for direct doc re-check before building on it.
- API key: not required for the public market endpoints above.
- Coverage: BTC, ETH, SOL fully covered under `linear`.
- Cost: $0.

### OKX v5
- Funding rate current: `GET /api/v5/public/funding-rate`. History: a separate "funding-rate-history" endpoint exists (confirmed present in the docs nav; full parameter set not independently re-verified in this pass — treat field-level details as **UNVERIFIED** pending direct confirmation).
- Open interest: `GET /api/v5/public/open-interest`.
- Liquidation orders: `GET /api/v5/public/liquidation-orders` — per multiple independent sources this returns only the **last 7 days** and OKX's own reporting note states liquidations are **partially reported** across USDT/USDC/USD-margined instrument families (i.e. not every liquidation event is guaranteed present). Treat as directional, not a complete ledger.
- Funding interval: **default 8h (00:00/08:00/16:00 UTC) but varies per instrument (1h/2h/4h/8h)**, with an explicit "8/N interval factor" OKX applies to the funding formula so per-period rates aren't directly comparable across differently-scheduled instruments, and an automatic switch to hourly settlement when a rate hits its cap/floor.
- API key: public data endpoints do not require authentication.
- Coverage: BTC, ETH, SOL all covered under `SWAP` instType.
- Cost: $0.
- Rate limit: public data endpoints generally 20 req/2s (OKX-wide default for this class of endpoint).

### Deribit
- Funding rate history: `POST/GET public/get_funding_rate_history` — `instrument_name`, `start_timestamp`, `end_timestamp`; **explicitly documented as applicable only to PERPETUAL instruments**; returns `interest_1h` and `interest_8h` fields — this is a genuinely realized-rate endpoint, no ambiguity.
- Funding mechanics: Deribit expresses funding as an 8-hour-equivalent rate but **settles/transfers continuously (effectively every second/millisecond)**, not at discrete 8h boundaries like Binance — a different normalization trap from OKX/Bybit's discrete-interval switching, but a trap nonetheless if you assume "8h rate → apply once every 8h."
- Options: primary venue for BTC/ETH listed options (strikes, expiries, greeks, mark IV) via public market-data endpoints; DVOL index provides a VIX-style 30-day forward-looking implied-vol index per asset (`BTC`/`ETH`, and now with a documented but thinner build-out for other assets).
- SOL: Deribit has added **linear (USDC) SOL futures with matching expiries to every SOL option expiry**, improving settlement/liquidity infrastructure in 2026 — options exist and have exchange support, but actual traded open interest/liquidity depth for SOL strikes should be checked live before treating a SOL 25-delta skew number as meaningful (thin books produce noisy skew). **UNVERIFIED**: exact current SOL options open interest vs BTC/ETH.
- API key: public market-data (including funding history and options tickers) does not require authentication.
- Cost: $0.

### Coinglass
- Pricing (from `coinglass.com/pricing`, fetched directly): **Hobbyist $29/mo, Startup $79/mo, Standard $299/mo, Professional $699/mo, Enterprise custom.** Rate limits scale 30 → 80 → 300 → 1,200 requests/minute. Commercial use requires Standard ($299/mo) or above per the pricing page's own terms.
- Historical depth scales by tier: 1-minute granularity from 6 days (Hobbyist) up to 60 days (Professional); hourly from 180 days up to 720 days; daily is "all-time" on every paid tier.
- Funding: `fundingRate/oi-weight-ohlc-history` (OI-weighted, cross-exchange) and `fundingRate/exchange-list` (per-exchange comparison in one call) — genuinely useful convenience over hitting 3 exchanges yourself.
- Liquidations: two materially different products under one brand —
  - **Liquidation Heatmap**: per Coinglass's own description, a **model** that infers clustered liquidation price levels from open-interest snapshots and an assumed leverage distribution. This is **not measured data** — it is a forward-looking estimate and should never be presented with the same confidence as a funding rate.
  - **Aggregated Liquidation History** (`/api/futures/liquidation/aggregated-history`, base `open-api-v4.coinglass.com`): aggregates the liquidation *events* actually pushed by exchange feeds across the `exchange_list` you specify. This is closer to "real" but inherits each underlying exchange's own incompleteness (Binance's 1/sec snapshot cap, OKX's partial reporting, etc.) — Coinglass does not manufacture liquidation events here, but it cannot see what the exchanges themselves don't expose. Interval granularity is tier-gated (Hobbyist/Startup limited to 4h/30min minimum bucket; Standard+ unrestricted).
- SOL coverage: yes, covered across futures/funding/OI/liquidation and spot products.
- Gotcha: the free web dashboard and the paid API are separate products; scraping the free dashboard is against ToS and structurally fragile — budget for at least Hobbyist ($29/mo) if Coinglass is used at all.

### Amberdata
- Pricing: **not publicly published.** The pricing page (`amberdata.io/pricing`) routes both listed tiers ("Startup" and "Enterprise") to a sales quote form — no USD figures are disclosed anywhere in public materials found. Treat any specific price you hear informally as **UNVERIFIED**.
- Coverage: derivatives analytics (options, futures) delivered via REST, WebSocket, S3 bulk export, CSV, and Python SDK; separate free-signup "AD Derivatives" analytics platform exists alongside the paid raw-data API.
- Fit: institutional-grade and priced accordingly (informal market chatter places it well above $200/mo for meaningful derivatives access) — not a fit for a single-user personal dashboard budget without a quote in hand.

### Laevitas
- Pricing (from search of `laevitas.ch`): a **free tier** with limited history/charting; **Premium $50/mo** (full year of historical data, full toolkit — API access unclear at this tier, treat as **UNVERIFIED** whether API access is included vs dashboard-only); **Enterprise $500/mo** (API access, unlimited dashboards, priority support). A newer **x402 pay-per-request** option (USDC micropayments, no API key, no subscription) was also found — potentially attractive for a single-user, low-frequency personal dashboard since you'd pay only for the calls you actually make instead of a flat monthly fee.
- Coverage: options chains (live pricing/bid/offer/mark per strike/expiry), ATM implied vol, term structure, multi-expiry skew, benchmarked across venues; recently added Bullish exchange options data alongside existing venues.
- SOL: **UNVERIFIED** whether SOL options analytics specifically are covered with the same depth as BTC/ETH — Laevitas's marketing emphasizes BTC/ETH; confirm live before relying on it for the 4th/SOL slot.
- Fit: the $50/mo Premium tier (if it does include API/programmatic access — needs direct confirmation) or the pay-per-request x402 option are the two price points worth evaluating for this project's budget.

### Velo Data
- Pricing: **not disclosed in any fetched page.** `velodata.app/pricing` permanently redirects to the marketing homepage (`velo.xyz`) with no visible price list; documentation directs prospective users to request a trial via email. Treat Velo as **quote-only / UNVERIFIED pricing** for this research — do not budget against it without contacting them.
- Coverage: OHLC, funding rates, historical open interest, cross-venue aggregation via a TypeScript SDK; used by trading firms/hedge funds per their own positioning — signals institutional pricing, not a casual personal-dashboard tier.

### CoinAPI
- Pricing page (`coinapi.io/pricing` and the Market Data API sub-page) returned **HTTP 403 to automated fetch** both directly and via the product-specific pricing page — could not independently verify current tier prices from the primary source in this session. Secondary/aggregated sources (third-party pricing trackers) suggest a **Business plan at roughly $599/mo** for ~100,000 requests/day and lower unnamed tiers around $79+/mo, but **these figures are UNVERIFIED against CoinAPI's own current pricing page** and should be re-confirmed by hand before any purchase decision.
- Coverage: CoinAPI's core product is spot/exchange-rate market data; derivatives-specific coverage (funding, OI) is not its primary strength compared to Coinglass/Amberdata/Kaiko — likely a poor fit for this specific track regardless of price.

### Kaiko
- Pricing: **not publicly disclosed.** Kaiko's own site and docs describe a "Derivatives Metrics" product (derivatives prices, raw trades, trade aggregations, liquidation events) but all pricing requires direct sales contact. Kaiko is positioned as institutional-grade (reference rates used in regulated financial products, e.g. the S&P Kaiko Digital Asset Indices partnership) — pricing is very unlikely to fit a personal single-user budget. **UNVERIFIED**, treat as out of budget by default.

---

## 4. Budget recommendation — what each tier genuinely buys for derivatives

- **$0/month.** Fully sufficient for the dashboard's core requirement. Binance (fapi + dapi) + Bybit v5 + OKX v5 together give funding (current + realized history), open interest (USD and coin-margined, convert dapi yourself), long/short account and top-trader ratios, and taker buy/sell volume for BTC/ETH/SOL with no API key. Deribit adds free options (IV, DVOL, skew) for BTC/ETH and now nominally SOL. The only real gaps at $0 are: (a) a trustworthy cross-exchange *aggregated* liquidation number — none of the free venues gives you more than their own partial/sampled feed, so at $0 your liquidation indicator should honestly be labeled "Binance-observed liquidations (partial, sampled)" rather than "aggregated liquidations"; (b) pre-computed OI-weighted funding/basis across venues, which is straightforward but non-trivial arithmetic you'd own yourself; (c) >30 days of OI/long-short-ratio history unless you start storing snapshots from day one.

- **Under $50/month.** Coinglass Hobbyist ($29/mo) closes the biggest $0 gap: a cross-exchange aggregated liquidation-history endpoint (still model/estimate-flavored for the heatmap product, but the aggregated-history endpoint is a real improvement over any single exchange's own feed) plus OI-weighted funding and multi-exchange OI in one call, with 6 days of 1-minute and 180 days of hourly history. This is the single best dollar-for-dollar upgrade for this track. Laevitas's $50/mo Premium tier is the alternate use of this budget if options analytics (term structure, skew across venues) matter more to you than liquidation aggregation than perpetuals — but confirm its API access scope before committing, since that detail was not clearly documented in what could be verified.

- **$50–200/month.** Buys Coinglass Startup ($79/mo, more endpoints/rate limit) or stacking Coinglass Hobbyist + Laevitas Premium together (~$79/mo combined) to get both liquidation aggregation and cross-venue options analytics. It does **not** buy access to Amberdata, Velo, or Kaiko — all three are quote-gated and, based on their institutional positioning and the informal pricing signals found, are very unlikely to clear a $200/mo ceiling. CoinAPI's unverified ~$599/mo figure also exceeds this band and its core strength isn't derivatives anyway. **Recommendation: for this project's stated single-user, provenance-first use case, there is no compelling reason to spend above ~$79–129/mo on this track** — the marginal data quality gain from the enterprise-tier vendors is aimed at trading desks needing sub-second tick data and audit-grade SLAs, not a personal dashboard that needs to honestly label "last updated" and "stale."

---

## 5. Traps — the specific ways this data is silently wrong

- **Predicted vs. realized funding conflated.** Any ticker-style field showing "current funding rate" (Binance `premiumIndex.lastFundingRate`, OKX/Bybit ticker `fundingRate`) reflects the state of an in-progress premium calculation that settles at `nextFundingTime` — it is continuously recalculated (Binance recomputes its premium index every ~5 seconds) right up to settlement. Only the dedicated *history* endpoints (`fundingRate` on Binance, `funding/history` on Bybit, `funding-rate-history` on OKX, `get_funding_rate_history` on Deribit) are unambiguously realized values. **A fetcher that reads the ticker field and stores it as "today's funding rate" is storing a moving target, not a fact** — this is structurally the same class of silent bug that produced this project's original zeroed-out funding/OI/long-short indicators: a value that looks plausible but isn't the thing you think it is.

- **Interval mismatch breaks both comparison and annualization.** Binance is fixed 8h for BTC/ETH/SOL. OKX and Bybit both run dynamic per-instrument intervals (1h/2h/4h/8h) that auto-shorten when a rate hits its cap/floor. Multiplying a raw per-period rate by a fixed "periods per day" constant to annualize, or comparing a Binance 8h-rate directly against an OKX 1h-rate during a volatility spike, produces numbers that are wrong by exactly the interval ratio (e.g. 8x) — with no error, no warning, just a quietly wrong APR.

- **Coin-margined vs USDT-margined unit mixing.** Binance's `dapi` (COIN-M) OI and volume figures are denominated in contracts/coins, not USD; `fapi` (USDT-M) figures are USD-notional. OKX/Bybit unify the endpoint surface (`linear`/`inverse` under one path) but the *units in the response* still differ by instrument type. Summing OI across instrument types without converting to a common USD basis first yields a number that looks like "aggregate open interest" but is actually a meaningless mix of dollars and coins.

- **Liquidation data is largely modeled or sampled, not measured, and is the highest-risk indicator in this entire track for silent misrepresentation.** Binance's real-time public liquidation stream was restricted years ago and now pushes at most a 1-order/second snapshot — most liquidation events on Binance are simply never visible on the public feed. OKX's liquidation-orders endpoint is capped at a 7-day window and is documented as "partially reported." Coinglass's widely-cited Liquidation Heatmap is explicitly a model (inferred leverage distribution applied to OI snapshots), not a record of actual forced closures — presenting it as "$X liquidated in the last hour" without qualification misrepresents what the number is. **This dashboard's entire premise is provenance; the liquidation tile is the one place a naive implementation is most likely to silently lie about data quality — it must be labeled as estimated/partial by construction, not as an afterthought.**

- **Aggregator "coverage" claims for SOL and options are thinner than the marketing suggests.** Multiple vendors (Laevitas, Amberdata) foreground BTC/ETH in their options materials; SOL options liquidity, even on Deribit (the most credible venue), is materially thinner than BTC/ETH, so a computed 25-delta skew for SOL can be noisy/meaningless if built from a handful of illiquid strikes. Check live open interest per strike before trusting a SOL options-derived number, and prefer showing "UNAVAILABLE — insufficient options liquidity" over a noisy number that looks authoritative.

- **Historical-depth ceilings are silent and asset-agnostic.** Binance's `openInterestHist` and both long/short-ratio history endpoints cap at 30 days regardless of asset — a dashboard that assumes it can backfill 90 days of OI history from Binance directly will silently get truncated results with no error, just a shorter-than-expected array.

---

## 6. Sources cited (fetched directly during this research)

- https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History — confirmed `/fapi/v1/fundingRate` is realized/settled history, params, 1000-record max, no API key required.
- https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Mark-Price — confirmed `/fapi/v1/premiumIndex` fields (`lastFundingRate`, `nextFundingTime`, `estimatedSettlePrice`) and IP-weight (1 vs 10).
- https://bybit-exchange.github.io/docs/v5/market/history-fund-rate — confirmed `/v5/market/funding/history` path, params, 200-record page limit, realized-rate semantics.
- https://bybit-exchange.github.io/docs/v5/market/tickers — confirmed `/v5/market/tickers` funding and open-interest fields and links to dedicated history/long-short-ratio endpoints.
- https://docs.deribit.com/api-reference/market-data/public-get_funding_rate_history — confirmed method name, required params, `interest_1h`/`interest_8h` response fields, PERPETUAL-only scope.
- https://docs.coinglass.com/reference/aggregated-liquidation-history — confirmed endpoint path (`/api/futures/liquidation/aggregated-history`, base `open-api-v4.coinglass.com`), that it aggregates exchange-pushed liquidation events rather than being purely synthetic, and tier-gated interval granularity.
- https://www.coinglass.com/pricing — confirmed exact tier prices: Hobbyist $29/mo, Startup $79/mo, Standard $299/mo, Professional $699/mo, Enterprise custom; rate limits 30/80/300/1,200 req/min; commercial-use gating at Standard+; historical-depth-by-tier table (1m: 6–60 days, 1h: 180–720 days, daily: all-time).
- https://www.amberdata.io/pricing — confirmed no public prices exist; both listed tiers route to a sales quote form.
- https://www.coinapi.io/products/market-data-api/pricing — attempted fetch returned HTTP 403; pricing could not be independently verified from the primary source (noted as UNVERIFIED in report).
- https://velodata.app/pricing — confirmed this URL 301-redirects to the marketing homepage with no visible price list (pricing UNVERIFIED / quote-only).

Additional detail (funding-interval variability on OKX/Bybit, Binance liquidation-stream restriction wording, Binance 30-day history caps, OKX 7-day liquidation window, Coinglass liquidation-heatmap methodology) was cross-checked via targeted web search of vendor help-center articles and API docs pages rather than a single direct fetch each; those specific claims are flagged inline above and should be spot-verified against the live docs before being hard-coded into a fetcher, per this project's "no confident wrong numbers" mandate.
