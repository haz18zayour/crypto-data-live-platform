# 11 · Data model

The compact, authoritative design. Distilled from `research/R5-data-integrity-engineering.md`
and `research/R0-lessons-from-prior-system.md` so stories can inline this instead of the full
research. Where this conflicts with a research file, **this file wins** — it is the decision.

---

## The one rule

**A wrong number must look different from a right one.** Everything below exists to make that
structurally true rather than a matter of discipline.

## 1. Status is a type, not a convention

Four outcomes, modelled as a discriminated union of frozen dataclasses — never one class with
optional fields:

```
Ok(value, source_timestamp)          # we have it, and it is current
Stale(value, source_timestamp)       # we have it, but it is past its freshness budget
Unavailable(reason)                  # we do not have it, and here is why
Error(reason, detail)                # the attempt failed
```

`Unavailable` and `Error` **have no `value` attribute at all**. Reading one is an
`AttributeError`, not a zero.

**Forbidden:** any helper that converts absence back to a number — `.value_or(0.0)`,
`.as_float()`, `or 0`, `fillna(0)`, a neutral default. This is the exact mechanism by which
the prior system's funding rate, open interest and long/short ratio reported a confident
`0.0` for months because a fetcher was never called.

### 1.1 Three kinds of absence, kept distinct

```
NOT_DEFINABLE   the metric has no meaning on this chain and never will
                (SOPR/MVRV on Solana: account-based, no UTXO to timestamp).
                Not purchasable at any price. Permanent, and correct.
PAYWALLED       exists, we lack credentials (realized cap on Coin Metrics free)
FETCH_FAILED    should exist, did not arrive — timeout, 500, empty after filtering
NOT_FETCHED     the pipeline never attempted it
```

`NOT_FETCHED` is the default state of every indicator at the start of a run. It exists so that
"never ran" and "ran and got nothing" are different rows. Collapsing these four into one blank
cell destroys the information the owner most needs: whether a gap is permanent, purchasable,
broken, or a bug.

## 2. Schema

```sql
CREATE TYPE datapoint_status  AS ENUM ('OK','STALE','UNAVAILABLE','ERROR');
CREATE TYPE unavailable_reason AS ENUM ('NOT_DEFINABLE','PAYWALLED','FETCH_FAILED','NOT_FETCHED');

CREATE TABLE datapoints (
  id               bigserial PRIMARY KEY,
  indicator_key    text NOT NULL,          -- FK in spirit to the registry
  asset            text NOT NULL,          -- what we DISPLAY it as
  measured_on      text NOT NULL,          -- what it was ACTUALLY measured on
  value            double precision,       -- NULL unless status IN ('OK','STALE')
  status           datapoint_status NOT NULL,
  reason           unavailable_reason,
  source_vendor    text NOT NULL,
  endpoint         text NOT NULL,
  source_field     text NOT NULL,          -- WHICH FIELD of the response
  fetched_at       timestamptz NOT NULL,   -- when WE fetched
  source_timestamp timestamptz,            -- when the SOURCE says it is as-of
  CONSTRAINT asset_match     CHECK (status <> 'OK' OR measured_on = asset),
  CONSTRAINT value_iff_ok    CHECK ((status IN ('OK','STALE')) = (value IS NOT NULL)),
  CONSTRAINT reason_required CHECK ((status IN ('UNAVAILABLE','ERROR')) = (reason IS NOT NULL))
);

CREATE INDEX ON datapoints (indicator_key, asset, fetched_at DESC);
```

**Long and narrow, never wide.** The prior system stored one column pair per indicator
(`ls_ratio_score`, `oi_raw`, …), so adding an indicator required a migration and its integrity
check covered exactly two hardcoded rows while drifting from reality unnoticed. Here a new
indicator is a row.

### Why each constraint exists

| Constraint | Prevents |
|---|---|
| `asset_match` | BTC's MVRV displayed as SOL's. The prior system did this to 8 coins and called the result *"not degraded data, wrong data"*. Now a **database error** |
| `value_iff_ok` | Status and value drifting apart — a value with no status, or an `OK` with nothing in it |
| `reason_required` | Absence that does not say why |

A mismatched row **may** be inserted as `UNAVAILABLE` for audit. The constraint only forbids
it carrying `OK`. Recording that we fetched the wrong thing is useful; displaying it as
correct is not.

### Two timestamps, two owners

`fetched_at` is set by the **writer**. `source_timestamp` is set by the **fetcher**, from the
source's own as-of time. They answer different questions and must never be conflated.

**A `source_timestamp` in the future is an error, not a value.** The prior system read funding
from `premiumIndex.lastFundingRate` — a continuously-moving estimate for an *upcoming*
settlement — instead of the settled series, and stored it as history. Measured: `0.00002925`
against a settled `0.00003113`, on a number that keeps drifting. This assertion is what makes
that class of bug impossible.

## 3. Registry — one declarative source of truth

```yaml
- key: btc_daily_close
  vendor: okx
  endpoint: https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D
  source_field: 'candle[4] (close), where candle[8] == "1"'
  definable_for: [BTC]
  expected_update_interval_seconds: 86400
  freshness_warn_seconds:  108000   # 30h
  freshness_stale_seconds: 172800   # 48h
```

