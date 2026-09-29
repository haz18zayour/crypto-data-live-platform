# PRD-010 · Research: integrity dashboard

## What we already knew, and whether it still holds

Most of what we inlined is a generic Testing & QA tool survey. It is only partly relevant here. The project lessons from earlier PRDs matter more, and all of them still apply.

| Claim from our knowledge base | Still true? | What the source says | Citation |
|---|---|---|---|
| Vitest for Vite/TS projects, pytest for Python: "free OSS runners cover ~90%" | **Yes** | Nothing we fetched contradicts it. The repo already runs `vitest run` and pytest. | repo `web/package.json:11` |
| A test suite plus the TS type system can make "an unwired indicator fails the build" | **Only partly. This is the main correction.** | Vite "only performs transpilation on `.ts` files and does **NOT** perform type checking", so a failing type check has to come from `tsc`. Our build script is already `tsc -b && vite build` (`web/package.json:8`), so type errors do stop the build. But `web/src/registry.ts:3,23` loads `registry.yaml?raw` and runs `parse()` **at runtime**. That makes every indicator key a plain `string` to the compiler, so no mapped-type exhaustiveness trick can see a new registry key. | https://vite.dev/guide/features |
| Exhaustive `Record` / mapped types catch missing keys at compile time | **Yes, but only if the key is a literal union** | `type EnumRecord<K extends string, V> = {[key in K]: V}` gives a compile error when a member is missing. That only works when `K` is a literal union known at compile time, not the output of a runtime YAML parse. | https://www.richinfante.com/2024/04/06/ts-enum-record-required-keys |
| Lesson: "a migration passing its tests ≠ production touched" | **Yes, and it applies directly** | Any new `datapoint_status` value or integrity view is a migration. Migrations are blast-radius changes and need a separate, owner-approved production apply. Postgres also cannot drop an enum value once added, and a value added with `ADD VALUE` inside a transaction "cannot be used until after the transaction has been committed". | https://www.postgresql.org/docs/current/sql-altertype.html |
| Lesson: "real-Postgres throwaway-schema tests are UNMARKED" | **Yes** | This applies to every frozen-detection view or RPC test in this PRD. | project lesson |
| Lesson: "CI can silently never test what the green check implies" | **Yes, and stronger here** | A freshness rollup built from run logs inherits GitHub's scheduling behaviour. GitHub says `schedule` runs are "delayed during periods of high loads… some queued jobs may be dropped". The rollup has to be computed from the data, not from workflow runs. | https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows |
| (Not held) How to detect frozen values | **Gap** | Nothing in our knowledge base covers this. See the sections below. | — |

## Existing implementations

**Freshness SLAs (a solved pattern).** dbt source freshness is the reference design. Each source gets `warn_after` / `error_after` thresholds, `max(loaded_at_field)` is compared against them, and the result is pass, warn or error. dbt's docs stress that `loaded_at_field` must be normalised to UTC. For views, a `loaded_at_field` is **required** because "views don't expose row-level metadata" (https://docs.getdbt.com/reference/resource-properties/freshness). Soda Core uses the same shape, `freshness(col): warn: when > 6h, fail: when > 24h`, on Postgres (UNVERIFIED: this comes from search-result summaries, not a fetched page). We already have this model: `freshness_warn_seconds` / `freshness_stale_seconds` per indicator (`ingest/registry.py:124-125`), checked against `source_timestamp` (`ingest/pipeline.py:772`). The rollup is an aggregation over logic we already have, not a new mechanism.

