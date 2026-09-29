---
id: US-1001
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
- [test: IndicatorDefinition gains derives_from: str | None, and a validator requires it for every entry carrying talib_function, rejecting a talib_function entry with derives_from unset] Every derived indicator names its root
- [test: a validator rejects a derives_from value that does not match any existing registry key] derives_from cannot point at nothing
- [test: IndicatorDefinition gains freshness_unmeasurable: str | None] The declaration exists
- [test: every entry in registry.yaml currently declares exactly one of frozen_after_observations or expected_constant; btc_daily_close (or the equivalent root close entry) declares frozen_after_observations; btc_funding_rate (and eth/sol/bnb funding) declare expected_constant with a reason citing the 0.01% clamp] Real data populated, not just schema
- [test: every talib_function-carrying entry in registry.yaml (RSI, EMA stack, MACD, StochRSI, Bollinger, ATR, OBV) declares derives_from pointing at the correct underlying price/volume series for its own asset] Real dependency links populated
- [test: defillama_stablecoin_supply and sol_staking (validators.app) entries in registry.yaml declare freshness_unmeasurable with their real reasons] The two wall-clock fetchers are marked, not silently green
- [test: a registry entry missing a required frozen declaration, or a talib_function entry missing derives_from, fails registry validation at load time] The coverage gate itself
- [cmd: uv run pytest -q] The full offline suite stays green
- [cmd: uv run mypy ingest --strict] Strict typing holds on the new fields

## Notes for the implementer

- Check `fetched_at` spread on already-persisted Fear & Greed rows (or the vendor's own docs)
  before deciding its exact `expected_constant` reason — the G1 assumption flagged the exact
  update cadence as unverified.
- `derives_from` should name the registry key for the *raw* price/rate series a technical indicator
  is computed from for the same asset (e.g. an EMA/RSI/MACD/Bollinger/ATR/OBV entry for BTC points
  at whichever registry key represents BTC's underlying OHLCV-derived close series). Look at how
  `talib_function` entries are already grouped by asset in `registry.yaml` to find the right target
  key per entry — do not guess a single global root for all assets.
- This is a registry/config change, not a database migration — no blast-radius gate applies to
  this story alone. The frozen-declaration and derives_from fields are consumed by US-1002's SQL
  view; do not build any SQL in this story.
