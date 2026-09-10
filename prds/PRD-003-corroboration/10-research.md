# PRD-003 · Research — Cross-source corroboration

Research stage only. Nothing here is a decision; `20-decisions.yaml` (gate G1) is where these become commitments.

---

## What we already knew, and whether it still holds

| Claim in our knowledge base | Still true? | What the source says | Citation |
|---|---|---|---|
| OKX `bar=1D` is UTC+8; use `bar=1Dutc`, and assert `hour==minute==second==0` on the daily timestamp | **Holds, and generalises** | Not re-checked against OKX docs this round — it is already encoded in `ingest/registry.yaml:3` and was measured on this project. What *is* new: the same silence exists at the second venue. Coinbase's candles reference documents `granularity` values and the response schema but says **nothing** about how the 86400 bucket is aligned. The assertion must therefore be repeated per venue, not inherited. | https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles |
| R3: "OKX is the only venue found that explicitly flags a closed candle" | **Holds, but needs a footnote** | Kraken does not flag closure, but it *documents a positional guarantee* that is nearly as strong: "The last entry in the OHLC array is for the current, not-yet-committed timeframe, and will always be present, regardless of the value of `since`." Dropping the last element is a documented contract on Kraken, not a guess. Coinbase documents no equivalent — neither a flag nor a positional rule. | https://docs.kraken.com/api/docs/rest-api/get-ohlc-data |
| Binance returns 451 and Bybit 403 from GitHub-hosted US runners | **Holds, and it decides this PRD** | Project measurement, unchanged. Consequence not previously written down: the obvious corroborating venue for spot BTC is unavailable, so the second source is **Coinbase or Kraken**, and that is forced, not chosen. | `prds/PRD-001-spine/50-evidence/US-011/reachability-ci.json` |
| Measured spread: median 7.1 bps, p90 10.8, max 13.8 over 59 days; the `bar=1D` defect was 35.2 bps | Holds — project measurement, not web-checkable | Worth an external anchor: Coin Metrics excludes a constituent market from its reference rate when that market's VWAP "sits more than 3 percent from the median". **300 bps.** Our proposed tolerance is roughly one-fifteenth of the loosest shipped equivalent, because they are resolving and we are reporting. Expect it to fire more often than intuition suggests. | https://gitbook-docs.coinmetrics.io/coin-metrics-prices/coin-metrics-prices/reference-rate-metrics |
| The 7.1 bps median contains the USDT peg basis, so tolerance must be per-pair | **Holds** | Both candidate venues also list a USDT-quoted BTC pair (Kraken `XBTUSDT`, Coinbase `BTC-USDT`), so a like-for-like comparison is technically available. That makes this a live choice rather than a constraint. Availability came from search results I did not fetch — verify the pair id against the products endpoint before committing it to the registry. | search-derived, unverified |
| `[cmd:]` truncates at the first `]`; `[ci:]` is unsatisfiable; a skipped test passes a gate; G5 answers don't restore attempts; bold PRD ids blind `uf next` | **All hold, and three of the five bite here** | Any acceptance criterion that indexes a candle array contains `]`. Any criterion that proves corroboration against a live venue can skip when the network is absent. Both are pre-existing traps aimed squarely at this PRD's story shape. | project knowledge base |

**Not covered by our knowledge base at all:** the response field ordering difference between venues, the "no candle published when there were no ticks" behaviour, and the fact that `datapoints` cannot currently hold two venues for one quantity. Those are below.

---

## Existing implementations

Three systems ship this problem in production. All three are informative, and **two of them do the exact thing this PRD forbids.**

