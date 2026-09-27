# US-1206 attempt 3 evidence

Checked locally on 2026-09-27.

## Criteria evidence

- US-1206-C1: `tests/test_persist_board.py::test_adversarial_fast_tier_missed_window_reads_stale_within_450_seconds` forces `btc_open_interest` to age 451 seconds against its loaded 300/450/600 registry bounds and asserts the persisted result is `Stale` while the other fast-tier cells remain `OK`.
- US-1206-C2: `tests/test_persist_board.py::test_adversarial_full_cycle_reconciles_all_71_registry_rows_once_each` runs fast, medium, daily, and the separate `sol_active_addresses` job path, then asserts the flattened union equals the full 71-row board registry exactly once.
- US-1206-C3: `c3-canary-collect-schedule-independence.md` records the independent canary and collect schedules, trigger types, heartbeat secrets, and commands.

## Commands run

```text
.\.venv\Scripts\python.exe -m pytest tests/test_persist_board.py::test_adversarial_fast_tier_missed_window_reads_stale_within_450_seconds tests/test_persist_board.py::test_adversarial_full_cycle_reconciles_all_71_registry_rows_once_each -q
..                                                                       [100%]
2 passed in 4.63s
```

```text
.\.venv\Scripts\python.exe -m pytest -q -x
287 passed, 48 deselected in 11.00s
```

```text
.\.venv\Scripts\python.exe -m pytest -q
287 passed, 48 deselected in 12.05s
```

```text
.\.venv\Scripts\python.exe -m mypy ingest --strict
Success: no issues found in 19 source files
```

```text
.\.venv\Scripts\python.exe -m ruff check tests/test_persist_board.py
All checks passed!
```

```text
npm.cmd --prefix web run typecheck
> crypto-data-live-web@0.0.0 typecheck
> tsc -b --pretty false
```

`npm.cmd --prefix web test` was attempted twice, with 120s and 300s timeouts. Both attempts stayed in the `playwright install chromium chromium-headless-shell` pretest step until the sandbox timeout.

Running the Vitest body directly from `web/` reached the configured jsdom environment:

```text
npx.cmd vitest run --configLoader runner
Test Files  1 failed | 10 passed (11)
Tests  1 failed | 51 passed (52)
```

The remaining failing test was the existing live endpoint case
`src/BoardMatrix.test.tsx::integration: the assembled page against live Supabase > the assembled page loads every cell from the live board_read endpoint`, which rendered `fetch failed` in this sandbox.
