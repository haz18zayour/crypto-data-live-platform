# PRD-004 · Research — Spot OHLCV and technical indicators

Research date: 2026-09-10. Branch `feat/prd-004-indicators`. Read-only stage; nothing in this document was implemented.

The brief names the real work correctly: **the goldens, and the choice of N**. Both turn out to have published external answers we did not have on file, and one of them (N) has a measured upper bound imposed by BNB's listing date on Coinbase that nobody has looked at yet.

---

## What we already knew, and whether it still holds

| Claim we hold | Still true? | What the source says | Citation |
|---|---|---|---|
| TA-Lib documents an *unstable period* for a family of recursive functions; RSI/EMA/ATR are in it | **Yes** | The Python docs annotate individual functions: "The `RSI` function has an unstable period." Same annotation on `STOCHRSI`. | https://ta-lib.github.io/ta-lib-python/func_groups/momentum_indicators.html |
| "~22" functions carry an unstable period | **Close — 23, and the membership matters more than the count** | The `TA_FUNC_UNST_*` enum covers ADX, ADXR, ATR, CMO, DX, EMA, HT_DCPERIOD, HT_DCPHASE, HT_PHASOR, HT_SINE, HT_TRENDLINE, HT_TRENDMODE, KAMA, MAMA, MFI, MINUS_DI, MINUS_DM, NATR, PLUS_DI, PLUS_DM, RSI, **STOCHRSI**, T3. Search-result derived from the talib binding docs, not a page I fetched — treat the exact enum as **UNVERIFIED**; the RSI and STOCHRSI membership is confirmed by the fetched page above. | https://ta-lib.org/functions/ |
| **MACD** is in the same risk family | **No — TA-Lib does not flag it, and that is the trap** | The momentum-indicators page carries the unstable-period note on RSI and STOCHRSI and **carries no such note on MACD**, despite MACD being built from three EMAs. Anyone reading the docs to decide `required_bars` will conclude MACD is safe at 35 bars. It is not; the EMA-26 underneath it is recursive. | https://ta-lib.github.io/ta-lib-python/func_groups/momentum_indicators.html |
| Wilder smoothing is `avg = (prev × (N−1) + current) / N` | **Yes, verbatim** | "Average Gain = [(previous Average Gain) x 13 + current Gain] / 14." Described as "a smoothing technique similar to calculating an exponential moving average." | https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-strength-index-rsi |
| ATR uses the same Wilder recursion | **Yes, verbatim** | "Current ATR = [(Prior ATR x 13) + Current TR] / 14" | https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-true-range-atr |
| Warm-up for RSI(14) is "~50–70 bars (3–5×N)" | **Understated by 4×, and it was our own derivation, not a source** | A charting vendor states its operational number outright: "SharpCharts uses at least 250 data points before the starting date of any chart… a formula will need at least 250 data points to replicate our RSI numbers." The ATR page repeats it: "we calculate back at least 250 periods (typically much further)." | https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-strength-index-rsi · https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-true-range-atr |
| Bollinger's own site states the stdev is population (divide by N) | **Not supported by the page R3 cites.** The rules page gives only the defaults: "20 periods for the moving average and standard deviation calculations, and two standard deviations for the width." It says nothing about N vs N−1. | The population convention is real but the load-bearing citation is TA-Lib's behaviour, not Bollinger's site: "TA Lib does not have a ddof parameter… to get the same results as TA-Lib, `ddof=0` must be set in pandas." | https://www.bollingerbands.com/bollinger-band-rules |
| numpy/pandas stdev default mismatch is a live bug class | **Yes** — and moot for us, because TA-Lib's `BBANDS` is population by construction. It becomes live again the moment anything cross-checks with pandas. | See above. | Search-derived; TA-Lib `ddof=0` equivalence corroborated across multiple results |
| OKX exposes a `confirm` flag; `1Dutc` is UTC-aligned | **Yes — verified live today** | `GET /api/v5/market/history-candles?instId=BNB-USDT&bar=1Dutc` returned rows ending in `"1"` at exact 00:00 UTC boundaries. The `0/1` semantics R3 flagged as UNVERIFIED can now be treated as confirmed for `1`. | https://www.okx.com/api/v5/market/history-candles?instId=BNB-USDT&bar=1Dutc&limit=2&after=1767225600000 |
| Coinbase Exchange candles cap at 300 per request | **Yes** | "The maximum number of data points for a single request is `300` candles." Granularities `{60, 300, 900, 3600, 21600, 86400}`. | https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles |
| OKX `history-candles` caps at 100, `candles` at 300 | **Yes**, plus a limit we had no note of: at most ~1,440 candles are retrievable per bar size from the live endpoint. Search-derived, so **UNVERIFIED** on the 1,440 figure. | — | https://github.com/ccxt/ccxt/issues/20756 (search result, not fetched) |
| `ta` (bukosabino) is "actively maintained, commit as recent as April 2026" | **Stale / wrong.** PyPI shows v0.11.0 released 2023-11-02, with classifiers listing only Python 3.6 and 3.7. Whatever repo activity R3 saw has not produced a release in nearly three years. Do not present this as the maintained pure-Python option. | https://pypi.org/project/ta/ |
| pandas-ta-classic is the maintained fork, v0.6.52 | **Yes**, 2026-06-24, Python 3.10–3.14. | https://pypi.org/project/pandas-ta-classic/ |
| TA-Lib Python wrapper is "v0.6.x, wheels since 0.6.5" | **Superseded.** Current release is **0.7.1, 2026-07-16**, Python 3.9–3.14. Wheels-since-0.6.5 still correct. | https://pypi.org/project/TA-Lib/ |
| Binance 451 / OKX+Coinbase reachable from US runners | Not re-tested. Settled by our own measurement in PRD-001 US-011; nothing found contradicts it. | — | — |

