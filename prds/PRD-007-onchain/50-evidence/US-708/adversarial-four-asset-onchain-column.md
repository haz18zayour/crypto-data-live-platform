# US-708 adversarial on-chain readout

Acceptance protocol item: the adversarial case for PRD-007's guarantee.

| Asset | MVRV | Active addresses | Exchange flow | Staking |
|---|---|---|---|---|
| BTC | OK, Coin Metrics `CapMVRVCur` | OK, Coin Metrics `AdrActCnt` | OK, Coin Metrics `FlowInExNtv - FlowOutExNtv` | UNAVAILABLE / NOT_DEFINABLE: proof-of-work has no staking concept |
| ETH | OK, Coin Metrics `CapMVRVCur` | OK, Coin Metrics `AdrActCnt` | OK, Coin Metrics `FlowInExNtv - FlowOutExNtv` | UNAVAILABLE / NOT_DEFINABLE: out of scope for this PRD's SOL staking cell, not a claim ETH staking is undefined |
| BNB | OK, Coin Metrics `CapMVRVCur` | OK, Coin Metrics `AdrActCnt` | UNAVAILABLE / NOT_DEFINABLE: Coin Metrics has no BNB exchange-flow metric on the free tier, confirmed live as `bad_parameter` on 2026-09-15 | UNAVAILABLE / NOT_DEFINABLE: out of scope for this PRD's SOL staking cell, not a claim BNB staking is undefined |
| SOL | UNAVAILABLE / NOT_DEFINABLE: no researched vendor sells genuine SOL realized-cap or MVRV, and Solana has no UTXO realized-cap anchor | OK, Helius/Solana RPC one-hour non-vote activity build | UNAVAILABLE / NOT_DEFINABLE: self-curated Solana exchange labels would create a confidently wrong number | OK, Validators.app staking data |

The forced paid-tier cell is covered by
`tests/test_coinmetrics_fetcher.py::test_forced_caprealusd_forbidden_response_stays_paywalled_without_mvrv_fallback`:
the request remains `metrics=CapRealUSD`, returns `UNAVAILABLE/PAYWALLED`, and never requests
or substitutes `CapMVRVCur`.

The category-collapse guard is covered by
`tests/test_registry_not_definable.py::test_us_708_registry_not_definable_reasons_are_unique`:
every registered `not_definable` reason string is unique across registry cells.
