# AGENTS.md

Entry point for agentic coding tools (Claude Code, GitHub Copilot) working in
this repo. Read this first.

> Claude Code also reads this as `CLAUDE.md`; keep one canonical copy here.

## What this is

**The Open State: Alberta Assisted Living** — a Civic Access Protocol
implementation that lets a citizen reach the Government of Alberta's public
**Assisted Living Navigator** through their own AI assistant, in plain language,
to find continuing care, supportive living, and seniors' housing. Accessibility
is the purpose, not a feature.

It is a sibling implementation to the camping reference in the `the-open-state`
repo, and follows the same architecture (provider abstraction, FastMCP, uv,
stdio/HTTP).

## Read these, in order

1. **The Open State `CONSTITUTION.md`** — the binding commitments. Never violate
   these. The ones that bite here: read-only (never apply/reserve/pay),
   accessibility and plain language are mandatory, be honest about vacancy and
   limits, identify honestly.
2. **`COMPLIANCE.md`** — how each article is satisfied here.
3. **`docs/alberta-assisted-living-api-findings.md`** — the verified API
   contract. Reality wins over assumptions; this records what the API actually
   does (including its quirks).
4. **`README.md`** — what it does, how to run and connect it.

## Architecture (mirrors the reference implementation)

```
AI assistant
   | (MCP)
MCP tools (server.py)          # plain-language, platform-agnostic
   |
FacilityProvider (base.py)     # abstract interface + normalized shapes
   |
NavigatorProvider              # maps the Navigator GraphQL API -> shapes
   |
NavigatorClient (client.py)    # thin GraphQL HTTP client (read-only)
```

`geocoding.py` resolves place names to coordinates for "near me" search.
`filters.py` maps plain words ("memory care", "private room") to API filters.

## How to work

- **Read-only, always.** Do not add code that applies for, reserves, holds, or
  pays for a space, or that calls the API's operator/mutation endpoints.
- **Accessibility first.** Keep accessibility a first-class filter and state it
  plainly and first. Output must read cleanly with a screen reader — no tables,
  no emoji.
- **Honesty.** Vacancy is a snapshot; say so. If the API and the spec disagree,
  reality wins — flag it in the findings doc (see the `hasPotentialVacancy`
  note). Fail visibly; never guess a location or a fact.
- **Identify honestly.** The API is public and accepts an honest `User-Agent`;
  do not impersonate a browser or spoof `Origin`.
- Prefer small, typed, tested functions. Keep the provider interface clean.

## Tests

```bash
uv sync
uv run pytest
```

Tests run fully offline against responses recorded from the live API. No live
network calls in tests.