---

## Existing implementations

**How people who ship this actually pin correctness.**

*The vendor answer to "how many bars".* StockCharts is the clearest published case of an operator who had to answer exactly our question and wrote the number down. Their charts compute RSI and ATR over at least 250 prior periods and they warn that a spreadsheet fed less will not reproduce their displayed values: "250 periods will allow for more smoothing than 30 periods, which will slightly affect RSI values" (https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-strength-index-rsi). They also ship the counter-artifact: a downloadable Excel worked example, plus the explicit caveat that "spreadsheet values for a small subset of data may not match exactly with what is seen on the price chart" (https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-true-range-atr). That pair — a fixed published vector *and* a stated convergence requirement — is precisely the two-part golden this PRD needs.

*The library maintainers' answer to "why don't my numbers match".* The most-cited issue on `ta-lib-python` about TradingView/Binance mismatch is resolved not as a bug but as a warm-up explanation: indicators with exponential memory "depend on previous values, not just the current period," so starting at a different point produces different early values that "converge over time as more historical data accumulates," and the reporter's 200-candle rolling window was the cause (https://api.github.com/repos/TA-Lib/ta-lib-python/issues/469/comments). The same thread notes `STOCH` carries a lookback of 15 for a period of 14. This is our US-201 argument, arrived at independently by TA-Lib's own users.

