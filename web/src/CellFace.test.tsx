import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import type { BoardCell } from "./board";
import { CellFace } from "./CellFace";
import type { Datapoint } from "./datapoint";

const NOW = new Date("2026-09-14T00:01:00Z");
const provenance = {
  indicatorKey: "btc_daily_close",
  asset: "BTC",
  measuredOn: "BTC",
  sourceVendor: "OKX",
  endpoint:
    "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1Dutc",
  sourceField: 'candle[4] (close), where candle[8] == "1"',
  fetchedAt: "2026-09-14T00:01:00Z",
  sourceTimestamp: "2026-09-13T00:00:00Z",
} as const;

function cell(state: Datapoint): BoardCell {
  return {
    family: "daily_close",
    asset: state.asset,
    indicatorKey: state.indicatorKey,
    state,
  };
}

function renderCells(...states: Datapoint[]) {
  render(
    <table>
      <tbody>
        <tr>
          {states.map((state) => (
            <CellFace key={`${state.indicatorKey}:${state.status}`} cell={cell(state)} now={NOW} />
          ))}
        </tr>
      </tbody>
    </table>,
  );
  return screen.getAllByRole("cell");
}

describe("cell provenance", () => {
  test("every OK and STALE cell shows its vendor and its source timestamp with no interaction", () => {
    const cells = renderCells(
      { ...provenance, status: "OK", value: 11111.11 },
      {
        ...provenance,
        indicatorKey: "btc_rsi",
        status: "STALE",
        value: 48.2,
      },
    );

    for (const renderedCell of cells) {
      expect(within(renderedCell).getByText("OKX")).toBeVisible();
      expect(
        within(renderedCell).getByText("13 Sep 2026, 00:00:00 UTC"),
      ).toBeVisible();
      expect(renderedCell.querySelector("details")).not.toHaveAttribute("open");
    }
  });

  test("a STALE cell shows its age in the same glance as its value", () => {
    const [renderedCell] = renderCells({
      ...provenance,
      status: "STALE",
      value: 11111.11,
    });
    const summary = renderedCell.querySelector("summary");

    expect(summary).not.toBeNull();
    expect(within(summary as HTMLElement).getByText("11,111.1 · 1 day old")).toBeVisible();
    expect(within(summary as HTMLElement).getByText("Stale")).toBeVisible();
  });

  test("the timestamp shown is source_timestamp and not fetched_at", () => {
    const [renderedCell] = renderCells({
      ...provenance,
      status: "OK",
      value: 11111.11,
    });
    const summary = renderedCell.querySelector("summary");

    expect(summary).not.toBeNull();
    expect(
      within(summary as HTMLElement).getByText("13 Sep 2026, 00:00:00 UTC"),
    ).toBeVisible();
    expect(
      within(summary as HTMLElement).queryByText("14 Sep 2026, 00:01:00 UTC"),
    ).not.toBeInTheDocument();
  });

  test("an ERROR cell shows its reason and shows no number at all", () => {
    const [renderedCell] = renderCells({
      ...provenance,
      status: "ERROR",
      reason: "FETCH_FAILED",
      detail: "Synthetic upstream timeout",
    });

    expect(within(renderedCell).getByText("Fetch failed")).toBeVisible();
    expect(within(renderedCell).getByText("Synthetic upstream timeout")).toBeVisible();
    expect(within(renderedCell).queryByTestId("cell-value")).not.toBeInTheDocument();
  });

  test("a cell with a reference period distinct from its publication date shows both", () => {
    const [renderedCell] = renderCells({
      ...provenance,
      indicatorKey: "usd_m2",
      asset: "USD",
      measuredOn: "USD",
      status: "OK",
      value: 23218,
      referencePeriod: "2026-07-01T00:00:00Z",
      publishedAt: "2026-09-08T00:00:00Z",
      sourceTimestamp: "2026-09-08T00:00:00Z",
    });

    expect(within(renderedCell).getByText("01 Jul 2026, 00:00:00 UTC")).toBeVisible();
    expect(
      within(renderedCell).getAllByText("08 Sep 2026, 00:00:00 UTC"),
    ).toHaveLength(2);
    expect(within(renderedCell).getByText("Reference period")).toBeVisible();
    expect(within(renderedCell).getByText("Published")).toBeVisible();
  });

  test("opening a cell reveals endpoint source field and fetch time", () => {
    const [renderedCell] = renderCells({
      ...provenance,
      status: "OK",
      value: 11111.11,
    });
    const disclosure = renderedCell.querySelector("details");
    const summary = renderedCell.querySelector("summary");

    expect(disclosure).not.toBeNull();
    expect(summary).not.toBeNull();
    fireEvent.click(summary as HTMLElement);

    expect(disclosure).toHaveAttribute("open");
    expect(within(renderedCell).getByText(provenance.endpoint)).toBeVisible();
    expect(within(renderedCell).getByText(provenance.sourceField)).toBeVisible();
    expect(within(renderedCell).getByText("14 Sep 2026, 00:01:00 UTC")).toBeVisible();
  });

  test("the detail view can be opened and closed by keyboard alone", () => {
    const [renderedCell] = renderCells({
      ...provenance,
      status: "OK",
      value: 11111.11,
    });
    const disclosure = renderedCell.querySelector("details");
    const summary = renderedCell.querySelector("summary") as HTMLElement;

    summary.focus();
    expect(summary).toHaveFocus();
    fireEvent.keyDown(summary, { key: "Enter" });
    expect(disclosure).toHaveAttribute("open");
    fireEvent.keyDown(summary, { key: " " });
    expect(disclosure).not.toHaveAttribute("open");
  });
});
