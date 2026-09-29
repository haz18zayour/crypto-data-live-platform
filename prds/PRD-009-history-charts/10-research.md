# PRD-009 · History and charts — Research

## What we already knew, and whether it still holds

| Claim from our knowledge base / brief / architecture | Still true? | What the source says | Citation |
|---|---|---|---|
| DefiLlama stablecoin supply "structurally cannot be backfilled beyond since-we-started-collecting" (brief, leading candidate for a fifth absence case) | **WRONG** | DefiLlama documents `/stablecoincharts/{chain}` as "Get historical mcap sum of all stablecoins in a chain", returning `array of {date, totalCirculating}`. Fetched live: `/stablecoincharts/Ethereum` returns daily entries back to `date: "1511913600"` (2017-11-29), with `totalCirculatingUSD.peggedUSD`, which is the same field name our fetcher reads from `/stablecoinchains`. What PRD-008 confirmed is still true, but only for `/stablecoinchains`. It is a different endpoint from the same vendor. | https://api-docs.defillama.com/ · https://api-docs.defillama.com/llms-free.txt · https://stablecoins.llama.fi/stablecoincharts/Ethereum |
| `datapoints` accumulates every distinct `source_timestamp` (unique on `indicator_key, asset, source_vendor, source_timestamp`) | True | `supabase/migrations/20260910120000_create_corroborations.sql:8-14`. **But** the only secondary index is `(indicator_key, asset, fetched_at desc)` (`20260908140000_create_datapoints.sql:36`), not `source_timestamp`. See gotcha #1. | repo |
| FRED `series/observations` is "already a time series by construction" | True, with a trap | `limit` goes up to 100000. The vintage-date query cap is "2000 json" for most combinations and lower for daily series with some output types. Our fetcher uses `output_type=4` with a narrowed ~2-year `realtime_start` (`ingest/fetchers/fred.py:132-144`). A deep backfill with the same parameters hits the cap that caused FETCH_FAILED in US-808. | https://fred.stlouisfed.org/docs/api/fred/series_observations.html |
| Coin Metrics `asset-metrics` time-range queries can backfill | True, with a trap | Community rate limit is "10 requests per 6 seconds (sliding window) per IP address", with page_size max 10000. The history window is bounded by entitlement. "If you query outside that window, you get **an empty response**, not an error." `min_time` comes from `/catalog-v2/*`. Pagination is via `next_page_url` "unmodified". | https://gitbook-docs.coinmetrics.io/access-our-data.md?ask=Community%20API%20rate%20limits%20and%20page_size%20maximum%20for%20timeseries%20asset-metrics · https://gitbook-docs.coinmetrics.io/access-our-data.md?ask=Does%20the%20Community%20API%20restrict%20how%20far%20back%20start_time%20can%20go%20for%20free%20metrics%20like%20CapMVRVCur%20and%20AdrActCnt%2C%20and%20what%20is%20the%20pagination%20next_page_token%20mechanism |
| OKX `history-candles` / `funding-rate-history` can backfill | Partly | **Candles: deep.** A live request for `bar=1D&after=2021-01-01` returned BTC-USDT daily candles from Dec 2020. **Funding: shallow.** Paging from the oldest end (`before=1`) returned 100 records whose oldest `fundingTime` is `1782115200000`. By my own arithmetic that is 2026-06-22 08:00 UTC, about 3 months back. A third-party article claims "caps responses to the last 400 records (≈1 year)". The live measurement contradicts it, so treat the article as wrong. | https://www.okx.com/api/v5/market/history-candles?instId=BTC-USDT&bar=1D&after=1609459200000&limit=5 · https://www.okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=100&before=1 · (search result, not fetched: https://www.holysheep.cn/articles/en-okx-funding-rate-history-api-for-backtesting-2026-07-12-0017.html) |
| Fast-tier derivatives (`open_interest`, `taker_ratio`) already have 300+ rows, so they need no backfill | True, but misleading | Those 300+ rows are 5-minute points, which is about a day of history. The fetcher requests `period: "5m"` (`okx_derivatives.py:259,322`). OKX's `1D` long/short endpoint returns about 6 months of daily rows in one call (oldest `1775059200000`, which is 2026-04-01 by my arithmetic). OKX's separate `open-interest-history` returns daily `[ts, oi, oiCcy, oiUsd]`, the same three measures as the snapshot endpoint. | https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy=BTC&period=1D · https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-history?instId=BTC-USDT-SWAP&period=1D&limit=100 · https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP |
| Architecture: "uPlot for dense sparkline panels" | Holds, but not installed | uPlot's own sparkline demo is exactly this pattern: `width:150,height:30`, both axes `show:false`, `scales.x.time:false`, 20 canvases in a table. `web/package.json` has no uPlot or Lightweight Charts dependency yet. | https://raw.githubusercontent.com/leeoniya/uPlot/master/demos/sparklines.html |
| KB (databases): Supabase free tier is 500 MB, and daily writes dodge the 7-day pause | Holds, and gets more relevant | Backfilling daily history for ~150 indicators × assets × years is still small. Fast-tier 5-minute rows are the only real growth driver. **UNVERIFIED:** a row is about 200–300 bytes with indexes, so 1M rows ≈ 300 MB, which is inside 500 MB but not by a wide margin. | KB |
| KB (realtime): push/streaming guidance | Not relevant | Sparklines are poll-read history. Nothing in this PRD needs realtime. | — |

