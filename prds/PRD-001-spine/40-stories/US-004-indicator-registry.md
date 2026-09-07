---
id: US-004
title: Indicator registry — one declarative source of truth
priority: 4
touches:
  - ingest/registry.py
  - ingest/registry.yaml
  - tests/test_registry.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
  - prds/PRD-001-spine/10-research.md
---

As the owner, I want every indicator declared in one file that names its vendor, endpoint,
**exact response field**, freshness budget and which assets it is definable for, so that
adding an indicator is a row rather than a migration, and so integrity coverage can be
generated from it instead of hand-maintained.

The prior system stored indicators as columns — `ls_ratio_score`, `oi_raw`, … — which meant
its integrity check covered exactly two hardcoded rows and drifted from reality without
anyone noticing.

## Acceptance criteria

- [test: every registry entry declares vendor, endpoint, source_field, freshness budget and definable assets] An entry missing any of these fails validation at load time
- [test: an entry whose source_field is absent is rejected] Recording only the endpoint is insufficient — this is the F11 defence, where funding was read from the wrong field of the right endpoint
- [test: registry rejects duplicate indicator keys] Two entries cannot claim the same key
- [test: definable_for lists assets explicitly and rejects a wildcard] An indicator must state which assets it is genuinely valid for; there is no "all"
- [cmd: uv run python -m ingest.registry --validate] Validating the shipped registry exits 0

## Notes for the implementer

Each entry carries at minimum:

```yaml
- key: btc_daily_close
  vendor: okx
  endpoint: https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D
  source_field: "candle[4] (close), where candle[8] == \"1\""
  definable_for: [BTC]
  expected_update_interval_seconds: 86400
  freshness_warn_seconds: 108000    # 30h
  freshness_stale_seconds: 172800   # 48h
```

- `definable_for` is about **meaning, not availability**. SOPR on Solana is not "missing", it
  is undefined — Solana is account-based and has no UTXO to timestamp. That distinction is why
  a wildcard is rejected.
- `expected_update_interval` and the freshness thresholds are deliberately three separate
  numbers. How often a source publishes is not the same question as how stale is tolerable.
- Only `btc_daily_close` is registered in this PRD. Do not add speculative entries for
  indicators that later PRDs will introduce.
- The registry is blast-radius: changing an entry retroactively changes the meaning of every
  stored value carrying that key.
