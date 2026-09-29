---
id: US-1008
title: Registry schema extension — frozen-detection declarations, derives_from for TA-Lib entries, freshness_unmeasurable for wall-clock fetchers
priority: 1
touches:
  - ingest/registry.py
  - ingest/registry.yaml
  - tests/test_registry.py
context:
  - AGENTS.md
  - prds/PRD-010-integrity-dashboard/10-research.md
  - prds/PRD-010-integrity-dashboard/20-decisions.yaml
---

As the owner, I want every registered indicator to explicitly declare how frozen-value detection
applies to it, so that a new indicator can never silently ship without the audit this PRD adds —
the same coverage discipline this project already applies to goldens, tests, and backfill recipes.

Research found that a global threshold would itself become a judgement about the market (OKX
funding rate legitimately clamps near zero for many consecutive intervals in a calm market), and
that ~70% of the board is TA-Lib-derived from a root series that a naive per-indicator frozen check
would never catch freezing (Wilder/EMA smoothing keeps moving even when its input is stuck). Two
fetchers (`defillama_stablecoins.py:237-243`, `validators_app.py:48`) stamp `source_timestamp` as
fetch-wall-clock rather than a real vendor observation time, making any freshness check on them
structurally always green.

## Acceptance criteria

- [test: IndicatorDefinition gains frozen_after_observations: int | None and expected_constant: str | None, and a validator rejects an entry declaring both or neither] Exactly one frozen-detection declaration per indicator, no default
- [test: IndicatorDefinition gains derives_from: str | None, and a validator requires exactly one of derives_from or frozen_propagation_unavailable (a new str | None field) for every entry carrying talib_function, rejecting a talib_function entry with neither or both set] Every derived indicator either names its real root or explicitly declares that propagation cannot apply to it
- [test: a validator rejects a derives_from value that does not match any existing registry key, and rejects an entry whose derives_from equals its own key (a self-loop)] derives_from cannot point at nothing or at itself
- [test: IndicatorDefinition gains freshness_unmeasurable: str | None] The declaration exists
- [test: every entry in registry.yaml currently declares exactly one of frozen_after_observations or expected_constant; btc_daily_close declares frozen_after_observations] Real data populated, not just schema
- [test: every BTC talib_function entry (RSI, EMA stack, MACD, StochRSI, Bollinger, ATR, OBV) declares derives_from=btc_daily_close, the one asset where a real, board-visible, persisted close price already exists to point at] The one case where real propagation is possible today
- [test: every ETH/SOL/BNB talib_function entry declares frozen_propagation_unavailable with a reason explaining that no per-asset close/volume series is separately registered for that asset (technical indicators are computed directly from freshly-fetched OHLCV bars per ingest/pipeline.py's compute path, never from a persisted per-asset "close" indicator; only BTC also exposes its close as its own board cell, by deliberate product decision — confirmed live: ETH/SOL/BNB daily close renders "Daily close is intentionally BTC-only on this board")] An honest, documented limitation instead of a fabricated root — this project's own no-proxy rule applies to its own audit layer exactly as it does to market data: absent real data to derive from, state that plainly rather than inventing a stand-in
- [test: npm --prefix web test passes with no regression in existing fixture-derived counts (src/fixtures/mixedBoard.test.ts, src/CoverageHeadline.test.tsx, src/BoardMatrix.test.tsx) — these tests hard-code exact NOT_DEFINABLE/OK counts derived from the real registry and must show zero new visible cells and zero changed cell count for any existing entry] The regression class that sank the first three attempts (each one invented a new eth_daily_close/sol_daily_close/bnb_daily_close board cell to give derives_from somewhere to point), checked directly — this story adds new OPTIONAL FIELDS to existing entries only; it must never add, remove, or change the definable_for of any registry row
- [test: defillama_stablecoin_supply and sol_staking (validators.app) entries in registry.yaml declare freshness_unmeasurable with their real reasons] The two wall-clock fetchers are marked, not silently green
- [test: a registry entry missing a required frozen declaration, or a talib_function entry missing both derives_from and frozen_propagation_unavailable, fails registry validation at load time] The coverage gate itself
- [cmd: uv run pytest -q] The full offline suite stays green
- [cmd: uv run mypy ingest --strict] Strict typing holds on the new fields

## Notes for the implementer

- Check `fetched_at` spread on already-persisted Fear & Greed rows (or the vendor's own docs)
  before deciding its exact `expected_constant` reason — the G1 assumption flagged the exact
  update cadence as unverified.
- **Do not add any new registry entry at all in this story, for any asset.** Three prior attempts
  tried registering `eth_daily_close`/`sol_daily_close`/`bnb_daily_close` (or an equivalent
  synthetic root) as new board-visible entries, purely to give `derives_from` something to point
  at, and each one broke `npm --prefix web test`'s existing hard-coded coverage counts by silently
  adding cells this project's own design explicitly rules out (daily close is BTC-only, by
  deliberate product decision). This story only adds optional fields to `IndicatorDefinition` and
  populates them on the ~150 rows already in `registry.yaml` — it does not add, remove, or resize
  any `definable_for` list, and it does not create any new indicator. Building a real, fetchable,
  non-board-visible per-asset root (which would need its own vendor/endpoint/fetcher/persist wiring,
  not just a schema field) is out of scope here; `frozen_propagation_unavailable` is the honest,
  correctly-scoped answer for the three assets that genuinely have no existing root to point at.
- Run `npm --prefix web test` yourself before finishing this story — it is the fastest, cheapest
  signal that a change accidentally added, removed, or altered a visible cell. This project's own
  test suite already hard-codes exact NOT_DEFINABLE/OK/FETCH_FAILED counts derived from the real
  registry precisely to catch this class of regression; do not treat a failure there as unrelated
  to your own change, and do not touch those tests' expected counts to make them pass — if a count
  changed, your registry.yaml change is the bug, not the test.
- This is a registry/config change, not a database migration — no blast-radius gate applies to
  this story alone. The frozen-declaration, derives_from, and frozen_propagation_unavailable fields
  are consumed by US-1002's SQL view; do not build any SQL in this story.
