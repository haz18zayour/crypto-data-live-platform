---
id: US-203
title: Vendor response models that reject a reshape
priority: 3
touches:
  - ingest/schemas.py
  - ingest/fetchers/okx.py
  - tests/test_schemas.py
context:
  - AGENTS.md
  - project-documents/11_Data_Model.md
---

As the owner, I want every vendor response parsed through a model that refuses anything it did
not expect, so that a silently reshaped payload becomes a loud error instead of a wrong number.

Four sources broke or gated on the prior system in nine months — Reddit, LunarCrush,
CryptoPanic, CryptoCompare — and CCData retired its free tier outright in May 2026. Vendor
churn is an assumption here, not an emergency.

Two defaults work against us, and both must be turned off explicitly:

- **Pydantic's `extra` defaults to `ignore`**, so a vendor renaming a field produces a model
  where it is simply absent or default-valued rather than an error.
- **OKX returns every candle field as a string.** A lax `float` accepts `"79111.8"`, a bare
  number, and in some paths a null, equally happily.

## Acceptance criteria

- [test: an unexpected extra field is rejected] The model sets `extra='forbid'`; a payload with one more key than expected raises
- [test: a missing expected field is rejected] Not defaulted, not None — an error naming the field
- [test: a type change is rejected] A field arriving as a number where a string is expected, or null where a value is expected, raises rather than coercing
- [test: a rejected payload becomes Error with FETCH_FAILED, never Ok] The failure crosses the fetcher boundary as the status union, so a reshape can never reach the database as a value
- [cmd: uv run mypy ingest --strict] Strict typing passes

## Notes for the implementer

- One model per vendor endpoint, living beside the fetcher that uses it.
- `extra='forbid'` **and** strict field types. Neither is on by default and each catches a
  different failure.
- Parse at the fetcher boundary, before any value is constructed. A validation failure must
  produce `Error(FETCH_FAILED, detail)` — the detail is what makes the 2am diagnosis quick.
- Do not "helpfully" coerce. A vendor changing `"79111.8"` to `79111.8` is a contract change we
  want to hear about, even though the number is the same.
