---
id: US-705
title: Exchange flows (Coin Metrics) — BTC/ETH only; BNB and SOL each NOT_DEFINABLE with distinct, confirmed reasons
priority: 5
touches:
  - ingest/registry.yaml
  - tests/test_registry.py
  - tests/test_registry_not_definable.py
  - tests/test_persist_board.py
context:
  - AGENTS.md
  - prds/PRD-007-onchain/10-research.md
  - project-documents/11_Data_Model.md
---

As the owner, I want exchange flows registered exactly where they genuinely exist and declared
absent everywhere else, with each absence carrying its own real reason rather than one shared
excuse, so the board never implies BNB and SOL are missing this metric for the same cause when
they aren't.

Coin Metrics reports net exchange flow via `FlowInExNtv`/`FlowOutExNtv`. Live-probed at G1: both
are `FREE` for BTC and ETH, but return `bad_parameter` for BNB — confirmed `NO-METRIC`, not
merely unconfirmed, and a finding the roadmap never called out. SOL's exchange flows are `OMIT`
for a completely different reason (research R8): Solana's exchange-wallet labeling ecosystem is
materially less mature than Ethereum's, and even mature vendors with a decade of BTC/ETH
labeling publicly disagree with each other on the same flow events — a self-curated Solana label
set would produce a confidently-wrong number, not a lesser one.

## Acceptance criteria

- [test: the registry carries two exchange-flow entries — BTC, ETH — sourced from Coin Metrics] Only where the metric genuinely exists
- [test: BNB's exchange-flow entry declares not_definable with a reason naming Coin Metrics' confirmed NO-METRIC response, distinct from SOL's reason] The specific, live-confirmed cause, not a copy of SOL's
- [test: SOL's exchange-flow entry declares not_definable with a reason naming the immature exchange-labeling ecosystem, distinct from BNB's reason] The specific research finding, not a copy of BNB's
- [test: BNB's and SOL's exchange-flow reasons are not identical strings] Directly guards against the two absences being collapsed into one shared excuse — the exact category-collapse R2 warned against
- [test: `assert_registry_coverage` passes for both new entries] Golden, response model, required_bars, parameters
- [test: a run persists one exchange-flow datapoint per asset for BTC and ETH] End to end for this metric
- [integration: a full run against live Coin Metrics persists exchange flows for BTC and ETH] Real requests, real database, two rows
- [cmd: uv run pytest -q --no-header -o addopts=] The full offline suite stays green

## Notes for the implementer

- Reuse US-701's fetcher and rate-limit-backoff logic; this story only adds registry entries and
  a net-flow computation (`FlowInExNtv - FlowOutExNtv`, or persist both directions separately if
  that better matches Coin Metrics' own field semantics — confirm against the live response
  before choosing, and record which you did in `source_field`).
- Same web-test hardcoded-count note as every prior story adding a family to this board.
