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

export const indicatorStaleAfterSeconds = {
  btc_daily_close: 172800,
  btc_rsi: 172800,
  btc_funding_rate: 57600,
  btc_mvrv: 172800,
  btc_active_addresses: 172800,
  btc_exchange_flow: 172800,
  btc_open_interest: 600,
  btc_long_short_ratio: 600,
  btc_taker_ratio: 600,
  btc_ema_20: 172800,
  btc_ema_50: 172800,
  btc_ema_200: 172800,
  btc_atr: 172800,
  btc_bollinger_upper: 172800,
  btc_bollinger_middle: 172800,
  btc_bollinger_lower: 172800,
  btc_obv: 172800,
  btc_macd: 172800,
  btc_stochrsi: 172800,
  eth_rsi: 172800,
  eth_funding_rate: 57600,
  eth_mvrv: 172800,
  eth_active_addresses: 172800,
  eth_exchange_flow: 172800,
  eth_open_interest: 600,
  eth_long_short_ratio: 600,
  eth_taker_ratio: 600,
  eth_ema_20: 172800,
  eth_ema_50: 172800,
  eth_ema_200: 172800,
  eth_atr: 172800,
  eth_bollinger_upper: 172800,
  eth_bollinger_middle: 172800,
  eth_bollinger_lower: 172800,
  eth_obv: 172800,
  eth_macd: 172800,
  eth_stochrsi: 172800,
  sol_rsi: 172800,
  sol_funding_rate: 57600,
  sol_active_addresses: 777600,
  sol_staking: 172800,
  sol_open_interest: 600,
  sol_long_short_ratio: 600,
  sol_taker_ratio: 600,
  sol_ema_20: 172800,
  sol_ema_50: 172800,
  sol_ema_200: 172800,
  sol_atr: 172800,
  sol_bollinger_upper: 172800,
  sol_bollinger_middle: 172800,
  sol_bollinger_lower: 172800,
  sol_obv: 172800,
  sol_macd: 172800,
  sol_stochrsi: 172800,
  bnb_rsi: 172800,
  bnb_funding_rate: 57600,
  bnb_mvrv: 172800,
  bnb_active_addresses: 172800,
  bnb_open_interest: 600,
  bnb_long_short_ratio: 600,
  bnb_taker_ratio: 600,
  bnb_ema_20: 172800,
  bnb_ema_50: 172800,
  bnb_ema_200: 172800,
  bnb_atr: 172800,
  bnb_bollinger_upper: 172800,
  bnb_bollinger_middle: 172800,
  bnb_bollinger_lower: 172800,
  bnb_obv: 172800,
  bnb_macd: 172800,
  bnb_stochrsi: 172800,
  macro_vixcls: 172800,
  macro_dff: 172800,
  macro_t10y2y: 172800,
  macro_dfii10: 172800,
  macro_dtwexbgs: 1209600,
  macro_cpiaucsl: 5184000,
  macro_m2sl: 5184000,
  spot_etf_net_flow: 172800,
  stablecoin_supply: 172800,
  fear_greed_index: 172800,
} satisfies { [K in IndicatorKey]: number };

export function getIndicatorDefinition(key: IndicatorKey): IndicatorDefinition {
  const definition = definitions.find((candidate) => candidate.key === key);
  if (!definition) {
    throw new Error(`Indicator ${key} is not present in the registry`);
  }
  return definition;
}

export function isIndicatorKey(key: string): key is IndicatorKey {
  return key in indicatorStaleAfterSeconds;
}
