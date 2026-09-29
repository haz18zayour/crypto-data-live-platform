# US-910 SoSoValue Probe Notes

Attempted in this sandbox on 2026-09-29 with `SOSOVALUE_API_KEY` and `DATABASE_URL`
present in `.env.local`.

Command shape:

```text
probe_sosovalue_summary_history("BTC", sample_limit=BACKFILL_LIMIT, rate_probe_requests=25)
```

Result: blocked by local socket policy before any HTTP response was returned:

```text
httpx.ConnectError: [WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions
```

Follow-up changes after the verifier rejection:

- `BACKFILL_LIMIT` now matches SoSoValue's own current endpoint maximum of 300 records,
  from `https://sodex.com/documentation/for-developers/api-reference/market-data-api/etf/summary-history`.
- `probe_sosovalue_summary_history` records the observed `rows`, `oldest_date`,
  `newest_date`, response fields, and `X-RateLimit-*` headers when the vendor returns
  them. If headers are absent, it falls back to the bounded 429 probe.
- The live test no longer asserts `probe.rows == BACKFILL_LIMIT`; it asserts only that
  the real response has more than one row and no more than the requested cap, then
  persists rows through `run_backfill`.
- Backfilled rows now include the observed vendor row count and date range in
  `source_field`, so the verifier can see the actual probed window in persisted
  provenance rather than an assumed constant.

The real proof path remains the explicit integration test:
`tests/test_backfill_sosovalue.py::test_live_sosovalue_run_backfill_persists_real_vendor_rows_after_probe`.
It requires a networked environment with `SOSOVALUE_API_KEY` and `DATABASE_URL`/`TEST_DATABASE_URL`;
it probes SoSoValue's real history endpoint, then persists real rows through the assembled
`run_backfill` entry point.
