import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { App } from "./App";

vi.mock("./data", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./data")>();
  return {
    ...actual,
    fetchLatestCorroboration: vi.fn().mockResolvedValue({
      status: "DIVERGED",
      divergenceBps: 35.2,
      toleranceBpsAtWrite: 25,
      datapoints: [
        {
          status: "OK",
          value: 78_834.1,
          indicatorKey: "btc_daily_close",
          asset: "BTC",
          measuredOn: "BTC",
          sourceVendor: "OKX",
          endpoint: "https://www.okx.com/candles",
          sourceField: "close",
          fetchedAt: "2026-09-10T01:00:00.000Z",
          sourceTimestamp: "2026-09-10T00:00:00.000Z",
        },
        {
          status: "OK",
          value: 79_111.8,
          indicatorKey: "btc_daily_close",
          asset: "BTC",
          measuredOn: "BTC",
          sourceVendor: "COINBASE",
          endpoint: "https://api.exchange.coinbase.com/candles",
          sourceField: "close",
          fetchedAt: "2026-09-10T01:00:00.000Z",
          sourceTimestamp: "2026-09-10T00:00:00.000Z",
        },
      ],
    }),
  };
});

it("the stored divergence reaches the page with both venue values", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );

  const panel = await screen.findByLabelText("Diverged values");
  expect(panel).toHaveTextContent("35.2 bps");
  expect(panel).toHaveTextContent("OKX");
  expect(panel).toHaveTextContent("$78,834.10");
  expect(panel).toHaveTextContent("COINBASE");
  expect(panel).toHaveTextContent("$79,111.80");
});
