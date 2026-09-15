# US-607 adversarial case

Acceptance protocol item 4 for PRD-006: attack the guarantee that a funding
datapoint's interval is derived from that instrument's current settled cadence,
not from a registry value, an oldest observed cadence, an average, or a hardcoded
8h assumption.

## Machine checks

- `tests/test_okx_derivatives_fetcher.py::test_adversarial_funding_interval_change_uses_newest_gap_not_old_history`
  builds a funding-rate-history payload with a newest 1h gap followed by older
  8h gaps. The expected source field contains `interval_seconds=3600`, excludes
  `interval_seconds=28800`, and excludes "average".
- `tests/test_okx_derivatives_fetcher.py::test_two_assets_in_one_run_can_persist_different_derived_funding_intervals`
  runs the board assembler with BTC deriving `interval_seconds=3600` while ETH
  derives `interval_seconds=28800` in the same run.
- `tests/test_okx_derivatives_fetcher.py::test_persisted_funding_datapoint_source_field_names_derived_interval`
  sends a derived funding result through `persist_board` with a monkeypatched
  writer and asserts the persisted definition's `source_field` is the runtime
  source field naming the derived interval.

## Commands run

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_okx_derivatives_fetcher.py -m "not integration"
```

Result: `23 passed, 13 deselected, 1 warning in 0.24s`.

The warning was pytest cache creation failing with Windows access denied under
`.pytest_cache`; it did not affect the test result.

```powershell
.\.venv\Scripts\python.exe -m ruff check tests/test_okx_derivatives_fetcher.py
```

Result: `All checks passed!`.

`uv run ...` was attempted first, but this environment returned `Access is denied`
for `uv.exe`; the repo's existing virtualenv Python was used for the same pytest
and ruff entry points.
