## What we already knew, and whether it still holds

The KB sections that were loaded (auth, hosting, CI/CD) cover only the platform layer: Cloudflare Pages/Access, GitHub Actions and Supabase. Nothing in PRD-008 changes that layer, so those notes still hold. The project-specific claims below are the ones that matter.

| Claim from our knowledge base / brief | Still true? | What the source says | Citation |
|---|---|---|---|
| FRED is free, keyed, 120 req/min | **Yes** | "Up to 120 requests per minute are allowed before being served a 429 error code. Not complying with the throttling can result in a temporary block." | https://fred.stlouisfed.org/docs/api/fred/errors.html |
| Brief: `DTWEXBGS` lags **1–3 business days** | **No, wrong** | The series is daily, but it is published in the **weekly** H.10 release. On 2026-09-27 the latest observation was 2026-09-18, updated 2026-09-21, and the next release is 2026-09-28. Just before each release the newest value is about 10 days old. Our own 2026-09-08 measurement of **11 days** (`15_Services_and_Credentials.md:44`) agrees with this; the brief's figure does not. | https://fred.stlouisfed.org/series/DTWEXBGS |
| `DTWEXBGS` is a broad, methodologically different index, not DXY | **Yes** | Title is "Nominal Broad U.S. Dollar Index", Index Jan 2006=100, source is the Fed Board. | https://fred.stlouisfed.org/series/DTWEXBGS |
| Brief: **M2 lags ~3–4 weeks**; Services doc: M2 **69 days** behind | **Both are "right", measured from different anchors** | The August 2026 observation (dated 2026-08-01) was published 2026-09-22. That is ~22 days after the month ended, but ~52 days after the date FRED stamps on the observation. The next release is 2026-10-27, by which point the value is ~87 days past its stamp. The 69-day figure measures from the observation date; the 3–4 week figure measures from the end of the period. The spec must choose one anchor (see Blind spots #1). | https://fred.stlouisfed.org/series/M2SL |
| Brief: **CPI lags ~5–6 weeks** | **Only from the observation date** | August 2026 CPI (dated 2026-08-01) was published 2026-09-11; the next release is 2026-10-14. That is 41 days after the observation date but only 11 days after the month ended. | https://fred.stlouisfed.org/series/CPIAUCSL |
| `SP500` / `NASDAQCOM` are clean FRED rows | **Partly wrong for SP500** | FRED carries only **10 years** of SP500 history, and the page says "Reproduction of S&P 500 in any form is prohibited except with the prior written permission of S&P Dow Jones Indices LLC." | https://fred.stlouisfed.org/series/SP500 |
| SoSoValue has a free Demo API at ~20 calls/min, "beta" | **Yes, with new constraints** | 20 req/min **and 100,000 requests/month** per key. A breach returns HTTP 429 with code `42901`. A key is required (`x-soso-api-key`). | https://sosovalue.gitbook.io/soso-value-api-doc/llms-full.txt |
| SoSoValue covers BTC/ETH ETF flows | **Yes, and more** | `/etfs/summary-history` `symbol` accepts `BTC, ETH, SOL, LTC, HBAR, XRP, DOGE, LINK, AVAX, DOT` with `country_code` `US` or `HK`. **SOL is covered. BNB is not in the API enum.** | https://sosovalue.gitbook.io/soso-value-api-doc/llms-full.txt |
| Services doc: SoSoValue "likely key on Demo tier" | **Confirmed** | Every call carries the `x-soso-api-key` header against base `https://openapi.sosovalue.com/openapi/v1`. | https://sosovalue.gitbook.io/soso-value-api-doc |
| DefiLlama stablecoins are free and keyless | **Yes** | The stablecoin endpoints are on the free tier. Only `/stablecoins/stablecoindominance/{chain}` is Pro ($300/mo). | https://api-docs.defillama.com/ |
| DefiLlama gives "BTC/ETH/SOL/BNB-relevant" stablecoin supply | **Only 3 of 4 assets** | `/stablecoinchains` returned 217 entries. Ethereum was ~$146.4B, Solana ~$16.4B, BSC ~$13.8B, Tron ~$94.0B. There is **no Bitcoin entry**. | https://stablecoins.llama.fi/stablecoinchains |
| alternative.me F&G: six sub-weights | **Yes, but one is dead** | Volatility 25%, momentum/volume 25%, social 15%, **surveys 15% "currently paused"**, dominance 10%, Google Trends 10%. The page requires attribution displayed alongside the data. | https://alternative.me/crypto/fear-and-greed-index/ |
| F&G API is free and keyless | **Yes** | Live response: `value` is a **string** (`"70"`), `timestamp` is unix seconds at 00:00 UTC, and `time_until_update` appears **only on the newest element**. | https://api.alternative.me/fng/?limit=2 |
| CoinGecko Demo: 100 calls/min, 10k/month | **Yes** | Demo plan is "10k call credits/mo", 100/min, "Attribution required". `/global` is cached "every 10 minutes". | https://www.coingecko.com/en/api/pricing, https://docs.coingecko.com/reference/crypto-global |
| Google Trends has no public API (R4's reason to omit it) | **Still holds** | Search results (not fetched) say the API is still an application-gated alpha as of Aug/Sep 2026, with no GA date. | Search hit: https://developers.google.com/search/blog/2025/07/trends-api (announcement, not fetched) |

## Existing implementations

- **This repo has already built the shape PRD-008 needs.** PRD-001's M2 cell (US-004) stores `referencePeriod` and `publishedAt` separately (`web/src/datapoint.ts:16-17`). Age is computed from publication, not from the reference period: `const publishedAt = datapoint.publishedAt ?? datapoint.sourceTimestamp` (`web/src/data.ts:255`). The verifier note in `.uf/state.json` confirms the cell renders both dates. PRD-008 should reuse this for every FRED row. It should not invent a second "lag" field.
- **FRED, as FRED documents it.** Most people call `fred/series/observations` once per series. The endpoint defaults are `realtime_start`/`realtime_end` = today, `sort_order=asc`, `limit` up to 100000, and `output_type` options include "Observations, Initial Release Only (4)" and "by Vintage Date" (https://fred.stlouisfed.org/docs/api/fred/series_observations.html). For bulk pulls FRED now also offers v2 `fred/v2/release/observations`, which returns "all series on a release in bulk and … the entire history" (https://fred.stlouisfed.org/docs/api/fred/v2/index.html).
- **SoSoValue v1 OpenAPI.** Endpoints are `GET /etfs/summary-history`, `GET /etfs`, `GET /etfs/{ticker}/market-snapshot` and `GET /etfs/{ticker}/history` (https://sosovalue.gitbook.io/soso-value-api-doc/2.-etf/etf.md).
  - Aggregate response fields: `date`, `total_net_inflow`, `total_value_traded`, `total_net_assets`, `cum_net_inflow`.
  - Per-ticker adds `net_inflow`, `cum_inflow`, `net_assets`, `prem_dsc` and `volume`.
  - Success envelope: `{"code":0,"message":"success","data":…}` (https://sosovalue.gitbook.io/soso-value-api-doc/llms-full.txt).
  - Search also turned up SoSoValue-API projects (github.com/markinho1970/sosomon, github.com/0xshubhs/AutoFund-AI) and an Apify ETF-flow scraper. **I did not fetch these**, so they are leads, not evidence.
- **DefiLlama.** Documented paths include `/stablecoins`, `/stablecoincharts/{chain}`, `/stablecoin/{asset}` and `/stablecoinchains` (https://api-docs.defillama.com/). The docs list them under `api.llama.fi`, but the legacy host `stablecoins.llama.fi` still answered live today (https://stablecoins.llama.fi/stablecoinchains).

## Approach options

**A. One generic FRED fetcher driven by a series registry, plus one thin fetcher each for SoSoValue, DefiLlama and alternative.me.**
- **How it works:** A pydantic registry row holds `series_id`, display name, release cadence, reference-period semantics and disclosure text. One fetcher calls `series/observations` for each row.
- **Trade-offs:** Adding or removing a macro row becomes a config change, so the "10 rows is a scope jump" worry turns into a story-count-neutral decision.
- **Cost:** $0. About 7 FRED calls per run, well under 120/min.
- **Who uses it:** This is how PRD-006/007 were built.

**B. FRED v2 bulk pull by release** (H.10, H.6, H.15, CPI).
- **How it works:** Fewer calls, each returning full history.
- **Trade-offs:** Each release returns every series on it, most of which we discard. It ties ingest to release IDs instead of series IDs, and it is newer and less trodden.
- **Cost:** $0.
- **When it helps:** Only for a one-off backfill.

**C. Go to the originating publishers** (NY Fed for SOFR/EFFR, BLS for CPI, Fed Board for H.6/H.10) instead of FRED.
- **How it works:** One integration per publisher.
- **Trade-offs:** Better native publication-date metadata. But it means 3–4 more integrations, formats and possibly keys, all for numbers FRED mirrors.
- **Where it fits:** As a *transport* cross-check later, not as primary.

**D. Scrape Farside for ETF flows.**
- **Trade-offs:** R4 found it is HTML-only and returned 403 to automated fetches. It repeats the prior system's scrape fragility.
- **Verdict:** Rejected.

**Recommendation: A.** It turns the brief's biggest scope question (which macro rows) into registry config instead of stories, and it reuses the `referencePeriod`/`publishedAt` datapoint that already exists.

## Edge cases and gotchas

1. **"Lag" has three anchors and the numbers disagree by 30+ days.** The anchors are the observation `date` (FRED stamps monthly series with the first day of the month), the end of the period, and the publication date. The M2 example is the clearest: 22, 52 or 87 days depending on the anchor and on where you are in the release cycle (https://fred.stlouisfed.org/series/M2SL). An acceptance criterion like "M2 shows ~3–4 week lag" will be judged against whichever anchor the implementer happens to pick. The spec must say the face shows the **reference period** plus the **published date**, which is the existing US-004 pattern.
2. **`DTWEXBGS` staleness follows a weekly sawtooth, not a daily one.** A fixed "stale after 3 days" threshold turns this row red every week, by design (https://fred.stlouisfed.org/series/DTWEXBGS). Staleness thresholds must come from each series' **release cadence** (weekly, monthly, daily), not from its observation frequency.
3. **UNVERIFIED — naive `realtime_start` makes everything look published today.** With default parameters, each observation's `realtime_start` equals the request's `realtime_start`, which defaults to today (https://fred.stlouisfed.org/docs/api/fred/series_observations.html). Reading it as the "published at" date would stamp CPI as published today. The real publication date needs `output_type=4` with an early `realtime_start`, or `fred/series` `last_updated`, or release dates. Confirm with a live probe before a story commits to a field.
4. **UNVERIFIED — FRED returns `"."` for missing observations** (holidays, market closures on `VIXCLS`/`SP500`). Coercing `"."` to 0 or NaN-then-0 breaks the project's "never `0`" rule. It should skip to the last real observation, and the face should show that observation's date. Relatedly, the Services doc measured **DFF as 5 days behind on 2026-09-08**, the day after Labor Day, so holidays alone can blow through a naive "next-day" threshold.
5. **SoSoValue only returns the last month of history.** `start_date`/`end_date` say "Only the most recent 1 month is supported" (https://sosovalue.gitbook.io/soso-value-api-doc/llms-full.txt). There is no backfill: an ETF-flow history chart only grows from the first ingest, and any outage longer than ~30 days leaves a gap that can never be refilled. The docs also say `limit` "max 300", which contradicts the one-month window; probe it live.
6. **SoSoValue has a monthly quota as well as a per-minute one.** 100,000 requests/month is ~3,300/day. That is fine at daily cadence, but it gets eaten quickly if ETF rows are mistakenly put on the 5-minute `ingest-fast` tier from PRD-012 (the T+1 data doesn't change intraday anyway).
7. **A zero ETF flow is a real, reported value.** Per-ticker `net_inflow` of 0 is common on quiet days. The "never render `0`" rule is about *unavailable* values; it must not turn a reported zero into `UNAVAILABLE`. Stories need separate "reported zero" and "missing" test cases.
8. **ETF dates follow the US trading calendar.** On Monday, "yesterday's flow" is Friday's, and there is nothing at all on US market holidays. An age check that is not trading-day aware will flag every Monday as stale. Worse, it might relabel Friday's flow as Sunday's.
9. **SoSoValue returns money as long-decimal numbers** (e.g. `-55066297.0000000000000000`, `13534833596.0950000000000000`). Parse them with `Decimal` or a pydantic condecimal, not float, or the PRD-002 determinism golden files will drift.
10. **Don't hit DefiLlama's per-asset endpoint on a schedule.** `stablecoins.llama.fi/stablecoin/1` (USDT) is **larger than 10 MB**: my fetch failed with "maxContentLength size of 10485760 exceeded". Pulling it every run is a wall-clock and egress risk, which is exactly the "credit budget ok, timeout blown" lesson already in our KB. Use `/stablecoinchains` (small, current totals) or `/stablecoincharts/{chain}`.
11. **DefiLlama chain names are not asset names.** It's `BSC`, not `BNB`, and there is no `Bitcoin` entry (https://stablecoins.llama.fi/stablecoinchains). So the BTC column must render `UNAVAILABLE` with a reason, never a global total dressed up as "BTC". Also, `totalCirculatingUSD` has sub-keys (`peggedUSD`, and other pegs). Choose "USD-pegged only" versus "all pegs" explicitly and put that choice in `source_field`.
12. **F&G: string values, and a 15% weight that no longer exists.** The value is a string, and `time_until_update` appears only on the latest row (https://api.alternative.me/fng/?limit=2). The site still lists surveys at 15% while marking them "currently paused" (https://alternative.me/crypto/fear-and-greed-index/). **UNVERIFIED** how the remaining weights are renormalized. The disclosure on the face should not repeat the published weights as though all six are live.
13. **UNVERIFIED — the FRED key leaks through the URL.** FRED takes `api_key` as a query parameter. httpx's `HTTPStatusError` message and structlog request logging include the full URL, so the key ends up in public Actions logs unless it is redacted.

## Services and keys this PRD needs

| Service | Why | Env var | Already provisioned? |
|---|---|---|---|
| FRED | Macro rows | `FRED_API_KEY` | **Locally yes.** Marked READY in `15_Services_and_Credentials.md:44`, reused from `crypto-investing-signals`. **Also verify it exists as a GitHub Actions secret and that the workflow passes it** (the KB's "CI never ran it" lesson). |
| SoSoValue OpenAPI | ETF net flows (T+1) | `SOSOVALUE_API_KEY` (proposed name) | **No.** Needs sign-up at sosovalue.com/developer, plus a GH Actions secret. |
| DefiLlama | Stablecoin supply per chain | none | N/A, keyless (verified live today) |
| alternative.me | Fear & Greed | none | N/A, keyless (verified live today and in the US-011 reachability CI run) |
| CoinGecko Demo | BTC dominance, **only if in scope** | `COINGECKO_DEMO_API_KEY` (proposed) | **No.** Recommended out of scope; see open questions. |

## Open questions for the human

Ranked by decision impact.

| # | Question | My committed hypothesis | What breaks if I'm wrong |
|---|---|---|---|
| 1 | Which lag anchor goes on the cell face? | Show **reference period** ("Aug 2026") and **published date** ("published Sep 22"). Compute staleness from the published date against each series' release cadence. Never show a single "N days lag" number. | If you want one number, every lag criterion in the brief (3–4 wk, 5–6 wk, 1–3 d) has to be restated. As written, two of them fail against live data. |
| 2 | Which FRED rows ship in PRD-008? | **Seven rows:** `VIXCLS`, `DFF`, `T10Y2Y`, `DFII10`, `DTWEXBGS`, `CPIAUCSL`, `M2SL`. Together they span daily, weekly and monthly releases, which is the whole adversarial case. **Defer** `SP500` (copyright plus 10-year cap), `NASDAQCOM` (drop with SP500 for symmetry), `SOFR` (near-duplicate of DFF for display) and `FEDFUNDS` (monthly average of DFF). | If you want equity indices, the S&P licence line needs a decision first. More rows cost almost nothing under the registry approach, so this is about scope and honesty, not story count. |
| 3 | ETF flows: which assets? | **BTC, ETH, SOL** (US), all present in the SoSoValue API enum. **BNB renders `UNAVAILABLE`** with the reason "not offered by SoSoValue API". The website has a `us-bnb-spot` page (search result, not fetched), but the API symbol list has no BNB. | If a BNB ETF exists and you want it, we need a second source (Farside scrape or a paid feed), which reopens the scraping question. |
| 4 | Stablecoin supply: per-chain or global? | Per-chain `peggedUSD` for **Ethereum, Solana, BSC**. The BTC column is `UNAVAILABLE` ("no stablecoin supply tracked on Bitcoin"). No global total row in this PRD. | A global total would be dominated by Tron (~$94B), a chain this board doesn't track. Showing it without that context invites misreading. |
| 5 | Does BTC dominance ship? | **No, defer to a later PRD or leave it out permanently.** It needs a new key and a UI attribution requirement. It is methodology-sensitive (stablecoins inside total market cap). And F&G already folds dominance in as 10%, so showing both edges toward the "counted twice" pattern. | If it ships, add the CoinGecko key, an attribution element, and a single-provider-only rule (R4 §3). |
| 6 | Which cadence tier? | All PRD-008 rows go on the **slow** tier from PRD-012. Nothing here changes intraday. | On the fast tier we burn the SoSoValue monthly quota (~8,640 calls/month for one ticker at 5-minute cadence, multiplied across tickers) for zero new data. |
| 7 | Corroboration for FRED rows? | Ship them `uncorroborated`. FRED mirrors the Fed/BLS, so "corroborating" DFF against the NY Fed checks a mirror against its origin: it catches transport bugs, not source errors. Label it that way if it is ever added. | If G1 requires corroboration, we need Option C integrations: 2–3 more stories. |

## Blind spots

1. **Revisions will fight the determinism harness.** CPI (seasonally adjusted) is revised as seasonal factors are recalculated, and M2 has been restated after H.6 methodology changes (R4 §2; M2SL page notes methodology changes, https://fred.stlouisfed.org/series/M2SL). When a value changes under the *same* observation date, it will look like non-determinism to PRD-002's golden files, or it will be silently overwritten by an upsert. Nobody decided whether a revision is shown ("revised from X") or swallowed. Swallowing it is exactly the quiet dishonesty this project exists to prevent.
2. **The FRED key is shared with another project.** It was "reused from `crypto-investing-signals`". The 120/min limit is **per key**, and FRED warns that "not complying with the throttling can result in a temporary block" (https://fred.stlouisfed.org/docs/api/fred/errors.html). A burst from the *other* project can take every macro row on this board to `UNAVAILABLE`, and the error will look like ours. Issue a dedicated key (instant, free).
3. **Attribution and licensing are UI requirements, and nobody has written them as criteria.** alternative.me requires attribution displayed next to the data (https://alternative.me/crypto/fear-and-greed-index/). CoinGecko Demo requires it if dominance ever ships (https://www.coingecko.com/en/api/pricing). S&P prohibits reproduction without permission (https://fred.stlouisfed.org/series/SP500). Cloudflare Access keeps the audience to one person, which lowers exposure. But the F&G attribution belongs on the cell's face anyway, and the brief's own adversarial case #3 half-covers it. Make it an explicit criterion so a verifier can grep for it.

## Sources

Fetched:
- https://fred.stlouisfed.org/series/DTWEXBGS
- https://fred.stlouisfed.org/series/M2SL
- https://fred.stlouisfed.org/series/CPIAUCSL
- https://fred.stlouisfed.org/series/SP500
- https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- https://fred.stlouisfed.org/docs/api/fred/errors.html
- https://fred.stlouisfed.org/docs/api/fred/v2/index.html
- https://sosovalue.gitbook.io/soso-value-api-doc
- https://sosovalue.gitbook.io/soso-value-api-doc/2.-etf/etf.md
- https://sosovalue.gitbook.io/soso-value-api-doc/llms-full.txt
- https://api-docs.defillama.com/
- https://stablecoins.llama.fi/stablecoinchains
- https://stablecoins.llama.fi/stablecoin/1 (fetch failed: response larger than 10 MB, cited as evidence for gotcha #10)
- https://alternative.me/crypto/fear-and-greed-index/
- https://api.alternative.me/fng/?limit=2
- https://docs.coingecko.com/reference/crypto-global
- https://www.coingecko.com/en/api/pricing

Surfaced by search only (not fetched, not relied on for any claim above):
- https://developers.google.com/search/blog/2025/07/trends-api
- https://sosovalue.com/assets/etf/us-bnb-spot
- https://sosovalue.com/developer
- https://github.com/markinho1970/sosomon
- https://github.com/0xshubhs/AutoFund-AI
- https://apify.com/gochujang/crypto-etf-flow-tracker/api/openapi
