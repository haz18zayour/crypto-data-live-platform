# R5 · Data Integrity Engineering — Failing Loud Instead of Wrong

**Scope:** engineering against silent data failure for a single-user, 4-asset, ~25-40 indicator
crypto observability dashboard. **Date:** 2026-09-07.
**Companion doc:** `R0-lessons-from-prior-system.md` — ten measured failures from the owner's
prior system are the acceptance-test bar for everything below.

---

## 1. Executive summary — 7 practices ranked by value-per-effort

For a one-person project, cost is entirely engineering time, not licence fees — every tool
below except the enterprise observability platforms is free. Ranked by (damage prevented) /
(hours to build):

| # | Practice | Effort | Why it's near the top |
|---|---|---|---|
| 1 | **Dead-man's-switch on every scheduled job** | ~30 min | Cheapest defense that exists. Directly would have caught F8 (runner died, 24h silent). Healthchecks.io free tier (20 checks) covers this entire project with room to spare. |
| 2 | **Status enum replacing every bare float** (`OK\|STALE\|UNAVAILABLE\|ERROR`, never inferred) | ~1-2 days for schema + fetcher wrapper | Directly closes F1 (never-fetched read as 0.0) and F6 (stale read as confident). This is a type-system change, not a monitoring add-on — it is structurally impossible to regress once the column exists and the UI refuses to render numbers without it. |
| 3 | **Per-source freshness budget + UI staleness treatment** | ~1 day | Closes F6. Requires only a `freshness_budget_seconds` column per indicator and a comparison at render time — no external tool needed. |
| 4 | **Frozen-value / repeat detection** (flag N consecutive identical values from a source that should vary) | ~half day | Distinct from freshness — a source can be "fresh" (recent `fetched_at`) while silently returning the same payload. Cheap: compare current value to last N stored values. |
| 5 | **Provenance columns on every datapoint** (`source_vendor`, `endpoint`, `fetched_at`, `source_timestamp`, `measured_on_asset`) | ~half day, one-time schema decision | Closes F2 (wrong asset presented as native) at the schema level — a `WHERE measured_on_asset != displayed_asset` becomes impossible to satisfy silently. |
| 6 | **Golden-file / snapshot tests on indicator computation** (same input bars -> same output, forever) | ~1 day for harness, ongoing per indicator | Closes F5 (score depended on process uptime / growing cache). |
| 7 | **Recorded-cassette contract tests per vendor** (VCR.py / respx) | ~1-2 hours per source, one-time | Catches a vendor silently reshaping its response before it corrupts data, and is the only entry on this list that is genuinely a "test," not a runtime guard. |

Everything below #7 (Great Expectations, Monte Carlo, OpenLineage, etc.) is **overkill for this
project's scale** — see Section 3. The right-sized version of "data observability" here is:
one Postgres status column, one heartbeat pinger, one nightly assertion script, and tests
that pin down computation determinism. That combination, at near-zero cost, would have
prevented 8 of the 10 recorded failures (F1, F2, F5, F6, F7, F8, and partially F3/F9 via
provenance visibility).

---

## 2. Concrete recommended design

### 2.1 Status enum (fail-closed at the type level)

```sql
CREATE TYPE datapoint_status AS ENUM ('OK', 'STALE', 'UNAVAILABLE', 'ERROR');
```

Rule: **a numeric value and a status are never independent fields that can drift apart.**
Model them as one discriminated thing, not a `value` column plus a `status` column that a
bug can leave inconsistent (this is exactly how F1 happened — the value column had `0.0`,
nothing recorded that the fetch never ran).

Python (dataclass + explicit union, no bare float ever crosses a function boundary):

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Union

@dataclass(frozen=True)
class Ok:
    value: float
    source_timestamp: datetime
    status: Literal["OK"] = "OK"

@dataclass(frozen=True)
class Stale:
    value: float                 # last known good value, shown but visually marked
    source_timestamp: datetime   # how old it actually is
    status: Literal["STALE"] = "STALE"

@dataclass(frozen=True)
class Unavailable:
    reason: str                  # "fetcher not invoked" | "source 404" | "no bars in window"
    status: Literal["UNAVAILABLE"] = "UNAVAILABLE"

