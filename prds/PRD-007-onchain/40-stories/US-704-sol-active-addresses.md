---
id: US-704
title: SOL active addresses — built from Helius RPC, vote transactions classified client-side
priority: 4
touches:
  - ingest/fetchers/solana_rpc.py
  - ingest/schemas.py
  - ingest/registry.yaml
  - tests/test_solana_rpc_fetcher.py
  - tests/test_registry.py
  - tests/test_persist_board.py
context:
  - AGENTS.md
  - prds/PRD-007-onchain/10-research.md
  - project-documents/11_Data_Model.md
---

As the owner, I want SOL's active-addresses cell built from the public Solana RPC rather than
rendered as a permanent absence, because research (R8) found this specific metric class is
cheap and genuinely feasible — unlike SOL's MVRV and exchange flows, which are not.

This is the hardest story in this PRD, and the research gate corrected a real mistake in this
PRD's own framing before any code was written: **there is no RPC-level parameter to filter vote
transactions, and there never has been.** `getBlock`'s only parameters are `commitment`,
`encoding`, `transactionDetails`, `maxSupportedTransactionVersion`, and `rewards`. A 2022 feature
request to add a `votes: bool` parameter was explicitly closed "not planned," and that
repository is now archived. Vote/non-vote classification must inspect each transaction's
top-level instructions for the vote program address, client-side, against the full block data
this fetcher pulls anyway.

## Acceptance criteria

- [test: the fetcher calls Helius's getBlock with no vote-filter parameter of any kind] Proves the implementation does not assume a parameter that has never existed
- [test: a transaction whose only top-level instruction targets the vote program address (`Vote111111111111111111111111111111111111111`) is classified as a vote and excluded from the active-addresses count] The client-side classification this story exists to implement
- [test: a transaction with any non-vote top-level instruction is classified as non-vote and its fee-payer counted] The inverse case, proving the classifier discriminates rather than excluding everything or nothing
- [test: the daily active-addresses value is the count of distinct non-vote fee-payer signers across the day's fetched blocks] The actual metric definition, stated as a test so it cannot drift silently
- [test: an HTTP or RPC error returns Error with detail, and no value] Same discipline as every fetcher in this project
- [test: a malformed or reshaped getBlock response is rejected by the response model] `extra="forbid"` on the new response model — an added, renamed, or retyped field fails loud
- [test: source_timestamp is the block's own timestamp for the day's boundary and is strictly in the past] The F11 defence
- [integration: a live Helius request fetches a real day's SOL blocks and returns a non-zero active-addresses count] Hits the real endpoint; this is what actually proves the vote-program-address classification technique works, since research flagged it as the fetcher's own unverified recall, not a cited source
- [cmd: uv run mypy ingest --strict] Strict typing holds for the new module

## Notes for the implementer

- **Helius requires an API key, unlike Coin Metrics' anonymous-by-IP free tier.** This is a
  provisioning dependency: an account and API key must exist and be stored as a repo secret
  before this story's live/integration criteria can run at all. If this blocks you, that is a
  provisioning gap, not a code defect — flag it rather than working around it with a different,
  unresearched RPC provider.
- **Verify the vote-program-address classification technique against a real fetched block before
  writing it into a test as settled fact.** Research explicitly flagged this as its own
  unverified recall: *"the standard client-side technique is to inspect each transaction's
  account keys / program invocations for the vote program address... this needs direct
  confirmation... before it becomes a story's acceptance criterion."* Confirm it against
  Solana's own program documentation or a real fetched block showing the pattern, and cite what
  you confirmed it against in the implementation's own comments — do not carry the unverified
  assumption forward silently.
- Solana's daily transaction volume means a full day's blocks is a genuinely large fetch —
  budget for pagination/slot-range iteration, not a single call. Helius's free tier caps at
  10 req/s overall with tighter per-method sub-limits (`getProgramAccounts` 5/s, DAS calls 2/s)
  — this story only needs `getBlock`/`getSignaturesForAddress`, which are not among the
  tighter-capped methods, but pace calls regardless rather than assume the headline number
  covers every method.
- This cell's family is `active_addresses`, the same family US-703 registered for BTC/ETH/BNB —
  it is a different vendor and methodology under the same row label, and that is deliberate: each
  cell's own provenance names its actual source, so the board stays honest about *which* source
  produced *which* cell even when they share a row.
