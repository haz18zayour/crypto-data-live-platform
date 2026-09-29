---
id: US-910
title: SoSoValue, DefiLlama (stablecoincharts), and alternative.me backfill recipes
priority: 7
touches:
  - ingest/backfill.py
  - ingest/fetchers/sosovalue.py
  - ingest/fetchers/defillama_stablecoins.py
  - ingest/fetchers/alternative_me.py
  - tests/test_backfill_sosovalue.py
  - tests/test_backfill_defillama.py
  - tests/test_backfill_alternative_me.py
context:
  - AGENTS.md
  - prds/PRD-009-history-charts/10-research.md
  - prds/PRD-009-history-charts/20-decisions.yaml
---

As the owner, I want ETF net flows, stablecoin supply, and Fear & Greed to backfill from each
vendor's real history, with SoSoValue's actual shape and limits live-probed first since research
could not confirm them from documentation alone.

DefiLlama's `/stablecoincharts/{chain}` is a different endpoint from the same already-integrated
vendor, confirmed live to hold daily history back to 2017 for Ethereum — this removes stablecoin
supply from the brief's original (and now overturned) "cannot backfill" assumption.

## Acceptance criteria

- [integration: a live probe of SoSoValue's history-capable endpoint for one asset returns a real response, and its actual date range and rate limit are confirmed rather than assumed from the unverified third-party claim research found] Settles the assumption flagged in 30-spec.md before any backfill code commits to a specific window
- [test: SoSoValue backfill persists Decimal values via the same str()-conversion discipline as the live fetcher (never Decimal(float) directly)] Reuses PRD-008's already-fixed float-precision defect, does not reintroduce it
- [test: DefiLlama backfill reads /stablecoincharts/{chain} for Ethereum, Solana, and BSC, and the most recent backfilled value for each chain matches that chain's current live /stablecoinchains value within the same day] Proves the two endpoints agree at the seam, not a silent splice between them
- [test: alternative.me backfill reads historical Fear & Greed values but never persists or renders the vendor's own value_classification verdict label] Directly guards against the exact vendor-supplied verdict research flagged as a gotcha
- [test: BTC's stablecoin-supply cell and BNB's ETF-flow cell remain NOT_DEFINABLE for backfill exactly as they are for live — no backfill attempt is made against a settled absence] Consistency with PRD-008's decisions
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- Depends on US-903's shared backfill entry point and coverage test.
- `SOSOVALUE_API_KEY` must be available wherever this backfill actually runs — check the relevant
  workflow's `env:` block directly.
- Do not assume SoSoValue's history endpoint is the same URL/shape as `etfs/summary-history` with
  a larger `limit` parameter until the live probe confirms it — research explicitly could not
  fetch SoSoValue's own documentation.