## Existing implementations

- **Sparkline as display, with no verdict (Tufte).** Tufte defines a sparkline as "a small intense, simple, word-sized graphic with typographic resolution". His canonical example shows min and max points, the final value tied to the rightmost point by a colour accent, and a gray "normal range" band. **Important for G1:** in Tufte's own example the gray band is a *clinical normal range*, meaning an external judgement. That is exactly what this product forbids. Tufte's own prior art lets us use min/max/last markers and a labelled axis. It does **not** let us use a "normal band" computed from history, because that band is a percentile verdict drawn as a shape. https://www.edwardtufte.com/notebook/sparkline-theory-and-practice-edward-tufte/
- **Dense sparkline tables with uPlot.** Canvas-only (`uplot: false` DOM wrapper removed), no axes, no cursor or legend configured. It is built for many small charts in a table. https://raw.githubusercontent.com/leeoniya/uPlot/master/demos/sparklines.html
- **Top-N rows per group in Postgres.** `LATERAL (... ORDER BY ... LIMIT N)` applies the limit per outer row. A commenter warns that it forces a nested loop, which is fine when the outer set is small (~150 × assets) and the inner side is index-backed. https://www.cybertec-postgresql.com/en/understanding-lateral-joins-in-postgresql/
- **Supabase row cap.** Search results (docs page not fetched successfully) say Supabase returns at most 1,000 rows per request by default, adjustable under API settings → Max Rows. There is a known report of the change not taking effect. Search results only: https://supabase.com/docs/reference/python/limit · https://www.answeroverflow.com/m/1480937862227693600
- **Vendor history shapes, measured live today:**

