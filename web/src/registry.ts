import { parse } from "yaml";

import registryYaml from "../../ingest/registry.yaml?raw";
import type { BoardRegistryEntry } from "./board";

export type IndicatorDefinition = {
  key: string;
  vendor: string;
  endpoint: string;
  source_field: string;
  freshness_warn_seconds: number;
  freshness_stale_seconds: number;
  corroboration?: {
    venue: string;
    pair: string;
    tolerance_bps: number;
  };
  uncorroborated?: {
    note: string;
  };
};

export const definitions = parse(registryYaml) as (IndicatorDefinition &
  BoardRegistryEntry)[];

export function getIndicatorDefinition(key: string): IndicatorDefinition {
  const definition = definitions.find((candidate) => candidate.key === key);
  if (!definition) {
    throw new Error(`Indicator ${key} is not present in the registry`);
  }
  return definition;
}
