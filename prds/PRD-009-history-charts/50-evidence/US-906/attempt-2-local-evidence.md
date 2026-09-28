US-906 attempt 2 local evidence, 2026-09-28

Changed live C4 test:

- `tests/test_backfill_fred.py::test_live_dff_run_backfill_persists_90_days_without_vintage_cap`
- It no longer skips when `FRED_API_KEY` is missing; it raises.
- It invokes the public `ingest.backfill.run_backfill` entry point for `macro_dff`.
- It spies on `ingest.backfill.persist_board` and asserts every run is persisted with
  `origin="backfill"`.
- It bounds the live DFF run to the most recent 120 days and asserts returned reference
  periods span at least 90 days and every endpoint keeps `output_type=4`.

Commands run in this sandbox:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_backfill_fred.py -q
5 passed, 1 deselected in 0.26s
```

```text
.\.venv\Scripts\python.exe -m pytest tests/test_backfill_fred.py -q -m integration -o addopts=
FAILED tests/test_backfill_fred.py::test_live_dff_run_backfill_persists_90_days_without_vintage_cap
RuntimeError: FRED request failed: ConnectError
Underlying socket error: [WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions
```

```text
.\.venv\Scripts\python.exe -m pytest -q
378 passed, 6 skipped, 74 deselected, 2 errors in 9.00s
```

The two full-suite errors were pre-existing unmarked Postgres tests failing to connect to
the configured Supabase pooler from this sandbox:

- `tests/test_backfill_coinmetrics.py::test_live_coinmetrics_run_backfill_persists_earliest_btc_active_addresses_at_catalog_min_time`
- `tests/test_backfill_coverage.py::test_backfill_rerun_persists_once_through_real_datapoint_identity`

Direct pooler reachability check also failed:

```text
Test-NetConnection aws-0-ap-southeast-1.pooler.supabase.com -Port 5432
TcpTestSucceeded: False
```

Exact `uv run pytest -q` could not be executed in this sandbox:

```text
Program 'uv.exe' failed to run: Access is denied
```

Type check:

```text
.\.venv\Scripts\python.exe -m mypy ingest --strict
Success: no issues found in 24 source files
```
