import type {
  IntegrityFreshnessState,
  IntegrityRead,
  IntegrityRow,
} from "./integrity";

type VendorRollup =
  | {
      sourceVendor: string;
      kind: "measurable";
      state: Exclude<IntegrityFreshnessState, "unmeasurable">;
      worstRow: IntegrityRow;
    }
  | {
      sourceVendor: string;
      kind: "unmeasurable";
      reason: string;
    };

const freshnessRank = {
  fresh: 0,
  warn: 1,
  stale: 2,
  unmeasurable: 3,
} satisfies Record<IntegrityFreshnessState, number>;

function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }
  if (seconds < 60 * 60) {
    return `${(seconds / 60).toFixed(1)}m`;
  }
  if (seconds < 60 * 60 * 24) {
    return `${(seconds / (60 * 60)).toFixed(1)}h`;
  }
  return `${(seconds / (60 * 60 * 24)).toFixed(1)}d`;
}

export function rollUpFreshnessByVendor(
  rows: readonly IntegrityRow[],
): VendorRollup[] {
  const rowsByVendor = new Map<string, IntegrityRow[]>();
  for (const row of rows) {
    const vendorRows = rowsByVendor.get(row.sourceVendor) ?? [];
    vendorRows.push(row);
    rowsByVendor.set(row.sourceVendor, vendorRows);
  }

  return [...rowsByVendor.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([sourceVendor, vendorRows]) => {
      const unmeasurable = vendorRows.find(
        (row) => row.freshnessState === "unmeasurable",
      );
      if (unmeasurable) {
        return {
          sourceVendor,
          kind: "unmeasurable",
          reason:
            unmeasurable.freshnessUnmeasurableReason ??
            "source timestamp age cannot measure vendor data freshness",
        };
      }

      const worstRow = [...vendorRows].sort(
        (left, right) =>
          freshnessRank[right.freshnessState] - freshnessRank[left.freshnessState] ||
          (right.sourceTimestampAgeSeconds ?? -1) -
            (left.sourceTimestampAgeSeconds ?? -1),
      )[0];
      return {
        sourceVendor,
        kind: "measurable",
        state: worstRow.freshnessState as Exclude<
          IntegrityFreshnessState,
          "unmeasurable"
        >,
        worstRow,
      };
    });
}

function FreshnessSummary({ rollup }: { rollup: VendorRollup }) {
  if (rollup.kind === "unmeasurable") {
    return <span>unmeasurable: {rollup.reason}</span>;
  }

  const ageSeconds = rollup.worstRow.sourceTimestampAgeSeconds;
  return (
    <span>
      {rollup.state}:{" "}
      {ageSeconds === null ? "age unavailable" : `${formatDuration(ageSeconds)} old`}{" "}
      against warn {formatDuration(rollup.worstRow.freshnessWarnSeconds)} / stale{" "}
      {formatDuration(rollup.worstRow.freshnessStaleSeconds)}
    </span>
  );
}

export function IntegrityPanel({ read }: { read: IntegrityRead }) {
  const rollups = rollUpFreshnessByVendor(read.rows);

  return (
    <section className="integrity-panel" aria-labelledby="integrity-panel-title">
      <div className="integrity-panel-header">
        <div>
          <p className="eyebrow">Integrity</p>
          <h2 id="integrity-panel-title">Per-source freshness</h2>
        </div>
        <p className="integrity-computed-at">Computed {read.computedAt}</p>
      </div>
      {read.selfCheckState === "stale-self-check" ? (
        <p className="integrity-self-check integrity-self-check--stale" role="alert">
          Integrity check itself may be stale.
        </p>
      ) : (
        <p className="integrity-self-check">Integrity check current.</p>
      )}
      <div
        className="integrity-rollup"
        role="table"
        aria-label="Freshness grouped once per source vendor"
      >
        <div className="integrity-rollup-head" role="row">
          <span>Vendor</span>
          <span>Freshness</span>
        </div>
        {rollups.map((rollup) => (
          <div
            key={rollup.sourceVendor}
            role="row"
            className={`integrity-rollup-row integrity-rollup--${rollup.kind === "measurable" ? rollup.state : "unmeasurable"}`}
          >
            <strong>{rollup.sourceVendor}</strong>
            <span>
              <FreshnessSummary rollup={rollup} />
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
