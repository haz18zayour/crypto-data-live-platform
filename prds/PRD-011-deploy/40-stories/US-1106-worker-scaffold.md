---
id: US-1106
title: Worker scaffold — wrangler.jsonc serving web/dist as an SPA, .node-version pinned, local build verified
priority: 1
touches:
  - wrangler.jsonc
  - web/.node-version
  - package.json
context:
  - AGENTS.md
  - prds/PRD-011-deploy/10-research.md
  - prds/PRD-011-deploy/20-decisions.yaml
---

As the owner, I want the existing web app packaged as a Cloudflare Worker serving static
assets, so that Access can protect it at the Worker level (covering every hostname in one
setting) rather than needing Cloudflare Pages' fragile, dashboard-only two-Access-app
procedure.

## Acceptance criteria

- [test: a wrangler.jsonc (or wrangler.toml) exists at the repo root declaring assets.directory pointing at web/dist and not_found_handling set to "single-page-application"] The Worker config itself
- [cmd: npm --prefix web run build] Produces a real web/dist directory (tsc -b && vite build), proving the build this config depends on actually works today
- [test: a web/.node-version (or repo-root .node-version) file pins a Node version that is NOT one of Cloudflare's older build images (12.18.0 or 18.17.1) — research found Vite 7/TypeScript 5.9 do not build on those] Pins a working version explicitly rather than relying on Cloudflare's disputed default
- [cmd: npx wrangler deploy --dry-run] Cloudflare's own tooling validates the wrangler config without requiring a real API token or account access yet
- [test: web/src/registry.ts's import of ../../ingest/registry.yaml (outside web/) still resolves correctly given the chosen build/deploy context] Confirms research's finding that a build context checking out only web/ would break this import does not apply to the chosen approach

## Notes for the implementer

- This story is code-only and needs no Cloudflare account access — `wrangler deploy --dry-run`
  validates configuration locally. Do not attempt a real `wrangler deploy` in this story; that
  is US-1103, which depends on the owner's own account/dashboard setup.
- Follow research's Option C exactly (Workers static assets), not Cloudflare Pages — see
  `20-decisions.yaml` decision 2 for why Pages was rejected.
- If `wrangler` is not already a dependency, add it to `web/package.json` (or the repo root,
  whichever matches where the deploy workflow in US-1107 will run it from) — check which makes
  more sense given the existing `web/` npm scripts before choosing.
