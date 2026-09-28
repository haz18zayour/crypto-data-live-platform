import { useEffect, useState, type KeyboardEvent, type ReactNode } from "react";

import type { Datapoint } from "./datapoint";
import { fetchHistory, HISTORY_POINT_LIMIT, type HistoryPoint } from "./history";
import { Sparkline } from "./Sparkline";

export function formatUtcTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  const day = String(date.getUTCDate()).padStart(2, "0");
  const time = [date.getUTCHours(), date.getUTCMinutes(), date.getUTCSeconds()]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
  return `${day} ${months[date.getUTCMonth()]} ${date.getUTCFullYear()}, ${time} UTC`;
}

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
  children,
}: {
  datapoint: Datapoint;
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
      </dl>
    </details>
  );
}
