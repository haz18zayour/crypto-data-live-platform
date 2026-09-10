---
id: US-305
title: A missing bar at the second venue is NOT_CORROBORATED, not an error
priority: 5
touches:
  - ingest/corroborate.py
  - ingest/status.py
  - tests/test_not_corroborated.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want "the second venue had no bar for that day" treated as its own outcome, so
that a quiet market neither fires an alarm nor invents a disagreement.

Coinbase publishes **no candle at all when there were no ticks**, and warns that historical
rate data "may be incomplete". That is a **third** outcome, distinct from a value and from a
fetch failure:

- degraded to a fetch error, it fires the dead-man's-switch on a non-event
- degraded to zero, the divergence is 10,000 bps and the page screams

Neither is true. The honest statement is that the primary value stands and nothing corroborated
it.

## Acceptance criteria

- [test: a missing second-venue bar yields NOT_CORROBORATED, not ERROR] The primary value is still stored and still usable
- [test: NOT_CORROBORATED is distinct from a fetch failure at the second venue] A 500 from Coinbase is an error; no bar published is not
- [test: no divergence value is fabricated when there is nothing to compare] Not zero, not null-as-zero — absent
- [test: the dead-man's-switch does not fire on a NOT_CORROBORATED result] A quiet market is not an outage
- [test: the reason is recorded so the page can say why] Reusing the vocabulary of `11_Data_Model.md` — absence always says why

## Notes for the implementer

- This is the same discipline as `UNAVAILABLE` vs `ERROR` in PRD-001, applied one level up:
  the distinction between *permanent*, *purchasable*, *broken* and *simply absent* is exactly
  the information the owner needs and the thing a blank cell destroys.
- Do not retry a missing bar. There is nothing to retry — the venue published nothing.
