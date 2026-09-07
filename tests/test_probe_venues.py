import io
import unittest
import urllib.error

from scripts import probe_venues


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
        self.assertTrue(all(row["status"] is not None for row in results))
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
        self.assertIsNone(row["status"])
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

        self.assertEqual(451, row["status"])
        self.assertIsNone(row["error"])
        self.assertEqual("blocked", row["body_prefix"])


if __name__ == "__main__":
    unittest.main()
