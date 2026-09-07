# R3 — OHLCV Sourcing & Indicator Computation Correctness

Research date: 2026-09-07. Track: OHLCV/price sourcing, indicator libraries, indicator correctness, verification strategies, for a 4-asset (BTC, ETH, SOL + 1 pinned) single-user observability dashboard where **provable correctness beats breadth**.

---

## 1. Executive Summary

- **Single venue is NOT adequate.** Binance — the deepest, cheapest, most complete public OHLCV source — returns **HTTP 451 to US and several other jurisdictions** on its public REST API (`api.binance.com`), a restriction that applies to the IP address making the request, not to whether a key is used. This is a hard, non-negotiable failure mode for anything hosted on US-region cloud infrastructure or a Cloudflare Worker resolving through US edge nodes. **Recommendation: Coinbase Exchange (or Kraken) as primary spot source for BTC/ETH/SOL, with Binance as a secondary/cross-check source run from a non-restricted region if available, and CoinGecko as a fallback aggregator.** For the single pinned "4th coin," CoinGecko is the pragmatic default since it may not trade on all venues.
- **Every exchange's most recent kline is unclosed/partial** and none of Binance, Kraken, or Bybit expose a boolean "is this candle closed" field in the plain REST kline array — you must infer it by comparing the candle's open/close time to wall-clock time, or (Binance) drop any row whose `closeTime` is in the future, or (Kraken) drop the documented always-present final "not-yet-committed" row, or (Bybit) infer from `closePrice` semantics ("is the last traded price when the candle is not closed"). **OKX is the one exception**: its kline array includes an explicit `confirm` field (0 = unconfirmed, 1 = confirmed) — this is the single cleanest signal among the five venues and a strong argument for using OKX as at least a cross-check source. Consuming the last row without this check silently corrupts every indicator built on it — this is very likely the root cause class behind the prior system's "grows forever from a 500-bar seed" bug class, generalized to "computed on an incomplete last bar."
- **pandas-ta (the original, twopirllc) is functionally abandoned** — the maintainer has stated it will be archived unless funded, PyPI's last real release predates 2026, and the GitHub repo has had ownership/hosting churn (forks scrambling to preserve it). The maintained continuation is **pandas-ta-classic** (PyPI, v0.6.52, released June 24 2026, Python ≥3.10, 193 native indicators + 62 candlestick patterns, no TA-Lib dependency required). This is the concrete, current answer to "what's actually maintained today."
- **RSI, EMA, ATR, StochRSI, and Bollinger Bands all have silently-divergent "correct" implementations** that differ not by bugs but by *which textbook definition* a library author picked. The single highest-value engineering control identified: pin every indicator's smoothing method (Wilder vs SMA vs EMA), stdev convention (population vs sample — **numpy defaults to population `ddof=0`, pandas defaults to sample `ddof=1`, and John Bollinger's own definition is population**), and warm-up bar count explicitly in code and tests, rather than trusting a library default.
- **Verification is tractable and cheap**: TA-Lib's own C test suite and the Wikipedia/StockCharts worked examples serve as free, citable reference vectors; cross-checking a handful of points against TradingView's displayed values catches smoothing-method mismatches; golden-file regression tests plus Hypothesis-style property tests (monotonic timestamps, OHLC internal consistency, output bounded ranges) catch the rest.

---

## 2. Part A — OHLCV Source Comparison & Recommendation

### 2.1 Per-source comparison

