# US-808 adversarial case

This is the PRD-008 acceptance-protocol demonstration item.

Attacks:

- Staleness gradient: render the board with same-day macro rows next to weekly `DTWEXBGS`, monthly CPI, and monthly M2; read reference period and published date separately on the cell face.
- Dollar-index label grep: test `test_us_808_rendered_board_and_source_never_label_the_fed_broad_index_with_proprietary_ice_name` scans `ingest/`, `web/src/`, and `tests/` for the prohibited ICE label.
- Category-collapse check: test `test_us_808_macro_flow_not_definable_reasons_do_not_collapse_into_existing_board_reasons` proves BNB ETF-flow absence and BTC stablecoin-supply absence are distinct from each other and from older board absences.
- Fear & Greed disclosure: web test `the Fear and Greed cell face shows alternative.me composite and paused-survey disclosure` renders the closed cell face and checks `alternative.me`, `six-weight composite`, and `surveys 15% currently paused`.