- **`source_field` is mandatory.** Recording only the endpoint is how the funding-rate bug
  stayed invisible — right endpoint, wrong field.
- **`definable_for` is about meaning, not availability**, and a wildcard is rejected. An
  indicator must state which assets it is genuinely valid for.
- Integrity coverage is **generated from this registry**, so an indicator with no coverage is
  a build error rather than an oversight.
- The registry is blast-radius: changing an entry retroactively changes the meaning of every
  stored value carrying that key.

## 4. Freshness — three numbers, not one

| Field | Question it answers |
|---|---|
| `expected_update_interval` | how often the source *publishes* |
| `freshness_warn` | when to flag it visually (≈1.5× interval) |
| `freshness_stale` | when it becomes `STALE` (≈2× interval) |

Two thresholds survive one missed cycle without crying wolf, and catch two. A daily-close
indicator: interval 24h, warn 30h, stale 48h.

**Frozen is a separate check.** A source can be *fresh* — `fetched_at` seconds ago — while
returning an identical payload forever. Detecting that means comparing against the last N
stored values, and it is PRD-009. PRD-001 only provides the columns that make it possible.

## 4b. Reference period vs published date

**The timestamp a value describes is not the timestamp at which it became knowable.** Measured
against the live FRED API on 2026-09-08:

| Series | Latest observation | Days behind that day |
|---|---|---|
| `DFF` (Fed funds) | 2026-09-03 | 5 |
| `DTWEXBGS` (broad USD) | 2026-08-28 | 11 |
| `M2SL` (M2) | 2026-07-01 | **69** |

`M2SL` is a *monthly* series: the July figure is the newest that exists, and it was published
weeks after July ended. Displaying `23218` as today's M2 is false in two separate ways — wrong
period, and silent about the delay.

So a lagged indicator carries **two** timestamps, not one:

- `reference_period` — the period the value describes (July 2026)
- `source_timestamp` / `published_at` — when it became knowable

The UI shows both, and the freshness budget is computed against **publication**, not the
reference period — otherwise every monthly series is permanently `STALE` by construction.

This generalises past macro: funding rate (settled vs predicted), ETF flows (T+1), an unclosed
daily candle, and CPI are all the same shape. `ai-hedge-fund` reached it independently and
enforces it by filtering on `filing_date` rather than `report_period`, because the latter
"leaks 3-6 weeks of future" (R9 §2).

## 4c. Corroboration — disagreement is a finding, not a problem to resolve

Every other rule in this document defends against a failure someone predicted. Corroboration is
the only one that catches a wrong number **nobody thought to check for**, and it is therefore
the most valuable single mechanism here. Designed in PRD-003.

The shape: fetch the same quantity from two or more independent venues, compare, and record the
comparison.

**The trap to avoid:** silently picking a winner. Averaging two disagreeing sources, or
preferring the "primary" one, throws away the only signal that something is wrong and produces
a confident number — which is exactly the failure mode this product exists to eliminate. If two
venues disagree beyond tolerance, **that is the finding**, and it must reach the face of the
value.

Concretely:

- The measured OKX case is the worked example. `bar=1D` (Hong Kong day) gave **78,834.1**;
  `bar=1Dutc` gave **79,111.8** — 0.35% apart. Comparing OKX against Coinbase would have
  flagged it automatically on day one. Instead it was caught because a person read the
  timestamp. That is not a repeatable defence.
- Tolerance is per-indicator and belongs in the registry, not hardcoded. Spot close across major
  venues sits far tighter than, say, aggregated open interest. R5 flagged a specific numeric
  tolerance as **UNVERIFIED** — it must be measured from observed spreads, not guessed.
- Divergence needs its own visible state. Whether that is a new `reason` value, a separate
  `corroboration` column, or a companion row is a PRD-003 decision; what is settled here is that
  it may not be silently swallowed, and that a corroborated value and an uncorroborated one must
  not look identical.
- Corroboration is not available for everything. A metric published by exactly one vendor
  (Coin Metrics MVRV) has no second opinion, and that fact should itself be visible rather than
  implied.

## 5. Fallbacks are different indicators

If a value cannot be obtained from its declared source, the answer is `UNAVAILABLE` — **not a
substitute source under the same label.** The prior system silently swapped FRED's `DTWEXBGS`
(26 currencies, weekly, lagged) for yfinance's `DX-Y.NYB` (6 currencies, real-time) behind one
"DXY" label; the value jumped discontinuously whenever the fallback engaged and nothing
recorded which had produced it.

A second source is a second registry entry with its own key, displayed as its own series, or
it does not exist.

## 6. Rendering

TypeScript mirrors the union, with an exhaustive `switch` and a `never` fallthrough so an
unhandled status is a **compile error**:

```ts
type Datapoint =
  | { status: "OK";          value: number; sourceTimestamp: string }
  | { status: "STALE";       value: number; sourceTimestamp: string }
  | { status: "UNAVAILABLE"; reason: Reason }
  | { status: "ERROR";       reason: Reason; detail: string };
```

- `UNAVAILABLE` renders an em dash and its reason. **Never `0`. Never blank.**
- `STALE` renders the value **with its age and a visible stale treatment** — shown, but never
  shown as if current.
- Provenance (vendor, endpoint, source timestamp) is on the face of the value, not behind a
  click.
- No "last known good" fallback that silently presents an older value as current.