| Vendor / series | Live endpoint today | History endpoint | Measured / documented depth | Backfillable? |
|---|---|---|---|---|
| OKX spot candles (+ TA-Lib-derived indicators) | `history-candles` | same | Daily back to ≤ Dec 2020 | Yes, deep |
| OKX funding | `funding-rate-history` | same | ~3 months | Yes, shallow |
| OKX open interest | `public/open-interest` (snapshot) | `rubik/stat/contracts/open-interest-history` | ≥ ~100 daily rows in one page (2026-06-20 → 2026-09-27) | Yes, via a **different endpoint** |
| OKX long/short, taker volume | `rubik/...` period `5m` | same, `period=1D` | ~6 months at 1D. **UNVERIFIED:** 5m depth is short, roughly days | Yes at 1D only |
| Coin Metrics (MVRV, active addresses) | `timeseries/asset-metrics` | same, `start_time` | Entitlement-bounded; check `catalog-v2` `min_time` | Yes |
| FRED | `series/observations` output_type=4 | same | Full series; vintage cap on realtime ranges | Yes, chunked |
| SoSoValue ETF flows | `etfs/summary-history` | same | **UNVERIFIED:** docs not fetched. Search result says 20 req/min (https://apify.com/gochujang/crypto-etf-flow-tracker/api/openapi) | Probably. Measure it |
| DefiLlama stablecoin supply | `/stablecoinchains` (current) | `/stablecoincharts/{chain}` | Daily since 2017 (Ethereum) | **Yes**, contrary to the brief |
| alternative.me F&G | `/fng/` | `/fng/?limit=0` | Live call returned daily values back to at least `1698883200` (2023-11-02) | Yes |
| Solana RPC (fixed-hour block measure) | Helius | historical blocks | Technically possible. A single hour took ~2.5 h wall-clock (lessons log) | **No, in practice.** This is the real fifth-absence candidate |
| validators.app | current snapshot | none known (UNVERIFIED) | — | Likely no |

## Approach options

**A. Reuse `datapoints` and add an `origin` column plus a `(indicator_key, asset, source_vendor, source_timestamp desc)` read path, served by a `history_read` view or an RPC that returns N points per key.**
Backfill writes ordinary rows with `origin='backfill'` and real `source_timestamp`s, using the same unique index for idempotent upserts. `board_read` is fixed so backfill can never become "latest" (gotcha #1).
Trade-offs: one table and one provenance model, and the verifier can cross-check backfilled rows with the same queries it already uses. It needs a migration that touches `board_read`, which is blast radius. Cost: $0. Who does this: most single-Postgres dashboards (KB: "start on one managed Postgres").

**B. Dedicated `history_points` table for backfill only, with live rows staying in `datapoints` and a UNION view for sparklines.**
Trade-offs: `board_read` can't be polluted, because backfill never touches `datapoints`. The cost is two provenance models, a UNION with dedup rules where live and backfilled timestamps overlap, and every honest-absence rule has to be written twice. Cost: $0.

**C. A materialized per-key rollup (`sparkline_mv`) holding a downsampled array of the last N points, refreshed after each ingest.**
Trade-offs: the fastest reads and one row per cell, so it fits PostgREST's 1,000-row cap. But it adds refresh scheduling (one more thing that can silently go stale, the failure class this project exists to prevent), and downsampling can smooth away the real extreme the adversarial case asks us to preserve. Cost: $0. **UNVERIFIED:** unnecessary at this row count.

**D. Fetch history from vendors client-side at render time. No backfill.**
Rejected. It puts vendor keys (FRED, SoSoValue) in the browser, OKX/Binance geo issues move to the user's IP, and provenance disappears.

**Recommendation: A**, with an RPC that returns at most N points per key as one JSON array per cell. It keeps a single provenance model and one honest-absence vocabulary. The row cap and ordering problems are solved by the read shape, not by a second store.

## Edge cases and gotchas

1. **Backfill will hijack the board.** `board_read` is `distinct on (indicator_key, asset) ... order by fetched_at desc, id desc` (`20260927120000_...sql:28-47`). A backfill row inserted today with `fetched_at = now()` and a 2024 `source_timestamp` becomes the "current" value on the board. The workaround of setting `fetched_at` to the historical time would falsify provenance. The fix has to be in `board_read`, for example `where origin = 'live'`. Ordering by `source_timestamp` instead has its own trap: `DESC` puts NULLs first in Postgres by default, and UNAVAILABLE rows have NULL `source_timestamp`. **This is the single most likely first-implementation bug in this PRD.**
2. **Multiple vendors per indicator give a zig-zag sparkline.** Corroboration means spot price exists from both Coinbase and OKX. A "last N rows per indicator/asset" query interleaves the two vendors and draws a sawtooth that is not market movement. Sparkline reads must pin `source_vendor`, which the unique index already supports.
3. **Mixed granularity in one line.** Live OI and taker data are 5m rows, while backfill is only available at `1D`. One polyline over "last N rows" makes the x-axis lie: 288 points a day recently, one a day before. Either resample per indicator at read time (for example, daily last value) or plot on a real time axis where the density change is visible. `scales.x.time:false` from the uPlot demo is **wrong** for this product.
4. **OKX daily buckets are not UTC days.** Every OKX `1D` timestamp measured today ends in `16:00:00 UTC` (e.g. `1790524800000`), which is UTC+8 midnight. Coin Metrics and FRED days are UTC. Cross-vendor alignment isn't in scope, but a sparkline labelled "daily" with a UTC axis is off by 8h for OKX. **UNVERIFIED:** OKX offers `1Dutc` bars.
5. **Coin Metrics returns empty, not an error, outside the entitlement window.** A backfill that treats "0 rows returned" as "no history exists" will silently record a short history. Query `catalog-v2` `min_time` first and assert on it.
6. **FRED vintage cap, again.** Initial-release history (`output_type=4`) over years of a daily series needs chunked `realtime_start` windows. Otherwise it hits the ~2000-vintage cap that already broke VIXCLS/DFF/T10Y2Y/DFII10 once. Switching the backfill to `output_type=1` avoids the cap but writes *revised* values next to live *initial-release* values in one line. That is a silent definitional splice.
7. **Snapshot vs history endpoint splice (OKX OI).** Live OI comes from `public/open-interest` with an intraday `ts`. History comes from `open-interest-history` as period buckets. The values are in the same units (live `oiCcy 28844.80` vs history `28754.47` for the latest bucket), but the `endpoint` and `source_field` columns must say which is which. The verifier's "real numbers from the vendor" cross-check has to hit the endpoint that actually wrote the row.
8. **DefiLlama live rows use `source_timestamp = fetched_at`** (`defillama_stablecoins.py:119-126`), so every run adds a row. Backfilled `/stablecoincharts` rows sit at daily 00:00 UTC. The series will be one point per day historically and one per run recently (see #3). Also confirm today's `/stablecoincharts/{chain}` last value ≈ today's `/stablecoinchains` value before trusting the splice.
9. **TA-Lib warm-up.** **UNVERIFIED:** Wilder-smoothed RSI and ATR depend on all prior bars. Recomputing history from backfilled candles gives slightly different early values than a longer-seeded run. Backfill must fetch a lookback of several multiples of the period before the first plotted point, or the golden files will diverge.
10. **PostgREST 1,000-row cap.** A board-wide "last 60 points for every cell" query is tens of thousands of rows, silently truncated at 1,000 (search results above). Return one aggregated array per cell from an RPC, or query per visible cell.
11. **Wall-clock vs CI timeout** (lessons log). Coin Metrics at 10 req/6 s and SoSoValue at ~20 req/min are fine for a handful of keys, but a full-registry backfill in the 10-minute ingest workflow may not be. Measure first, and give backfill its own `workflow_dispatch` job with its own timeout.
12. **"Not enough history" is a read-time state, not a row status.** Adding it to the `unavailable_reason` enum would mean writing fake rows. Derive it from the point count (below a threshold → render the state). Keep a *separate* state for "history begins <date>, vendor offers no earlier data". That one is a fact about the vendor, while the point count is a fact about us.
13. **alternative.me ships a verdict label.** The fetched response contains `"value_classification": "Greed"`. A history view must never render that field, even on hover.

## Services and keys this PRD needs

| Service | Why | Env var | Already provisioned? |
|---|---|---|---|
| OKX public REST | Candles, funding, OI history, rubik 1D history | none | Yes (no key) |
| Coin Metrics Community | On-chain history | none (community) | Yes |
| FRED | Macro history | `FRED_API_KEY` | Yes. Commit `cca0323` fixed the canary; **must also be in any new backfill workflow's env block** (lessons log) |
| SoSoValue | ETF flow history | `SOSOVALUE_API_KEY` | Yes. Same caveat for a new workflow |
| DefiLlama | `/stablecoincharts/{chain}` history | none | Yes (no key); new endpoint, same vendor |
| alternative.me | F&G history | none | Yes |
| Supabase | Migration + RPC | `DATABASE_URL` | Yes. **Applying the migration to prod is a manual, owner-gated step** (lessons log) |
| Healthchecks.io | Only if backfill becomes a scheduled job | new `HEALTHCHECKS_PING_URL_BACKFILL` | **No.** Needs the real check created and a verified last-ping timestamp |

## Open questions for the human

| # | Question | My committed hypothesis | What breaks if I'm wrong |
|---|---|---|---|
| 1 | What is the exact "distribution context" mechanism? | Sparkline plus min and max *value labels* at the axis ends, with their dates. The last point is marked, with no colour change based on position. **No band, no percentile, no shading, no "range position" bar.** The time window is fixed per tier (e.g. 90d daily, 7d fast) and shown in text. | If a band or range-position marker ships, it is a verdict drawn as a shape. That breaks the project's one rule, and it will read as a signal. |
| 2 | Does `/stablecoincharts/{chain}` count as "no new vendor"? | Yes. Same vendor, new endpoint. It is allowed, and it removes DefiLlama from the "cannot backfill" list. | If it's ruled out, stablecoin supply ships as "history since <first collection date>", and the brief's fifth absence case stays for the wrong reason. |
| 3 | FRED backfill semantics: initial release (`output_type=4`, chunked) or current vintage? | Initial release, chunked, to match the live rows' semantics. | Revised history next to initial-release live values is a silent splice. That is the "wrong number looks right" failure. |
| 4 | Backfill: one-off or ongoing? | A `workflow_dispatch` job with an `indicator_key` input, idempotent through the unique index. It runs manually when a registry row is added, plus a test that fails if a registry row has no backfill recipe or an explicit "not backfillable: <reason>" declaration. | If it's one-off only, every future indicator ships with "not enough history" forever and nobody notices. |
| 5 | Minimum points before a sparkline draws | ≥ 7 points *and* ≥ 2 distinct values are required to draw. Otherwise show "not enough history yet (n points since <date>)". | Too low and a 2-point line reads as a trend. Too high and real sparse monthly series (M2, CPI) never draw. Monthly series need their own threshold, e.g. 6. |
| 6 | Fast tier: resample or plot raw? | Real time axis with raw points. Density changes stay visible, with no resampling. | Resampling hides the backfill/live seam, while raw plotting on an index axis (the uPlot demo default) distorts time. |
| 7 | Where does the `board_read` fix live? | Same migration as `origin`, a blast-radius review, applied to prod by hand with owner sign-off, **before** any backfill runs. | If backfill runs first, the production board shows historical values as current. |

## Blind spots

1. **The adversarial cross-check can pass while the data is wrong.** The brief asks for real vendor numbers to confirm a swing. If the verifier cross-checks against the *same endpoint and parameters* the backfill used, it proves nothing about splices (gotchas #6, #7, #8). The seam is where live and backfilled rows meet. The cross-check must pick a date on each side of the seam, and for OI or FRED it must compare against the *live* endpoint's value for the overlap day.
2. **Scale choice is itself a judgement.** Auto-scaling y to min/max makes a 0.3% wobble fill the cell and look like a crash, which is the most common way sparklines mislead. Tufte's "lumpy, ~45°" aspect guidance assumes a human picks the aspect ratio. For funding rate (which crosses zero) and ETF flows (signed), a y-range that excludes zero hides the sign flip, and that flip is the fact the user cares about. Decide per indicator class whether zero must be included, and write it into the registry, not the component.
3. **The historical-extremes window becomes an implicit claim.** "Min/max over the last 90 days" silently changes meaning when backfill depth differs by vendor: funding has ~3 months, candles have 6 years, and the 1D rubik series has ~6 months. Two adjacent cells labelled "range" would cover different spans. Every scale label must print its own actual span ("min 2026-06-22 → now"), or users will read comparable ranges where there are none. That comes close to the forbidden cross-indicator comparison without anyone intending it.

## Sources

- https://api-docs.defillama.com/
- https://api-docs.defillama.com/llms-free.txt
- https://stablecoins.llama.fi/stablecoincharts/Ethereum
- https://www.okx.com/api/v5/market/history-candles?instId=BTC-USDT&bar=1D&after=1609459200000&limit=5
- https://www.okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=100&before=1
- https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy=BTC&period=1D
- https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-history?instId=BTC-USDT-SWAP&period=1D&limit=100
- https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP
- https://www.okx.com/docs-v5/en/ (fetched; the content was truncated before the endpoint sections, so it isn't cited for any claim)
- https://gitbook-docs.coinmetrics.io/access-our-data.md?ask=Community%20API%20rate%20limits%20and%20page_size%20maximum%20for%20timeseries%20asset-metrics
- https://gitbook-docs.coinmetrics.io/access-our-data.md?ask=Does%20the%20Community%20API%20restrict%20how%20far%20back%20start_time%20can%20go%20for%20free%20metrics%20like%20CapMVRVCur%20and%20AdrActCnt%2C%20and%20what%20is%20the%20pagination%20next_page_token%20mechanism
- https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- https://api.alternative.me/fng/?limit=0
- https://www.edwardtufte.com/notebook/sparkline-theory-and-practice-edward-tufte/
- https://raw.githubusercontent.com/leeoniya/uPlot/master/demos/sparklines.html
- https://www.cybertec-postgresql.com/en/understanding-lateral-joins-in-postgresql/
- Search results only (not fetched): https://supabase.com/docs/reference/python/limit · https://www.answeroverflow.com/m/1480937862227693600 · https://www.holysheep.cn/articles/en-okx-funding-rate-history-api-for-backtesting-2026-07-12-0017.html · https://apify.com/gochujang/crypto-etf-flow-tracker/api/openapi
