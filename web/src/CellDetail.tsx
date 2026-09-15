import type { KeyboardEvent, ReactNode } from "react";

import type { Datapoint } from "./datapoint";

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

export function CellDetail({
  datapoint,
  children,
}: {
  datapoint: Datapoint;
  children: ReactNode;
}) {
  return (
    <details className="cell-disclosure">
      <summary onKeyDown={toggleWithKeyboard}>
        {children}
        <span className="cell-detail-cue">Details</span>
      </summary>
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
