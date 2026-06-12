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
- **Stay pinned to the Constitution.** Compliance is pinned in
  `constitution.lock` and checked by the `constitution-sync` workflow. If a
  "constitution drift" issue opens, re-review `COMPLIANCE.md` against the new
  upstream text, then update the pin (`blob_sha`, `sha256`,
  `commit_at_verification`, `verified_date`). Do not just bump the pin without
  re-reviewing.
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

## The Open State — binding conformance

This project implements the **Civic Access Protocol** and conforms to
[The Open State Constitution](https://github.com/JCrossman/the-open-state/blob/main/CONSTITUTION.md)
at tag `constitution-v1.1`. These rules are binding: if a requested change
conflicts with one, say so and stop rather than complying — cite the article.

**Scope note — this server is read-only.** It performs no sign-in, stores no
session, holds no credentials, and takes no consequential action (no booking,
payment, submission, cancellation, or record change); every tool is a public-data
read. So the Civic Access Protocol kit (`@open-state/kit` — `vault` / `capture` /
`confirmGated`), which mechanically satisfies the credential, session, and
consequential-action parts of Arts. 1, 2, 9, and 10, has nothing to wrap here:
those articles are satisfied **by absence**, and the kit is therefore **not a
dependency** of this package. (Pinning the kit would not by itself make this
implementation "compliant" anyway — see The Open State `CONFORMANCE.md`: the kit
covers four articles partially and does nothing for Arts. 3–8.)

**Binding forward rule.** The moment this tool gains a citizen login, a stored
session, or any consequential (write) action, that code MUST adopt
`@open-state/kit` and route through it — sign-in via `capture`, session storage
via the `vault`, every consequential action via the `confirmGated` two-phase gate
— *before it ships*, and the kit MUST then be pinned in `package.json`. Adding
such a path without the kit is a conformance violation: stop and flag it.

The non-negotiables, binding now:

- **The human decides (Art. 2).** Tools may fully *prepare* a consequential action
  but MUST stop at the citizen's own final step (use the kit's `confirmGated`
  shape when such an action exists). Never design to win a contested public
  resource by automation. *(No such action exists today — this server only reads.)*
- **No stored government credentials (Art. 1).** No passwords or secrets in code,
  logs, tool output, or any server. Any future citizen session lives only in the
  kit vault, on-device, encrypted; never expose a session to the model. *(This
  server holds none — the Navigator read API needs no auth.)*
- **Accessibility is the purpose (Art. 3).** Screen-reader-clean output (no tables,
  no emoji), plain language, accessibility attributes first-class and filterable
  (restrict results to only accessible options), and accessible *through to the
  point of action* — never hand the citizen back to an inaccessible interface.
- **Health/disability data is the most protected class (Art. 5.4).** Treat anything
  revealing disability, health, or accessibility needs with heightened protection;
  never store it and never use it beyond serving the request. This server is
  stateless and stores nothing.
- **Honesty (Art. 7).** Distinguish verified from assumed. Fail visibly in plain
  language; never guess a location or a fact. Honest identification (no browser
  impersonation, no `Origin` spoofing) and polite request rates; no degradation of
  the upstream service.
- **Assistive technology, not a bot (Art. 10).** Act only in the citizen's own
  session, at their direction, through the service's **own data interface**. Never
  impersonate anyone and never defeat a human gate — the citizen passes it
  personally.

No citizen should be excluded from what is already theirs.