| Source | Key required | Rate limit (public/free) | Historical depth | Granularities | Paid tier (USD/mo, 2026) |
|---|---|---|---|---|---|
| **Binance** (`api.binance.com`) | No (public market data) | 2400 weight/min per IP; klines cost 2 weight ≈ ~1000 calls/min effective | Full history from listing, paginated via `startTime`/`endTime`, 500 default / 1000 max rows per call | 1s,1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,3d,1w,1M | Free (no paid tier for public market data) |
| **Binance.US** | No | Similar structure, separate domain `api.binance.us` | Shallower listing history than global Binance | Same set as global, fewer pairs | Free |
| **Coinbase Exchange** (`api.exchange.coinbase.com`) | No for public candles | 10 req/s (public), max 300 candles/request | Full history from listing | 60s,300s,900s,3600s,21600s,86400s (1m/5m/15m/1h/6h/1d) — **no native 4h** | Free (Advanced Trade / Exchange API has no paid data tier; Coinbase does not sell historical data separately) |
| **Kraken** | No | ~1 req/sec sustained for Trades/OHLC before throttling | **Only 720 most recent bars per interval** via REST — no deep history endpoint | 1,5,15,30,60,240,1440,10080,21600 (minutes) | Free; deeper history requires their separate historical data product/CSV downloads |
| **OKX** | No for market data | 20 req/2s typical; live candles limit 300, **history-candles limit 100** per call | History-candles endpoint goes back further via pagination | 1m…1M incl. UTC-aligned variants (e.g. `1Dutc`) | Free |
| **Bybit** | No for public v5 kline | 600 req/5s per IP shared across public endpoints | Max 1000 rows/request; historical depth not documented, generally deep for major pairs | 1,3,5,15,30,60,120,240,360,720 (min), D, W, M | Free |
| **CoinGecko** | Free tier: no key (Demo); paid: key required | Demo 100 calls/min, 10k credits/mo | OHLC: Demo/Basic = 1 day window only; **Analyst/Lite+ = from 2021, down to 1-minute/1-second granularity** | Coin-level OHLC + onchain OHLCV | **Basic $35/mo (300 calls/min, 100k credits) · Analyst $129/mo (500 calls/min, 500k credits) · Lite $499/mo (500 calls/min, 2M credits)** — 20% off on annual billing. [coingecko.com/en/api/pricing] |
| **CoinAPI** | Key required, all tiers | Credit-metered (Usage Credits, 1 UC ≈ $1 pay-as-you-go) | Deep multi-exchange OHLCV, daily bars billed per bar-day | Sub-second to 1M | **Startup $79/mo (1,000 REST credits/day) · Streamer $249/mo (10,000 REST credits/day) · Pro $599/mo**; PAYG with $25 free credit | 
| **Kaiko** | Key required | Enterprise, sales-gated | Deep CEX history back to 2010-2014 depending on venue | 1m, 1h, 1d standard; custom on request | **UNVERIFIED** — no public pricing; sales-only enterprise model |
| **Amberdata** | Key required | Sales-gated for most tiers; some self-serve "purchase online" market data | Institutional-grade, multi-venue | 1m, 1h, 1d standard | **UNVERIFIED** — no public self-serve price list found; has a "buy market data online" self-serve product but tier prices not published |
| **CryptoCompare / CCData (now CoinDesk Data)** | Key required | Free tier **retired May 2026** per search findings | Daily/hourly/minute OHLCV historically offered | 1m,1h,1d historically | **All plans now sales-only** since CoinDesk's Feb 2025 rebrand to "CoinDesk Data" — self-serve pricing page removed. Treat as UNVERIFIED for exact 2026 numbers. |
| **Polygon.io (rebranded "Massive" in 2025/26)** | Key required | Free/Basic: 5 calls/min, EOD + 15-min-delayed data | Custom aggregate bars (multiplier + timespan) over date range, UTC | Configurable multiplier/timespan bars | Pricing is **per asset class** (crypto priced separately from stocks); published stocks ladder is Basic $0 / Starter $29 / Developer $79 / Advanced $199 — **crypto-specific tier prices were not confirmed on massive.com/pricing (page only showed stocks tiers at fetch time) — UNVERIFIED for crypto** |
| **Tiingo** | Key required | Free "Starter" tier exists | Crypto REST + WebSocket, multi-exchange aggregated | Standard OHLCV | **Starter $0/mo · Power $30/mo**; exact crypto history depth/granularity per tier not itemized on the pricing page — UNVERIFIED detail beyond the two price points |

### 2.2 The Binance geo-restriction gotcha — concrete findings

