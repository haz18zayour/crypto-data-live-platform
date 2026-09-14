import type { BoardModel } from "./board";
import { assertNever } from "./datapoint";

export type CoverageCounts = {
  total: number;
  ok: number;
  stale: number;
  unavailable: number;
  notDefinable: number;
  paywalled: number;
  fetchFailed: number;
};

export function countCoverage(board: BoardModel): CoverageCounts {
  const coverage: CoverageCounts = {
    total: board.cells.length,
    ok: 0,
    stale: 0,
    unavailable: 0,
    notDefinable: 0,
    paywalled: 0,
    fetchFailed: 0,
  };

  for (const { state } of board.cells) {
    switch (state.status) {
      case "OK":
        coverage.ok += 1;
        break;
      case "STALE":
        coverage.stale += 1;
        break;
      case "UNAVAILABLE":
      case "ERROR": {
        const reason = state.reason;
        switch (reason) {
          case "NOT_FETCHED":
            coverage.unavailable += 1;
            break;
          case "NOT_DEFINABLE":
            coverage.notDefinable += 1;
            break;
          case "PAYWALLED":
            coverage.paywalled += 1;
            break;
          case "FETCH_FAILED":
            coverage.fetchFailed += 1;
            break;
          default:
            assertNever(reason);
        }
        break;
      }
      default:
        assertNever(state);
    }
  }

  return coverage;
}
