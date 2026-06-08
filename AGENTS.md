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

Built in **Node.js (ESM)** with the official `@modelcontextprotocol/sdk`, to
match the Camp MCP. Speaks MCP over **stdio**.

## Read these, in order

1. **The Open State `CONSTITUTION.md`** — the binding commitments. Never violate
   these. The ones that bite here: read-only (never apply/reserve/pay),
   accessibility and plain language are mandatory, be honest about vacancy and
   limits, identify honestly.
2. **`COMPLIANCE.md`** — how each article is satisfied here.
3. **`docs/alberta-assisted-living-api-findings.md`** — the verified API
   contract. Reality wins over assumptions; this records what the API actually
   does (including its quirks).
4. **`README.md`** — what it does, how to run, build, and connect it.

## Architecture

```
AI assistant
   | (MCP, stdio)
src/index.mjs                       # entry: wires deps, connects StdioServerTransport
   |
src/server.mjs  (createServer)      # registers the 4 tools (McpServer.registerTool)
   |
src/providers/navigator-provider.mjs  # maps the Navigator GraphQL -> normalized objects
   |
src/providers/navigator-client.mjs    # thin GraphQL client over built-in fetch (read-only)
```

`src/format.mjs` does plain-language, screen-reader-friendly output.
`src/geocoding.mjs` resolves place names to coordinates (Nominatim, keyless).
`src/filters.mjs` maps plain words ("memory care", "private room") to API filters.
`src/config.mjs` reads `ALA_*` env vars. `src/errors.mjs` holds the typed errors.

The `.mcpb` is built by `scripts/build.mjs` (esbuild bundles `src/index.mjs` +
the SDK into a single `dist/server/index.mjs` with no native deps), then
`mcpb pack dist`.

## How to work

- **Read-only, always.** Do not add code that applies for, reserves, holds, or
  pays for a space, or that calls the API's operator/mutation endpoints.
- **Accessibility first.** Keep accessibility a first-class filter and state it
  plainly and first. Output must read cleanly with a screen reader — no tables,
  no emoji.
- **Honesty.** Vacancy is a snapshot; say so. If the API and the spec disagree,
  reality wins — flag it in the findings doc (see the `hasPotentialVacancy`
  note: it does not filter, so vacancy is filtered client-side on real counts).
  Fail visibly; never guess a location or a fact.
- **Identify honestly.** The API is public and accepts an honest `User-Agent`;
  do not impersonate a browser or spoof `Origin`.
- Prefer small, focused functions. Keep the provider/client boundary clean.

## Build, run, test

```bash
npm install
npm start            # node src/index.mjs (stdio)
npm test             # node --test (offline; 47 tests against recorded fixtures)
npm run build        # esbuild -> dist/server/index.mjs
npx @anthropic-ai/mcpb pack dist alberta-assisted-living.mcpb
```

No live network calls in tests — they run against fixtures recorded from the live
API in `test/fixtures/`.
