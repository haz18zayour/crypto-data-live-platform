---
id: US-602
title: Funding rate registered across BTC/ETH/SOL/BNB, persisted alongside the technical board
priority: 2
touches:
  - ingest/registry.yaml
  - ingest/pipeline.py
  - tests/test_registry.py
  - tests/test_persist_board.py
context:
  - AGENTS.md
  - prds/PRD-006-derivatives/10-research.md
  - project-documents/11_Data_Model.md
---

As the owner, I want funding rate registered and persisted for all four assets, so that the
fetcher US-601 proved on BTC actually reaches the database and the board for every asset this
project covers.

## Acceptance criteria

- [test: the registry carries four funding-rate entries, one per asset, each with talib_function omitted] Matches `btc_daily_close`'s existing precedent for a non-TA-Lib registry entry
- [test: every funding-rate entry declares uncorroborated, citing the G1 finding] "No second venue's derivatives public endpoints were confirmed to exist or be reachable; Binance's futures API returns HTTP 451 to US IPs on public endpoints" — the actual reason, not a placeholder
- [test: `assert_registry_coverage` passes for all four new entries] Golden, response model, required_bars and parameters are all present per the existing generic coverage check — no special-casing for non-TA-Lib entries
- [test: a run persists one funding-rate datapoint per asset, with the derived interval in its source_field] Reuses US-601's fetcher; this story is registration and persistence, not new fetch logic
- [test: an asset whose funding-history fetch fails persists as ERROR/FETCH_FAILED, and the other three assets still persist] One asset's failure does not take down the run, matching the discipline `persist_board` already applies to the technical board
- [integration: a full run against live OKX persists funding rate for all four assets and the row count matches the registry] Real requests, real database, four rows
- [cmd: uv run pytest -q --no-header -o addopts=] The full offline suite stays green

## Notes for the implementer

- ETH/SOL/BNB instIds follow the same `{ASSET}-USDT-SWAP` pattern as BTC. Confirm each is a
  real, tradable OKX perpetual before assuming the pattern holds — BNB in particular has been a
  thinner-liquidity case elsewhere in this project's history (PRD-004's Coinbase daily-close
  measurement).
- This story does **not** call `run_all_assets()`/`persist_board()`'s existing TA-Lib-only path.
  Follow the same shape (`Result` per key, one `persist_datapoint` call per entry) but as a
  standalone assembly step — US-606 is where this and the other three metrics' equivalents get
  wired into one ingest run together. Do not couple them prematurely here.
- Reuse `okx_derivatives.py`'s fetcher for each asset the same way `okx.py`'s BTC fetcher is
  retargeted per-asset in `pipeline.py`'s `_AssetClient` — do not duplicate the interval-
  derivation logic per asset.
