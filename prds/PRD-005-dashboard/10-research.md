# PRD-005 · Research

Written 2026-09-13, against the board as it actually exists today: **50 rows in
`public.datapoints`, 45 distinct `(indicator_key, asset)` cells, 4 assets, one historical
`ERROR` row left over from PRD-001's adversarial demo.** Every number below was measured, not
recalled.

---

## 0 · The measurements this PRD has to be designed around

```
select count(*), count(distinct indicator_key), count(distinct asset) from datapoints;
 -> 50 | 45 | 4
select count(*) from (select distinct on (indicator_key, asset) id
                      from datapoints order by indicator_key, asset, fetched_at desc) t;
 -> 45
status histogram -> OK 49, ERROR 1
the ERROR row    -> btc_daily_close / BTC / FETCH_FAILED, fetched 2026-09-09 20:49 UTC
```

Three consequences, and each one shapes a story.

**(a) Registry keys are already asset-scoped.** There is no `rsi` entry with
`definable_for: [BTC, ETH, SOL, BNB]`. There are `btc_rsi`, `eth_rsi`, `sol_rsi`, `bnb_rsi`,
each with `definable_for` naming one asset. 45 = 11 families x 4 assets + `btc_daily_close`.
**The matrix axes do not exist in the data yet** — they have to be derived, and section 3 is
about how, because the obvious derivation is a string split and string splits are how this
project gets bitten.

**(b) `distinct on` collapses 50 rows to exactly 45.** The board is one row per cell and the
table grows by ~45 rows per day. Today the difference is 5 rows and irrelevant; in a year it is
~16,000 rows the browser would download to display 45 numbers. Section 2 settles this now,
while it is cheap.

**(c) Staleness will essentially never fire on its own.** `freshness_stale_seconds` is 172800
(48h) against a 24h collection cadence, so `STALE` only appears when collection has *already
been broken for two days*. The adversarial case cannot wait for a natural STALE; it has to
manufacture one. Noted here so the story that demands a mixed board does not quietly get
written as "wait and see".

---

## 0b · Found while writing this: the web suite has never been gated

`.uf/config.json` runs its `typecheck` and `test` gates behind `f.existsSync('package.json')`,
and `.github/workflows/uf-verify.yml` guards its Node steps behind `test -f package.json`. Both
check the **repository root**. `package.json` lives in `web/`.

```
$ test -f package.json && echo YES || echo NO
NO
$ cd web && npm test
Test Files  4 passed (4)
     Tests  13 passed (13)
```

So thirteen passing web tests have never run in a single gate or CI job since US-009 created
them. Nothing was broken by it — they pass — but **every guard reported success by skipping**,
which is the exact failure this product exists to oppose, occurring inside our own harness.

Every remaining story in this PRD is a web story. Fixing this is therefore not housekeeping, it
is the precondition for any criterion in PRD-005 meaning anything, and it goes first.

---

## 1 · Existing implementations

**Data-observability tooling converged on the same pillars we arrived at independently.** Monte
Carlo's five pillars are freshness, volume, schema, quality and lineage; freshness is defined
as "how up-to-date your tables are, and the cadence at which they update", which is the same
three-number freshness model already in `11_Data_Model.md`. Their coverage guidance —
prioritise coverage where downtime impacts trust and adoption — is the commercial restatement
of this project's founding complaint. **Useful confirmation, no new technique.** Their UI goes
somewhere we deliberately do not: anomaly charts, trend graphs, lineage maps. That is PRD-009
and PRD-010 at the earliest, and mostly never.

**What none of them do is the thing this page is for.** Every observability product surfaces
*failures*. None distinguishes "this metric cannot exist for this asset" from "this metric
should exist and is missing", because in a warehouse every column is definable by
construction. Our `NOT_DEFINABLE` has no analogue in the prior art, so section 4 is ours to get
right with no reference implementation to lean on.

**Grid semantics — the concrete trap.** Component libraries routinely render tables as `div`
elements with CSS Grid, and the accessibility literature is blunt about the cost: overriding
the default CSS display of table elements removes their default semantics. A dense 12 x 4
matrix is exactly the layout that tempts `display: grid` on a table element. Doing so silently
destroys row and column association for a screen reader, and nothing in our test suite would
notice. `role="grid"` is **not** the escape hatch either — claiming it obliges the full
roving-tabindex keyboard contract, which is strictly more work than keeping the native table
semantics and laying out with `table-layout: fixed`.

**Tabular figures.** `font-variant-numeric: tabular-nums` gives every digit equal width so
columns of numbers align and do not wiggle on refetch. Two caveats worth carrying into the
story: it is a no-op if the chosen face lacks the feature, and many faces make punctuation
tabular too, which over-spaces decimals.

