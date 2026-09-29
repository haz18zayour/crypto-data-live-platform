import { formatUtcDate } from "./FrozenBadge";
import {
  formatWindow,
  historySufficiency,
  type HistoryPoint,
} from "./history";

const WIDTH = 160;
const HEIGHT = 40;
// Keeps the last-point marker inside the box at the extremes.
const INSET = 4;

function formatValue(value: number): string {
  return value.toLocaleString("en-US", { maximumSignificantDigits: 6 });
}

function Extreme({
  name,
  point,
}: {
  name: "max" | "min";
  point: HistoryPoint;
}) {
  return (
    <span className={`sparkline-${name}`}>
      <span className="sparkline-extreme-word">{name}</span>{" "}
      <span className="sparkline-extreme-value">{formatValue(point.value)}</span>
      <span aria-hidden="true"> · </span>
      <time dateTime={point.sourceTimestamp}>
        {formatUtcDate(point.sourceTimestamp)}
      </time>
    </span>
  );
}

// A scale, never a verdict: one neutral line on a real time axis, every returned point drawn
// with no resampling, the last point marked, and the min and max read out with their own dates.
// No band, no percentile, and no colour that depends on where a point sits in the range.
export function Sparkline({ history }: { history: readonly HistoryPoint[] }) {
  const sufficiency = historySufficiency(history);
  if (!sufficiency.sufficient) {
    const { count, since } = sufficiency;
    return (
      <p className="sparkline-insufficient">
        <span className="sparkline-insufficient-glyph" aria-hidden="true">
          ◌
        </span>{" "}
        Not enough history yet ({count} {count === 1 ? "point" : "points"}
        {since ? (
          <>
            {" "}
            since <time dateTime={since}>{formatUtcDate(since)}</time>
          </>
        ) : null}
        )
      </p>
    );
  }

  const { points } = sufficiency;
  const first = points[0];
  const last = points[points.length - 1];
  const max = points.reduce((best, point) => (point.value > best.value ? point : best));
  const min = points.reduce((best, point) => (point.value < best.value ? point : best));
  const t0 = Date.parse(first.sourceTimestamp);
  const tSpan = Date.parse(last.sourceTimestamp) - t0;
  const vSpan = max.value - min.value;
  const x = (point: HistoryPoint) =>
    +(INSET + ((Date.parse(point.sourceTimestamp) - t0) / tSpan) * (WIDTH - 2 * INSET)).toFixed(2);
  const y = (point: HistoryPoint) =>
    +(INSET + ((max.value - point.value) / vSpan) * (HEIGHT - 2 * INSET)).toFixed(2);
  const span = formatWindow(first.sourceTimestamp, last.sourceTimestamp);

  return (
    <figure className="sparkline">
      <figcaption className="sparkline-top">
        <Extreme name="max" point={max} />
        <span className="sparkline-window">{span}</span>
      </figcaption>
      <svg
        className="sparkline-plot"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`${points.length} points from ${formatUtcDate(first.sourceTimestamp)} to ${formatUtcDate(last.sourceTimestamp)}`}
      >
        <polyline
          className="sparkline-line"
          points={points.map((point) => `${x(point)},${y(point)}`).join(" ")}
        />
        <circle className="sparkline-last" cx={x(last)} cy={y(last)} r={3.5} />
      </svg>
      <Extreme name="min" point={min} />
    </figure>
  );
}
