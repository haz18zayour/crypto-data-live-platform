import { assertNever, type Datapoint, type UnavailableReason } from "./datapoint";

const reasonMessages: Record<UnavailableReason, string> = {
  NOT_DEFINABLE: "Not definable for this chain",
  PAYWALLED: "Requires a paid tier",
  FETCH_FAILED: "Fetch failed",
  NOT_FETCHED: "Not fetched yet",
};

function formatTimestamp(timestamp: string): string {
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

export function formatAge(timestamp: string | null, now: Date): string {
  if (!timestamp) return "Age unavailable";

  const seconds = Math.max(
    0,
    Math.floor((now.getTime() - new Date(timestamp).getTime()) / 1000),
  );
  if (seconds < 60) return `${seconds} ${seconds === 1 ? "second" : "seconds"} old`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} ${minutes === 1 ? "minute" : "minutes"} old`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} ${hours === 1 ? "hour" : "hours"} old`;

  const days = Math.floor(hours / 24);
  return `${days} ${days === 1 ? "day" : "days"} old`;
}

function Provenance({ datapoint }: { datapoint: Datapoint }) {
  return (
    <dl className="provenance" aria-label="Provenance">
      <div>
        <dt>Source vendor</dt>
        <dd>{datapoint.sourceVendor}</dd>
      </div>
      <div>
        <dt>Endpoint</dt>
        <dd className="endpoint">{datapoint.endpoint}</dd>
      </div>
      <div>
        <dt>Source field</dt>
        <dd>{datapoint.sourceField}</dd>
      </div>
      <div>
        <dt>Source timestamp</dt>
        <dd>
          {datapoint.sourceTimestamp
            ? formatTimestamp(datapoint.sourceTimestamp)
            : "Not supplied"}
        </dd>
      </div>
      {datapoint.referencePeriod ? (
        <div>
          <dt>Reference period</dt>
          <dd>{formatTimestamp(datapoint.referencePeriod)}</dd>
        </div>
      ) : null}
      {datapoint.publishedAt ? (
        <div>
          <dt>Published</dt>
          <dd>{formatTimestamp(datapoint.publishedAt)}</dd>
        </div>
      ) : null}
    </dl>
  );
}

function ValueCard({ datapoint, now }: { datapoint: Datapoint; now: Date }) {
  const ageFrom = datapoint.publishedAt ?? datapoint.sourceTimestamp;

  switch (datapoint.status) {
    case "OK":
      return (
        <article className="datapoint" aria-label="Current datapoint">
          <header>
            <span className="status status--ok">CURRENT</span>
            <span className="age">{formatAge(ageFrom, now)}</span>
          </header>
          <p className="value" data-testid="datapoint-value">
            {datapoint.value.toLocaleString("en-US", {
              style: "currency",
              currency: "USD",
            })}
          </p>
          <Provenance datapoint={datapoint} />
        </article>
      );
    case "STALE":
      return (
        <article className="datapoint datapoint--stale" aria-label="Stale datapoint">
          <header>
            <span className="status status--stale">STALE</span>
            <strong className="age">{formatAge(ageFrom, now)}</strong>
          </header>
          <p className="value" data-testid="datapoint-value">
            {datapoint.value.toLocaleString("en-US", {
              style: "currency",
              currency: "USD",
            })}
          </p>
          <p className="warning">This value is past its freshness budget.</p>
          <Provenance datapoint={datapoint} />
        </article>
      );
    case "UNAVAILABLE":
      return (
        <article className="datapoint datapoint--unavailable" aria-label="Unavailable datapoint">
          <header>
            <span className="status">UNAVAILABLE</span>
          </header>
          <p className="value" data-testid="datapoint-value">
            —
          </p>
          <p className="reason">{reasonMessages[datapoint.reason]}</p>
          <Provenance datapoint={datapoint} />
        </article>
      );
    case "ERROR":
      return (
        <article className="datapoint datapoint--error" aria-label="Datapoint error">
          <header>
            <span className="status status--error">ERROR</span>
          </header>
          <p className="value" data-testid="datapoint-value">
            —
          </p>
          <p className="reason">{reasonMessages[datapoint.reason]}</p>
          <p className="detail">{datapoint.detail}</p>
          <Provenance datapoint={datapoint} />
        </article>
      );
  }

  return assertNever(datapoint);
}

export function DatapointValue({
  datapoint,
  now = new Date(),
}: {
  datapoint: Datapoint;
  now?: Date;
}) {
  return <ValueCard datapoint={datapoint} now={now} />;
}
