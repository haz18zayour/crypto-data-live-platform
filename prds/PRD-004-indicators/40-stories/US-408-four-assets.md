---
id: US-408
title: Four assets, with per-venue history availability declared
priority: 8
touches:
  - ingest/registry.yaml
  - ingest/pipeline.py
  - tests/test_assets.py
context:
  - AGENTS.md
  - prds/PRD-004-indicators/10-research.md
---

As the owner, I want all four assets computed, with each venue's actual history depth recorded,
so that a shortfall is a declared limit rather than a runtime surprise or a value computed on
too little data.

**Measured today:** Coinbase has **no daily BNB candles before late October 2025** — roughly
**317 bars available**. Against a 250-bar requirement that clears by about 67 days, which is
thin enough to matter. The BNB-USD product itself is `online` with `trading_disabled: false`;
it is the *history* that is short, so the failure would appear as a puzzling truncation rather
than an obvious "unsupported pair".

## Acceptance criteria

- [test: the registry declares measured history availability per asset per venue] A number with a measurement date, not a guess
- [test: an asset with fewer available bars than required_bars is declared uncorroborated at that venue] Rather than computed on short data or silently skipped
- [test: BNB's Coinbase availability is recorded and compared against required_bars] The specific measured case, pinned as a regression
- [test: all four assets produce an indicator value or an explicit status] No asset silently absent from the board
- [integration: a full run computes indicators for BTC, ETH, SOL and BNB against live venues] The real scale test — four assets, real requests
- [cmd: uv run pytest -q --no-header -o addopts=] The whole suite passes at ~32 indicators

## Notes for the implementer

- Availability is **measured and dated**, then declared. Re-measuring is a deliberate act with a
  committed edit, the same discipline as the corroboration tolerance.
- An asset short of bars at one venue is still perfectly good at the other. Uncorroborated is
  the honest outcome, not exclusion — this product's whole point is that absence says why.
