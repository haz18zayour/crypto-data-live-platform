export type UnavailableReason =
  | "NOT_DEFINABLE"
  | "PAYWALLED"
  | "FETCH_FAILED"
  | "NOT_FETCHED";

export type Provenance = {
  indicatorKey: string;
  asset: string;
  measuredOn: string;
  sourceVendor: string;
  endpoint: string;
  sourceField: string;
  fetchedAt: string | null;
  sourceTimestamp: string | null;
  referencePeriod?: string;
  publishedAt?: string;
};

type AvailableProvenance = Omit<Provenance, "sourceTimestamp"> & {
  sourceTimestamp: string;
};

export type Datapoint =
  | (AvailableProvenance & { status: "OK"; value: number })
  | (AvailableProvenance & { status: "STALE"; value: number })
  | (Provenance & { status: "UNAVAILABLE"; reason: UnavailableReason })
  | (Provenance & {
      status: "ERROR";
      reason: UnavailableReason;
      detail: string;
    });

export function assertNever(value: never): never {
  throw new Error(`Unhandled datapoint: ${JSON.stringify(value)}`);
}
