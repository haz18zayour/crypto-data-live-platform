import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchLatestCorroboration } from "./data";
import type { IndicatorDefinition } from "./registry";

const definition: IndicatorDefinition = {
  key: "btc_daily_close",
  vendor: "okx",
  endpoint: "https://www.okx.com/candles",
  source_field: "close",
  freshness_warn_seconds: 108_000,
  freshness_stale_seconds: 172_800,
  corroboration: {
    venue: "coinbase",
    pair: "BTC-USD",
    tolerance_bps: 25,
  },
};

const primaryRow = {
  id: 20,
  indicator_key: "btc_daily_close",
  asset: "BTC",
  measured_on: "BTC",
  value: 78_834.1,
  status: "OK",
  reason: null,
  source_vendor: "okx",
  endpoint: "https://www.okx.com/candles",
  source_field: "close",
  fetched_at: "2026-09-10T01:00:00.000Z",
  source_timestamp: "2026-09-10T00:00:00.000Z",
};

const secondaryRow = {
  ...primaryRow,
  id: 10,
  value: 79_111.8,
  source_vendor: "coinbase",
  endpoint: "https://api.exchange.coinbase.com/products/BTC-USD/candles",
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchLatestCorroboration", () => {
  it("loads the stored comparison and both peer venue rows without combining them", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse([primaryRow]))
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 7,
            datapoint_a_id: 10,
            datapoint_b_id: 20,
            divergence_bps: 35.2,
            tolerance_bps_at_write: 25,
            status: "DIVERGED",
            reason: null,
          },
        ]),
      )
      .mockResolvedValueOnce(jsonResponse([secondaryRow]));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchLatestCorroboration(definition, {
      supabaseUrl: "https://example.supabase.co",
      anonKey: "test-key",
    });

    expect(result).toEqual({
      status: "DIVERGED",
      divergenceBps: 35.2,
      toleranceBpsAtWrite: 25,
      datapoints: [
        expect.objectContaining({ sourceVendor: "OKX", value: 78_834.1 }),
        expect.objectContaining({
          sourceVendor: "COINBASE",
          value: 79_111.8,
        }),
      ],
    });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(String(fetchMock.mock.calls[1][0])).toContain("corroborations_read");
  });

  it("loads a stored NOT_CORROBORATED result as its own reasoned state", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse([primaryRow]))
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 8,
            datapoint_a_id: 20,
            datapoint_b_id: null,
            divergence_bps: null,
            tolerance_bps_at_write: null,
            status: "NOT_CORROBORATED",
            reason: "FETCH_FAILED",
          },
        ]),
      );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchLatestCorroboration(definition, {
      supabaseUrl: "https://example.supabase.co",
      anonKey: "test-key",
    });

    expect(result).toEqual({
      status: "NOT_CORROBORATED",
      datapoint: expect.objectContaining({ sourceVendor: "OKX", value: 78_834.1 }),
      reason: "Second venue did not provide a comparable bar (FETCH_FAILED).",
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
