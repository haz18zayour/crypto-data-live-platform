# US-910 SoSoValue Live Probe Local Attempt

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

The real proof path is now an explicit integration test:
`tests/test_backfill_sosovalue.py::test_live_sosovalue_run_backfill_persists_real_vendor_rows_after_probe`.
It requires a networked environment with `SOSOVALUE_API_KEY` and `DATABASE_URL`/`TEST_DATABASE_URL`;
it probes SoSoValue's real history endpoint, then persists real rows through the assembled
`run_backfill` entry point.
