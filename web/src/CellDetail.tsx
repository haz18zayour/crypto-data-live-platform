import { useEffect, useState, type KeyboardEvent, type ReactNode } from "react";

import type { CellFrozenBadge } from "./board";
import type { Datapoint } from "./datapoint";
import { formatUtcTimestamp } from "./FrozenBadge";
import { fetchHistory, HISTORY_POINT_LIMIT, type HistoryPoint } from "./history";
import { Sparkline } from "./Sparkline";

function toggleWithKeyboard(event: KeyboardEvent<HTMLElement>) {
  if (event.key !== "Enter" && event.key !== " ") return;

  event.preventDefault();
  const disclosure = event.currentTarget.parentElement as HTMLDetailsElement;
  disclosure.open = !disclosure.open;
}

type HistoryLoad =
  | { state: "loading" }
  | { state: "loaded"; history: HistoryPoint[] }
  | { state: "failed"; message: string };

// History is read only for a cell someone opened, pinned to the vendor that wrote the cell's own
// value so two corroborating venues never interleave into one line.
function CellHistory({ datapoint }: { datapoint: Datapoint }) {
  const [load, setLoad] = useState<HistoryLoad>({ state: "loading" });
  useEffect(() => {
    let current = true;
    fetchHistory(
      datapoint.indicatorKey,
      datapoint.asset,
      datapoint.sourceVendor,
      HISTORY_POINT_LIMIT,
    ).then(
      (history) => current && setLoad({ state: "loaded", history }),
      (error: unknown) =>
        current &&
        setLoad({
          state: "failed",
          message: error instanceof Error ? error.message : String(error),
        }),
    );
    return () => {
      current = false;
    };
  }, [datapoint.indicatorKey, datapoint.asset, datapoint.sourceVendor]);

  return (
    <div className="cell-history">
      {load.state === "loading" ? (
        <p className="cell-history-note">Loading history…</p>
      ) : load.state === "failed" ? (
        <p className="cell-history-note">History could not be read: {load.message}</p>
      ) : (
        <Sparkline history={load.history} />
      )}
    </div>
  );
}

export function CellDetail({
  datapoint,
  frozen,
  children,
}: {
  datapoint: Datapoint;
  frozen?: CellFrozenBadge;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const hasHistory = datapoint.status === "OK" || datapoint.status === "STALE";
  return (
    <details
      className="cell-disclosure"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary onKeyDown={toggleWithKeyboard}>
        {children}
        <span className="cell-detail-cue">Details</span>
      </summary>
      {open && hasHistory ? <CellHistory datapoint={datapoint} /> : null}
      <dl className="cell-source-detail" aria-label="Source detail">
        <div>
          <dt>Endpoint</dt>
          <dd>{datapoint.endpoint}</dd>
        </div>
        <div>
          <dt>Source field</dt>
          <dd>{datapoint.sourceField}</dd>
        </div>
        <div>
          <dt>Fetch time</dt>
          <dd>
            {datapoint.fetchedAt
              ? formatUtcTimestamp(datapoint.fetchedAt)
              : "Not supplied"}
          </dd>
        </div>
        {frozen ? (
          <div>
            <dt>Integrity</dt>
            <dd>
              Frozen value unchanged since{" "}
              <time dateTime={frozen.sinceSourceTimestamp}>
                {formatUtcTimestamp(frozen.sinceSourceTimestamp)}
              </time>
            </dd>
          </div>
        ) : null}
      </dl>
    </details>
  );
}
