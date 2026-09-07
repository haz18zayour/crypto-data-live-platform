# Skills — which one, at which phase

Every skill below is installed on this machine. **Nothing here is copied into the product** —
they live in `hz-skills-universal`, junctioned into `~/.claude/skills`, `~/.codex/skills` and
`~/.claude/plugins/marketplaces`. This file is the routing table: it says which skill to fire
at which phase, and what that phase must produce.

Invoke a personal skill as `/name`. Invoke a plugin skill as `plugin:name`.

## Which harness can invoke what — read this before routing

Not every skill exists in both harnesses, and firing one that isn't there fails silently.

| | Claude Code | Codex |
|---|---|---|
| `/pre-prd-research` `/prd` `/plan` `/spec` `/build` `/test` `/review` `/ship` `/ralph` `/code-simplify` `/deploy` | ✅ | ✅ (in `~/.codex/skills`) |
| Cloudflare set — `cloudflare` `wrangler` `workers-best-practices` `durable-objects` `agents-sdk` `sandbox-sdk` `turnstile-spin` `web-perf` | ✅ | ✅ |
| `superpowers:*` · `agent-skills:*` · `open-design-local:*` · `mattpocock-skills:*` · `karpathy-skills` | ✅ | ❌ **Claude Code plugins only** |

**Consequence for routing:** the plugin skills are for the *planning* half of the cycle,
which runs in Claude Code anyway. `uf run`'s implementer is Codex by default and can reach
the personal and Cloudflare skills but **not** the plugin ones — so never write a story whose
instructions depend on a `plugin:name` skill. Put what the story needs into its `context:`
block instead, where `uf compile` inlines the actual text and fails the build if it is missing.

> **Rule:** a story or spec may only reference a skill that exists. `uf compile` resolves every
> reference in a story's `context:` block and **fails the build** if it does not resolve. The
> previous pipeline pointed six story files at a `skills/` directory that never existed, for
> nineteen PRDs, and nothing ever said so.

---

## Product phases (once per product)

| Phase | Skill | Produces |
|---|---|---|
| Idea → shape | `superpowers:brainstorming` | the problem, sharpened |
| Extract intent | `agent-skills:interview-me` | what you actually want, one question at a time |
| Rough concept | `agent-skills:idea-refine` | structured exploration before committing |
| Strategy docs | *(no skill — write them)* | `project-documents/01`–`04` |
| Stack + services | read `KNOWLEDGE.md` | `10_Technical_Architecture.md`, `15_Services_and_Credentials.md` |
| Roadmap → PRDs | `agent-skills:planning-and-task-breakdown` (`/plan`) | `05_Product_Roadmap.md` — the PRD list, ordered |
| Design system | `open-design-local:frontend-design`, `open-design-local:color-expert`, `taste-skill` | `20_Design_System.md` |
| API shape | `agent-skills:api-and-interface-design` | `14_API_Design.md` |
| Test strategy | `agent-skills:test-driven-development` | `24_Testing_Strategy.md` |

## PRD phases (once per PRD)

| File | Skill | Notes |
|---|---|---|
| `10-research.md` | **`/pre-prd-research`** | The one that interrogates *you*. Hard-stops at the research file by design — do not let it write the spec. |
| `20-decisions.yaml` | — | Your answers + `assumptions:` rows, each with a `tripwire:` |
| `30-spec.md` | **`/prd`** or `agent-skills:spec-driven-development` (`/spec`) | Written **from** `10-research.md`, not from memory |
| `40-stories/*.md` | **`/plan`**, sized with `/ralph` | One story per file. Every criterion needs `[cmd:]` `[test:]` `[browser:]` `[ci:]` or `[human]` |
| implement | `agent-skills:incremental-implementation` (`/build`), `agent-skills:test-driven-development` (`/test`) | Fired by `uf run`, not by you |
| verify | `superpowers:verification-before-completion`, `agent-skills:code-review-and-quality` (`/review`) | Fired by `uf run`. Different vendor, read-only. |
| blast radius | `agent-skills:security-and-hardening` | Required before merging auth / RLS / payments / migrations |
| merge | `superpowers:finishing-a-development-branch`, `agent-skills:git-workflow-and-versioning` | |
| ship | `agent-skills:shipping-and-launch` (`/ship`), `/deploy`, `/deploy-local-android-app` | |

## When something goes wrong

| Situation | Skill |
|---|---|
| A story failed 3× | `superpowers:systematic-debugging` — four phases, root cause before any fix |
| Build or tests broken | `agent-skills:debugging-and-error-recovery` |
| Code works but reads badly | `agent-skills:code-simplification` (`/code-simplify`) |
| UI broken on mobile | `mobile-responsive-debugging` |
| Needs a browser check | `agent-skills:browser-testing-with-devtools` |
| High-stakes call (auth, money, data loss) | `agent-skills:doubt-driven-development` |
| Slow | `agent-skills:performance-optimization`, `web-perf` |
| Unfamiliar framework | `agent-skills:source-driven-development` — cite the source, don't recall it |

## Stack-specific (Cloudflare / Supabase products)

`cloudflare` · `wrangler` · `workers-best-practices` · `durable-objects` · `agents-sdk` ·
`sandbox-sdk` · `cloudflare-email-service` · `turnstile-spin` · `web-perf`

## Design & content

`open-design-local:*` has 132 skills — treat it as a library you reach into, never a set to
load. The ones that earn their place: `frontend-design`, `design-review`, `color-expert`,
`apple-hig`, `copywriting`, `d3-visualization`, `data-report`, `creative-director`.

---

## The injection cap

Relevant past failures from `~/.uf/packs/failures.ndjson` are injected into every story
prompt — **at most 6, ranked by relevance to that story**. This cap is deliberate. The
previous pipeline's memory mechanism was an unbounded append-only `progress.txt`; it grew
until nobody read it, and in practice it was written for only 2 of 19 PRDs. A capped,
ranked, relevance-filtered injection is the thing that actually survives contact with a
real project.
