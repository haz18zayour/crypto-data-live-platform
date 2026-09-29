# US-909 adversarial demonstration

This story's adversarial case attacks the PRD-009 guarantee at two weak points:

- sparse history: `web/src/Sparkline.test.tsx` constructs a `btc_daily_close` history with exactly one persisted-style row and asserts the insufficient-history state renders with no SVG or polyline.
- seam splice: `tests/test_backfill_seam.py` runs a real backfill path, then checks that a later-fetched historical row cannot appear in `board_read` or `datapoints_read`; the live integration test cross-checks the overlapping BTC funding-rate row against `fetch_btc_funding_rate_history`, not by replaying the backfill request parameters.

Verifier commands:

```powershell
uv run pytest tests/test_backfill_seam.py -q
npm --prefix web test -- Sparkline.test.tsx
uv run pytest tests/test_backfill_seam.py::test_live_backfilled_funding_overlap_matches_fresh_live_endpoint_value -q -o addopts=
```
