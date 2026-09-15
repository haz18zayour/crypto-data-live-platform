---
id: US-603
title: Open interest — USDT-margined only, fetcher and registry entries for four assets
priority: 3
touches:
  - ingest/fetchers/okx_derivatives.py
  - ingest/schemas.py
  - ingest/registry.yaml
  - tests/test_okx_derivatives_fetcher.py
  - tests/test_registry.py
context:
  - AGENTS.md
  - prds/PRD-006-derivatives/10-research.md
  - project-documents/11_Data_Model.md
---

As the owner, I want open interest fetched and persisted for all four assets, in one
denomination only, so that a coin-margined figure can never be summed with a USD-margined one
under one label.

Research names this the second load-bearing trap in this data category, distinct from the
funding-rate interval problem: OKX (like Binance and Bybit) unifies linear and inverse
contracts under one `instType` parameter, but the **response units still differ** —
coin-denominated for inverse, USD-denominated for linear. This board fetches **linear
(USDT-margined) only**, per the G1 decision, so the trap cannot occur by construction rather
than by a validation check that could itself have a gap.

## Acceptance criteria

- [test: the fetcher requests instId={ASSET}-USDT-SWAP only, never a -USD-SWAP inverse instrument] Linear only, structurally — not filtered after the fact
- [test: a malformed or reshaped response is rejected by the response model] `extra="forbid"` on the new `OkxOpenInterestResponse`
- [test: an HTTP error returns Error with the status code in the detail, and no value] Same discipline as every fetcher in this project
- [test: source_timestamp is the response's own timestamp field and is strictly in the past] The F11 defence
- [test: the registry carries four open-interest entries, one per asset, each declaring uncorroborated] Same reasoning as US-602's funding-rate entries
- [test: `assert_registry_coverage` passes for all four new entries] Golden, response model, required_bars, parameters
- [test: a run persists one open-interest datapoint per asset] End to end for this metric
- [integration: a live OKX request returns open interest for all four USDT-margined perpetuals] Hits the real endpoint for each asset
- [cmd: uv run pytest -q --no-header -o addopts=] The full offline suite stays green

## Notes for the implementer

- Endpoint: `GET https://www.okx.com/api/v5/public/open-interest` with `instType=SWAP` and
  `instId={ASSET}-USDT-SWAP`.
- Verify the response's own value field (`oi` vs `oiCcy` vs `oiUsd` — research did not
  independently re-confirm every field name) actually reports a **USD-denominated** figure for
  a linear instrument before treating any field as the persisted value. If OKX's linear-contract
  response reports a coin-denominated quantity under a field like `oiCcy`, do not convert it
  yourself in this story — persist whichever field OKX documents as authoritative for that
  instrument type, and record which field it was in `source_field`, the same way `btc_daily_close`
  records exactly which array index and confirm-flag it reads.
- Do not build a cross-asset "total open interest" figure. This project's rule against composite
  values applies here too — each asset's open interest is its own cell, never summed into one
  headline number.