**Frozen values (a partly solved pattern).** Two published approaches:
- **Zero variance over a run of N points.** An air-quality pipeline flags `STUCK_SENSOR` "when variance σ² = 0 over N ≥ 6 consecutive hours". It points out that such values pass every range check because "42.0 is within normal operating bounds". It has no rule for readings that are legitimately constant (https://github.com/AseemPrasad/Air-Quality-Intelligence/issues/44).
- **Make stale data look different, not flat.** BetterDB found that exported gauges "kept their last value forever when a connection died… dashboards showed flat lines and value-based alerts never fired". Their fix was to drop series after `3 × poll interval` without a successful read, and to add an explicit `poll_stale` indicator (https://github.com/BetterDB-inc/monitor/pull/462). This is the product's core rule restated by someone who shipped it.
- **dbt-utils `not_constant`.** It "asserts that a column does not have the same value in all rows" and supports `group_by_columns` (https://github.com/dbt-labs/dbt-utils). It is **not** in dbt Core, which ships only `not_null`, `unique`, `accepted_values` and `relationships` (https://docs.getdbt.com/reference/resource-properties/data-tests).

**Healthchecks.io as a rollup source.** Management API v3 `GET /api/v3/checks/` returns `status ∈ {new, up, grace, down, paused}`, plus `last_ping` and `grace`. A **read-only** key can reach only the list, get, flips and badges endpoints, and omits `ping_url`. The API is throttled at about 100 requests per minute (https://healthchecks.io/docs/api/).

## Approach options

### Option A: Pure SQL integrity views plus a generated TS key union (recommended)
- **How it works:**
  - A Postgres view or RPC computes, per indicator, asset and vendor: freshness state from `source_timestamp` versus the registry thresholds, and "frozen" as the latest K consecutive **distinct-`source_timestamp`** OK rows with identical `value`.
  - A codegen step (Python, run in CI) emits `web/src/registry.generated.ts` containing `export const INDICATOR_KEYS = [...] as const`.
  - The UI declares per-key wiring as `{[K in IndicatorKey]: ...}`, so `tsc -b` fails when a key is missing.
  - A pytest asserts the generated file is up to date with `registry.yaml`, so a stale codegen fails CI.
- **Trade-offs:** Deterministic and cheap. Needs a migration (blast radius) and codegen discipline.
- **Cost:** $0.

### Option B: Detection at ingest time, with a new `FROZEN` status enum value
- **How it works:** At write time, `persist.py` compares the new value to the previous distinct observation and writes a `FROZEN` status.
- **Trade-offs:**
  - Enum values can never be removed (https://www.postgresql.org/docs/current/sql-altertype.html).
  - It changes the `value_iff_ok` and `reason_required` constraints.
  - Every UI discriminated union must handle the new state.
  - History already written stays unflagged unless backfilled.
  - The detector runs inside the thing it audits, so if ingest stops, the audit stops too.
- **Cost:** $0, but the largest blast radius of the three options.

### Option C: Adopt dbt or Soda for the checks
- **How it works:** Run `dbt source freshness` plus `dbt_utils.not_constant`, or `soda scan`, in a GitHub Actions job. Write the results to a table the board reads.
- **Trade-offs:** Battle-tested semantics. But it adds a second toolchain and a second config source that must be kept in sync with `registry.yaml`, which is the drift this PRD exists to prevent. `not_constant` is "all rows identical", not "the last K identical", so it would need a custom test anyway.
- **Cost:** $0 on OSS, plus the operational surface.

**Recommendation: Option A.** It keeps `registry.yaml` as the only source of truth and moves the audit outside the ingest path. It also turns "wired for every indicator" into a compiler error instead of a convention.

## Edge cases and gotchas

1. **Two fetchers set `source_timestamp` to the wall clock, so their freshness can never fail.**
   - `ingest/fetchers/defillama_stablecoins.py:237-243` sets `source_timestamp=fetched_at`.
   - `ingest/fetchers/validators_app.py:48` sets `source_timestamp = datetime.now(UTC)`.
   - For these indicators the freshness rollup is **structurally always green**, and a frozen vendor response would be invisible to it.
   - The frozen-value detector is the only defence there. The dashboard must also mark these rows as "freshness unmeasurable: vendor provides no observation time" rather than showing a green SLA. That is the product's own rule: a wrong number must look different.
2. **An upstream that repeats the same observation leaves no trail of repeated rows.**
   - `persist.py:74-121` upserts on `(indicator_key, asset, source_vendor, source_timestamp)`. If a vendor returns the same timestamp again, the existing row is updated in place and `fetched_at` is overwritten.
   - So "N identical rows" only ever happens when `source_timestamp` advances and the value does not.
   - Detection has to be defined over **distinct observations**, not over fetches. An implementer who writes "last N rows by `fetched_at`" will test against fixtures that can never occur in production.
3. **Some values are legitimately constant: funding rate is the main one.**
   - When the premium index sits inside a band, the funding rate is clamped to the 0.01% interest rate, and BTC funding "rarely strays far from 0.01% per 8-hour interval" (https://www.kucoin.com/news/flash/bitcoin-perpetuals-funding-rate-analysis-the-0-01-benchmark-and-its-impact).
   - `btc_funding_rate`, `eth_funding_rate` and `sol_funding_rate` (OKX) could show `0.0001` for many consecutive intervals in a calm market.
   - A naive K-identical rule would flag a healthy market as broken, which is itself a judgement about the market.
   - Other candidates:
     - Fear & Greed is an integer from 0 to 100 and repeats day to day. (UNVERIFIED: our `alternative_me` fetcher's exact granularity.)
     - Monthly M2 repeats by design within its reference period.
   - The threshold has to be per indicator and declared in the registry, including an explicit "constant runs are expected" declaration with a reason.
4. **Floating-point equality.** `value double precision` combined with TA-Lib recomputation can produce values that differ only in the last ULP. Values that are really frozen could then read as "changed". The reverse can also happen: rounding on the vendor side can make real movement look frozen. (UNVERIFIED: whether any fetcher rounds.) Decide on exact `=` versus a per-indicator epsilon, and write it down.
5. **Derived indicators inherit freezes.** If `btc_daily_close` is frozen, RSI, EMA, Bollinger, MACD and ATR all move smoothly toward a constant input and are **not** identical point to point. EMA keeps changing for many bars. Detection on derived indicators alone will miss it. Detect on the raw input, then propagate the flag to every indicator that depends on it.
6. **Views need an explicit timestamp.** dbt's rule for views applies here too: freshness must name the column, because a view has no row-level metadata (https://docs.getdbt.com/reference/resource-properties/freshness). `board_read` orders by `fetched_at`. The rollup must use `source_timestamp`, or it measures "we ran" rather than "the data is fresh".
7. **Scheduling silently drops runs.** A per-source SLA computed from Actions run history will miss runs that never started (https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows). Compute the rollup from data age at read time, so a dropped run shows up as ageing data.
8. **A detector nobody has seen fire is untested.** Statistical and range checks cannot see a stale value, because it sits inside the normal distribution; the air-quality issue above makes the same point about range checks. The acceptance test must inject a real frozen sequence into a throwaway schema and assert the flag. Per the project lesson, that test must not carry the `integration` marker.
9. **A stale generated file is its own drift.** If `registry.generated.ts` is committed and someone edits `registry.yaml` without regenerating, `tsc` passes against the old list. Either generate it in the build step or add a test that diffs it against the YAML.
10. **Healthchecks API limits and key exposure.** 100 requests per minute (https://healthchecks.io/docs/api/). The frontend is static and polls every 30–60 seconds. Never put an HC key in the browser, even a read-only one. Pull HC status inside the ingest job and write it to Postgres.

## Services and keys this PRD needs

| Service | Why | Env var | Already provisioned? |
|---|---|---|---|
| Healthchecks.io Management API (read-only key) | Only if the SLA rollup includes the switch's own view (up / grace / down) next to data age | `HEALTHCHECKS_API_KEY_READONLY` (proposed) | **No.** Only `HEALTHCHECKS_PING_URL` exists (`.env.example:13`, workflows). It must also be added to every workflow `env:` block that runs the collector (project lesson). |
| Supabase Postgres | Integrity view or RPC | existing `DATABASE_URL` | Yes. The production migration apply is still a separate owner-approved step. |

## Open questions for the human

| # | Question | My hypothesis | What breaks if I'm wrong |
|---|---|---|---|
| 1 | Is "frozen" a separate state shown on the cell, or only on the integrity panel? | It is shown on the cell as a provenance badge ("value unchanged across K observations since T"). The cell is not downgraded from OK. That keeps the market value untouched while making the integrity problem visible. | Panel-only means a frozen number still looks identical to a right one on the main board, which breaks the product's one rule. Downgrading to STALE conflates two failure modes. |
| 2 | Per-indicator frozen threshold in the registry, including an explicit declaration that constant runs are expected (e.g. funding at 0.01%)? | Yes. Add a required registry field such as `frozen_after_observations: int` or `frozen: {expected_constant: reason}`, with no default, so a new indicator must decide. | A global K either flags calm funding markets (a false positive that reads as a judgement) or is too loose to catch real freezes. |
| 3 | What happens to the two wall-clock-stamped fetchers (DefiLlama stablecoins, validators.app)? | They are shown as "freshness unmeasurable" on the rollup, with frozen detection as the sole check. Fixing the stamping is out of scope for this PRD. | Showing them green on the SLA rollup ships the exact false comfort this PRD exists to remove. |
| 4 | Enum value versus computed view? | Computed view or RPC. No new `datapoint_status` value. | An enum value can never be removed, and it touches constraints and every UI union. |
| 5 | Does "fails the build" mean `tsc` fails, or a vitest or pytest fails? | Both: the generated key union plus mapped types for UI wiring (tsc), and pytest for "every key has a golden, a test and a coverage entry" plus "the generated file is up to date". | Test-only gets skipped by a marker. tsc-only can't see Python-side wiring. |
| 6 | Should the rollup include Healthchecks.io's own status? | Not in v1. Data age from Postgres is the ground truth, and HC is the independent alarm. It can be added later. | Adding it now needs a new secret wired into four workflows, which has already bitten this project once. |

## Blind spots

1. **The auditor shares a failure mode with the audited.** The integrity view reads the same `datapoints` table through the same PostgREST and the same browser poll. If the board's query is stuck — a TanStack Query cache serving an old response, a PostgREST schema cache that was never reloaded (a known project lesson), or a Cloudflare edge cache — the integrity panel will be stale in exactly the same way and report "all green" from old data. The panel needs its own "integrity computed at T (server clock)" stamp, and the browser must compare it with its own clock.
2. **Frozen detection does nothing for derived indicators, and they are most of the board.** About 70% of registry keys are TA-Lib outputs (EMA, BB, MACD, OBV, ATR, StochRSI). A frozen close series makes them converge smoothly, not repeat, so they pass the identical-value test while being entirely wrong. Unless the flag propagates from input to derived indicators, the dashboard will certify most of the board as healthy during the exact failure it was built for.
3. **The coverage gate can be satisfied without real coverage.** "An indicator without UI, test and coverage wiring fails the build" is easy to meet by adding a key to a mapping with a placeholder: an `it.todo`, a golden file copied from another indicator, or a `// @ts-expect-error`. A mapped type proves a key exists, not that the wiring is real. The gate should check substance: the golden file's hash is unique per indicator, and the named test exists and actually asserts on that key. Otherwise this PRD reproduces the "self-audit that doesn't audit" that the brief's title calls out.

## Sources

- https://docs.getdbt.com/reference/resource-properties/freshness
- https://docs.getdbt.com/reference/resource-properties/data-tests
- https://github.com/dbt-labs/dbt-utils
- https://github.com/AseemPrasad/Air-Quality-Intelligence/issues/44
- https://github.com/BetterDB-inc/monitor/pull/462
- https://healthchecks.io/docs/api/
- https://www.richinfante.com/2024/04/06/ts-enum-record-required-keys
- https://vite.dev/guide/features
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://www.postgresql.org/docs/current/sql-altertype.html
- https://www.kucoin.com/news/flash/bitcoin-perpetuals-funding-rate-analysis-the-0-01-benchmark-and-its-impact
