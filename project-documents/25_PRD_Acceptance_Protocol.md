# 25 · PRD acceptance protocol

Agreed with the owner 2026-09-10: **run autonomously inside a PRD, stop hard between PRDs.**

Work proceeds without check-ins while a PRD is in flight — stories, retries, spec fixes, gate
answers that are mine to give, the merge. The next PRD does not begin until the owner has seen
this PRD proven and said go.

---

## Why the checkpoint cannot just read `uf status`

`uf status` showing all-green is necessary and **not sufficient**, and PRD-001 proved it on this
repo. **US-006 passed 6/6 criteria, verified independently by a different vendor, while storing
a Hong Kong day close as a UTC one** — 78,834.1 instead of 79,111.8, 0.35% wrong, on the value
every technical indicator would have been built from. No gate caught it. A human read a
timestamp.

So the checkpoint is a **demonstration against reality**, not a report. Of the defects found in
PRD-001, four of six came from criteria nobody had written. A protocol that only re-reads the
criteria inherits that blind spot exactly.

## What must be true before the next PRD starts

| # | Requirement | How it is shown |
|---|---|---|
| 1 | Every story passed | `uf status` — the floor, not the proof |
| 2 | Every gate answered, none open | `uf gates` reports nothing outstanding |
| 3 | **It works against real services** | Run the thing. Live vendors, live database, real values printed |
| 4 | **A deliberate failure behaves correctly** | Break something on purpose and show the honest outcome |
| 5 | Nothing regressed | Full suite, ruff, mypy `--strict`, and PRD-001's spine still ingesting |
| 6 | Docs match reality | `uf log`, credential statuses, architecture updated where the PRD changed a decision |
| 7 | Merged and CI green | `main` builds; the branch is not left dangling |

**Item 4 is the one that carries weight.** Anyone can demonstrate a system working. This
product's entire claim is about how it behaves when something is wrong, so the acceptance
demonstration must include an adversarial case chosen to attack *this PRD's specific guarantee*.

## The adversarial case, per PRD

| PRD | The guarantee | The attack that proves it |
|---|---|---|
| 001 spine | absence never becomes a number | ✅ dead endpoint → em dash + `Fetch failed`, no stale fallback, ERROR row retained |
| 002 harness | a value cannot drift with history | pass a longer bar slice and show it is **rejected**, not silently different |
| 003 corroboration | disagreement is surfaced, not resolved | feed two venues that disagree and show the divergence reaches the page |
| 004 indicators | indicators are computed correctly | check one against an externally-computed value, not against ourselves |
| 005 dashboard | completeness is legible | force a mixed board — OK, STALE, NOT_DEFINABLE, FETCH_FAILED — and read it at a glance |
| later | — | chosen when the PRD is specced, and written into its brief |

## What I present at the checkpoint

Short. Evidence, not narration.

1. Stories passed, gates closed, spend.
2. **Real output** — actual values, from live services, with provenance.
3. **The adversarial case and what happened**, including a screenshot where it is visual.
4. Anything that is *not* done, or that I got wrong along the way, stated plainly.
5. What the next PRD would do, so the go/no-go is informed.

Then I stop and wait.

## What does not wait for the checkpoint

Gate G1 scope questions, G2 budget, G3 irreversible acts, G4 blast radius and G6 human
judgement still interrupt *whenever* they arise, mid-PRD. This protocol adds a stop; it removes
none.

**And G4 must be run manually** — the framework's gate does not fire. Confirmed on PRD-001,
where a migration touching `**/migrations/**` produced no gate at all.