- Since **late November 2022**, Binance's public read-only REST endpoints return **HTTP 451 "Unavailable For Legal Reasons"** for requests originating from restricted locations, explicitly including **the United States, Malaysia, and Ontario (Canada)**, "and such other locations as designated by Binance Operators." Source: ccxt issue tracker cross-referencing Binance's own terms (`binance.com/en/terms` §b Eligibility).
- This block is **enforced by the requesting IP's geolocation**, not by account/API-key region. Practically this means:
  - **A Cloudflare Worker is affected** if it executes in or routes through a restricted region's edge PoP — Cloudflare Workers execute at the edge location closest to the incoming request by default, so a Worker serving US-based dashboard traffic will very likely make its outbound `fetch()` to Binance from a US PoP and get 451'd. This is confirmed repeatedly in developer forum threads (PythonAnywhere, Google Cloud, Bubble) reporting 451s specifically from US-hosted compute.
  - A cloud VM in `us-east-1`/similar will be blocked; a VM in most EU/APAC regions (outside Malaysia) will generally work — but this is IP-geolocation dependent and can change without notice, so it is not a stable architectural foundation for a project that needs reliability.
  - **Binance.US** is a legally separate entity/API with a smaller pair/history footprint — usable as a partial substitute for US-based compute, but with reduced historical depth and different market microstructure (its own order book, not global Binance's).
  - **Practical implication for this project**: if your Worker or VM is US-hosted (or Cloudflare-Worker-edge, effectively unpredictable region), **do not depend on Binance as your only or primary source.** Coinbase, Kraken, and OKX have no equivalent public US-IP block on read-only market data.

### 2.3 Candle close-time vs open-time, and the "is this candle final" problem — per venue

| Venue | Timestamp field semantics | Explicit "closed" flag on REST? | How to detect an unclosed/partial last candle |
|---|---|---|---|
| Binance | Returns both `openTime` (index 0) and `closeTime` (index 6) per kline | **No** — no boolean field | Compare `closeTime` to current wall-clock time; if `closeTime > now`, the bar is still forming. (WebSocket kline stream does carry an `"x"` boolean "is this kline closed" field — REST does not.) |
| Kraken | Single `time` = candle **open** time (Unix seconds) | **No**, but documented behavior: *"The last entry in the OHLC array is for the current, not-yet-committed timeframe, and will always be present, regardless of the value of `since`."* | Always discard the last row, or compare `time + interval` to now |
| OKX | `ts` = candle open time | **Yes** — response tuple `[ts,o,h,l,c,vol,volUsd,confirm]`, `confirm` is documented to indicate whether the K-line is completed (search snippets consistently describe it as a completion flag; exact 0/1 semantics could not be confirmed from the JS-rendered doc page in this session — treat the 0/1 mapping as **UNVERIFIED**, but the field's existence and purpose are corroborated by multiple independent sources) | Filter on `confirm` directly — no wall-clock comparison needed. This is the cleanest of the five venues. |
| Bybit | `startTime` = candle open time, milliseconds | **No** | Documentation states `closePrice` "is the last traded price when the candle is not closed" — i.e., you must infer forming-status by comparing `startTime + interval` to now; no dedicated flag |
| Coinbase Exchange | Candle bucket start time | **No** | Same wall-clock comparison approach; Coinbase docs explicitly warn not to poll historical rates frequently and to use trade/book + WebSocket feed for anything real-time-sensitive |

**Conclusion on this gotcha**: across 5 major venues, only OKX gives you a first-class signal. Everywhere else, the safe rule is: **always drop or explicitly mark the most recent row as "provisional" based on a wall-clock comparison against the bar's own close time, before it enters any indicator computation.** This is exactly the class of bug the product brief describes ("plausible-looking values computed from mis-aligned, stale or insufficient data").

### 2.4 Volume comparability across exchanges

- Binance kline volume fields distinguish **base asset volume** (e.g., BTC) from **quote asset volume** (e.g., USDT), plus **taker-buy base/quote volume** subsets. Other venues report volume in whichever asset (base, sometimes only base) their API defaults to.
- Because "volume" is not a standardized unit across exchanges (base-asset units differ in economic meaning from quote-asset/USD-notional units, and taker-vs-maker attribution differs), **OBV and any volume-weighted indicator computed by summing volume across exchanges, or comparing OBV slope across exchanges, is not meaningful without normalizing to a common quote-currency notional value first.** Cross-exchange volume aggregation (e.g., "total BTC volume across Binance+Coinbase+Kraken") requires converting each venue's volume to the same currency and being explicit about whether spot vs perpetual futures volume is being mixed — perp volume is typically far larger than spot and reflects different participants/leverage dynamics.

### 2.5 Spot vs perpetual price series

Spot and perpetual futures order books are economically linked by funding-rate arbitrage but are **not the same price series** — perps trade at a basis to spot (funding-driven), and during volatile periods this basis can be persistent and non-trivial. All venue recommendations above (Binance/Coinbase/Kraken/OKX/Bybit spot klines) refer to **spot** market data; do not substitute a perp kline feed (e.g., Binance Futures `fapi.binance.com`) for spot price display without labeling it as such — mixing them silently is another way to produce "plausible but wrong" numbers.

### 2.6 UTC alignment for daily candles and downtime gaps

- Daily candle boundaries are venue-defined; most major venues (Binance, OKX explicit `1Dutc` variant, Coinbase) align daily bars to **00:00 UTC**, but always verify per-venue rather than assume — OKX exposing an explicit UTC-suffixed interval implies its default daily bar may *not* be UTC-aligned by default, which is itself a documented gotcha.
- Exchange downtime (maintenance windows, outages) produces **gaps in the kline sequence** — a naive consumer that assumes contiguous timestamps (e.g., `bar[i+1].time == bar[i].time + interval`) will silently mis-align data after a gap. Any ingestion pipeline must explicitly check timestamp deltas rather than assume contiguity.

### 2.7 Recommendation

For a 4-asset personal observability dashboard:
1. **Primary spot source: Coinbase Exchange** (or Kraken) for BTC/ETH/SOL — no geo-block risk, simple REST, adequate rate limits for a single-user dashboard polling every few minutes.
2. **Cross-check source: OKX** — its explicit `confirm` field makes it the best secondary source specifically for validating "is my primary source's last bar actually closed," and is not geo-blocked.
3. **Do not rely on Binance as the sole/primary source** given the geo-restriction risk on Worker/VM hosting; it's fine as a *tertiary* cross-check if your compute happens to run from an unrestricted region, but do not architect around it.
4. **Aggregator (CoinGecko) for the pinned 4th coin** if it isn't reliably listed with deep history on the above venues, and as a fallback for BTC/ETH/SOL if all direct venues are unreachable.
5. **Cross-venue aggregation is not "genuinely needed" for correctness of a single coherent price series** — pick one authoritative venue per asset and stick to it, since mixing venues' closes into one series introduces exactly the kind of silent inconsistency this project exists to eliminate. Cross-venue checking is valuable **only as a staleness/sanity cross-check**, displayed as a secondary "source B says X" data point with its own timestamp — never blended into a single computed value.

---

## 3. Part B — Indicator Library Comparison (2026 status)

| Library | Language | Maintenance status (2026) | Last release | Coverage | Dependency weight | License | Known issues |
|---|---|---|---|---|---|---|---|
| **pandas-ta** (twopirllc) | Python | **Effectively abandoned.** Maintainer publicly stated it will be archived without funding; PyPI's newest listing (`0.4.71b0`, Sep 2025) is a pre-release marked "may not be suitable for production." GitHub repo has suffered ownership/visibility churn, prompting community forks. | ~Sep 2025 (pre-release) | 150+ indicators, 60 candle patterns (needs TA-Lib installed for those) | Pandas + numpy + numba | MIT | Long-standing correctness bug reports (e.g., issue threads about off-by-one warm-up lengths); inconsistent smoothing defaults across indicators |
| **pandas-ta-classic** | Python | **This is the maintained option today.** Active community fork, comprehensive test coverage incl. property-based tests (Hypothesis) | **v0.6.52, released 2026-06-24** | 193 native indicators + 62 candlestick patterns, no TA-Lib required for core | Pandas only (no numba requirement per package description) | MIT (inherits) | New enough that long-term track record is thin — **use it, but golden-test every indicator you rely on (see Part D)** |
| **TA-Lib** (C lib) + `ta-lib-python` | C + Python wrapper | Actively maintained; ownership moved to a `TA-Lib` GitHub org | v0.6.x wrapper; **as of v0.6.5, official prebuilt binary wheels ship for Windows (x86_64, x86, arm64), macOS, Linux** — MSI installer available for the underlying C library (`ta-lib-0.7.1-windows-x86_64.msi`) | 150+ functions, industry-standard reference implementation | C library must be present at build/runtime (now solved by wheels/MSI) | BSD-style | Historically the single hardest Windows install in the Python TA ecosystem — **this is now resolved** for common platforms; still requires the correct wheel/MSI matching Python version and architecture |
| **`ta`** (bukosabino) | Python, pandas/numpy only | Actively maintained — commit as recent as **April 2026** confirmed, 97.76% test coverage | Rolling | Broad common-indicator coverage, pure pandas (no TA-Lib) | Pandas + numpy only | BSD-3 | Good for a no-C-dependency pure-Python stack |
| **finta** | Python, pandas | ~2.2k GitHub stars; lower recent-activity signal than `ta`/pandas-ta-classic | UNVERIFIED exact last-release date this session | Common indicators via pandas | Pandas only | LGPL | Smaller community, verify indicator-by-indicator before trusting |
| **tulipy** (Python bindings to Tulip Indicators C lib) | Python + C | **Inactive** — repo created ~4 yrs ago, last code push ~6 yrs ago per package registries | v0.4.0 | 100+ indicators via C bindings (fast) | Requires compiled Tulip C library | LGPL | Effectively unmaintained; fine for a frozen, well-tested C core but don't expect fixes |
| **polars-ta** | Python, Polars-native | **New and active** — release dated Jan 27, 2026 | 2026-01-27 | Growing; targets Polars DataFrame users | Polars (no pandas) | UNVERIFIED | Too new for a deep correctness track record; verify heavily if adopted |
| **technicalindicators** (npm) | TypeScript/JS | **Discontinued** — "hasn't seen any new versions released to npm in the past 12 months," last publish of v3.1.0 was ~6 years ago | v3.1.0 | Broad common-indicator coverage | Zero heavy deps | MIT | A drop-in fork, `fast-technical-indicators`, claims 100% API compatibility with performance improvements — worth evaluating if staying in the JS/TS ecosystem for Worker-side computation |
| **tulind** (npm, Node bindings to Tulip Indicators) | Node native addon | **Inactive** — last publish (`0.8.20`) ~5 years ago, ~2,174 weekly downloads | v0.8.20 | 100+ indicators | Native compiled addon (build complexity on Workers — not viable in Cloudflare Workers' V8 isolate sandbox, which cannot run native addons) | Apache-2.0 | Not usable inside a Cloudflare Worker due to native-addon requirement regardless of maintenance status |
| **indicatorts** | TypeScript | **Discontinued** — no new npm versions in past 12 months, ~5,976 weekly downloads, v2.2.2 last published ~1 year ago | v2.2.2 | Moderate common-indicator set, pure TS (Worker-compatible) | Pure TS, no native deps | UNVERIFIED license | Pure-TS (Worker-safe) but stalled; audit correctness before trusting for anything beyond simple SMA/EMA |

**Recommendation for this project**: given the stated priority ("correctness and provability over breadth"), do **not** default to any library's out-of-the-box behavior. Two viable paths:
1. **pandas-ta-classic** (Python backend) if computation happens server-side — actively maintained, but golden-test each indicator against TA-Lib/StockCharts reference values (Part D) before trusting it, since it's young.
2. **Hand-roll the handful of indicators actually needed** (RSI, EMA/MACD, ATR, Bollinger, StochRSI, OBV) with explicit, documented, single-sourced formulas (~200-400 lines total) rather than depending on a library whose defaults silently differ from what you assume — this directly eliminates the "which variant did the library pick" class of bug. Given only 4 assets and a handful of indicators, hand-rolling with golden-file tests is very plausibly the *simpler and more provably-correct* choice versus auditing an entire library's source for edge cases.

If computation must happen in a Cloudflare Worker (no native addons, no C bindings), the library options are the pure-JS/TS ones only (`technicalindicators`/its fork, `indicatorts`) — neither is actively maintained, reinforcing the hand-roll recommendation for a Worker-based architecture.

---

## 4. Part C — Indicator Correctness Reference

For every indicator below: canonical definition, common wrong/divergent variants actually shipped by real libraries, and minimum warm-up bars.

### 4.1 RSI (Relative Strength Index)

- **Canonical (Wilder's original, 1978)**: average gain/loss smoothed with **Wilder's smoothing**, α = 1/N (for N=14, α ≈ 0.0714). First average gain/loss = simple mean of the first N periods' gains/losses; subsequent values: `avg = prev_avg + α × (current − prev_avg)`, equivalent to `avg = (prev_avg × (N−1) + current) / N`. RSI = `100 − 100/(1+RS)`, RS = avgGain/avgLoss.
- **Wrong/divergent variants seen in the wild**: some libraries (notably pandas-based notebooks and some pandas-ta configurations) default to **EMA smoothing** (α = 2/(N+1) ≈ 0.133 for N=14) instead of Wilder's α=1/N, or even a naive **simple moving average** of gains/losses recomputed from scratch each bar (no memory of prior average).
- **Concrete magnitude of the difference** (worked example from a single bar update, avg gain 1.40, avg loss 0.60, new gain of 2.00): SMA-style recompute → new avg ≈ 1.49; EMA (α≈0.133) → new avg ≈ 1.48; Wilder (α≈0.071) → new avg ≈ 1.44. Over a sustained directional move, these compound: **Wilder vs EMA RSI values can diverge by 5–10 points** on the 0-100 scale during fast trending moves — enough to flip an "overbought (>70)" read to "neutral."
- **What TradingView/Binance/OKX/KuCoin/MetaTrader/TA-Lib all use**: **Wilder's smoothing**, by default. TA-Lib's RSI is explicitly documented as matching Wilder RMA / TradingView `ta.rsi`.
- **Warm-up**: minimum 14 bars to produce a first value (N+1 including the seed bar per a known TA-Lib issue — "RSI requires 1 more value than the timeperiod specifies"), but the Wilder-smoothed average only *converges* toward its steady-state weighting after several multiples of N — treat the first ~3-5×N (≈ 50-70 bars for RSI-14) as "displayable but flagged as still-warming," not fully converged.

### 4.2 EMA seeding and warm-up

- **Canonical seeding**: first EMA value = **SMA of the first N bars** (standard convention used by MACD's signal line construction and most reference implementations), then `EMA_t = price_t × k + EMA_{t-1} × (1-k)`, k = 2/(N+1).
- **Wrong/divergent variant**: seeding the very first EMA value with just the **first raw price** rather than an N-bar SMA. This produces a materially different early trajectory — the SMA-seeded version starts already "smoothed," the first-value-seeded version has to grow into the smoothing from a single noisy observation, and the two series don't converge until enough bars have passed for the seed's influence to decay.
- **Quantifying convergence**: because EMA weighting decays geometrically, the seed's residual influence after n bars is `(1-k)^n`. For a rule-of-thumb "seed influence below 1%" threshold, you need `(1-k)^n < 0.01` → `n > ln(0.01)/ln(1-k)`. For EMA-200 (k = 2/201 ≈ 0.00995), this requires **n ≈ 460 bars** before the seed choice stops mattering at the 1% level — i.e., **you need roughly 2.3× the period in bars** before an EMA-200 is trustworthy regardless of seeding method (general guidance found: "expect the EMA to stabilize after several hundred bars; early EMA values can be biased by the seed method" — consistent with this derivation). For EMA-9 (MACD signal line), the same math gives k=0.2, needing only ~21 bars to reach the same 1% threshold — MACD's signal line converges fast; a raw EMA-200 does not.

### 4.3 MACD

- **Canonical**: MACD line = EMA(12) − EMA(26) of close price (both EMAs SMA-seeded per above); Signal line = **EMA(9) of the MACD line**, itself SMA(9)-seeded from the first 9 MACD values, then continuing with standard EMA recursion from the 10th MACD value onward.
- **Common variant/error**: seeding the signal-line EMA with the first raw MACD value instead of an SMA(9) of the first 9 MACD values — same seed-bias problem as §4.2, but here the impact window is shorter (signal line only needs ~9-bar warm-up to stabilize by the 1% rule above, roughly 21 bars).
- **Warm-up**: EMA-26 needs its own warm-up (~60 bars by the 1% rule: k=2/27≈0.074, n≈ln(0.01)/ln(0.926)≈59) before the MACD *line* itself is trustworthy, and then the signal line needs the MACD line to already be stable before *its* 9-bar smoothing means anything. **Practical minimum: ~60-100 bars before MACD histogram values should be treated as fully converged**, not the naive 26+9=35 sometimes quoted as "minimum to get a number at all."

### 4.4 Stochastic RSI

- **Canonical / only correct definition**: **Stochastic-of-RSI** — apply the Stochastic Oscillator formula *to a series of RSI values* (not the reverse): `StochRSI = (RSI − min(RSI, N)) / (max(RSI, N) − min(RSI, N))`, typically N=14, then often smoothed with a %K (3-period) and %D (3-period) moving average on top, output range 0-1 (or 0-100 depending on convention).
- **The inconsistency the brief asks about**: despite "Stochastic-of-RSI" being the textbook-correct and universally cited definition, real-world confusion and bugs arise from (a) whether the %K/%D smoothing periods are applied at all (raw StochRSI vs smoothed StochRSI look very different — raw is extremely noisy), (b) whether the 0-1 or 0-100 scale is used, and (c) which RSI variant (Wilder vs EMA, per §4.1) feeds the Stochastic step — since StochRSI compounds on top of RSI, an RSI smoothing-method mismatch propagates and amplifies into StochRSI.
- **Warm-up**: needs a full RSI warm-up (§4.1, ~14-70 bars depending on strictness) *plus* an additional N bars (typically 14) of RSI history to compute the Stochastic min/max window, *plus* the %K/%D smoothing periods (commonly 3+3) on top. **Minimum bars before a smoothed StochRSI is meaningful: RSI period + Stoch lookback + smoothing periods ≈ 14+14+3+3 = 34 bars minimum, with the same "3-5× for full convergence" caveat from §4.1 pushing the safe number well over 100.**

### 4.5 ATR (Average True Range)

- **Canonical (Wilder's original)**: True Range = `max(high−low, |high−prevClose|, |low−prevClose|)`; ATR = Wilder-smoothed average of True Range: `ATR_t = (ATR_{t-1} × (N−1) + TR_t) / N`, first ATR = simple average of the first N true ranges.
- **Wrong/divergent variant**: plain **simple moving average of True Range** (equal-weighted rolling mean) instead of Wilder smoothing. Documented relationship: "Wilder ATR with period N is approximately equivalent to an EMA-based ATR with period ≈2N" — meaning an SMA(14)-ATR and a Wilder(14)-ATR are computing genuinely different things, not just noisy variants of the same thing. Both converge to similar values after ~30+ bars, but diverge meaningfully in fast-changing volatility regimes (exactly when ATR matters most for signal generation), and Wilder's is the default on TradingView, thinkorswim, and TradeStation.
- **Warm-up**: minimum N bars (14 typical) for the seed SMA of true ranges, plus the same multi-period convergence caveat (~30+ bars) before Wilder smoothing has "forgotten" its simple-average seed.

### 4.6 Bollinger Bands: %B and Bandwidth

- **Canonical (John Bollinger's own definition)**: middle band = SMA(N, typically 20) of close; bands = middle ± K × **population standard deviation** (K typically 2), explicitly **divide by N, not N−1** — Bollinger's own site states this was a deliberate choice ("we are calculating the deviation of a fixed set of data... we are not estimating a population parameter" — i.e., you're describing the window itself, not inferring a larger population from a sample). `%B = (price − lowerBand) / (upperBand − lowerBand)`. `Bandwidth = (upperBand − lowerBand) / middleBand` (= 4× the 20-period coefficient of variation at K=2).
- **The concrete, high-probability bug**: **numpy's `std()` defaults to `ddof=0` (population, matches Bollinger's definition) while pandas' `.std()` defaults to `ddof=1` (sample, Bessel-corrected, does NOT match Bollinger's definition)**. A Bollinger Bands implementation written against a pandas `Series.rolling(20).std()` call, without explicitly passing `ddof=0`, silently computes bands ~2.6% wider than the canonical definition at N=20 (the ratio √(N/(N−1)) = √(20/19) ≈ 1.026), shifting every %B and Bandwidth reading. This is exactly the class of "looks plausible, quietly wrong" bug the product brief is about, and it is trivially easy to introduce because pandas' default silently differs from numpy's default and from the textbook definition.
- **Warm-up**: minimum N bars (20 typical) for the first SMA+stdev window to exist at all; because it's a fixed rolling window (not exponentially decaying like EMA/Wilder), there is no additional "convergence" period beyond having N valid bars — this is one of the few indicators where "N bars = fully valid" is actually true, provided the standard-deviation convention is correct.

### 4.7 OBV / Volume

- **Canonical**: cumulative running total; add the period's volume when close > prevClose, subtract when close < prevClose, unchanged on no change.
- **Cross-exchange incomparability**: OBV's absolute level and even its trend are meaningless across venues/instruments unless the underlying volume unit is identical. Binance and most venues distinguish **base-asset volume** from **quote-asset volume**; mixing base-unit volume (e.g., "BTC traded") from one venue with quote-unit volume ("USDT traded") from another, or comparing OBV computed on a low-volume venue against a high-volume venue, produces numbers that look like a trend signal but reflect nothing but differing units/liquidity. **OBV must be computed and interpreted per single venue/instrument only**, never summed or blended across venues without an explicit normalization step (convert to common quote-currency notional).
- **Warm-up**: technically valid from bar 1 (cumulative sum), but the *first* bar has no prior close to compare against — must start accumulation from bar 2, and any "trend" read on OBV needs enough bars for the cumulative sum's slope to be meaningful (no hard minimum, but treating <20-30 bars of OBV history as directional signal is not defensible).

### 4.8 Multi-timeframe alignment, look-ahead bias, and repainting

- **The core mechanism**: on historical (closed) bars, OHLC values are fixed; on the *current, unclosed* bar, close/high/low continue updating with every tick until the bar closes. Any indicator computed off the current unclosed bar will change value repeatedly and can retroactively look like it gave a different signal once the bar finally closes — this is "repainting."
- **Multi-timeframe look-ahead bias**: combining a higher timeframe (e.g., 4H) value into a lower-timeframe (e.g., 1H) display becomes look-ahead bias specifically when the 4H bar being referenced **hasn't closed yet** relative to the 1H bar's own timestamp — i.e., showing "today's still-forming 4H RSI" next to a fully-closed 1H bar leaks partial/future information and will change retroactively.
- **Correct practice for this dashboard**: (1) always compute and display indicators from the **last fully-closed** bar of each timeframe, never the forming bar, using the per-venue detection methods in §2.3; (2) when showing a 4H value alongside a 1D value, clearly timestamp each with its own last-closed-bar time rather than implying simultaneity; (3) if a "live/current" value must be shown (e.g., current unclosed-bar price), label it explicitly as provisional/live and keep it visually and computationally separate from the confirmed-bar indicator values — never feed it into a smoothed indicator's running state.

### 4.9 Warm-up bars — summary table

| Indicator | Minimum bars for a value at all | Bars before "trustworthy/converged" (rule of thumb) |
|---|---|---|
| SMA(N) | N | N (fixed window — no further convergence needed) |
| EMA(N), general | N (for SMA seed) | ≈ ln(0.01)/ln(1 − 2/(N+1)) ≈ **2.3×N** for seed influence < 1% (e.g., ~30 for EMA-14, ~60 for EMA-26, ~460 for EMA-200) |
| RSI(14), Wilder | 15 (per known TA-Lib off-by-one behavior) | ~50-70 (3-5×N) |
| MACD(12,26,9) | 35 (26 for slow EMA + 9 for signal) | ~60-100 (slow EMA convergence dominates) |
| StochRSI(14,14,3,3) | 34 | 100+ (compounds RSI's own convergence need) |
| ATR(14), Wilder | 14 | ~30-40 |
| Bollinger(20, K=2) | 20 | 20 (fixed rolling window; no extra convergence — but only if stdev convention is correct) |
| OBV | 2 (needs a prior close) | 20-30 for a directionally meaningful read |

**The single most important engineering rule from this table**: *emitting an indicator value before its warm-up threshold, or worse, computing it over "whatever the cache holds" with no fixed, known bar count (the exact bug named in the product brief), is silently indistinguishable from a correct value on the screen.* Every indicator must carry its own bar-count-since-first-valid-input as metadata, and the UI must refuse to show a value (or must clearly flag it) below the "trustworthy" threshold, not just the "produces a number" threshold.

---

## 5. Part D — Verification Strategies (concrete, actionable — these become acceptance criteria)

1. **TA-Lib as a reference oracle.** TA-Lib's C implementation is the de facto industry-standard reference (it's what many charting platforms and brokers use under the hood). Compute the same indicator two ways — your implementation and `talib.RSI`/`talib.ATR`/etc. on an identical input array — and assert numerical equality within a small epsilon (e.g., 1e-6) after each one's respective warm-up period. This is a **direct, runnable acceptance test**, not just a design review.
2. **Golden-file / worked-example regression tests.** StockCharts' ChartSchool pages and Wikipedia's On-Balance-Volume / RSI articles publish fully worked step-by-step numeric examples with a small fixed input price series and the expected output at each step. Hard-code these fixed input arrays and their known-correct outputs as unit test fixtures ("golden files") — any future refactor that changes a computed value beyond epsilon must fail CI. This catches both regressions and the "which variant" ambiguity (Wilder vs EMA, population vs sample stdev) because the golden values are variant-specific.
3. **Cross-check against TradingView's displayed values.** For a handful of specific timestamps on BTC/ETH/SOL, manually record TradingView's displayed RSI(14)/ATR(14)/Bollinger values (which use Wilder smoothing and population stdev, per §4) and assert your computed values match within a small tolerance at those exact timestamps. This is a spot-check, not exhaustive, but catches "my library defaulted to the wrong variant" errors that a golden-file test using synthetic data might not catch on real, messy market data.
4. **Property-based testing (Hypothesis or equivalent) for invariants that must hold for *any* valid input**, not just specific worked examples:
   - RSI output is always bounded in [0, 100].
   - Bollinger upper band ≥ middle band ≥ lower band, always.
   - %B is not artificially bounded (can exceed [0,1] during a squeeze breakout — a common wrong "clamp to 0-1" bug is worth explicitly testing *against*).
   - OHLC internal consistency: `low ≤ open ≤ high` and `low ≤ close ≤ high` for every generated synthetic bar, and any indicator fed a corpus of such synthetic-but-valid bars should never throw, never emit NaN inside the valid computation range, and never emit a value outside its indicator's documented range.
   - Timestamps monotonically increasing with no duplicate bar times fed into any indicator's rolling state.
   - Feeding a strictly constant price series into ATR/Bollinger bandwidth should converge to exactly zero (this is a strong test that stdev/true-range logic isn't accidentally injecting noise).
5. **Warm-up-boundary tests as first-class acceptance criteria.** For every indicator in the §4.9 table, write an explicit test asserting: (a) the indicator refuses to emit / emits a clearly-flagged-provisional value below its "trustworthy" bar count, and (b) the emitted value at exactly N+1 vs N+100 bars for the same tail of data converges (i.e., feed 20 vs 500 bars of the same trailing data and confirm the outputs agree within epsilon once past warm-up) — this is a direct regression test against the exact bug that motivated this project ("the same market produced different numbers depending on process uptime").
6. **Determinism-under-replay test.** Feed the exact same fixed historical OHLCV window into the indicator pipeline twice, from two different "cache states" (e.g., once with a short trailing buffer just past warm-up, once with a much longer buffer) and assert identical output for the overlapping period. This directly targets the root-cause bug named in the product brief.

---

## 6. Traps (consolidated)

- Consuming the most recent kline row without checking whether it's closed (all venues except OKX require a manual wall-clock/flag check; OKX's `confirm` field semantics were not independently confirmed this session — verify before relying on it).
- Trusting a library's default RSI/ATR smoothing method without checking whether it's Wilder's or EMA/SMA — the difference is 5-10 RSI points during trending moves.
- Using pandas `.std()` on a Bollinger Bands calculation without `ddof=0` — silently produces bands ~2.6% wider than Bollinger's own definition at N=20.
- Treating "produces a non-null number" as equivalent to "warmed up" — RSI/MACD/StochRSI/EMA200 all produce *a* number almost immediately but need multiples of their period before that number reflects steady-state behavior (see §4.9).
- Summing or comparing OBV/volume-based indicators across exchanges or between spot and perpetual instruments without normalizing volume units first.
- Assuming Binance is a safe default source for any US-region or Cloudflare-Worker-hosted compute — public REST returns HTTP 451 for restricted IPs.
- Assuming kline timestamps are contiguous after any gap (exchange downtime, listing gaps) rather than checking timestamp deltas explicitly.
- Depending on the original `pandas-ta` package going forward — it is heading toward archival; `pandas-ta-classic` is the maintained fork as of mid-2026.
- Using `tulind` inside a Cloudflare Worker — it's a native Node addon and cannot run in the Workers V8 isolate sandbox regardless of its maintenance status.

---

## 7. Sources Cited

- https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints — Binance kline endpoint fields, limits, intervals
- https://github.com/ccxt/ccxt/issues/15891 — Binance public API 451 geo-restriction, restricted regions
- https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles — Coinbase Exchange candles granularity/limits
- https://docs.kraken.com/api/docs/rest-api/get-ohlc-data — Kraken OHLC endpoint, 720-bar limit, unclosed last-bar behavior
- https://bybit-exchange.github.io/docs/v5/market/kline — Bybit v5 kline fields, limits, intervals
- https://bybit-exchange.github.io/docs/v5/rate-limit — Bybit rate limit rules
- https://www.coingecko.com/en/api/pricing — CoinGecko plan pricing, credits, OHLC access by tier
- https://www.coinapi.io/products/market-data-api/pricing (via search cache) — CoinAPI Startup/Streamer/Pro pricing
- https://www.tiingo.com/about/pricing — Tiingo Starter/Power pricing
- https://pypi.org/project/pandas-ta/ — pandas-ta latest release status (pre-release, Sep 2025)
- https://pypi.org/project/pandas-ta-classic/ — pandas-ta-classic version 0.6.52, release date, feature count
- https://github.com/TA-Lib/ta-lib-python — TA-Lib Windows prebuilt wheels (since v0.6.5), MSI installer
- https://rsimonitor.com/articles/wilder-smoothing — Wilder vs EMA vs SMA RSI worked numeric example and formula
- https://www.macroption.com/atr-calculation/ — ATR Wilder vs SMA formulas and Wilder≈2N-EMA relationship
- https://www.bollingerbands.com/bollinger-band-rules — population vs sample standard deviation, John Bollinger's own statement
- https://numpy.org/doc/stable/reference/generated/numpy.std.html — numpy std() ddof=0 default (population)
- https://developers.binance.com/docs/derivatives/coin-margined-futures/market-data/rest-api/Taker-Buy-Sell-Volume — base vs quote vs taker-buy volume field definitions

Additional facts (Stochastic RSI definition, MACD signal-line SMA seeding, repainting/look-ahead mechanics, property-based testing for financial invariants) were corroborated via multiple independent search-result summaries (TrendSpider, CorporateFinanceInstitute, GrandAlgo, susanpotter.net) without a single fetchable canonical URL each — treat exact wording as paraphrased, not directly quoted, where no single URL is listed above. Kaiko, Amberdata, and CryptoCompare/CoinDesk Data exact 2026 pricing are marked **UNVERIFIED** in Section 2.1 — both are sales-gated/enterprise as of this research and no public price list was found.
