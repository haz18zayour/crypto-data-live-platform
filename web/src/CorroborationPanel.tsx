import {
  assertNeverCorroboration,
  type Corroboration,
  type VenueDatapoint,
} from "./corroboration";

function formatValue(value: number): string {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
  });
}

function VenueValue({ datapoint }: { datapoint: VenueDatapoint }) {
  return (
    <section className="venue-value">
      <h2>{datapoint.sourceVendor}</h2>
      <p data-testid="venue-value">{formatValue(datapoint.value)}</p>
      <p className="venue-timestamp">{datapoint.sourceTimestamp}</p>
    </section>
  );
}

export function CorroborationPanel({
  corroboration,
}: {
  corroboration: Corroboration;
}) {
  switch (corroboration.status) {
    case "CORROBORATED":
    case "DIVERGED": {
      const diverged = corroboration.status === "DIVERGED";
      return (
        <article
          className={`corroboration corroboration--${diverged ? "diverged" : "corroborated"}`}
          aria-label={diverged ? "Diverged values" : "Corroborated values"}
        >
          <header className="corroboration-summary">
            <strong className="corroboration-status">
              {corroboration.status}
            </strong>
            <span className="divergence">
              {corroboration.divergenceBps.toFixed(1)} bps
            </span>
            <span className="tolerance">
              Tolerance: {corroboration.toleranceBpsAtWrite.toFixed(1)} bps
            </span>
          </header>
          <div className="venue-values">
            {corroboration.datapoints.map((datapoint) => (
              <VenueValue
                key={`${datapoint.sourceVendor}-${datapoint.sourceTimestamp}`}
                datapoint={datapoint}
              />
            ))}
          </div>
        </article>
      );
    }
    case "NOT_CORROBORATED":
    case "UNCORROBORATED": {
      const notCorroborated = corroboration.status === "NOT_CORROBORATED";
      return (
        <article
          className={`corroboration corroboration--${notCorroborated ? "not-corroborated" : "uncorroborated"}`}
          aria-label={
            notCorroborated ? "Not corroborated value" : "Uncorroborated value"
          }
        >
          <header className="corroboration-summary">
            <strong className="corroboration-status">
              {corroboration.status}
            </strong>
          </header>
          <p className="corroboration-reason">{corroboration.reason}</p>
          <div className="venue-values venue-values--single">
            <VenueValue datapoint={corroboration.datapoint} />
          </div>
        </article>
      );
    }
  }

  return assertNeverCorroboration(corroboration);
}
