import type { BoardModel } from "./board";
import { countCoverage } from "./coverage";

type CoverageHeadlineProps = {
  board: BoardModel;
};

export function CoverageHeadline({ board }: CoverageHeadlineProps) {
  const coverage = countCoverage(board);

  return (
    <p
      role="status"
      aria-atomic="true"
      style={{ fontVariantNumeric: "tabular-nums" }}
    >
      <strong>
        {coverage.ok} of {coverage.total} indicators OK
      </strong>{" "}
      <span>· {coverage.stale} stale</span>{" "}
      <span>· {coverage.unavailable} unavailable</span>
      <br />{" "}
      <span>{coverage.notDefinable} not definable</span>{" "}
      <span>· {coverage.paywalled} paywalled</span>{" "}
      <span>· {coverage.fetchFailed} fetch failed</span>
    </p>
  );
}
