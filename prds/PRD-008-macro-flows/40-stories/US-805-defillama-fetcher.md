---
id: US-805
title: DefiLlama stablecoin-supply fetcher — per-chain ETH/SOL/BSC, BTC declared NOT_DEFINABLE
priority: 5
touches:
  - ingest/fetchers/defillama_stablecoins.py
  - ingest/schemas.py
  - ingest/registry.yaml
  - tests/test_defillama_stablecoins_fetcher.py
  - tests/test_registry_not_definable.py
context:
  - AGENTS.md
  - prds/PRD-008-macro-flows/10-research.md
  - prds/PRD-008-macro-flows/20-decisions.yaml
---

As the owner, I want per-chain stablecoin supply for Ethereum, Solana, and BSC built from
DefiLlama's free, keyless API, with Bitcoin's absence declared honestly (Bitcoin genuinely has no
stablecoin-supply concept, confirmed live: no Bitcoin entry exists in DefiLlama's own chain list),
so a viewer never mistakes a structural absence for a gap this project failed to fill.

DefiLlama's `/stablecoinchains` endpoint is confirmed free, keyless, and small (current totals
only). Its per-asset endpoint (e.g. `/stablecoin/1` for USDT) is confirmed **larger than 10MB** —
pulling it on a schedule is a wall-clock and egress risk, the same "credit budget ok, timeout
blown" failure class already logged from PRD-007. This story uses `/stablecoinchains` only.

## Acceptance criteria

- [test: Ethereum, Solana, and BSC each persist a real peggedUSD stablecoin-supply value from DefiLlama's stablecoinchains endpoint] The three confirmed-available chains
- [test: BTC's stablecoin-supply registry entry declares NOT_DEFINABLE with the reason naming DefiLlama's own chain list having no Bitcoin entry] The G1-confirmed settled absence — a genuinely different reason from BNB's ETF-flow absence in US-804, not a copy of it
- [test: the fetcher never calls DefiLlama's per-asset endpoint (e.g. /stablecoin/{id})] Directly guards against the >10MB response-size/wall-clock risk research found
- [test: source_field explicitly states "USD-pegged only" (peggedUSD), not "all pegs"] The explicit choice research flagged as needing disclosure, not an implicit default
- [test: no global stablecoin-supply total is registered anywhere on this board] The G1-confirmed scope boundary — a global total would be dominated by an untracked chain (Tron)
- [test: a malformed or reshaped DefiLlama response is rejected by the response model] `extra="forbid"` discipline
- [integration: a live DefiLlama request returns real stablecoin-supply data for at least one chain] Hits the real endpoint
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- No API key or account needed — DefiLlama's stablecoin endpoints are free and keyless, confirmed
  live in this PRD's research.
- DefiLlama's chain naming does not match this board's asset names — it is `BSC`, not `BNB`.
  Confirm the exact chain-name string live before writing it into a story as settled.
