import type { BoardCell } from "./board";
import { assertNever } from "./datapoint";
import { formatAge } from "./DatapointValue";

type Face = {
  name: string;
  glyph: string;
  word: string;
  detail: string;
};

function formatValue(value: number): string {
  return value.toLocaleString("en-US", { maximumSignificantDigits: 6 });
}

// Every state, OK included, goes through this one switch, so no value reaches the page without
// passing the absence logic. Each face carries a glyph and a word as well as its colour class.
function faceOf(state: BoardCell["state"], now: Date): Face {
  switch (state.status) {
    case "OK":
      return {
        name: "ok",
        glyph: "●",
        word: "OK",
        detail: formatValue(state.value),
      };
    case "STALE":
      return {
        name: "stale",
        glyph: "◐",
        word: "Stale",
        detail: `${formatValue(state.value)} · ${formatAge(state.publishedAt ?? state.sourceTimestamp, now)}`,
      };
    case "UNAVAILABLE":
    case "ERROR": {
      const errorDetail = state.status === "ERROR" ? state.detail : undefined;
      const reason = state.reason;
      switch (reason) {
        case "NOT_DEFINABLE":
          return {
            name: "not-definable",
            glyph: "⊘",
            word: "n/a",
            detail:
              "detail" in state ? state.detail : "Not definable for this chain",
          };
        case "PAYWALLED":
          return {
            name: "paywalled",
            glyph: "◇",
            word: "Requires paid tier",
            detail: errorDetail ?? "Credentials not held",
          };
        case "FETCH_FAILED":
          return {
            name: "fetch-failed",
            glyph: "✕",
            word: "Unavailable",
            detail: errorDetail ?? "Fetch failed",
          };
        case "NOT_FETCHED":
          return {
            name: "not-fetched",
            glyph: "!",
            word: "Not fetched",
            detail: errorDetail ?? "No row has been recorded",
          };
        default:
          return assertNever(reason);
      }
    }
    default:
      return assertNever(state);
  }
}

export function CellFace({ cell, now }: { cell: BoardCell; now: Date }) {
  const face = faceOf(cell.state, now);

  return (
    <td className={`cell cell--${face.name}`}>
      <span className="cell-glyph" aria-hidden="true">
        {face.glyph}
      </span>{" "}
      <span className="cell-word">{face.word}</span>{" "}
      <span className="cell-detail">{face.detail}</span>
    </td>
  );
}
