# Open State: Alberta Assisted Living

Part of **The Open State**, a reference implementation of the **Civic Access
Protocol**. This package lets a citizen reach the Government of Alberta's
**Assisted Living Navigator** through their own AI assistant, in plain language,
to find continuing care, supportive living, and seniors' housing — with
**accessibility as a first-class filter** — while keeping their control
throughout.

> Your services. Your assistant. Your access.

It runs locally and speaks MCP over **stdio**, so you add it to an assistant on
your own machine (Claude Desktop, Claude Code, or any MCP client). It is
**read-only**: it finds and explains options and points you to the facility and
to Alberta Health Services. It **never applies, reserves a space, pays, or
stores credentials.**

Built in **Node.js** (matching the Camp MCP), using the official
[`@modelcontextprotocol/sdk`](https://github.com/modelcontextprotocol/typescript-sdk).

> **Independent and unaffiliated.** This is an independent, public-interest tool
> built on Alberta's *public* Assisted Living Navigator data. It is **not
> operated by or endorsed by the Government of Alberta.**

## Conformance

This is a Civic Access Protocol implementation and **conforms to The Open State
Constitution** at tag
[`constitution-v1.1`](https://github.com/JCrossman/the-open-state/blob/main/CONSTITUTION.md).
It is **read-only** — no login, no stored session, no credentials, and no
consequential action — so the protocol's credential, session, and
consequential-action guarantees (Articles 1, 2, 9, 10) are met **by absence**, and
the Civic Access Protocol kit
([`@open-state/kit`](https://www.npmjs.com/package/@open-state/kit)) is **not a
dependency**. If this tool ever gains a citizen login or a consequential action,
it commits to adopting the kit for those (on-device vault, session capture, and a
human-confirmation gate). The article-by-article mapping is in
[`COMPLIANCE.md`](COMPLIANCE.md); the protocol's conformance requirements are in
[`CONFORMANCE.md`](https://github.com/JCrossman/the-open-state/blob/main/CONFORMANCE.md).

## Why this exists

The Assisted Living Navigator is genuinely useful, but finding the right place
for an aging parent — or for yourself — usually means clicking through a map and
filter UI under stress, often on behalf of someone with a disability, limited
English, or limited time. The same conversational layer that helps a busy family
member helps a senior who cannot navigate the interface at all. Accessibility is
the point: "accessible building" and "accessible bathroom" are first-class
filters, accessibility is stated plainly in every result, and the output reads
cleanly with a screen reader.

The binding rules and design are in The Open State repo:
[`CONSTITUTION.md`](https://github.com/JCrossman/the-open-state/blob/main/CONSTITUTION.md).
The verified API contract this server is built on is in
[`docs/alberta-assisted-living-api-findings.md`](docs/alberta-assisted-living-api-findings.md),
and the article-by-article compliance mapping is in [`COMPLIANCE.md`](COMPLIANCE.md).
That compliance is pinned to a specific version of the constitution and kept
honest by an automated drift check — see
[Staying in sync with the Constitution](#staying-in-sync-with-the-constitution).

## What it does

Four plain-language tools, all read-only:

| Tool | Purpose |
|---|---|
| `search_facilities_by_name` | Find facilities by name or a word in their name. Returns city, address, phone, care types, reported vacancy, and a facility id. |
| `find_facilities_near` | Find facilities near a place (town, address, or coordinates), **nearest first**, filtered by **accessibility (first-class)**, care type, room type, amenities, and current vacancy. |
| `get_facility_details` | One facility's full profile: accessibility (stated first), contact, operator, care types, funded/vacant spaces, rooms and pricing, amenities and services, charges, accreditation, and the **official accommodation-standards record**. Optionally returns photos as viewable images. |
| `explain_care_options` | Plain-language guide to Alberta's care types (seniors lodge, supportive living, Type A/B/B-secure/C), how funding and AHS placement work, and what every filter means. No network call. |

### Try it

- "What assisted living is near Sherwood Park?"
- "Find memory care within 15 km of downtown Calgary that has an accessible building and a private room."
- "Which places near my mom have an open space right now?"
- "Tell me everything about Villa Marguerite, and show me photos."
- "I'm new to this — what's the difference between supportive living and long-term care?"

The assistant finds and explains options. **You** take the next step: you call the
facility, or — for a publicly funded space — Alberta Health Services arranges
placement through a case manager (call Health Link at 811). This tool never acts
for you.

## Install in Claude Desktop (one-click, `.mcpb`)

The easiest way: **double-click `alberta-assisted-living.mcpb`** (or Claude
Desktop → Settings → Extensions → install from file). Claude Desktop shows an
install dialog and you're done — no JSON to edit.

**No prerequisites.** The whole server (including the MCP SDK) is bundled into a
single self-contained `server/index.mjs` and runs on the **Node runtime that
Claude Desktop already ships**. There is nothing to install — no Node, no Python,
no `uv`, no dependency download on first launch.

> Behind a corporate TLS-intercepting proxy? Node honours `NODE_EXTRA_CA_CERTS`;
> point it at your proxy's CA bundle (via the extension's environment, or the
> manual config below).

## Connect it to Claude Code

The repo ships a [`.mcp.json`](.mcp.json) that registers the server for
[Claude Code](https://claude.com/claude-code) as `node src/index.mjs`. Run
`npm install` once, then open the repo in Claude Code and approve the server.

## Run it directly

```bash
npm install
npm start            # = node src/index.mjs  (speaks MCP over stdio)
```

To poke at the tools with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector node src/index.mjs
```

## Manual Claude Desktop config

Prefer editing config yourself? After `npm install`, add this to
`claude_desktop_config.json` using an **absolute** path, then restart Claude
Desktop:

```json
{
  "mcpServers": {
    "alberta-assisted-living": {
      "command": "node",
      "args": ["/ABSOLUTE/PATH/TO/alberta-assisted-living/src/index.mjs"],
      "env": {}
    }
  }
}
```

## Build the `.mcpb` yourself

The bundle is a reproducible build of this repo (it is not committed):

```bash
npm install
npm run build                                   # esbuild -> dist/server/index.mjs
npx @anthropic-ai/mcpb pack dist alberta-assisted-living.mcpb
```

`manifest.json`, `scripts/build.mjs`, and `src/` define the bundle.

## How it reaches the data

The Navigator's data comes from a **public, unauthenticated GraphQL API**
(`alacapacity.api.alberta.ca/graphql`). This server reads it the way the
Navigator's own web app does — through the service's own data interface, using
Node's built-in `fetch` — and **identifies itself honestly** (it does not
impersonate a browser; the API accepts an honest User-Agent). It uses only the
read queries a citizen needs; it does **not** touch the operator
capacity-reporting queries or any of the API's write operations, which require an
operator login and change records.

"Near me" searches turn a place name into coordinates using OpenStreetMap's
keyless **Nominatim** service. Only the place text you provide is sent, only when
you ask for a location search; you can also pass exact `latitude`/`longitude`, or
turn geocoding off entirely (`ALA_ENABLE_GEOCODING=false`).

## Configuration

All optional, via environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `ALA_API_URL` | the Navigator GraphQL endpoint | Upstream API URL. |
| `ALA_USER_AGENT` | an honest identifying UA | Sent to the Navigator API. |
| `ALA_HTTP_TIMEOUT_MS` | `30000` | Upstream request timeout (ms). |
| `ALA_ENABLE_GEOCODING` | `true` | When `false`, location search requires coordinates. |
| `ALA_GEOCODER_URL` | Nominatim search | Geocoding endpoint. |
| `ALA_GEOCODER_USER_AGENT` | the `ALA_USER_AGENT` value | Identifying UA for the geocoder (Nominatim policy). |
| `ALA_GEOCODER_TIMEOUT_MS` | `20000` | Geocoder request timeout (ms). |
| `ALA_DEFAULT_RADIUS_KM` / `ALA_MAX_RADIUS_KM` | `25` / `200` | Search radius default and cap. |
| `NODE_EXTRA_CA_CERTS` | — | Standard Node var; set to a CA bundle to work behind a TLS-intercepting proxy. |

## Tests

```bash
npm test            # = node --test  (47 tests)
```

Tests run fully offline against responses recorded from the live API — no live
network calls.

## Honest notes and known limits

Reality, recorded rather than guessed (Constitution Art. 7):

- **Vacancy is a snapshot, not a guarantee.** The vacant-bed counts are what the
  operator last reported to the Navigator. Only Type A–C report a live vacant
  count; supportive living and seniors lodge report funded capacity only. Always
  confirm with the facility.
- **Accessibility comes from the listing.** A facility is called accessible when
  its listing reports accessible features (accessible building, accessible
  bathroom, accessible spaces). A listing can be incomplete, so a result that
  shows no accessible features may still be worth a direct call. Summary/search
  results do not carry amenity detail — open `get_facility_details` for the full
  accessibility picture.
- **`only_with_vacancy` is filtered on the real reported counts**, not the API's
  `hasPotentialVacancy` flag, which (verified live) does not narrow results.
- **Postal-code-only lookups can miss.** Nominatim does not have full Canadian
  postal-code coverage; a town or street address resolves more reliably.
- **This tool never acts.** It finds and explains. Applying for a publicly funded
  space happens through an Alberta Health Services case manager; arranging a
  private space happens with the operator. You take those steps yourself.

## Staying in sync with the Constitution

The Civic Access Protocol [`CONSTITUTION.md`](https://github.com/JCrossman/the-open-state/blob/main/CONSTITUTION.md)
lives in the separate `the-open-state` repo and may be revised over time (its own
terms require revisions to *strengthen, not weaken* the protections). So
[`COMPLIANCE.md`](COMPLIANCE.md) is a claim about a **specific version**, pinned
in [`constitution.lock`](constitution.lock) by the constitution's git blob SHA.

A scheduled GitHub Action
([`.github/workflows/constitution-sync.yml`](.github/workflows/constitution-sync.yml))
re-checks the upstream constitution weekly and **opens an issue** if it has
changed since the pin, prompting a re-review of `COMPLIANCE.md` and a re-pin. It
is silent while in sync. Run it locally with `npm run check:constitution`.

Because `the-open-state` is **public**, the check needs no credentials or secret
setup — the workflow passes the built-in `GITHUB_TOKEN` only for API rate-limit
headroom. Full details and the re-pin steps are in
[`COMPLIANCE.md`](COMPLIANCE.md#staying-in-sync-with-the-constitution).

## What this is not

Not a company. Not a data business. Not a new app you are forced to use. It is
public-interest assistive infrastructure, meant to be shared and forked, and
ultimately adopted by the public sector itself.

*No citizen should be excluded from what is already theirs.*