*The mechanical minimum, from the library itself.* The abstract API exposes `Function('x').lookback` as a first-class property (https://ta-lib.github.io/ta-lib-python/abstract.html). That returns the number of leading inputs consumed before the first output, for the given parameters — which is the *floor* for `required_bars`, computed by the engine rather than by us reading a table. It is not the converged number, but it is a free, per-indicator, per-parameter assertion that our chosen N is at least legal.

*What TA-Lib does not auto-fix.* The unstable period defaults to zero and `get_unstable_period` returns 0 for every function unless set (https://github.com/TA-Lib/ta-lib-python/issues/664, filed and closed as completed). So TA-Lib does not strip unconverged leading values for you. Combined with our exactly-N contract this is fine — we read only the final element — but it kills any assumption that "TA-Lib handles warm-up."

*Independent second implementations.* `pandas-ta-classic` is the live maintained option (Python 3.10–3.14, v0.6.52) and explicitly documents that "34 core indicators auto-use TA-Lib's C implementation when installed; pass `talib=False` to force native" (https://pypi.org/project/pandas-ta-classic/). See the gotchas section — this single sentence is the difference between a differential oracle and a tautology.

---

## Approach options

### Option A — Published worked-example vectors as the primary golden

Commit the fixed input series from the StockCharts RSI and ATR worked examples (and hand-computed Bollinger/OBV vectors) as fixtures, assert our pipeline reproduces the published outputs within epsilon *at the length the publisher used*, and separately assert convergence by re-running the same tail at N=250.

- **Trade-offs:** genuinely external, free, version-stable, and variant-specific — a Wilder-vs-EMA mismatch cannot pass. But the vectors are short, so they prove the *formula*, not the convergence. Coverage is partial: RSI, ATR, Bollinger and OBV are hand-checkable; MACD and StochRSI are not published as worked tables anywhere I found.
- **Cost:** zero dollars, meaningful hours transcribing spreadsheets.
- **Who uses it:** StockCharts publishes them for exactly this purpose; TA-Lib's own C test suite follows the same shape.

### Option B — Differential testing against a second, independent implementation

Run every indicator through `pandas-ta-classic` with `talib=False` on the identical bar slice and assert agreement within epsilon after warm-up.

- **Trade-offs:** covers all seven families including MACD and StochRSI, where no published vector exists. But two implementations agreeing is weaker evidence than a published number — they can share an inherited error, and pandas-ta's lineage has documented warm-up off-by-one history. Also fragile: it silently becomes a self-check if `talib=False` is ever dropped.
- **Cost:** one extra dev dependency; no runtime cost if confined to tests.

### Option C — Manual TradingView spot-check, recorded as evidence

Read RSI(14), ATR(14), MACD and Bollinger off TradingView for a named BTC daily bar, commit the screenshot and the numbers, assert our pipeline matches within tolerance.

- **Trade-offs:** the strongest possible "agrees with the outside world" evidence, and it catches convention errors that synthetic vectors miss. But it is manual, unrepeatable in CI, and TradingView's StochRSI convention differs from TA-Lib's (below), so it will produce a *false failure* on StochRSI unless the convention is pinned first.
- **Cost:** free, roughly an hour, once.

### Option D — Hand-roll the seven indicators from single-sourced formulas

R3's second recommendation. Removes library-default ambiguity entirely.

- **Trade-offs:** rejected by the architecture doc already, and rightly. Hand-rolling means our implementation *is* the thing under test, so it needs strictly more external verification than TA-Lib does, not less. It also re-opens the Wilder-vs-EMA decision the architecture closed by choosing the reference implementation.

**Recommendation: A as the merge gate, B as the coverage filler, C once as a committed evidence artifact.** Option A is the only one that satisfies the brief's adversarial case literally — a number computed outside this codebase, by someone else, before we existed — and B is the only way to reach MACD and StochRSI, which A cannot.

---

## Edge cases and gotchas

**1. `pandas-ta-classic` silently delegates to TA-Lib when TA-Lib is installed.** "34 core indicators auto-use TA-Lib's C implementation when installed; pass `talib=False` to force native" (https://pypi.org/project/pandas-ta-classic/). Our environment *will* have TA-Lib installed, because it is the compute engine. A differential test written the obvious way therefore compares TA-Lib against TA-Lib and passes unconditionally. This is US-006's failure at library scope, with no visible symptom. If Option B is taken, `talib=False` needs its own assertion, not just its own argument.

**2. TA-Lib's `STOCHRSI` is not TradingView's Stoch RSI, and the defaults hide it.** The signature is `STOCHRSI(close, timeperiod=14, fastk_period=5, fastd_period=3, fastd_matype=0)` (https://ta-lib.github.io/ta-lib-python/func_groups/momentum_indicators.html). Note `fastk_period=5`, not 14 — so the default stochastic lookback over the RSI series is 5 periods, while the near-universal published convention is 14. TA-Lib applies *fast* stochastic (`STOCHF`) where TradingView applies the smoothed form: TradingView's K is a 3-period average of the raw stochastic and its D is a 3-period average of K (https://www.tradingview.com/support/solutions/43000502333-stochastic-rsi-stoch-rsi/, K period 3, D period 3). The practical consequence: TA-Lib's `fastd` output corresponds to TradingView's **K**, not its D, and only if `fastk_period` is corrected to 14 first. Ship the defaults and the board displays a number that is defensible, reproducible, self-consistent, and matches no external reference on earth.

**3. MACD carries no unstable-period warning but has the longest real warm-up in the set.** The docs annotate RSI and STOCHRSI and leave MACD unannotated (same page). A reader deriving `required_bars` from the annotations will set MACD at 35 and every other recursive indicator at 250. The EMA-26 inside MACD is recursive regardless of what the docs annotate.

**4. TA-Lib will not tell you a value is unconverged, because the unstable period defaults to zero.** `get_unstable_period` returns 0 for every function out of the box (https://github.com/TA-Lib/ta-lib-python/issues/664). There is no NaN band, no flag, no exception. A 30-bar RSI array returns a plausible float at index 14.

**5. `TA_SetUnstablePeriod` is process-global mutable state.** US-201's note already flags this; it remains the single most likely way to reproduce "same market, different score" *inside our own determinism suite* under random test ordering. Any story that touches TA-Lib needs the autouse fixture in the same commit.

**6. Coinbase has no daily candles for BNB before late October 2025 — measured today.** A daily-granularity request for 2025-09-01 to 2025-09-06 returns `[]`; a request for 2025-10-28 onward returns rows. Coinbase's BNB-USD product is `online` with `trading_disabled: false`, so the pair itself is fine — the *history* is not.

| Probe | Result |
|---|---|
| `BNB-USD` product status | `online`, `trading_disabled: false` |
| Daily candles 2025-09-01 → 2025-09-06 | empty array |
| Daily candles 2025-10-28 → 2025-11-01 | 5 rows |
| Implied daily bars available today | roughly 317 |

Sources: https://api.exchange.coinbase.com/products/BNB-USD and https://api.exchange.coinbase.com/products/BNB-USD/candles?granularity=86400&start=2025-10-28T00:00:00Z&end=2025-11-01T00:00:00Z

**7. N=250 fits in one request per venue; N=500 does not, and N=500 is impossible for BNB on Coinbase.** Coinbase caps at 300 candles per request (https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles); OKX caps `market/candles` at 300 and `market/history-candles` at 100. Choosing 250 keeps every fetch a single unpaginated call at both venues and stays inside BNB's ~317-bar Coinbase history. Choosing 500 forces pagination — which reintroduces gap-stitching, the exact surface US-205 was built to police — and makes BNB structurally impossible on the corroborating venue.

**8. OBV under an exactly-N contract is not the OBV anyone means.** OBV is a cumulative running total from an arbitrary origin. Over exactly 250 bars its *absolute level* is an artifact of where the window starts and carries no information; only its slope or its delta does. An OBV cell on the board showing a large absolute number will be a number that changes meaningfully every day for reasons unrelated to the market. This needs a decision, not an implementation.

**9. The quote currencies differ, on all four assets.** OKX is `*-USDT`, Coinbase is `*-USD`. PRD-003's 25 bps corroboration tolerance was calibrated on BTC. Extending it unchanged to four assets extends it to three pairs with wider basis and thinner books, and any USDT dislocation fires divergence on all four simultaneously — which will read as a bug in our code on the day it is most important that it does not.

**10. Nothing pins the TA-Lib C library version, only the wrapper.** The Python package is at 0.7.1 (https://pypi.org/project/TA-Lib/) and the wrapper version is what `uv.lock` records. The C library underneath is installed separately per platform. A golden that pins a number without pinning the C library version is a golden that can legitimately break on a runner image refresh.

---

## Services and keys this PRD needs

| Service | Why | Env var | Provisioned? |
|---|---|---|---|
| OKX public market data | Primary spot OHLCV for all four assets; only venue with a `confirm` flag | none — unauthenticated | Yes, in use since PRD-001 |
| Coinbase Exchange public candles | Corroborating venue | none — unauthenticated | Yes, in use since PRD-003 |
| TA-Lib C library on the CI runner | Compute engine; the Python wheel needs it present | none | **No** — needs an install step in the workflow, and a pinned version |
| Supabase Postgres | Persist ~32 cells | existing | Yes |
| Healthchecks.io | Dead-man's-switch | existing | Yes |

No new paid service, no new key. The only new provisioning is the C library in CI.

---

## Open questions for the human

| # | Question | My committed hypothesis | What breaks if I'm wrong |
|---|---|---|---|
| 1 | What is `required_bars` for the recursive family? | **250, uniform, for RSI, ATR, MACD, StochRSI, and the EMA stack below 200.** It is a published operator's number rather than our derivation, it fits one unpaginated request at both venues, and it fits BNB's Coinbase history. | Too low and every value is quietly unconverged — the exact failure this PRD exists to prevent. Too high and BNB drops off the board and every fetch needs pagination. |
| 2 | Is EMA-200 in the "EMA stack"? | **No — cut it, or ship it only for BTC/ETH/SOL from OKX at N≈500.** At N=250 an SMA-seeded EMA-200 has undergone 50 recursions; residual seed weight is about 78%. That is not an EMA-200, it is an SMA-200 with noise. | Shipping it at 250 puts a cell on the board that is mislabelled rather than merely imprecise, which is worse than an absent cell by this product's own standard. |
| 3 | Which StochRSI convention? | **TradingView's (RSI 14, stoch 14, K 3, D 3), implemented as stochastic-of-RSI, not TA-Lib's `STOCHRSI` defaults.** It is the convention every external reference uses, so it is the only one an external golden can check. | Ship TA-Lib defaults and Option C's spot-check produces a false failure, and no published vector will ever match. |
| 4 | Does OBV go on the board, and as what? | **As an N-bar delta or slope, not the raw cumulative level**, and if that is unacceptable, cut OBV. | A raw cumulative OBV is window-origin-dependent, so it violates the spirit of the exactly-N contract while technically satisfying it. |
| 5 | Do derived indicators get corroborated the way prices do? | **No. Corroborate the input bars, not the output indicator.** Two venues' RSI will differ by more than 25 bps for legitimate microstructure reasons. Register indicators with an `uncorroborated.note` naming the corroborated bar series they are computed from. | Applying the 25 bps price tolerance to indicator outputs produces permanent, meaningless divergence on most of the ~32 cells. |
| 6 | Does BNB stay in scope given ~317 bars of Coinbase history? | **Yes, but with `definable_for` doing real work**: BNB indicators compute from OKX and corroborate against Coinbase only where the history reaches. | If BNB is silently included everywhere, the first EMA-200 or 500-bar indicator fails at runtime rather than at registry-load, which is the wrong boundary. |

---

## Blind spots

**1. The EMA-200 cell is the first structurally impossible cell, and the brief counts it in the ~32.** The brief promises an "EMA stack" across four assets. If that stack is 20/50/200, then at any N that BNB's Coinbase history can support, the 200 is dominated by its seed. The arithmetic is not close: the exactly-N contract, the 250-bar convergence figure, and a 200-period EMA cannot all three be satisfied. One of them has to give, and the honest answer is that the EMA-200 cell should not exist rather than exist wrong. This is the PRD's first real test of whether "better a smaller honest board" is a rule or a slogan — and it arrives on the cell most likely to be defended, because a missing 200-day EMA looks like an omission to anyone reading the board.

**2. The golden is a golden of a *tuple*, and only one element of that tuple is currently version-pinned.** A pinned value for RSI(14) is only meaningful as (indicator, parameters, N, TA-Lib C library version, wrapper version). The wrapper is in the lockfile. The C library is installed by a CI step and is not pinned anywhere in the repo today. When that step floats — and it will, on a runner image refresh — every golden fails at once, and the failure will look like a code regression rather than an environment change. Worse is the near-miss case: a patch-level C library change that moves one indicator by an amount inside epsilon. Then nothing fails, and the pinned number silently stops describing what the code does.

**3. The registry's `corroboration` field was designed for fetched values and this PRD hands it ~32 derived ones.** The existing entry corroborates `btc_daily_close` at 25 bps between two venues quoting the same instrument. An RSI is not fetched from anywhere; it is computed from bars that were themselves corroborated. The registry currently offers two shapes — `corroboration` or `uncorroborated.note` — and neither describes "this value inherits corroboration from its inputs." The likely path of least resistance is to write 32 `uncorroborated.note` entries saying roughly the same thing, at which point US-207's registry-generated coverage becomes 32 rows of boilerplate that nobody reads, which is precisely the "coverage becomes noise" outcome the brief flagged as risk #2. The registry needs a third shape before it needs 32 entries, not after.

---

## Sources

- https://ta-lib.org/functions/
- https://ta-lib.github.io/ta-lib-python/func_groups/momentum_indicators.html
- https://ta-lib.github.io/ta-lib-python/abstract.html
- https://ta-lib.github.io/ta-lib-python/doc_index.html
- https://github.com/TA-Lib/ta-lib-python/issues/664
- https://api.github.com/repos/TA-Lib/ta-lib-python/issues/469/comments
- https://pypi.org/project/TA-Lib/
- https://pypi.org/project/pandas-ta-classic/
- https://pypi.org/project/ta/
- https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-strength-index-rsi
- https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-true-range-atr
- https://www.bollingerbands.com/bollinger-band-rules
- https://www.tradingview.com/support/solutions/43000502333-stochastic-rsi-stoch-rsi/
- https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles
- https://api.exchange.coinbase.com/products/BNB-USD
- https://api.exchange.coinbase.com/products/BNB-USD/candles?granularity=86400&start=2025-09-01T00:00:00Z&end=2025-09-06T00:00:00Z
- https://api.exchange.coinbase.com/products/BNB-USD/candles?granularity=86400&start=2026-01-05T00:00:00Z&end=2026-01-09T00:00:00Z
- https://api.exchange.coinbase.com/products/BNB-USD/candles?granularity=86400&start=2025-10-28T00:00:00Z&end=2025-11-01T00:00:00Z
- https://www.okx.com/api/v5/market/history-candles?instId=BNB-USDT&bar=1Dutc&limit=2&after=1767225600000

Search-result derived, not directly fetched, and flagged as such above: the `TA_FUNC_UNST_*` enum membership list, the OKX ~1,440-candle ceiling (https://github.com/ccxt/ccxt/issues/20756), and the TA-Lib `ddof=0` equivalence for `BBANDS`.
