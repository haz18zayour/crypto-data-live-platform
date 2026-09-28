import type { BoardCell } from "./board";
import { CellDetail, formatUtcTimestamp } from "./CellDetail";
import { assertNever, type Datapoint, type UnavailableReason } from "./datapoint";
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

const reasonLabels: Record<UnavailableReason, string> = {
  NOT_DEFINABLE: "Not definable",
  PAYWALLED: "Requires paid tier",
  FETCH_FAILED: "Fetch failed",
  NOT_FETCHED: "Not fetched",
};

function isSourced(state: BoardCell["state"]): state is Datapoint {
  return "sourceVendor" in state;
}

function needsFaceDisclosure(state: BoardCell["state"]): state is Datapoint {
  return isSourced(state) && state.indicatorKey === "fear_greed_index";
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

  const content = (
    <>
      <span className="cell-primary">
        <span className="cell-glyph" aria-hidden="true">
          {face.glyph}
        </span>{" "}
        <span className="cell-word">{face.word}</span>{" "}
        <span
          className="cell-detail"
          data-testid={
            cell.state.status === "OK" || cell.state.status === "STALE"
              ? "cell-value"
              : undefined
          }
        >
          {face.detail}
        </span>
      </span>
      {cell.state.status === "ERROR" ? (
        <span className="cell-reason">{reasonLabels[cell.state.reason]}</span>
      ) : null}
      {cell.state.status === "OK" || cell.state.status === "STALE" ? (
        <>
          <span className="cell-provenance">
            <span className="cell-vendor">{cell.state.sourceVendor}</span>
            <span aria-hidden="true"> · </span>
            <span>Source</span>{" "}
            <time dateTime={cell.state.sourceTimestamp}>
              {formatUtcTimestamp(cell.state.sourceTimestamp)}
            </time>
          </span>
          {cell.state.referencePeriod ? (
            <span className="cell-reference-period">
              <span>Reference period</span>{" "}
              <time dateTime={cell.state.referencePeriod}>
                {formatUtcTimestamp(cell.state.referencePeriod)}
              </time>
            </span>
          ) : null}
          {cell.state.publishedAt ? (
            <span className="cell-published-at">
              <span>Published</span>{" "}
              <time dateTime={cell.state.publishedAt}>
                {formatUtcTimestamp(cell.state.publishedAt)}
              </time>
            </span>
          ) : null}
          {needsFaceDisclosure(cell.state) ? (
            <span className="cell-face-disclosure">{cell.state.sourceField}</span>
          ) : null}
        </>
      ) : null}
    </>
  );

  return (
    <td className={`cell cell--${face.name}`}>
      {isSourced(cell.state) ? (
        <CellDetail datapoint={cell.state}>{content}</CellDetail>
      ) : (
        content
      )}
    </td>
  );
}
