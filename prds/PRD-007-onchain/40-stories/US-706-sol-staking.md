---
id: US-706
title: SOL staking — Validators.app; BTC/ETH/BNB each NOT_DEFINABLE with distinct reasons
priority: 6
touches:
  - ingest/fetchers/validators_app.py
  - ingest/schemas.py
  - ingest/registry.yaml
  - tests/test_validators_app_fetcher.py
  - tests/test_registry.py
  - tests/test_registry_not_definable.py
  - tests/test_persist_board.py
context:
  - AGENTS.md
  - prds/PRD-007-onchain/10-research.md
  - project-documents/11_Data_Model.md
---

As the owner, I want SOL staking data built from Validators.app's free API, with the other three
assets' absence each explained for the reason that actually applies to them, so a viewer never
reads "no staking data" as one uniform gap when the causes are completely different.

Validators.app is confirmed free with no paid tier — but it is not fully anonymous the way Coin
Metrics is: it requires a verified account and API token, rate-limited to 20–40 requests per 5
minutes depending on endpoint. This is a provisioning dependency, not a code concern.

BTC has no staking concept at all — it is proof-of-work, permanently and unconditionally. ETH
and BNB both have genuine staking (ETH's proof-of-stake validators, BNB Chain's own validator
set) — their absence here is a deliberate scope decision for this PRD, following the roadmap and
research R8's specific SOL-staking recommendation, not a claim that staking is undefined on
those chains. `btc_daily_close`'s existing `not_definable` entries already establish this exact
pattern: a board-scope reason, stated as such, not a claim of universal impossibility.

## Acceptance criteria

- [test: the fetcher authenticates with a token read from configuration, never hardcoded] Matches this project's fail-loud configuration discipline from US-002
- [test: an HTTP 429 (rate limit) returns Error(FETCH_FAILED) with the status in the detail, never a silent retry] Validators.app's documented rate limit must be respected, not discovered by breaking it
- [test: a malformed or reshaped response is rejected by the response model] `extra="forbid"` on the new response model
- [test: the registry's SOL staking entry declares uncorroborated or corroboration explicitly] Per US-306
- [test: BTC's staking entry declares not_definable with a reason naming proof-of-work having no staking concept] The permanent, chain-level reason
- [test: ETH's staking entry declares not_definable with a reason naming this PRD's scope decision, not a claim ETH staking is undefined] The deliberate-scope reason, distinct from BTC's
- [test: BNB's staking entry declares not_definable with the same scope reasoning as ETH's, and both are distinguishable from BTC's reason] Two assets sharing one legitimate reason is fine; neither may share BTC's permanent-impossibility reason
- [test: `assert_registry_coverage` passes for the new entry] Golden, response model, required_bars, parameters
- [test: a run persists one staking datapoint for SOL] End to end for this metric
- [integration: a live Validators.app request returns real SOL validator/stake data] Hits the real endpoint

## Notes for the implementer

- **Provision a Validators.app account and API token before starting this story's live/
  integration criteria.** A verified account and token are required — this is not a discoverable
  code path, it is a manual prerequisite. Store the token as a repo secret
  (`VALIDATORS_APP_API_TOKEN` or similar), following the same pattern used for other credentialed
  services in this project.
- Confirm the exact endpoint and response shape for validator count / active stake against the
  live API once credentials exist — research confirmed the API's existence and rate limits but
  did not fetch a live authenticated response, so exact field names are unverified pending this
  story's own confirmation.
- Same web-test hardcoded-count note as every prior story adding a family to this board.
