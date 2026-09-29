# US-909 adversarial demonstration

This story's adversarial case attacks the PRD-009 guarantee at two weak points:

- sparse history: `web/src/Sparkline.test.tsx` constructs a `btc_daily_close` history with exactly one persisted-style row and asserts the insufficient-history state renders with no SVG or polyline.
- seam splice: `tests/test_backfill_seam.py::test_backfilled_overlap_matches_fresh_independent_live_endpoint_value` runs the real `stablecoin_supply` backfill path into Postgres, then performs a fresh DefiLlama live read from `/stablecoinchains` for the same overlap day. The persisted backfill row must come from `/stablecoincharts/Ethereum`, the persisted live row must come from `/stablecoinchains`, and the values must match. This attacks the seam with two different vendor endpoints instead of replaying backfill's own request.
- current-value splice: `tests/test_backfill_seam.py::test_backfill_run_cannot_splice_a_historical_value_into_current_board_views` runs a real backfill path after a live row exists, then asserts `board_read` and `datapoints_read` still expose only the live row.
- human check: US-909-C4 remains a human criterion. A person must inspect the live board and compare the displayed sparse-history/current-value behavior with the vendor data; this note is only the item to perform, not a completion claim.

Verifier commands:

```powershell
uv run pytest tests/test_backfill_seam.py -q
npm --prefix web test -- Sparkline.test.tsx
```

Local attempt in this sandbox:

```text
uv run pytest tests/test_backfill_seam.py -q
Program 'uv.exe' failed to run: Access is denied

.\.venv\Scripts\ruff.exe check tests/test_backfill_seam.py
All checks passed!

.\.venv\Scripts\python.exe -m pytest tests/test_backfill_seam.py -q
ss [100%]
2 skipped in 0.23s
```

Attempt 3 fix:

The previous default test gate reached
`tests/test_backfill_seam.py::test_backfilled_overlap_matches_fresh_independent_live_endpoint_value`
and failed before judging any criterion because the mocked DefiLlama payload used string values
for `totalCirculatingUSD.peggedUSD`. The actual `DefiLlamaStablecoinChartsResponse` model accepts
numeric JSON there, matching DefiLlama's live shape, so the seam fixture now emits numbers while
preserving the same backfill/live endpoint distinction.

```text
.\.venv\Scripts\ruff.exe check tests/test_backfill_seam.py
All checks passed!

.\.venv\Scripts\python.exe -m pytest tests/test_backfill_seam.py -q -rs
ss [100%]
SKIPPED ... PostgreSQL backfill seam tests could not connect ... port 5432 failed: Permission denied
2 skipped in 0.24s

cmd /c "cd web && npx vitest run Sparkline.test.tsx --configLoader runner"
Test Files  1 passed (1)
Tests  15 passed (15)
```
