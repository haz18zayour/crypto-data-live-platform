---
id: US-702
title: MVRV registered across BTC/ETH/BNB; SOL declared NOT_DEFINABLE
priority: 2
touches:
  - ingest/registry.yaml
  - ingest/pipeline.py
  - tests/test_registry.py
  - tests/test_persist_board.py
context:
  - AGENTS.md
  - prds/PRD-007-onchain/10-research.md
  - project-documents/11_Data_Model.md
---

As the owner, I want MVRV registered for every asset where it genuinely exists and declared
absent where it doesn't, so that US-701's fetcher reaches the board for real assets instead of
staying a proof of concept.

Live-probed at this PRD's G1 gate: `CapMVRVCur` is `FREE` on Coin Metrics for BTC, ETH, and BNB.
For SOL it returns `bad_parameter` — not merely unconfirmed, genuinely unsupported. No vendor
researched (Coin Metrics, Glassnode, CryptoQuant, Messari, Santiment) sells real SOL MVRV at any
price, because Solana is account-based with no UTXO to anchor a realized-cap methodology to.

## Acceptance criteria

- [test: the registry carries three MVRV entries — BTC, ETH, BNB — each with talib_function omitted] Matches `btc_daily_close` and PRD-006's derivatives entries' existing precedent for a non-TA-Lib registry entry
- [test: SOL's MVRV entry declares not_definable with the reason naming the account-based/no-UTXO/no-vendor finding] Not a placeholder — the actual, cited reason
- [test: every MVRV entry declares uncorroborated or corroboration explicitly] Per US-306; Coin Metrics is the only source researched for this metric, so uncorroborated with that stated
- [test: `assert_registry_coverage` passes for all three new entries] Golden, response model, required_bars, parameters
- [test: a run persists one MVRV datapoint per asset for BTC/ETH/BNB] End to end for this metric
- [test: an asset whose MVRV fetch fails persists as ERROR/FETCH_FAILED, and the other two still persist] One asset's failure does not take down the run
- [integration: a full run against live Coin Metrics persists MVRV for BTC, ETH and BNB] Real requests, real database, three rows
- [cmd: uv run pytest -q --no-header -o addopts=] The full offline suite stays green

## Notes for the implementer

- **Check whether this PRD's other stories have already added indicator families to the
  registry before this one runs.** Every prior indicator-family addition on this board (PRD-006's
  four derivatives stories) grew the completeness matrix's total cell count, and `web/src/`'s test
  suite (`BoardMatrix.test.tsx`, `CoverageHeadline.test.tsx`, `board.test.ts`,
  `fixtures/mixedBoard.test.ts`) hardcodes that total rather than deriving it from the registry.
  Update those four files' expected counts in this story's own commit — three of PRD-006's seven
  stories needed a second attempt purely because this was missed the first time.
- Reuse US-701's fetcher for each asset the same way `okx.py`'s BTC fetcher is retargeted
  per-asset elsewhere in this project — do not duplicate the rate-limit-backoff logic per asset.
