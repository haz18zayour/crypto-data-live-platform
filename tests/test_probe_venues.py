import io
import importlib.util
from pathlib import Path
import unittest
import urllib.error

PROBE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "probe_venues.py"
SPEC = importlib.util.spec_from_file_location("probe_venues", PROBE_PATH)
assert SPEC is not None
probe_venues = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(probe_venues)


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = io.BytesIO(body)
        self.closed = False

    def getcode(self):
        return self.status

    def read(self, size=-1):
        return self._body.read(size)

    def close(self):
        self.closed = True


class ProbeVenuesTests(unittest.TestCase):
    def test_probe_records_an_http_status_for_every_configured_venue(self):
        statuses = {
            venue["url"]: 200 + index
            for index, venue in enumerate(probe_venues.VENUES)
        }

        def opener(request, timeout):
            self.assertEqual(timeout, probe_venues.REQUEST_TIMEOUT_SECONDS)
            return FakeResponse(statuses[request.full_url], b'{"ok": true}')

        results = probe_venues.probe_all(opener=opener)

        self.assertEqual(
            {venue["venue"] for venue in probe_venues.VENUES},
            {row["venue"] for row in results},
        )
        self.assertTrue(all(row["http_status"] is not None for row in results))
        self.assertTrue(all(row["error"] is None for row in results))

    def test_probe_records_a_transport_failure_as_a_result_rather_than_raising(self):
        def opener(request, timeout):
            raise TimeoutError("timed out")

        row = probe_venues.probe_venue(
            "timeout_exchange",
            "https://example.invalid/reachability",
            opener=opener,
        )

        self.assertEqual("timeout_exchange", row["venue"])
        self.assertIsNone(row["http_status"])
        self.assertIn("TimeoutError: timed out", row["error"])

    def test_http_error_records_status_without_transport_error(self):
        def opener(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                451,
                "Unavailable For Legal Reasons",
                hdrs=None,
                fp=io.BytesIO(b"blocked"),
            )

        row = probe_venues.probe_venue(
            "binance_spot",
            "https://api.binance.com/api/v3/klines",
            opener=opener,
        )

        self.assertEqual(451, row["http_status"])
        self.assertIsNone(row["error"])
        self.assertEqual("blocked", row["body_prefix"])

    def test_probe_passes_timeout_by_keyword(self):
        def opener(request, data=None, timeout=None):
            self.assertIsNone(data)
            self.assertEqual(probe_venues.REQUEST_TIMEOUT_SECONDS, timeout)
            return FakeResponse(200, b'{"ok": true}')

        row = probe_venues.probe_venue(
            "okx",
            "https://www.okx.com/api/v5/market/candles",
            opener=opener,
        )

        self.assertEqual(200, row["http_status"])

    def test_probe_does_not_record_programming_errors_as_reachability(self):
        def opener(request, timeout=None):
            raise TypeError("bad caller contract")

        with self.assertRaises(TypeError):
            probe_venues.probe_venue(
                "broken_probe",
                "https://example.com",
                opener=opener,
            )


if __name__ == "__main__":
    unittest.main()
