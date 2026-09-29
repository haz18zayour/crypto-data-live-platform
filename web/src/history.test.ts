import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchHistory } from "./history";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchHistory", () => {
  it("calls the bounded history RPC with the cell and source vendor pinned", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValueOnce(
      jsonResponse([
        {
          id: 1,
          indicator_key: "btc_daily_close",
          asset: "BTC",
          measured_on: "BTC",
          value: 78_900,
          status: "OK",
          source_vendor: "okx",
          endpoint: "https://example.test/history",
          source_field: "close",
          fetched_at: "2026-09-28T00:05:00.000Z",
          source_timestamp: "2026-09-28T00:00:00.000Z",
          reference_period: null,
          published_at: null,
          origin: "live",
        },
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);

    const points = await fetchHistory(
      "btc_daily_close",
      "BTC",
      "okx",
      60,
      {
        supabaseUrl: "https://example.supabase.co",
        anonKey: "test-key",
      },
    );

    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "https://example.supabase.co/rest/v1/rpc/history_read",
    );
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({
        p_indicator_key: "btc_daily_close",
        p_asset: "BTC",
        p_source_vendor: "okx",
        p_point_limit: 60,
      }),
    });
    expect(points).toEqual([
      expect.objectContaining({
        indicatorKey: "btc_daily_close",
        sourceVendor: "okx",
        sourceTimestamp: "2026-09-28T00:00:00.000Z",
        value: 78_900,
      }),
    ]);
  });
});
