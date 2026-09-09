import { render, screen, within } from "@testing-library/react";
import { describe, expect, expectTypeOf, it } from "vitest";

import { DatapointValue } from "./DatapointValue";
import { assertNever, type Datapoint } from "./datapoint";

const provenance = {
  indicatorKey: "btc_daily_close",
  asset: "BTC",
  measuredOn: "BTC",
  sourceVendor: "OKX",
  endpoint:
    "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1Dutc",
  sourceField: 'candle[4] (close), where candle[8] == "1"',
  fetchedAt: "2026-09-09T01:00:00.000Z",
  sourceTimestamp: "2026-09-09T00:00:00.000Z",
};

describe("DatapointValue", () => {
  it("an UNAVAILABLE datapoint renders an em dash and its reason, never a zero", () => {
    const cases = [
      ["NOT_DEFINABLE", "Not definable for this chain"],
      ["PAYWALLED", "Requires a paid tier"],
      ["FETCH_FAILED", "Fetch failed"],
    ] as const;

    for (const [reason, message] of cases) {
      const { unmount } = render(
        <DatapointValue
          datapoint={{ status: "UNAVAILABLE", reason, ...provenance }}
          now={new Date("2026-09-09T02:00:00.000Z")}
        />,
      );

      const value = screen.getByTestId("datapoint-value");
      expect(value).toHaveTextContent("—");
      expect(value).not.toHaveTextContent("0");
      expect(screen.getByText(message)).toBeVisible();
      unmount();
    }
  });

  it("a STALE datapoint renders the value with its age and a visible stale treatment", () => {
    render(
      <DatapointValue
        datapoint={{ status: "STALE", value: 111234.5, ...provenance }}
        now={new Date("2026-09-12T00:00:00.000Z")}
      />,
    );

    const card = screen.getByLabelText("Stale datapoint");
    expect(card).toHaveClass("datapoint--stale");
    expect(within(card).getByText("STALE")).toBeVisible();
    expect(within(card).getByText("3 days old")).toBeVisible();
    expect(within(card).getByTestId("datapoint-value")).toHaveTextContent(
      "$111,234.50",
    );
  });

  it("adding a status to the union without handling it is a compile error", () => {
    expectTypeOf(assertNever).parameter(0).toEqualTypeOf<never>();
  });

  it("the value displays its source vendor, endpoint and source timestamp", () => {
    render(
      <DatapointValue
        datapoint={{ status: "OK", value: 111234.5, ...provenance }}
        now={new Date("2026-09-09T02:00:00.000Z")}
      />,
    );

    expect(screen.getByText("OKX")).toBeVisible();
    expect(screen.getByText(provenance.endpoint)).toBeVisible();
    expect(screen.getByText("09 Sep 2026, 00:00:00 UTC")).toBeVisible();
  });

  it("a value whose reference period differs from its publication date shows both", () => {
    const datapoint: Datapoint = {
      status: "OK",
      value: 23218,
      ...provenance,
      indicatorKey: "m2",
      asset: "USD",
      measuredOn: "USD",
      referencePeriod: "2026-07-01T00:00:00.000Z",
      publishedAt: "2026-09-08T00:00:00.000Z",
      sourceTimestamp: "2026-09-08T00:00:00.000Z",
    };

    render(
      <DatapointValue
        datapoint={datapoint}
        now={new Date("2026-09-09T00:00:00.000Z")}
      />,
    );

    expect(screen.getByText("Reference period")).toBeVisible();
    expect(screen.getByText("01 Jul 2026, 00:00:00 UTC")).toBeVisible();
    expect(screen.getByText("Published")).toBeVisible();
    expect(screen.getAllByText("08 Sep 2026, 00:00:00 UTC")).toHaveLength(2);
    expect(screen.getByText("1 day old")).toBeVisible();
  });
});