@dataclass(frozen=True)
class ErrorResult:
    reason: str
    status: Literal["ERROR"] = "ERROR"

Indicator = Union[Ok, Stale, Unavailable, ErrorResult]
```

There is no code path that produces a `float` on its own — every caller pattern-matches on
`status` before touching `.value`. A fetcher that is never invoked cannot produce an `Ok`;
it can only fail to produce anything, which the pipeline must treat as `Unavailable` by
default (the absence of a call is not a `0.0`, it's a missing dict key / missing row).

TypeScript mirror (discriminated union, exhaustive switch enforced by the compiler):

```typescript
type Indicator =
  | { status: "OK"; value: number; sourceTimestamp: string }
  | { status: "STALE"; value: number; sourceTimestamp: string }
  | { status: "UNAVAILABLE"; reason: string }
  | { status: "ERROR"; reason: string };

function render(i: Indicator): string {
  switch (i.status) {
    case "OK": return formatValue(i.value);
    case "STALE": return formatStale(i.value, i.sourceTimestamp);
    case "UNAVAILABLE": return "—"; // never "0"
    case "ERROR": return "⚠";
    default: {
      const _exhaustive: never = i;   // compile error if a status is unhandled
      return _exhaustive;
    }
  }
}
```

This is the concrete answer to the brief's question 3: making "missing" unrepresentable as a
number means **there is no code path where a number exists without a status that was
actively set to OK**, and the compiler (TS) or a lint/mypy rule (Python: forbid bare
`float`/`Optional[float]` return types on fetcher functions, require the union) enforces it
statically rather than by convention.

### 2.2 Provenance-carrying schema (Postgres/Supabase)

One narrow fact table, not one row per API call blown out with a wide JSONB blob (avoids the
storage bloat the JSONB search results warn about — use JSONB only for the genuinely
variable-shaped payload, not for the queryable columns):

```sql
CREATE TABLE datapoints (
    id              bigserial PRIMARY KEY,
    indicator_key   text NOT NULL,          -- 'funding_rate', 'mvrv', ...
    asset           text NOT NULL,          -- displayed asset, e.g. 'BTC'
    measured_on     text NOT NULL,          -- asset the value was ACTUALLY computed on
    value           double precision,       -- NULL unless status = 'OK' or 'STALE'
    status          datapoint_status NOT NULL,
    reason          text,                   -- populated for UNAVAILABLE/ERROR
    source_vendor   text NOT NULL,          -- 'binance', 'coinmetrics', ...
    endpoint        text NOT NULL,          -- '/fapi/v1/fundingRate'
    fetched_at      timestamptz NOT NULL,   -- when WE fetched
    source_timestamp timestamptz,           -- when the vendor says the value is as-of
    freshness_budget_seconds int NOT NULL,  -- SLA for this indicator
    raw_response_ref text,                  -- pointer to raw payload (object storage), not inline
    CONSTRAINT asset_match CHECK (
        status != 'OK' OR measured_on = asset  -- F2 defense: cannot be OK if wrong-asset
    )
);
CREATE INDEX ON datapoints (indicator_key, asset, fetched_at DESC);
```

- `measured_on != asset` can still be *inserted* as `STALE`/`UNAVAILABLE` for audit purposes,
  but the CHECK constraint makes it a database-level impossibility for a mismatched row to
  carry `OK` — F2's "not degraded data, wrong data" becomes a constraint violation, not a
  silent proxy.
- Storage control: keep raw vendor payloads out of the hot table (`raw_response_ref` points
  to a file/object store or a separate cold table); the hot table stays narrow enough for a
  single Postgres instance to hold years of 25-40 indicators at a few fetches/day-to-hourly
  without partitioning. Only sub-minute price series need a TimescaleDB hypertable or simple
  monthly table partitioning if row count becomes a concern — not needed at this cadence mix.
- This is deliberately **simpler than OpenLineage's Job/Run/Dataset/facet model or W3C
  PROV's Entity/Activity/Agent graph** — both are built for multi-tool, multi-team lineage
  graphs (see 3.4). One row per datapoint with source + timestamps IS the provenance graph
  at this scale; a graph database or lineage service is not needed to answer "where did this
  number come from and when."

### 2.3 Freshness model

Two orthogonal cadence attributes per indicator, not one:

- **`expected_update_interval`** — how often the source *should* publish (8h for funding,
  24h for on-chain close, 7d for Trends, ~35d for M2 with lag).
- **`freshness_budget_seconds`** — how stale is tolerable before the UI must say so; not the
  same number as the interval. DQOps's pattern of a warning threshold and a harder error
  threshold (e.g. warn at 1.5x interval, mark STALE at 2x, `UNAVAILABLE` beyond a hard cap)
  is a good default — it survives one missed cycle without crying wolf but catches two.
  Concretely: daily-close indicator, interval 24h, warn at 30h ("stale if older than 26h" per
  the brief maps to this), hard STALE at 48h.
- **Frozen-value detection is a separate check from freshness**, and this is the one the
  brief specifically flags: a source can report a `fetched_at` of 30 seconds ago (looks
  fresh) while returning byte-identical payloads for days because its own upstream froze.
  Concrete rule: store the last N raw values per indicator; if the last 3 consecutive
  `source_timestamp`-distinct fetches produce an identical `value` for a series that
  historically has non-zero variance, flip status to a fifth soft-flag (`SUSPECT_FROZEN`,
  can piggyback on `STALE` with `reason = 'frozen: identical for N cycles'`) rather than
  trusting "recently fetched" alone. This is exactly the sensor-drift pattern found in
  research on stale-sensor detection (Section 6) — deterministic repeat-value filters catch
  frozen series with zero false positives because a value statistically identical to
  yesterday's, in a series with real variance, is definitionally suspicious regardless of
  distributional anomaly scores.

### 2.4 UI treatment

Borrowing from status pages and trading-desk panels (Section 6): never render a bare number
without its status adjacent.

- **OK** — value in normal weight, small "as of Ts" caption.
- **STALE** — value shown (so the user isn't blind) but visually desaturated/amber-bordered,
  caption states exact age ("stale — last updated 31h ago, budget 26h").
- **UNAVAILABLE** — no number at all, an em-dash or explicit "—", never `0` or blank space
  that could be misread as zero.
- **ERROR** — a warning glyph, reason on hover.
A single roll-up strip at the top of the dashboard (à la a status page's overall-health bar)
counts indicators by status so the user catches "6 STALE" at a glance without reading every
tile — directly answers the brief's "surface freshness so a human notices without reading
logs."

---

## 3. Tooling comparison — honest verdicts

| Tool | What it checks | License / cost | Verdict for this project |
|---|---|---|---|
| **Great Expectations (GX Core)** | Declarative expectations (`expect_column_max_to_be_between`, etc.) on dataframes/tables; freshness via `ExpectColumnMaxToBeBetween` on a timestamp column | Apache-2.0, free; GX Cloud (hosted UI) being wound down in 2026 after acquisition | **Overkill for daily use, but the one enterprise-grade tool worth borrowing one pattern from**: use its freshness-expectation *idea* (`max timestamp within N of now`) as a design reference; don't adopt the framework's full expectation-suite machinery for 25-40 indicators — a hand-written assertion script is less code than onboarding GX's config surface. |
| **Soda Core** | YAML-defined checks, similar niche to GX, plus a hosted Soda Cloud tier | Core is Apache-2.0/free; Soda Cloud is priced per-need, not published, generally SMB-unfriendly per comparisons found | **Overkill.** Materially the same value proposition as GX Core for this project; no reason to run both, and neither is needed at 25-40 indicators when four SQL assertions + a status enum do the job. |
| **dbt tests + dbt-expectations** | Native dbt tests (not_null, unique, relationships, accepted_values) plus dbt-expectations' richer set incl. `expect_row_values_to_have_recent_data` for freshness | Free, Apache-2.0 (maintained by Datadog/community, originally calogica) | **Right-sized only if you already run dbt.** If the pipeline is plain Python/Postgres (likely, given the scale), adopting dbt purely for its test runner is a bigger lift than writing the equivalent four SQL `CHECK`/assertion queries directly. Worth it only if a dbt layer gets adopted for other reasons. |
| **Elementary** | dbt-native observability: freshness, volume, schema-change, anomaly detection, Slack/Teams alerts | OSS (Apache-2.0) CLI is free and fully featured for single-project use; Cloud/paid tiers are quote-only (no published USD figure found — earlier public estimates around $600/mo could not be verified for 2026, **UNVERIFIED**) | **Overkill** unless already on dbt — same reasoning as above; the OSS CLI is legitimately good if a dbt layer exists, but building one just to get Elementary is backwards. |
| **Monte Carlo** | End-to-end enterprise data observability: ML-driven anomaly detection, lineage, incident management | Custom enterprise pricing; third-party estimates place typical deployments at **$50K-$300K+/year** | **Wildly overkill.** Built for warehouses with hundreds of tables and a data team; single-user 25-40-indicator project has no plausible ROI here. |
| **Bigeye** | Similar category to Monte Carlo, metric-based monitors | Custom enterprise pricing, generally quoted as somewhat below Monte Carlo for similar scope, still five-figure+/year territory | **Wildly overkill**, same reasoning as Monte Carlo. |
| **Evidently** | Open-source ML/data drift and quality reports (originally ML-model focused, now broader) | Apache-2.0, free (open core; paid tiers exist for teams) | **Possible fit for the anomaly-detection slice only** (Section 5) if a Python-native drift check is wanted (e.g. population/level-shift detection on a price series) — but for 4 assets and a handful of anomaly rules, a dozen lines of pandas/numpy (rolling z-score, IQR) is simpler than onboarding Evidently's Report/TestSuite abstractions. Marginal — lean toward hand-rolled. |
| **Deequ / PyDeequ** | "Unit tests for data" on Spark DataFrames — completeness, uniqueness, distributional constraints | Apache-2.0, free | **Wrong tool entirely** — requires Apache Spark. There is no Spark cluster in this project and standing one up purely for Deequ would be absurd at this data volume. |
| **Pointblank** | R/Python-adjacent data-quality validation with readable reports (from the Great Tables/RStudio-adjacent ecosystem) | Open source, free | **Plausible small-project fit** for one-off validation reports, but functionally overlaps Pandera; no reason to run both. |
| **Pandera** | Statically-typed dataframe schema validation (pandas/Polars/etc.), integrates with pydantic/mypy | Apache-2.0 (Union.ai), free | **Right-sized and recommended** if any pandas dataframes sit in the pipeline (e.g. batch OHLCV processing) — it is exactly "type hints for dataframes," matching the fail-closed philosophy in Section 2.1 at negligible adoption cost. |
| **OpenLineage** | Standardized Job/Run/Dataset lineage events, designed for Airflow/Spark/dbt interop | Open source (LF AI & Data project), free | **Overkill** — built for cross-tool lineage exchange across an org's stack (Section 3.4 gives the concrete reasoning); this project's provenance need is fully met by the columns in Section 2.2. |
| **W3C PROV** | Formal Entity/Activity/Agent provenance ontology, RDF-based | Open standard, free | **Overkill / wrong shape.** PROV is for provenance living in a knowledge graph queried by generic tooling; a single Postgres table with source/timestamp columns *is* the practical PROV mapping (Entity = datapoint row, Activity = fetch, Agent = vendor) without adopting RDF or a graph store. |
| **OpenTelemetry (semantic conventions for data)** | Standardized trace/metric/log attribute names; strong conventions exist for HTTP/DB, ETL-specific conventions are still emerging as of 2026 | Free, CNCF | **Not a fit as a data-quality tool** — OTel is for operational tracing (job durations, error rates), which is useful for the scheduled-job-reliability track (Section 6) but does not replace the status-enum/provenance design above. If instrumented at all, use it for "did the fetch function get invoked and how long did it take" spans — directly relevant to F1. |
| **Healthchecks.io** | Dead-man's-switch heartbeat pinging; alerts if a scheduled ping doesn't arrive in time | Free Hobbyist tier: **20 checks, 3 team members, 100 log entries/check, 5 SMS credits**; paid $5-$20-$80/mo tiers for more checks/retention | **Exactly right-sized — the single best-value tool on this entire list.** 20 free checks covers every scheduled fetcher this project will ever have. This is the direct fix for F8. |
| **Cronitor** | Heartbeat + uptime monitoring, duration-based cron analytics | Free "Hacker" tier: 5 monitors (email/Slack only); paid $2/monitor/mo + $5/mo/user; Enterprise from $6,000/yr | **Fine alternative to Healthchecks.io** but the free tier (5 monitors) is tighter than Healthchecks.io's 20 — no reason to pay here when Healthchecks.io's free tier already covers the whole project. |
| **Better Stack** | Combined uptime/heartbeat/logs/incident/status-page platform | Free tier ~5 monitors; paid from $24-$29/mo/user plus per-add-on heartbeat/status-page fees | **Overkill for the narrow need** (just heartbeats) — its value is the bundled incident/status-page tooling a single-user project doesn't need. |
| **VCR.py / respx (Python), nock / MSW (JS/TS)** | Record-and-replay HTTP cassettes for deterministic tests against third-party APIs; MSW additionally intercepts at the network layer so app code is unaware | Free, open source | **Right-sized and recommended** — cheap, directly enables the contract tests in Section 7, and is the correct tool (not an enterprise data-quality platform) for "did the vendor silently change response shape." |

### 3.1 One-line bottom line
Buy nothing. Use Postgres constraints + a status enum + Pandera (if pandas is in the loop) +
Healthchecks.io free tier + VCR.py/nock cassette tests. That is a complete, right-sized stack
for this project's scale; everything with a five-figure price tag in this table exists to
solve problems (hundreds of tables, multiple teams, cross-tool lineage) this project does not
have.

---

## 4. How each of the five historical failures would have been caught

One mechanism + one testable assertion per failure, matching the brief's ask for concrete
acceptance criteria.

### F1 — A fetcher was never invoked; three indicators silently scored `0.0` for months
- **Mechanism:** the status-enum design in 2.1 makes "never called" and "called, got zero"
  structurally different states. A pipeline orchestrator that iterates a **registry of
  expected indicators** (not a list built from whatever ran) and asserts each one produced
  a row this cycle turns a silent omission into a visible `UNAVAILABLE` count.
- **Testable assertion:**
  ```python
  def test_all_registered_indicators_produce_a_result(monkeypatch):
      # simulate a wiring bug: futures fetcher never called before pipeline runs
      pipeline_registry = get_indicator_registry()
      results = run_pipeline(skip_fetchers=["futures"])  # deliberately omit
      for key in pipeline_registry:
          assert key in results, f"{key} missing from results entirely"
          assert results[key].status != "OK" or results[key].value != 0.0 or \
                 key not in ("funding_rate", "oi", "ls_ratio")
      # stronger: any indicator whose fetcher didn't run must be UNAVAILABLE, never OK
      for key in ("funding_rate", "oi", "ls_ratio"):
          assert results[key].status == "UNAVAILABLE"
  ```
  This assertion is impossible to satisfy under the old design (bare float defaulting to
  0.0) and trivially satisfied once fetchers must explicitly emit `Ok` to produce a number.

### F2 — One asset's data substituted for another's, presented as native
- **Mechanism:** the `asset_match` CHECK constraint in 2.2 (`status != 'OK' OR measured_on
  = asset`) makes it a database error, not a silent proxy, to insert an `OK` row where the
  measured asset differs from the displayed asset.
- **Testable assertion:**
  ```sql
  -- integration test: attempt to insert BTC on-chain data labeled as ETH's OK reading
  INSERT INTO datapoints (indicator_key, asset, measured_on, value, status, ...)
  VALUES ('mvrv', 'ETH', 'BTC', 1.8, 'OK', ...);
  -- EXPECTED: constraint violation (asset_match), test asserts the INSERT raises
  ```
  Equivalently at the application layer: `assert fetch_indicator("mvrv", asset="ETH").measured_on == "ETH"`
  fails loudly (raises/returns `UNAVAILABLE`) whenever the underlying fetcher only supports
  BTC and a caller tries to reuse it for ETH — this was exactly the silent substitution.

### F3 — Two algebraically-related indicators counted as independent (NUPL vs MVRV, corr 0.92)
- **Mechanism:** an explicit **derivation graph** — each indicator declares
  `derived_from: list[str]` in its registry entry. A CI check computes pairwise correlation
  across the registry's historical values and fails the build if two indicators not
  declared as related exceed a correlation threshold, or if two indicators *are* declared
  related but both are flagged "independent" in the UI weighting/labels.
- **Testable assertion:**
  ```python
  def test_no_undeclared_high_correlation_pairs():
      history = load_indicator_history(days=180)
      for a, b in itertools.combinations(registry.keys(), 2):
          corr = history[a].corr(history[b])
          if abs(corr) > 0.85:
              assert b in registry[a].derived_from or a in registry[b].derived_from, \
                  f"{a} and {b} correlate at {corr:.2f} but neither declares derivation"
  ```
  This is a statistical test, not a unit test — it runs on real accumulated history, but it
  is exactly the kind of test that would have surfaced NUPL/MVRV (0.92) and F&G/fg_zscore
  (0.72, if threshold set at 0.7) before they were double-counted.

### F4 — An indicator inverted against reality for 1,394 days
- **Mechanism:** this project's scope decision (per R0 Section 2) is to show raw values and
  their real distributions rather than directional scores — which structurally removes the
  class of bug where a score's *sign convention* can be backwards. Where a derived
  directional label is unavoidable, a **backtestable sanity assertion** checks the labeled
  direction against a simple, unambiguous ground truth over a rolling window.
- **Testable assertion:**
  ```python
  def test_bearish_label_correlates_with_negative_not_positive_forward_return():
      # ground truth: independently computed next-day BTC return, no dependency on
      # the indicator's own sign convention
      labeled_bearish_days = history[history["spx_correlation_label"] == "bearish"]
      fwd_return = labeled_bearish_days["next_day_btc_return"].mean()
      base_rate = history["next_day_btc_return"].mean()
      assert fwd_return <= base_rate, (
          f"days labeled bearish precede ABOVE-average returns "
          f"({fwd_return:.4f} vs base {base_rate:.4f}) — sign convention is inverted"
      )
  ```
  Run this once against 180+ days of accumulated history in CI/nightly and it directly
  reproduces the measurement that caught F4 in the post-mortem (+0.789% vs +0.091% base
  rate) — as an automated, recurring check rather than a one-time manual audit 1,394 days
  late.

### F5 — Indicator values depended on process uptime (ATR modifier, BB squeeze quantile grew from a live-forever cache)
- **Mechanism:** golden-file/snapshot determinism tests. Indicator computation must be a
  **pure function of (bars, fixed window)** — same input array in, same output every time,
  regardless of how long the process has been running or how large an in-memory cache has
  grown.
- **Testable assertion:**
  ```python
  def test_indicator_computation_is_deterministic_and_window_bounded():
      bars_100 = load_fixture("btc_ohlcv_100_bars.json")
      result_a = compute_bb_squeeze(bars_100)
      # simulate "process has been running a long time": prepend 10,000 extra historical
      # bars the way a growing unbounded cache would, but computation should ignore them
      bars_10100 = load_fixture("btc_ohlcv_10000_extra_bars.json") + bars_100
      result_b = compute_bb_squeeze(bars_10100, window=100)  # explicit fixed window
      assert result_a == result_b, (
          "same trailing 100 bars produced different output depending on cache size — "
          "computation is not window-bounded"
      )
  ```
  This is a direct, mechanical reproduction of "same market, different score" — it fails
  under the old unbounded-cache design and passes once the window is made an explicit,
  fixed parameter rather than "whatever's in memory."

### (Bonus, matching the brief's sixth listed failure) F8 — scheduled job silently stopped (self-hosted runner exited 0)
- **Mechanism:** dead-man's-switch heartbeat (Healthchecks.io) pinged only *after* the
  pipeline completes successfully; the check's own "expected every N hours, grace period M"
  timer — external to the job — is what raises the alarm, because (per the brief's framing)
  "a run cannot be trusted to report its own death."
- **Testable assertion (operational, not unit):** a scheduled synthetic check — "assert the
  most recent successful run's `fetched_at` across the registry is within the last
  `expected_interval + grace`" — evaluated by a process that does NOT depend on the pipeline
  process being alive (i.e., Healthchecks.io's server-side timer, not a self-check inside
  the job). This is precisely why F8 requires an external watcher: the runner exiting 0 was
  itself "successful" from the job's own point of view.

---

## 5. Anomaly detection notes (financial time series, cross-source corroboration)

- **Outliers / level shifts / unit changes / sign flips** are all forms of the same
  underlying test: does a new observation fall within a distribution consistent with the
  series' own recent history? A rolling z-score or IQR-based bound per indicator (a dozen
  lines of pandas) catches outliers and sudden level shifts; a **unit-change** (USD to
  millions) shows up as a ~1,000,000x jump that a naive z-score might dismiss as "just an
  extreme outlier" rather than flag distinctly — worth a dedicated check: `if new_value >
  100 * rolling_median: flag("possible unit change")` before falling through to the generic
  outlier check.
- **Cross-source corroboration**: where two vendors report the same quantity (e.g. BTC spot
  price from two exchanges/aggregators), a divergence check with an explicit tolerance is
  cheap insurance. For crypto spot price, tolerance should be a small percentage (order of
  0.1-0.5% for liquid pairs across major venues) rather than a fixed dollar amount, since
  absolute price scale varies; **the specific tolerance number was not found from an
  authoritative source and should be tuned empirically against this project's actual two
  vendors — treat any fixed number here as UNVERIFIED** until back-tested against real
  observed cross-venue spread.
- **Reconciliation/canary pattern**: keep one "boring," well-understood indicator (e.g. BTC
  spot price, which has the tightest cross-source agreement) as a canary — if the canary
  itself starts diverging from a second source, treat that as a signal the *pipeline*, not
  the market, is malfunctioning (clock skew, wrong endpoint, stale cache), since a canary
  indicator diverging is far more likely to be infrastructure than a real 0.5% two-exchange
  price gap.

---

## 6. Scheduled-job reliability — argued position

**"1 of 12 sources fails — should the whole run fail, or should that one indicator go
UNAVAILABLE?"**

Argue for **partial failure, never whole-run failure**, for this project specifically:

- The failure modes in R0 (F1, F9) were caused by fetchers being silently *skipped* or
  swapped for a worse source, not by the pipeline crashing outright — meaning the actual
  historical risk is under-detected partial failure, not over-tolerated partial failure.
- A single-user dashboard with independent indicators on wildly different cadences (8h
  funding vs monthly M2) has no reason to couple their fates — M2 being 5 weeks lagged is
  normal and expected; funding rate being 5 weeks lagged is a fetch failure. Coupling them
  into one pass/fail run either cries wolf constantly (bad) or hides a real failure inside
  "well, M2 is always lagged" noise (worse).
- The correct pattern (matching the "graceful degradation" research in Section 3): each
  fetcher runs independently, catches its own exceptions, and emits `UNAVAILABLE`/`ERROR`
  for its own indicator without raising past its own boundary. The orchestrator's job is to
  run all fetchers it can, record what happened, and let the dead-man's-switch (Section 1)
  catch the case where the *orchestrator itself* never ran — that is the one case that
  should be a hard, unmissable signal, and it is orthogonal to "did source #7 of 12 time
  out today."
- Idempotency and retry-with-backoff belong at the individual fetcher level (retry a 5xx/
  timeout 2-3 times with jittered backoff before giving up and marking `ERROR`), not at the
  orchestration level — retrying "the whole run" because one of twelve independent sources
  hiccuped wastes the other eleven's freshness budget for no reason.

---

## 7. Anti-patterns

- **Defaulting missing data to 0, "neutral," or last-known-good without marking it as such**
  — the root cause of F1 and the generic "billion-dollar mistake" pattern; nulls are
  information, defaults are silent decisions.
- **A self-check that validates a hardcoded sample instead of the full registry** — F7's
  `_assess_data_quality` checking exactly two hardcoded rows. Any integrity check must be
  *generated from* the indicator registry so a newly added indicator is automatically
  covered, not opt-in.
- **An unbounded, ever-growing in-memory cache feeding a windowed calculation** — F5;
  computation functions must take an explicit, bounded window as a parameter, never "however
  much history happens to be resident."
- **Choosing a data source because it's the one that still responds**, without recording
  that it was a fallback/unvalidated substitution — F9; provenance columns (2.2) make this
  visible even if it can't always be prevented.
- **An always-on listener process sharing a small box with scheduled batch jobs** — F10;
  resource contention silently degraded job runtime until it was caught and reverted. Prefer
  polling over persistent connections unless streaming is proven necessary at this scale.
- **Trusting a job's own exit code as proof it ran correctly** — F8; "exited 0" is not
  "did the right thing," especially for self-updating/self-hosted runners. External,
  independent heartbeat timers are the only defense that doesn't depend on the thing being
  monitored to report its own failure.
- **A vendor's response shape changing silently and being deserialized "successfully" into
  garbage** — defend with cassette-based contract tests (Section 3) that fail loudly when a
  recorded fixture no longer matches the shape the parser expects, rather than discovering
  it downstream as a wrong number.

---

## 8. Sources cited (fetched directly)

- https://healthchecks.io/ — free-tier limits (20 checks) for dead-man's-switch monitoring
- https://cronitor.io/pricing — Cronitor tier structure ($2/monitor/mo, 5 free monitors, $6,000/yr enterprise)
- https://github.com/elementary-data/elementary — Elementary OSS license (Apache-2.0) and built-in freshness/volume/schema/anomaly checks
- https://www.elementary-data.com/pricing — Elementary Cloud tier structure (quote-only, no published USD)
- https://openlineage.io/docs/ — OpenLineage Job/Run/Dataset/facet model and its enterprise-interop design target
- https://www.w3.org/TR/prov-overview/ — W3C PROV Entity/Activity/Agent core model
- https://chaoslabs.xyz/posts/oracle-data-freshness-accuracy-latency-pt-5 — crypto-oracle framing of data freshness (updates-per-second, inter-update-time measurement)
- https://dqops.com/docs/categories-of-data-quality-checks/how-to-detect-timeliness-and-freshness-issues/ — concrete max-days-lag threshold pattern with warning/error severities, and rolling anomaly-based freshness detection
- https://docs.greatexpectations.io/docs/reference/learn/data_quality_use_cases/freshness/ — GX's `ExpectColumnMaxToBeBetween`/`ExpectColumnMinToBeBetween` freshness API pattern
- https://github.com/calogica/dbt-expectations — `expect_row_values_to_have_recent_data` / `expect_grouped_row_values_to_have_recent_data` freshness test macros
- https://pandera.readthedocs.io/ — Pandera's statistically-typed dataframe validation, multi-backend support, Apache-2.0 license
- https://greatexpectations.io/gx-core/ — GX Core Apache-2.0 licensing and 2026 GX Cloud wind-down
- https://github.com/evidentlyai/evidently — Evidently open-source scope (ML/LLM/data quality reports)
- https://github.com/awslabs/python-deequ — PyDeequ's Spark dependency
- https://grafana.com/docs/grafana/latest/alerting/guides/missing-data/ — Grafana's No-Data vs stale-series distinction, informing the UI staleness treatment
- https://www.arcade.dev/patterns/graceful-degradation/ and https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_graceful_degradation.html — graceful-degradation argument for partial-failure semantics
- https://rogulski.it/blog/pytest-httpx-vcr-respx-remote-service-tests/ and https://punksecurity.co.uk/blog/using_vcrpy/ — VCR.py/respx cassette-based contract testing pattern
- https://thomas-dhollander.medium.com/robust-detection-of-stale-sensor-data-a-multi-faceted-challenge-bf9ed0609ef7 — frozen/repeat-value detection methodology (deterministic filter, 100% recall at zero false positives for stale-value episodes)

Items marked **UNVERIFIED** in the body: Elementary's paid-tier dollar figure; the specific
cross-source crypto-price divergence tolerance percentage (needs empirical tuning against
this project's actual two vendors, not literature).