---

## 2 · Approach options — getting 45 cells into the browser

### Option A — one `board_read` view using `distinct on`

```sql
create view public.board_read with (security_invoker = true) as
select distinct on (indicator_key, asset) id, indicator_key, asset, ...
from public.datapoints
order by indicator_key, asset, fetched_at desc;
```

- **How it works:** one PostgREST request returns exactly 45 rows, one per cell, latest wins.
  The ordering is mandatory and must lead with the grouping columns; Postgres returns the first
  row per group after that sort.
- **Trade-offs:** it is a migration, so it is **blast radius** (`**/migrations/**`) and G4 must
  be run manually — the framework's gate does not fire. Against that: response size is bounded
  forever, the existing `datapoints_indicator_asset_fetched_at_idx` on
  `(indicator_key, asset, fetched_at desc)` is exactly the index this sort wants, and the
  `security_invoker` plus revoke-then-grant-select-to-anon pattern is already established twice
  in this repo.
- **Cost:** $0.

### Option B — fetch every row, reduce latest-per-cell in TypeScript

- **How it works:** `select=*&order=fetched_at.desc`, then keep the first row seen per
  `(indicator_key, asset)`.
- **Trade-offs:** no migration, no gate, ships today. But it downloads the entire history to
  render one screen and degrades every single day, invisibly, until someone notices the page is
  slow. **This project exists because things degrade invisibly.** Shipping it would be an
  unusually direct self-contradiction.
- **Cost:** $0 now, a rewrite later.

### Option C — 45 single-row requests, one per registry key

- Correct, trivially cacheable per cell, and 45 round trips on every load. Rejected on latency,
  not principle.

**Recommended: A.** It is the only option whose cost does not grow with time, the index already
exists, and the migration pattern is proven. Pay the G4 review once.

---

## 3 · Deriving the matrix axes

The grid needs a family and an asset per cell. The registry gives a key and `definable_for`.
Three ways to bridge:

1. **Split the key on the asset prefix** — `bnb_bollinger_upper` gives `BNB` plus
   `bollinger_upper`. Works today, breaks the first time an indicator key contains an asset
   name for another reason, and fails silently into a wrong row rather than loudly.
2. **Take the asset from `definable_for`, then strip that prefix for the family.** Strictly
   better: the asset comes from a declared field, and the prefix strip can be *asserted* — if
   the key does not start with the lowercased asset, that is an error, not a fallback. Cheap,
   and it turns a silent misfile into a thrown exception.
3. **Add an explicit family field to every registry entry.** Most honest, and it touches
   `**/registry*` — blast radius, another G4, 45 edits.

**Recommended: 2**, with the assertion mandatory and tested. It buys most of option 3's safety
at none of its cost, and the assertion is what makes it safe rather than merely convenient.

---

## 4 · The blind spot that matters more than anything else here

**A cell missing from the registry must not render as `NOT_DEFINABLE`.**

The grid is the cross-product: 12 families x 4 assets = 48 cells, of which 45 have registry
entries. The three without are `daily_close` for ETH, SOL and BNB. The tempting rule is
"no registry entry, therefore not definable, therefore render settled, grey, unalarming".

That rule re-creates **US-412 exactly**. The EMA stack was in the spec, was never registered,
and coverage was blind to it because coverage is generated *from* the registry. Under the
tempting rule, a forgotten indicator renders as a calm grey "n/a for this asset" — the most
reassuring possible presentation of a bug. The page would be actively lying, in the one
direction it was built to prevent.

**The rule must invert the default.** Absence is `NOT_FETCHED` and reads as a problem, *unless*
the registry explicitly declares non-definability with a reason. `btc_daily_close` carries
`definable_for` naming BTC on a per-key basis, which says nothing about the other three assets,
so the declaration needs somewhere to live. Cheapest honest shape: a single `not_definable`
block on the family's existing entry naming the assets and the reason — one registry edit, not
45.

Until that declaration exists, ETH, SOL and BNB `daily_close` render as **not fetched**, and
that is the correct, useful, slightly annoying truth.

## 5 · The second blind spot — colour is doing all the work

`20_Design_System.md` says colour carries meaning and nothing else, and that status is the only
thing allowed to be chromatic. That is good taste and, taken literally, a **WCAG 1.4.1 (Level
A) failure**: colour may not be the *only* visual means of conveying information. Roughly 8% of
men have a colour vision deficiency, and a status grid whose only cue is a coloured dot is
named in the accessibility literature as the single most common dashboard failure.

