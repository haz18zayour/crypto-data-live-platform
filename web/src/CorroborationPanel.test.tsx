import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CorroborationPanel } from "./CorroborationPanel";
import type { Corroboration } from "./corroboration";

const okx = {
  status: "OK" as const,
  value: 78_834.1,
  indicatorKey: "btc_daily_close",
  asset: "BTC",
  measuredOn: "BTC",
  sourceVendor: "OKX",
  endpoint:
    "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1Dutc",
  sourceField: "close",
  fetchedAt: "2026-09-10T01:00:00.000Z",
  sourceTimestamp: "2026-09-10T00:00:00.000Z",
};

const coinbase = {
  ...okx,
  value: 79_111.8,
  sourceVendor: "COINBASE",
  endpoint: "https://api.exchange.coinbase.com/products/BTC-USD/candles",
};

function comparison(
  status: "CORROBORATED" | "DIVERGED",
  divergenceBps: number,
): Corroboration {
  return {
    status,
    divergenceBps,
    toleranceBpsAtWrite: 25,
    datapoints: [okx, coinbase],
  };
}

describe("CorroborationPanel", () => {
  it("a value whose divergence exceeds tolerance renders visibly differently from one inside tolerance", () => {
    const { rerender } = render(
      <CorroborationPanel corroboration={comparison("CORROBORATED", 13.8)} />,
    );
    const corroborated = screen.getByLabelText("Corroborated values");
    expect(corroborated).toHaveClass("corroboration--corroborated");
    expect(within(corroborated).getByText("CORROBORATED")).toBeVisible();

    rerender(
      <CorroborationPanel corroboration={comparison("DIVERGED", 35.2)} />,
    );
    const diverged = screen.getByLabelText("Diverged values");
    expect(diverged).toHaveClass("corroboration--diverged");
    expect(within(diverged).getByText("DIVERGED")).toBeVisible();
    expect(diverged).not.toHaveClass("corroboration--corroborated");
  });

  it("both venue values and the divergence in bps are shown, not just a warning", () => {
    render(<CorroborationPanel corroboration={comparison("DIVERGED", 35.2)} />);

    const card = screen.getByLabelText("Diverged values");
    expect(within(card).getByText("OKX")).toBeVisible();
    expect(within(card).getByText("$78,834.10")).toBeVisible();
    expect(within(card).getByText("COINBASE")).toBeVisible();
    expect(within(card).getByText("$79,111.80")).toBeVisible();
    expect(within(card).getByText("35.2 bps")).toBeVisible();
    expect(within(card).getByText("Tolerance: 25.0 bps")).toBeVisible();
  });

  it("an uncorroborated value is visually distinct from a corroborated one", () => {
    const { rerender } = render(
      <CorroborationPanel corroboration={comparison("CORROBORATED", 13.8)} />,
    );
    expect(screen.getByLabelText("Corroborated values")).toHaveClass(
      "corroboration--corroborated",
    );

    rerender(
      <CorroborationPanel
        corroboration={{
          status: "UNCORROBORATED",
          datapoint: okx,
          reason: "No independent second source is registered.",
        }}
      />,
    );
    const uncorroborated = screen.getByLabelText("Uncorroborated value");
    expect(uncorroborated).toHaveClass("corroboration--uncorroborated");
    expect(within(uncorroborated).getByText("UNCORROBORATED")).toBeVisible();
    expect(uncorroborated).not.toHaveClass("corroboration--corroborated");
  });

  it("NOT_CORROBORATED renders as its own state, distinct from both", () => {
    render(
      <CorroborationPanel
        corroboration={{
          status: "NOT_CORROBORATED",
          datapoint: okx,
          reason: "Coinbase has no closed bar for this UTC day.",
        }}
      />,
    );

    const card = screen.getByLabelText("Not corroborated value");
    expect(card).toHaveClass("corroboration--not-corroborated");
    expect(card).not.toHaveClass("corroboration--corroborated");
    expect(card).not.toHaveClass("corroboration--uncorroborated");
    expect(within(card).getByText("NOT_CORROBORATED")).toBeVisible();
    expect(
      within(card).getByText("Coinbase has no closed bar for this UTC day."),
    ).toBeVisible();
    expect(within(card).getByText("$78,834.10")).toBeVisible();
  });

  it("no averaged or combined value is displayed anywhere", () => {
    render(<CorroborationPanel corroboration={comparison("DIVERGED", 35.2)} />);

    expect(screen.getByText("$78,834.10")).toBeVisible();
    expect(screen.getByText("$79,111.80")).toBeVisible();
    expect(screen.queryByText("$78,972.95")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("venue-value")).toHaveLength(2);
  });
});
