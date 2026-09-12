---
id: US-403
title: Historical bars fetched to depth, truncation and gaps still fatal
priority: 3
touches:
  - ingest/fetchers/okx.py
  - ingest/fetchers/coinbase.py
  - tests/test_history_depth.py
context:
  - AGENTS.md
  - prds/PRD-004-indicators/10-research.md
---

As the owner, I want 250+ bars fetched reliably across paginated requests, with every guarantee
from PRD-002 still holding, so that a deeper fetch does not quietly reintroduce the hazards a
single-bar fetch never exposed.

One bar needed no pagination. 250 does, and pagination is where the shipped bugs live: **ccxt on
this exact venue** returned 100 history candles where 300 were requested, *"without obvious
notification"*.

Documented caps: Coinbase Exchange **300 candles per request**; OKX `candles` 300 and
`history-candles` **100**.

## Acceptance criteria

- [test: a request needing more bars than one page returns the full contiguous series] Pagination assembles correctly, in order, with no duplicates at the seams
- [test: a page that returns fewer rows than requested fails the whole fetch] Not a shorter series — PRD-002's rule at pagination scale
- [test: a gap at a page boundary is detected] The seam is where contiguity checks are most likely to be skipped
- [test: the assembled series is exactly required_bars long, newest first] The US-201 contract survives assembly
- [test: no code path synthesises or pads a bar to reach the count] Asserted directly
- [integration: a live fetch of 250 daily bars for BTC succeeds on both venues] Real requests, real pagination

## Notes for the implementer

- Respect the per-endpoint caps rather than discovering them: Coinbase 300, OKX `candles` 300,
  OKX `history-candles` 100.
- Contiguity is checked **across** the assembled series, not per page. A hole exactly at a seam
  is the failure a per-page check misses.
- No retries that silently paper over a short page.
