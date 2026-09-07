---
id: US-002
title: Ingestion package scaffold and fail-loud configuration
priority: 2
touches:
  - pyproject.toml
  - ingest/**
  - tests/**
context:
  - AGENTS.md
  - coding_standards.md
  - project-documents/10_Technical_Architecture.md
---

As the owner, I want a minimal Python package with typed configuration that refuses to start
when a required setting is missing, so that a misconfigured run fails at startup instead of
producing plausible-looking output.

## Acceptance criteria

- [cmd: uv sync] Dependencies resolve and install from `pyproject.toml`
- [cmd: uv run ruff check .] Lint is clean
- [cmd: uv run mypy ingest --strict] Strict type checking passes with no errors
- [test: config raises at import when a required variable is absent] A missing required setting is a startup failure, never a default value
- [test: config never logs a secret value] Secret fields are redacted in the config's repr and in any log line

## Notes for the implementer

- Python 3.12, `uv`, `pydantic-settings` v2, `httpx`, `structlog`. Keep the dependency list to
  what these criteria need — no TA-Lib, no pandas yet; PRD-003 adds those.
- Required settings for this PRD: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
  `HEALTHCHECKS_PING_URL`. Add each to `.env.example` with an empty value.
- `SUPABASE_SERVICE_ROLE_KEY` is a secret and must be redacted. It is used only by ingestion
  and must never appear in anything the browser receives.
- Defaults are forbidden for anything that changes behaviour. A default is how the prior
  system's `0.0` became indistinguishable from a real reading.
- No fetchers, no schema, no business logic in this story — scaffold and config only.
