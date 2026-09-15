# G4 blast radius review — PRD-005

Run manually on 2026-09-13. The framework gate does not fire; confirmed on PRD-001, where a
migration touching `**/migrations/**` produced no gate at all.

Three stories in this PRD touch declared blast radius.

## US-501 — `.github/workflows/**` and `.uf/config.json`

**Change.** The Node guards in the CI workflow and in the two `uf` verification gates currently
test for `package.json` at the repository root. It lives in `web/`. They are re-pointed at
`web/package.json` and the commands become `npm --prefix web ...`.

**What could go wrong.** A broken workflow file fails every push, loudly. There is no silent
mode of failure here.

**Why it is safe.** The guards presently protect nothing — they have never once caused a Node
step to run. The change can only increase what is checked. The Python steps, the Postgres
service and the deliberate `continue-on-error` on the live-venue integration step are untouched.
Reversible by reverting one commit.

**Verdict: proceed.**

## US-502 — `**/migrations/**`

**Change.** One new migration creating `public.board_read`, a read-only view over
`public.datapoints` using `distinct on (indicator_key, asset)`.

**What could go wrong.** A view can become a way around RLS if it is created without
`security_invoker`, exposing rows the anon role should not see.

**Why it is safe.** `security_invoker = true` plus `revoke all` then `grant select` to `anon`
and `authenticated` is the pattern already used twice in this repo, for `datapoints_read` and
`corroborations_read`, and US-502 carries an explicit criterion that anon can select and cannot
insert, update or delete. No table, constraint or policy is altered. The migration is additive
and reversible with `drop view`.

**Verdict: proceed.**

## US-504 — `**/registry*`

**Change.** A `not_definable` block added to one registry entry, `btc_daily_close`, plus the
pydantic model change that parses and validates it.

**What could go wrong.** The registry is the single source of truth for coverage, the pipeline
and the page. A schema change that makes an existing entry unparseable takes the whole
ingestion down.

**Why it is safe.** The field is optional and additive; the other 44 entries are untouched. The
registry model rejects an empty reason and rejects an asset listed in both `definable_for` and
`not_definable`, so a malformed declaration fails at load rather than at render. Registry
coverage across all 45 entries stays an acceptance criterion.

**Verdict: proceed.**

## Not touched

`**/fetchers/**`, `**/status*`, `**/freshness*`. No venue, no status union, no freshness budget
changes in this PRD.
