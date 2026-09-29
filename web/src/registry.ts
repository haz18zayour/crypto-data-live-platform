import { parse } from "yaml";

import registryYaml from "../../ingest/registry.yaml?raw";
import type { BoardRegistryEntry } from "./board";
import type { IndicatorKey } from "./registry.generated";
export { INDICATOR_KEYS } from "./registry.generated";
export type { IndicatorKey } from "./registry.generated";

export type IndicatorDefinition = {
  key: IndicatorKey;
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

export const indicatorDefinitionWiring = {
  btc_daily_close: { source: "registry.yaml" },
  btc_rsi: { source: "registry.yaml" },
  btc_funding_rate: { source: "registry.yaml" },
  btc_mvrv: { source: "registry.yaml" },
  btc_active_addresses: { source: "registry.yaml" },
  btc_exchange_flow: { source: "registry.yaml" },
  btc_open_interest: { source: "registry.yaml" },
  btc_long_short_ratio: { source: "registry.yaml" },
  btc_taker_ratio: { source: "registry.yaml" },
  btc_ema_20: { source: "registry.yaml" },
  btc_ema_50: { source: "registry.yaml" },
  btc_ema_200: { source: "registry.yaml" },
  btc_atr: { source: "registry.yaml" },
  btc_bollinger_upper: { source: "registry.yaml" },
  btc_bollinger_middle: { source: "registry.yaml" },
  btc_bollinger_lower: { source: "registry.yaml" },
  btc_obv: { source: "registry.yaml" },
  btc_macd: { source: "registry.yaml" },
  btc_stochrsi: { source: "registry.yaml" },
  eth_rsi: { source: "registry.yaml" },
  eth_funding_rate: { source: "registry.yaml" },
  eth_mvrv: { source: "registry.yaml" },
  eth_active_addresses: { source: "registry.yaml" },
  eth_exchange_flow: { source: "registry.yaml" },
  eth_open_interest: { source: "registry.yaml" },
  eth_long_short_ratio: { source: "registry.yaml" },
  eth_taker_ratio: { source: "registry.yaml" },
  eth_ema_20: { source: "registry.yaml" },
  eth_ema_50: { source: "registry.yaml" },
  eth_ema_200: { source: "registry.yaml" },
  eth_atr: { source: "registry.yaml" },
  eth_bollinger_upper: { source: "registry.yaml" },
  eth_bollinger_middle: { source: "registry.yaml" },
  eth_bollinger_lower: { source: "registry.yaml" },
  eth_obv: { source: "registry.yaml" },
  eth_macd: { source: "registry.yaml" },
  eth_stochrsi: { source: "registry.yaml" },
  sol_rsi: { source: "registry.yaml" },
  sol_funding_rate: { source: "registry.yaml" },
  sol_active_addresses: { source: "registry.yaml" },
  sol_staking: { source: "registry.yaml" },
  sol_open_interest: { source: "registry.yaml" },
  sol_long_short_ratio: { source: "registry.yaml" },
  sol_taker_ratio: { source: "registry.yaml" },
  sol_ema_20: { source: "registry.yaml" },
  sol_ema_50: { source: "registry.yaml" },
  sol_ema_200: { source: "registry.yaml" },
  sol_atr: { source: "registry.yaml" },
  sol_bollinger_upper: { source: "registry.yaml" },
  sol_bollinger_middle: { source: "registry.yaml" },
  sol_bollinger_lower: { source: "registry.yaml" },
  sol_obv: { source: "registry.yaml" },
  sol_macd: { source: "registry.yaml" },
  sol_stochrsi: { source: "registry.yaml" },
  bnb_rsi: { source: "registry.yaml" },
  bnb_funding_rate: { source: "registry.yaml" },
  bnb_mvrv: { source: "registry.yaml" },
  bnb_active_addresses: { source: "registry.yaml" },
  bnb_open_interest: { source: "registry.yaml" },
  bnb_long_short_ratio: { source: "registry.yaml" },
  bnb_taker_ratio: { source: "registry.yaml" },
  bnb_ema_20: { source: "registry.yaml" },
  bnb_ema_50: { source: "registry.yaml" },
  bnb_ema_200: { source: "registry.yaml" },
  bnb_atr: { source: "registry.yaml" },
  bnb_bollinger_upper: { source: "registry.yaml" },
  bnb_bollinger_middle: { source: "registry.yaml" },
  bnb_bollinger_lower: { source: "registry.yaml" },
  bnb_obv: { source: "registry.yaml" },
  bnb_macd: { source: "registry.yaml" },
  bnb_stochrsi: { source: "registry.yaml" },
  macro_vixcls: { source: "registry.yaml" },
  macro_dff: { source: "registry.yaml" },
  macro_t10y2y: { source: "registry.yaml" },
  macro_dfii10: { source: "registry.yaml" },
  macro_dtwexbgs: { source: "registry.yaml" },
  macro_cpiaucsl: { source: "registry.yaml" },
  macro_m2sl: { source: "registry.yaml" },
  spot_etf_net_flow: { source: "registry.yaml" },
  stablecoin_supply: { source: "registry.yaml" },
  fear_greed_index: { source: "registry.yaml" },
} satisfies { [K in IndicatorKey]: { source: "registry.yaml" } };

export function getIndicatorDefinition(key: IndicatorKey): IndicatorDefinition {
  indicatorDefinitionWiring[key];
  const definition = definitions.find((candidate) => candidate.key === key);
  if (!definition) {
    throw new Error(`Indicator ${key} is not present in the registry`);
  }
  return definition;
}

export function isIndicatorKey(key: string): key is IndicatorKey {
  return key in indicatorDefinitionWiring;
}