The fix costs nothing and improves the design: **every state carries a glyph and a word as well
as a hue.** The design system's intent — that chroma means something is notable — survives
intact; it just stops being load-bearing alone. This is a correction to `20_Design_System.md`,
and the doc should be updated rather than the contradiction left standing.

## 6 · The third blind spot — 45 OK cells is the boring case

Today the board is 44 OK and one historical error, and the natural instinct is to design
against that. A page that looks calm and correct when everything works is worth very little;
this one earns its place on the days it does not. **The mixed board is the design target and
the all-green board is the degenerate case**, which is why the adversarial demo comes *before*
the polish pass rather than after it.

## 7 · Services and keys

| Service | Why this PRD needs it | Env var | Already ready? |
|---|---|---|---|
| Supabase (anon, browser) | reads `board_read` through PostgREST under RLS | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` | **yes**, already wired in `web/src/data.ts` |
| Supabase (service role) | migration only, server side | `DATABASE_URL` | **yes** |

Nothing new. **Standing constraint, unchanged:** `SUPABASE_SERVICE_ROLE_KEY` bypasses RLS and
must never reach the client bundle or any `VITE_`-prefixed variable. US-009's bundle scan is
the machine check and it stays green.

## 8 · Open questions

| # | Question | My hypothesis | Impact if wrong |
|---|---|---|---|
| 1 | View or client-side reduction? | **View.** Bounded response forever; the index already exists; one G4 review. | A page that decays invisibly — the exact failure this product opposes |
| 2 | How is a cell with no registry entry rendered? | **`NOT_FETCHED`, alarming**, until the registry declares otherwise with a reason. | A forgotten indicator renders as reassuring grey. This is US-412 with a nicer font |
| 3 | Does colour remain the only status channel? | **No.** Glyph plus word plus hue on every state. WCAG 1.4.1 Level A. | Level A accessibility failure, and an unreadable page on a bad monitor |
| 4 | Values in the grid, or status only? | **Both** — value when OK or STALE, reason otherwise. Coverage is the header line; the grid is where you look next. | Either a grid you cannot read numbers from, or one where absence hides again |
| 5 | Is provenance visible without a click? | **Yes for vendor and source timestamp**, per non-negotiable 3 in `20_Design_System.md`; full detail on hover or expand. | Breaks a rule already ratified in the data model |
| 6 | How is the mixed board forced? | A **fixture-backed dev route** rendering a hand-built mixed board, plus one real forced failure. Not a 48-hour wait. | The adversarial case quietly becomes "trust me, it would look fine" |

## 9 · Where the criteria have to be sharper than usual

Nine of the eleven defects this session traced to acceptance criteria that said less than they
meant, against two genuine implementation defects. Design stories are the worst case for this,
because "looks good" is unfalsifiable. Three rules for this PRD's criteria:

1. **Name where the output lands.** A file path, a route, a screenshot committed under
   `50-evidence/`.
2. **Assert against parsed objects, not file text.** "The registry records X" was twice
   satisfied by a comment plus a grep. Criteria here assert on rendered DOM through Testing
   Library, or on a parsed registry object, never on source text.
3. **Bound by what the product needs**, not by the smallest bound that excludes today's bug.
   "At least 45 cells" passes on a grid that renders 45 and drops 3. The bound is **48 cells,
   zero blank**.

## 10 · Sources

- Supabase, [Select first row for each group in Postgres](https://supabase.com/docs/guides/database/postgres/first-row-in-group)
- Monte Carlo, [What is data observability, five key pillars](https://montecarlo.ai/blog-what-is-data-observability) and [Data observability architecture and optimizing your coverage](https://www.montecarlodata.com/data-observability-architecture-and-optimizing-your-coverage/)
- [WCAG 2.2 SC 1.4.1 Use of Color](https://www.thewcag.com/criteria/1.4.1); accessibility.chat, [Status indicators need more than pretty colors](https://www.accessibility.chat/articles/when-color-coding-fails-why-status-indicators-need-more-than-pretty-colors); AccessScan, [Accessible dashboards and data visualization](https://accessscan.app/guides/accessible-dashboards-and-data-viz)
- Sarah Higley, [Grids part 2: semantics](https://sarahmhigley.com/writing/grids-part2/); Accessibility.build, [Accessible data grid guide](https://accessibility.build/guides/accessible-data-grid)
- MDN, [font-variant-numeric](https://developer.mozilla.org/en-US/docs/Web/CSS/font-variant-numeric); Sebastian De Deyne, [Tabular numbers](https://sebastiandedeyne.com/tabular-numbers/)
