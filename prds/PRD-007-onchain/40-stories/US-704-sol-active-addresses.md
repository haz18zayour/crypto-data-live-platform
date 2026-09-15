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

**A second correction, found by budgeting the naive design before writing any code:** fetching a
full day's blocks costs roughly 200,000 Helius credits (one per `getBlock` call, ~200k blocks/day
at Solana's ~400ms block time) — six times the 1M/month free tier if run daily. This story
therefore fetches **one fixed UTC hour, exactly**, not a sampled or extrapolated estimate of the
full day — an honest, exact measurement of a smaller window rather than a falsely-precise guess
at a bigger one. At ~9,000 blocks/hour this costs ~270k credits/month, comfortably inside budget
with headroom for the staking cell (US-706) and retries. **This is a genuinely different
methodology from BTC/ETH/BNB's Coin Metrics-sourced `active_addresses` cells**, which are true
24-hour counts — the difference must be disclosed on the cell's own face (`source_field`), not
buried, so nothing downstream (a person reading the board, or a future analysis) can mistake an
hour's exact count for a day's.

## Acceptance criteria

- [test: the fetcher calls Helius's getBlock with no vote-filter parameter of any kind] Proves the implementation does not assume a parameter that has never existed
- [test: a transaction whose only top-level instruction targets the vote program address (`Vote111111111111111111111111111111111111111`) is classified as a vote and excluded from the active-addresses count] The client-side classification this story exists to implement
- [test: a transaction with any non-vote top-level instruction is classified as non-vote and its fee-payer counted] The inverse case, proving the classifier discriminates rather than excluding everything or nothing
- [test: the active-addresses value is the count of distinct non-vote fee-payer signers across exactly one fixed UTC hour's fetched blocks, never a sampled or extrapolated estimate of a full day] The actual metric definition, stated as a test so it cannot drift silently — no averaging, no scaling a partial count up to a "daily" figure
- [test: source_field states the exact hour window measured and that it is not a 24-hour count] The disclosure this design depends on to stay honest — must be readable on the cell's own face, not just in code comments
- [test: an HTTP or RPC error returns Error with detail, and no value] Same discipline as every fetcher in this project
- [test: a malformed or reshaped getBlock response is rejected by the response model] `extra="forbid"` on the new response model — an added, renamed, or retyped field fails loud
- [test: source_timestamp is the measured hour's own boundary and is strictly in the past] The F11 defence
- [integration: a live Helius request fetches a real hour of SOL blocks and returns a non-zero active-addresses count within the credit budget] Hits the real endpoint; this is what actually proves the vote-program-address classification technique works, since research flagged it as the fetcher's own unverified recall, not a cited source
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
- Pick a fixed UTC hour (e.g. 00:00–01:00) and keep it constant run to run — a floating or
  randomly-chosen window would make day-over-day comparison meaningless on top of the
  window-vs-day disclosure this story already owes. ~9,000 `getBlock` calls for one hour is
  still a real fetch — budget for slot-range iteration, not a single call. Helius's free tier
  caps at 10 req/s overall with tighter per-method sub-limits (`getProgramAccounts` 5/s, DAS
  calls 2/s) — this story only needs `getBlock`, not among the tighter-capped methods, but pace
  calls regardless rather than assume the headline number covers every method.
- Solana's actual non-vote transaction volume is very high (measured in the hundreds of millions
  per day network-wide as of 2026) — even one hour's worth of blocks contains a large number of
  transactions to parse and deduplicate signers from client-side. This is a compute/memory
  budgeting concern for the GitHub Actions runner, separate from the credit-budget concern above.
- This cell's family is `active_addresses`, the same family US-703 registered for BTC/ETH/BNB —
  it is a different vendor and methodology under the same row label, and that is deliberate: each
  cell's own provenance names its actual source, so the board stays honest about *which* source
  produced *which* cell even when they share a row.
