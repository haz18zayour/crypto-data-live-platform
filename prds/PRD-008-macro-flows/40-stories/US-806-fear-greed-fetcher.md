---
id: US-806
title: Fear & Greed fetcher — alternative.me, composite disclosure and paused-survey-weight on the cell's face
priority: 6
touches:
  - ingest/fetchers/alternative_me.py
  - ingest/schemas.py
  - ingest/registry.yaml
  - tests/test_alternative_me_fetcher.py
context:
  - AGENTS.md
  - prds/PRD-008-macro-flows/10-research.md
  - prds/PRD-008-macro-flows/20-decisions.yaml
---

As the owner, I want the Fear & Greed Index built from `alternative.me`'s free, keyless API,
labeled explicitly as that vendor's own six-weight composite, so nobody reading this board
mistakes it for an independent, validated market signal — no published evidence exists that it
predicts anything, and this project makes no judgement about the data it shows.

Confirmed live: the API returns `value` as a **string** (`"70"`), not a number, and
`time_until_update` appears only on the newest element. The site itself still lists a "surveys"
sub-weight at 15% while marking it "currently paused" — the disclosure must say so, not repeat the
published weights as if all six are currently live.

## Acceptance criteria

- [test: the fetcher parses the string-typed value field into a numeric Ok result, never leaving it as a raw string] Correct typed handling of the vendor's actual response shape
- [test: source_field names alternative.me as the vendor and states this is a six-weight composite (volatility 25%, momentum/volume 25%, social 15%, surveys 15% currently paused, dominance 10%, Google Trends 10%)] The disclosure lives on the cell's own face, not in a code comment — a verifier can grep for it
- [test: the disclosure explicitly notes the surveys sub-weight is currently paused, not presented as live] Directly guards against overstating the composite's current methodology
- [test: alternative.me's required attribution is present wherever this value is rendered] A real licensing requirement research flagged as a UI criterion, not optional
- [test: a malformed or reshaped alternative.me response is rejected by the response model] `extra="forbid"` discipline
- [integration: a live alternative.me request returns a real Fear & Greed value] Hits the real endpoint
- [cmd: uv run pytest -q] The full offline suite stays green

## Notes for the implementer

- No API key or account needed — confirmed free and keyless live in this PRD's research.
- This is exactly one indicator (one value, no per-asset breakdown — Fear & Greed is
  market-wide, not asset-specific). Do not register it once per asset the way most of this
  board's other families are.
