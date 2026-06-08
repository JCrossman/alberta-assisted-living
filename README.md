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

> **Independent and unaffiliated.** This is an independent, public-interest tool
> built on Alberta's *public* Assisted Living Navigator data. It is **not
> operated by or endorsed by the Government of Alberta.**

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

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
cd alberta-assisted-living
uv sync
```

## Run (local, stdio)

```bash
uv run python -m alberta_assisted_living.server
```

The server speaks MCP over stdio and waits for an assistant to connect. To poke
at the tools directly, use the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uv run python -m alberta_assisted_living.server
```

## Install in Claude Desktop (one-click, `.mcpb`)

The easiest way to add this to Claude Desktop is the bundled **`.mcpb`** file
(MCP Bundle): **double-click `alberta-assisted-living.mcpb`** (or open Claude
Desktop → Settings → Extensions → install from file). Claude Desktop shows an
install dialog, and you're done — no JSON to edit.

**Prerequisites** (the bundle stays tiny by *not* vendoring Python packages —
they can't be shipped portably across macOS/Windows/Linux — so they resolve on
your machine on first launch):

- [uv](https://docs.astral.sh/uv/) installed and on your `PATH`.
- Python 3.11+ (uv can install one for you).

The bundle uses the **UV runtime** (`server.type: "uv"`): on first launch, `uv`
reads `pyproject.toml` / `uv.lock` and sets up dependencies automatically, for
your platform. The first start may take a few seconds while that happens.

> If Claude Desktop reports it can't find `uv`, it isn't on the GUI's `PATH`
> (common on macOS, where apps get a minimal `PATH`). Install uv system-wide, or
> use the manual config below with an **absolute** path to `uv`.

### Build the `.mcpb` yourself

The bundle is a reproducible build of this repo (it is not committed):

```bash
npm install -g @anthropic-ai/mcpb   # one-time
mcpb pack . alberta-assisted-living.mcpb
```

`manifest.json` and `.mcpbignore` in this repo define the bundle.

## Connect it to Claude Desktop (manual config)

Prefer editing config yourself? Add this to your `claude_desktop_config.json`,
using **absolute** paths (Claude Desktop launches the server with a minimal
`PATH`), then restart Claude Desktop.

```json
{
  "mcpServers": {
    "alberta-assisted-living": {
      "command": "/ABSOLUTE/PATH/TO/uv",
      "args": [
        "--directory", "/ABSOLUTE/PATH/TO/alberta-assisted-living",
        "run", "python", "-m", "alberta_assisted_living.server"
      ],
      "env": {}
    }
  }
}
```

Find your `uv` path with `which uv` (macOS/Linux) or `where uv` (Windows).

## Connect it to Claude Code

The repository root ships a [`.mcp.json`](.mcp.json) that registers this server
for [Claude Code](https://claude.com/claude-code) with a **relative**
`--directory`, so it works for anyone who clones the repo with no per-machine
paths to edit. Open the repo in Claude Code and approve the
`alberta-assisted-living` server when prompted.

## Run (remote, HTTP)

The same tools also serve over **Streamable HTTP**, the transport a hosted,
one-click connector would use. Flip the env switch:

```bash
ALA_TRANSPORT=http ALA_PORT=8765 uv run python -m alberta_assisted_living.server
# MCP endpoint:  http://127.0.0.1:8765/mcp
# Liveness:      http://127.0.0.1:8765/health  -> {"status":"ok",...}
```

`stateless_http` is on by default so multiple replicas won't break sessions, and
an HTTP deployment applies a global rate limit for upstream politeness.

## How it reaches the data

The Navigator's data comes from a **public, unauthenticated GraphQL API**
(`alacapacity.api.alberta.ca/graphql`). This server reads it the way the
Navigator's own web app does — through the service's own data interface — and
**identifies itself honestly** (it does not impersonate a browser; the API
accepts an honest User-Agent). It uses only the read queries a citizen needs; it
does **not** touch the operator capacity-reporting queries or any of the API's
write operations, which require an operator login and change records.

"Near me" searches turn a place name into coordinates using OpenStreetMap's
keyless **Nominatim** service. Only the place text you provide is sent, only when
you ask for a location search; you can also pass exact `latitude`/`longitude`, or
turn geocoding off entirely (`ALA_ENABLE_GEOCODING=false`).

## Configuration

All optional, via environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `ALA_TRANSPORT` | `stdio` | `stdio` (local) or `http` (Streamable HTTP). |
| `ALA_API_URL` | the Navigator GraphQL endpoint | Upstream API URL. |
| `ALA_USER_AGENT` | an honest identifying UA | Sent to the Navigator API. |
| `ALA_HTTP_TIMEOUT` | `30` | Upstream request timeout (seconds). |
| `ALA_ENABLE_GEOCODING` | `true` | When `false`, location search requires coordinates. |
| `ALA_GEOCODER_URL` | Nominatim search | Geocoding endpoint. |
| `ALA_GEOCODER_USER_AGENT` | the `ALA_USER_AGENT` value | Identifying UA for the geocoder (Nominatim policy). |
| `ALA_DEFAULT_RADIUS_KM` / `ALA_MAX_RADIUS_KM` | `25` / `200` | Search radius default and cap. |
| `ALA_HOST` / `ALA_PORT` | `127.0.0.1` / `8000` | Bind address for `http` transport. |
| `ALA_MCP_PATH` | `/mcp` | Path the MCP endpoint is served at (`http`). |
| `ALA_STATELESS_HTTP` | `true` | Stateless HTTP so replicas don't break sessions. |
| `ALA_RATE_LIMIT_RPS` / `ALA_RATE_LIMIT_BURST` | `5` / `20` | Global rate limit for the `http` transport (`<= 0` disables). |

## Tests

```bash
uv run pytest
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
- **Postal-code-only lookups can miss.** Nominatim does not have full Canadian
  postal-code coverage; a town or street address resolves more reliably.
- **This tool never acts.** It finds and explains. Applying for a publicly funded
  space happens through an Alberta Health Services case manager; arranging a
  private space happens with the operator. You take those steps yourself.

## What this is not

Not a company. Not a data business. Not a new app you are forced to use. It is
public-interest assistive infrastructure, meant to be shared and forked, and
ultimately adopted by the public sector itself.

*No citizen should be excluded from what is already theirs.*
