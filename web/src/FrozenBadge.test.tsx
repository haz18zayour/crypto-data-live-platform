import { render, screen, within } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { buildBoard, type BoardCell } from "./board";
import { CellFace } from "./CellFace";
import type { Datapoint } from "./datapoint";
import type { IndicatorKey } from "./registry.generated";

const NOW = new Date("2026-09-29T12:00:00Z");

const datapoint = {
  indicatorKey: "btc_daily_close",
  asset: "BTC",
  measuredOn: "BTC",
  sourceVendor: "OKX",
  endpoint: "https://example.test/candles",
  sourceField: "close",
  fetchedAt: "2026-09-29T00:01:00Z",
  sourceTimestamp: "2026-09-29T00:00:00Z",
  status: "OK",
  value: 11111.11,
} satisfies Datapoint;

function integrityRow({
  indicatorKey = "btc_daily_close",
  frozen = true,
  frozenState = "frozen",
  frozenSinceSourceTimestamp = "2026-09-24T00:00:00Z",
  derivesFrom = null,
}: {
  indicatorKey?: IndicatorKey;
  frozen?: boolean | null;
  frozenState?: string;
  frozenSinceSourceTimestamp?: string | null;
  derivesFrom?: IndicatorKey | null;
} = {}) {
  return {
    indicatorKey,
    asset: "BTC",
    sourceVendor: "OKX",
    frozen,
    frozenState,
    frozenSinceSourceTimestamp,
    derivesFrom,
  };
}

function cellFor(state: Datapoint, rows = [integrityRow()]): BoardCell {
  return buildBoard(
    [{ key: state.indicatorKey, definable_for: [state.asset] }],
    [state],
    [state.asset],
    rows,
  ).cells[0];
}

function renderCell(cell: BoardCell) {
  render(
    <table>
      <tbody>
        <tr>
          <CellFace cell={cell} now={NOW} />
        </tr>
      </tbody>
    </table>,
  );
  return screen.getByRole("cell");
}

describe("frozen badge", () => {
  test("a cell whose own indicator is flagged frozen shows unchanged since the source date without changing OK status", () => {
    const rendered = renderCell(cellFor(datapoint));

    expect(within(rendered).getByText("OK")).toBeVisible();
    expect(within(rendered).getByTestId("cell-value")).toHaveTextContent("11,111.1");
    expect(rendered).toHaveClass("cell--ok");
    expect(within(rendered).getByText("unchanged since")).toBeVisible();
    expect(within(rendered).getByText("24 Sep 2026")).toHaveAttribute(
      "dateTime",
      "2026-09-24T00:00:00Z",
    );
  });

  test("a derived cell shows the root frozen date carried by the integrity read", () => {
    const derived = {
      ...datapoint,
      indicatorKey: "btc_rsi",
      sourceTimestamp: "2026-09-29T00:00:00Z",
      value: 48.2,
    } satisfies Datapoint;

    const rendered = renderCell(
      cellFor(derived, [
        integrityRow({
          indicatorKey: "btc_rsi",
          derivesFrom: "btc_daily_close",
          frozenSinceSourceTimestamp: "2026-09-20T00:00:00Z",
        }),
      ]),
    );

    expect(within(rendered).getByText("unchanged since")).toBeVisible();
    expect(within(rendered).getByText("20 Sep 2026")).toHaveAttribute(
      "dateTime",
      "2026-09-20T00:00:00Z",
    );
    expect(within(rendered).queryByText("29 Sep 2026")).not.toBeInTheDocument();
  });

  test("a cell not flagged frozen renders no badge", () => {
    const rendered = renderCell(
      cellFor(datapoint, [
        integrityRow({
          frozen: false,
          frozenState: "not_frozen",
          frozenSinceSourceTimestamp: null,
        }),
      ]),
    );

    expect(within(rendered).queryByText("unchanged since")).not.toBeInTheDocument();
  });

  test("an expected_constant indicator never renders the badge", () => {
    const expectedConstant = {
      ...datapoint,
      indicatorKey: "btc_funding_rate",
      value: 0.0001,
    } satisfies Datapoint;

    const rendered = renderCell(
      cellFor(expectedConstant, [
        integrityRow({
          indicatorKey: "btc_funding_rate",
          frozen: false,
          frozenState: "expected_constant",
          frozenSinceSourceTimestamp: "2026-09-20T00:00:00Z",
        }),
      ]),
    );

    expect(within(rendered).queryByText("unchanged since")).not.toBeInTheDocument();
    expect(within(rendered).getByText("OK")).toBeVisible();
  });
});
