---
id: US-804
title: SoSoValue ETF-flow fetcher — BTC/ETH/SOL, Decimal money parsing, BNB declared NOT_DEFINABLE
priority: 4
touches:
  - ingest/fetchers/sosovalue.py
  - ingest/schemas.py
  - ingest/registry.yaml
  - tests/test_sosovalue_fetcher.py
  - tests/test_registry_not_definable.py
context:
  - AGENTS.md
  - prds/PRD-008-macro-flows/10-research.md
  - prds/PRD-008-macro-flows/20-decisions.yaml
---

As the owner, I want US-listed spot ETF net flows for BTC, ETH, and SOL built from SoSoValue's
real API, with BNB's absence declared honestly (SoSoValue's API simply does not offer it), so a
viewer never mistakes "we didn't build it" for "no BNB ETF flow exists anywhere."

SoSoValue's `x-soso-api-key`-authenticated Demo API is confirmed live: 20 req/min, 100,000
req/month, `/etfs/summary-history` accepts `symbol` in `{BTC, ETH, SOL, LTC, HBAR, XRP, DOGE,
LINK, AVAX, DOT}` with `country_code` `US` — BNB is not in that enum. Money fields arrive as
long-decimal strings (e.g. `-55066297.0000000000000000`), which must be parsed as `Decimal`, not
`float`, or PRD-002's determinism golden files will drift.

## Acceptance criteria

- [test: the fetcher authenticates with a token read from configuration via the x-soso-api-key header, never hardcoded] Matches this project's fail-loud configuration discipline from US-002
- [test: BTC, ETH, and SOL each persist a real net-flow value from SoSoValue's summary-history endpoint] The three confirmed-available assets
- [test: BNB's ETF-flow registry entry declares NOT_DEFINABLE with the reason naming SoSoValue's API enum not including it] The G1-confirmed settled absence, distinct from any other NOT_DEFINABLE reason on this board
- [test: money fields are parsed as Decimal, never float, and a long-decimal string input round-trips without precision loss] Directly guards against the determinism-golden-drift risk research flagged
- [test: a reported net-flow value of exactly 0 persists as a real Ok(0) value, never as UNAVAILABLE] A quiet trading day is a real, reported zero, not a missing value — matches this project's "never render 0 for absence, but never hide a real zero either" distinction
- [test: an HTTP 429 (SoSoValue's documented per-minute/per-month rate limit, error code 42901) returns Error(FETCH_FAILED) with the status in the detail, never a silent retry] Fail-loud rate-limit discipline
- [test: a malformed or reshaped SoSoValue response is rejected by the response model] `extra="forbid"` discipline
- [integration: a live SoSoValue request returns real ETF flow data for at least one asset] Hits the real endpoint
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- **Provision a SoSoValue developer account and API key before starting this story's live/
  integration criteria.** Sign up at sosovalue.com/developer; this is a manual prerequisite, not
  a discoverable code path. Store the token as a repo secret (`SOSOVALUE_API_KEY`), following the
  same pattern used for other credentialed services in this project.
- Research flagged a possible contradiction between SoSoValue's documented "only the most recent
  1 month of history" constraint and a separate "limit max 300" parameter as UNVERIFIED — confirm
  the real response shape and date range live before committing to a specific backfill or
  pagination assumption.
- US trading-calendar awareness matters: on a US market holiday there is no flow to report at
  all, and "yesterday's flow" on a Monday is Friday's. Do not let a naive age check flag every
  Monday as stale, and do not let it misattribute Friday's flow to Sunday.
