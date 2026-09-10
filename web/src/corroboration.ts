import type { Datapoint } from "./datapoint";

export type VenueDatapoint = Extract<
  Datapoint,
  { status: "OK" | "STALE" }
>;

type ComparedVenues = {
  datapoints: [VenueDatapoint, VenueDatapoint];
  divergenceBps: number;
  toleranceBpsAtWrite: number;
};

export type Corroboration =
  | (ComparedVenues & { status: "CORROBORATED" })
  | (ComparedVenues & { status: "DIVERGED" })
  | {
      status: "NOT_CORROBORATED";
      datapoint: VenueDatapoint;
      reason: string;
    }
  | {
      status: "UNCORROBORATED";
      datapoint: VenueDatapoint;
      reason: string;
    };

export function assertNeverCorroboration(value: never): never {
  throw new Error(`Unhandled corroboration: ${JSON.stringify(value)}`);
}
