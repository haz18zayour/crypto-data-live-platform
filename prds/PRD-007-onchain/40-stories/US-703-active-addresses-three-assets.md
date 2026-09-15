---
id: US-703
title: Active addresses (Coin Metrics) registered across BTC/ETH/BNB
priority: 3
touches:
  - ingest/registry.yaml
  - tests/test_registry.py
  - tests/test_persist_board.py
context:
  - AGENTS.md
  - prds/PRD-007-onchain/10-research.md
  - project-documents/11_Data_Model.md
---

As the owner, I want active addresses registered for BTC, ETH and BNB from Coin Metrics, the
same fetcher and discipline as MVRV, so a second metric proves the pattern generalizes before
SOL's genuinely different build path (US-704) has to.

Live-probed at G1: `AdrActCnt` is `FREE` on Coin Metrics for BTC, ETH, and BNB. This story
registers exactly those three; SOL's `active_addresses` cell is **not** declared here — US-704
adds it from a completely different vendor and methodology under the same family label, so the
board shows one row spanning two sources rather than two competing rows for the same concept.

## Acceptance criteria

- [test: the registry carries three active-addresses entries — BTC, ETH, BNB — sourced from Coin Metrics, talib_function omitted] Same non-TA-Lib pattern as MVRV
- [test: every entry declares uncorroborated] Coin Metrics is the only source researched for this metric
- [test: `assert_registry_coverage` passes for all three new entries] Golden, response model, required_bars, parameters
- [test: a run persists one active-addresses datapoint per asset for BTC/ETH/BNB] End to end for this metric
- [test: an asset whose active-addresses fetch fails persists as ERROR/FETCH_FAILED, and the other two still persist] Per-cell failure isolation, same as every prior story on this board
- [integration: a full run against live Coin Metrics persists active addresses for BTC, ETH and BNB] Real requests, real database, three rows
- [cmd: uv run pytest -q --no-header -o addopts=] The full offline suite stays green

## Notes for the implementer

- Do **not** add a SOL `active_addresses` entry in this story, even though the family will need
  one. US-704 adds it from the Solana RPC build path once that fetcher exists — adding a
  placeholder or a stubbed entry here would leave a cell that looks registered but is backed by
  nothing, exactly the kind of gap this board's design exists to make loud rather than hide.
- Same web-test hardcoded-count note as US-702: check and update
  `BoardMatrix.test.tsx`/`CoverageHeadline.test.tsx`/`board.test.ts`/`fixtures/mixedBoard.test.ts`
  in this story's own commit if the total cell count changed.