**Pyth Network — disagreement is the output.** Each publisher submits a price plus its own confidence interval. The aggregate price is the median of three votes per publisher (the price, and both confidence bounds). The aggregate confidence half-width is then the larger of the distances from the aggregate to the 25th and 75th percentile votes. The design goal is stated explicitly: when a product trades at different prices on different exchanges, "the aggregate confidence interval should widen out to reflect the variation between these prices" (https://docs.pyth.network/price-feeds/core/how-pyth-works/price-aggregation). Consumers are told never to trust the point estimate alone — value collateral at the lower bound, borrowed assets at the upper bound, and "decide that there is too much uncertainty when `σ/μ` exceeds some threshold and choose to pause any new activity" (https://docs.pyth.network/price-feeds/core/best-practices).

This is the closest shipped analogue to what the brief asks for. It also independently arrives at the brief's key move: the dispersion travels *with* the number to the consumer, and the consumer applies the threshold. It differs in one respect worth noting — Pyth publishes a half-width, not two named venues, so a Pyth consumer cannot tell *which* publisher was wrong.

**Chainlink — the disagreement is a trigger, and is then discarded.** A feed updates when off-chain values deviate from the on-chain value by more than a configured deviation threshold, or when a heartbeat timer expires; "the first condition that is met triggers an update." Node responses are combined by an aggregator contract into one answer (https://docs.chain.link/architecture-overview/architecture-decentralized-model). The documentation does not describe publishing the spread between node responses on-chain. Deviation is plumbing here, not a finding.

**Coin Metrics — the disagreement is an exclusion criterion, and is then discarded.** Constituent market selection removes markets "whose volume-weighted average price sits more than 3 percent from the median." At real-time frequency the weighted median uses inverse price variance, so "a venue printing an outlier price gets a high variance and therefore a small weight." Missing data is filled: "an interval with no transactions borrows the next interval's price, applied recursively," and inactive markets are dropped. The documentation publishes no dispersion or deviation measure alongside the rate (https://gitbook-docs.coinmetrics.io/coin-metrics-prices/coin-metrics-prices/reference-rate-metrics).

Note the second-order consequence for us: **Coin Metrics MVRV is not merely uncorroborated, it is a resolved consolidation of many venues whose disagreement has already been thrown away by someone else.** Marking it "uncorroborated" is correct but understates the situation.

**For this stack specifically** (Python fetchers, a YAML registry, a Postgres row with provenance), the generic data-engineering literature calls this reconciliation with a tolerance producing a "break" for investigation, and the tooling is enterprise ETL validators rather than anything reusable here (https://icedq.com/data-reconciliation-tool). There is no library to adopt. This is fifty lines of our own code, and the value is entirely in where the divergence is stored and what the page does with it.

---

## Approach options

The constraint that shapes all of these, found by reading `ingest/persist.py:66-73`: the existing upsert identity is `(indicator_key, asset, source_timestamp)`. **Two venues written under one `indicator_key` collide — the second write silently UPDATEs the first.** Any option that ignores this loses one of the two numbers with no error.

### Option A — One row, primary plus secondary columns
Add `value_secondary`, `secondary_vendor`, `secondary_endpoint`, `divergence_bps`, `corroboration` to `datapoints`. The existing identity and upsert logic are untouched.

- **Trade-offs:** Smallest migration, and PRD-002's determinism harness keeps working unchanged. But the schema itself says "primary" and "secondary", which is the vocabulary of preference. The first person who wants a single number will reach for `value` and be structurally encouraged to. The brief names this exact failure.
- **Cost:** One migration, no change to persist logic.
- **Who uses it:** the common in-house shape — a canonical field with a cross-check bolted on.

### Option B — One row per venue, identity extended with `source_vendor`
Migrate the unique key to `(indicator_key, asset, source_vendor, source_timestamp)`. Both venues are peers. A small `corroborations` table (or extra columns on neither row) holds `divergence_bps`, `tolerance_bps_at_write`, and the two row ids.

- **Trade-offs:** No preference is expressible in the schema, which is the point. Costs a change to the upsert identity and advisory-lock key that PRD-001 and PRD-002 already proved, so the contract harness must be re-run rather than assumed. The page needs a join.
- **Cost:** One migration plus edits to `persist_datapoint`; PRD-002's golden and contract tests re-verify it.
- **Who uses it:** Pyth's model, restructured for a relational store — publishers are peers and the dispersion is a separate published quantity.

### Option C — Two registry keys, no schema change
Register `btc_daily_close_okx` and `btc_daily_close_coinbase` as separate indicators. No collision, no migration. Divergence computed and stored as a third registry entry, or in a view.

- **Trade-offs:** Zero migration risk. But it dissolves the concept the PRD is about: nothing in the data says these two rows are measuring the same thing, so the relationship lives only in the code that happens to compare them. Registry coverage (US-207) would count three indicators where there is one quantity.
- **Cost:** Two YAML entries.
- **Who uses it:** nobody deliberately; it is what a codebase drifts into.

### Option D — Pyth-style: one value plus a confidence half-width
Store `value` and `confidence_bps`, discard venue identity.

- **Trade-offs:** Matches a genuinely shipped design and is compact. Rejected here: with only two sources the half-width *is* the spread, so it adds no information and removes the ability to say which venue said what. Diagnosing the `bar=1D` defect required knowing which side was 78,834.1.

**Recommended: Option B.** It is the only one where the schema cannot express a preference, and the brief's central risk is that a preference gets expressed later by someone who did not read the brief. Pay the migration once, while PRD-002's harness exists to verify it.

One detail that belongs in the spec regardless of option: **store the tolerance that was in force at write time.** A view that recomputes "was this in tolerance?" against the current registry retroactively re-judges every historical row whenever a tolerance is edited, which quietly rewrites the past to agree with the present.

---

## Edge cases and gotchas

**1. The two venues do not agree on array field order, and index 4 agrees by luck.** OKX candles are `[ts, open, high, low, close, …]`; our fetcher reads `newest[4]` for close (`ingest/fetchers/okx.py:93`). Coinbase's schema is documented as `[time, low, high, open, close, volume]` — low and high before open (https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles). Kraken's is `[timestamp, open, high, low, close, vwap, volume, count]` (https://docs.kraken.com/api/docs/rest-api/get-ohlc-data). Close lands at index 4 on all three, so a naive port *works* — and then the first person to generalise the fetcher to also read high and low silently swaps them on Coinbase. Never index positionally across venues; name the fields per venue in the registry as `source_field` already does.

**2. Our OKX fetcher converts bucket-start to bucket-end; Coinbase and Kraken return bucket-start.** `ingest/fetchers/okx.py:84-85` adds `timedelta(days=1)` after parsing the OKX timestamp. Coinbase documents its first element as "Bucket start time". If the second fetcher does not apply the identical convention, corroboration compares day *N* to day *N+1* **every single run**, and reports the day's price move as a divergence. On a quiet day that looks like a plausible 20 bps disagreement, which is worse than an obvious failure.

**3. Timestamp equality must gate the value comparison, not accompany it.** Compare `source_timestamp` first and refuse to compute a divergence unless they are equal. Two different days compared numerically produce a real-looking number. This is also the assertion that would have caught the original defect at the second venue.

**4. Kraken's last bar is always the live, unclosed one.** Documented: "will always be present, regardless of the value of `since`." Comparing a settled OKX day against a partially-formed Kraken day gives a divergence that is large at 01:00 UTC and near zero at 23:59 UTC. The check then looks *flaky* rather than *wrong*, and flaky checks get their thresholds widened. If Kraken is chosen, dropping the final element is mandatory and should be its own asserted criterion.

**5. Coinbase publishes no candle at all when there were no ticks, and warns that "historical rate data may be incomplete."** So "the second venue has no bar for this day" is a **third outcome**, distinct from a value and from a fetch failure. If it degrades to a fetch error, the dead-man's-switch fires on a non-event; if it degrades to zero, the divergence is 10,000 bps and the page screams.

**6. Coinbase's docs are silent on 86400 bucket alignment.** This PRD exists because a venue's undocumented bucket alignment was assumed. Do not assume the second one. Assert `hour==minute==second==0` per venue independently, in a test, as the registry note for `btc_daily_close` already requires for OKX.

**7. A shared bug in the comparison layer is invisible to corroboration.** If our own code applies the same wrong offset to both venues, the divergence is exactly zero and the check reports agreement. Corroboration defends against a wrong number at *one* source, not against a wrong number in the code that reads both. The per-venue UTC-alignment assertion is the only thing standing between us and that, which is why item 6 is not optional.

**8. Coinbase explicitly says its candle endpoint should not be polled frequently**, and GitHub-hosted runners share egress IPs with every other Actions user, so an IP-scoped public rate limit is not ours alone. I fetched https://docs.cdp.coinbase.com/exchange/docs/rate-limits and it did not contain the numeric limits — that is a gap, not an answer. Regardless of the number, a 429 from the second venue must produce **uncorroborated**, never a divergence and never a silent pass.

**9. `UNCORROBORATED` must be a stored value, not a NULL.** A NULL `divergence_bps` is indistinguishable in careless SQL from a computed zero and from "the corroboration step has not run yet". Those are three different facts and one of them is a bug.

**10. Divergence must not overload `status`.** Adding `DIVERGED` to the `Ok | Stale | Unavailable | Error` union in `ingest/status.py` would make a diverged-but-fresh row lose its freshness information — a row can be simultaneously stale and corroborated, or fresh and diverged. Corroboration is a second axis.

**11. The adversarial case needs an injection seam.** "Feed two venues that disagree beyond tolerance" is impossible if fetchers hardcode live URLs. `run_pipeline` already accepts `fetcher` as a parameter (`ingest/pipeline.py:15`) — extend that shape to a pair of callables rather than reaching around it with monkeypatching, or the proof of the PRD's central requirement will itself be untrustworthy.

**12. Two known `uf` traps aim directly at this PRD's stories.** Any `[cmd:]` criterion that indexes a candle array contains `]` and will be truncated mid-expression and then run, testing nothing. Put every comparison in a script file. And any test that reaches a live venue can skip when the network is absent, and a skip passes the gate — make the fixture raise.

---

## Services and keys this PRD needs

| Service | Why this PRD needs it | Env var | Already ready? |
|---|---|---|---|
| Coinbase Exchange public REST | Candidate second venue for `btc_daily_close`; the 59-day measurement was taken against it | none — public endpoint, unauthenticated | Yes. Measured 200 from a GitHub-hosted runner in US-011 |
| Kraken public REST | Alternative second venue | none — public endpoint, unauthenticated | Yes. Measured 200 from a GitHub-hosted runner in US-011 |

No new credentials. No new provisioning. Nothing in this PRD can halt at 2am waiting for a human to click something.

---

## Open questions for the human

| # | Question | My hypothesis | Impact if I am wrong |
|---|---|---|---|
| 1 | Which second venue for `btc_daily_close` — Coinbase or Kraken? | **Coinbase.** The 13.8 bps max is a measured property of *OKX `BTC-USDT` against Coinbase `BTC-USD` over 59 specific days*. Choosing Kraken discards the only evidence we have and leaves the tolerance guessed, which the brief forbids. | The tolerance ships with no measurement behind it. Every later argument about whether a finding is real has no baseline to appeal to. |
| 2 | Same instrument on both venues (`BTC-USDT` vs `BTC-USDT`) or deliberately different (`BTC-USDT` vs `BTC-USD`)? | **Deliberately different.** Two USDT-quoted pairs share a failure mode — they would agree perfectly through a USDT depeg while both being wrong about dollars. Keeping USD on one side means the peg basis is inside the tolerance, and a peg event fires the flag. That firing is *correct*: the stored number really has stopped being a dollar price. | If wrong, the check fires on peg wobbles the human considers noise, the tolerance gets widened to silence them, and it widens past the 35.2 bps defect. That is how this defence dies. |
| 3 | What tolerance for `btc_daily_close`? | **20 bps.** 1.45× the observed max (13.8) and 0.57× the measured defect (35.2) — inside the empty gap, biased toward the noise floor because a false finding costs a human glance and a missed one costs a wrong number. | Too tight: routine findings, and the flag becomes wallpaper. Too loose: a smaller-magnitude version of the same class of bug passes. |
| 4 | Schema shape — Option A, B, or C above? | **Option B**, one row per venue, identity extended with `source_vendor`. The migration cost is real but it is the only shape where "primary wins" cannot be written without a schema change. | Option A ships faster and the reconciliation creeps back in six months from now, in a one-line change nobody reviews as a policy decision. |
| 5 | When divergence exceeds tolerance, what does the page do with the number? | **Show both numbers and the spread. Never suppress, never blank.** Suppression is resolution wearing a different hat, and it deletes the evidence a human needs to work out which venue is wrong. | If the page suppresses, the product silently loses data on exactly the days it matters most. |
| 6 | Does divergence change `status`, or is it a separate field? | **Separate field.** A row can be stale *and* corroborated, or fresh *and* diverged. Collapsing them destroys one of the two facts. | Overloading `status` breaks PRD-001's discriminated-union render contract and forces the frontend to represent two axes with one enum. |
| 7 | What is the committed procedure for changing a tolerance? | **A commit that edits the registry value and adds the measurement justifying it, in the same commit, with the measurement window stated.** The brief already bans automatic tuning; this makes manual tuning auditable. | Without a written procedure, "no automatic threshold tuning" is satisfied in letter while a human tunes it after every inconvenient finding. |

---

## Blind spots

**1. The 59-day measurement window is a sample, and its maximum is a lower bound on the true maximum.** Thirteen point eight basis points is the worst disagreement observed in one calm stretch of one year, not the worst that can occur. The first genuine market dislocation — a venue outage, a thin-liquidity weekend, a peg event — will produce an honest disagreement above 20 bps, and the finding will look like a false positive because it will not correspond to any bug. The human will then be under pressure to widen the tolerance, having just watched it "fail". **Decide now, while nothing is on fire, what evidence would justify widening it** — and note that Coin Metrics' shipped exclusion band of 300 bps exists precisely because honest cross-venue disagreement gets much larger than 13.8 bps sometimes.

**2. The page will still show one number, and the human's eye goes to numbers, not badges.** "Disagreement is the output" is satisfied by storing both values and a red flag. But if OKX is the wrong side, the layout still puts a wrong figure in front of a reader, decorated. The `bar=1D` defect was caught because a human read a *timestamp*, not because a badge was red. Consider whether a divergent indicator should render as a *pair* rather than a value-with-annotation — that is a rendering question PRD-005 owns, but the shape of the stored row decides whether PRD-005 is *able* to do it. Getting Option B's schema right is what keeps that door open.

**3. `UNCORROBORATED` is the marking most likely to rot, and it rots by succeeding.** MVRV is genuinely uncorroborated on day one and the badge is honest. By the third new indicator, finding a second venue is an afternoon of work and marking it uncorroborated is thirty seconds, so the default drifts. Within a quarter the badge means "we did not try" and reads identically to "we tried and there is no second source" — at which point it conveys nothing and the page has a decorative honesty indicator. **Make the absence cost a sentence:** require a registry field naming why no second source exists for that specific quantity, so the cheap path is writing the reason rather than omitting one. This is the same mechanism as question 7 — the defences in this product all die the same way, by a human taking the fast option once.

---

## Sources

Fetched and read:

- https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles
- https://docs.kraken.com/api/docs/rest-api/get-ohlc-data
- https://docs.pyth.network/price-feeds/core/how-pyth-works/price-aggregation
- https://docs.pyth.network/price-feeds/core/best-practices
- https://gitbook-docs.coinmetrics.io/coin-metrics-prices/coin-metrics-prices/reference-rate-metrics
- https://docs.chain.link/architecture-overview/architecture-decentralized-model
- https://docs.cdp.coinbase.com/exchange/docs/rate-limits — fetched; did **not** contain the numeric rate limits. Recorded as a gap.
- https://docs.coinmetrics.io/methodologies/reference-rates — 404; superseded by the gitbook URL above.
- https://icedq.com/data-reconciliation-tool — general reconciliation vocabulary only; nothing stack-specific.

Search results referenced but not fetched, and flagged as such in the text: Kraken `XBTUSDT` and Coinbase `BTC-USDT` pair availability; USDT peg-drift magnitudes.
