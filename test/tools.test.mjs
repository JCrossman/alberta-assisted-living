import { test } from "node:test";
import assert from "node:assert/strict";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";

import { createServer } from "../src/server.mjs";
import { loadConfig } from "../src/config.mjs";
import { makeProvider, makeGeocoder, FACILITY_MINIMAL_ID, FACILITY_RICH_ID } from "./helpers.mjs";

async function connect() {
  const config = loadConfig();
  const server = createServer({
    provider: makeProvider(),
    geocoder: makeGeocoder(),
    config,
  });
  const [clientT, serverT] = InMemoryTransport.createLinkedPair();
  const client = new Client({ name: "test", version: "0" });
  await Promise.all([server.connect(serverT), client.connect(clientT)]);
  return client;
}

function textOf(res) {
  return (res.content || [])
    .filter((c) => c.type === "text")
    .map((c) => c.text)
    .join("\n");
}

async function call(name, args = {}) {
  const client = await connect();
  try {
    return await client.callTool({ name, arguments: args });
  } finally {
    await client.close();
  }
}

test("registers the four tools", async () => {
  const client = await connect();
  try {
    const { tools } = await client.listTools();
    assert.deepEqual(
      tools.map((t) => t.name).sort(),
      [
        "explain_care_options",
        "find_facilities_near",
        "get_facility_details",
        "search_facilities_by_name",
      ]
    );
  } finally {
    await client.close();
  }
});

test("search by name lists results and discloses independence", async () => {
  const out = textOf(await call("search_facilities_by_name", { search_term: "Villa Marguerite" }));
  assert.match(out, /Villa Marguerite/);
  assert.match(out, new RegExp(`facility id: ${FACILITY_RICH_ID}`));
  assert.match(out, /not operated by or endorsed by the Government of Alberta/);
  assert.ok(!out.includes("\t"));
});

test("search by name, no match, is friendly", async () => {
  const out = textOf(await call("search_facilities_by_name", { search_term: "Narnia Manor" }));
  assert.match(out, /could not find/i);
});

test("find near requires a location", async () => {
  const out = textOf(await call("find_facilities_near", {}));
  assert.match(out, /tell me where to search/i);
});

test("find near geocodes a place name", async () => {
  const out = textOf(await call("find_facilities_near", { location: "Sherwood Park" }));
  assert.match(out, /Sherwood Park/);
  assert.match(out, /km away/);
  assert.match(out, /nearest first/i);
});

test("find near, unresolvable location, fails visibly", async () => {
  const out = textOf(await call("find_facilities_near", { location: "Atlantis" }));
  assert.match(out, /could not find the location/i);
});

test("find near with explicit coordinates", async () => {
  const out = textOf(
    await call("find_facilities_near", { latitude: 53.5461, longitude: -113.4938 })
  );
  assert.match(out, /km away/);
});

test("find near describes the accessibility filter", async () => {
  const out = textOf(
    await call("find_facilities_near", {
      latitude: 53.5461,
      longitude: -113.4938,
      accessible_building: true,
    })
  );
  assert.match(out, /accessible building/i);
});

test("find near with an unknown filter word is friendly", async () => {
  const out = textOf(
    await call("find_facilities_near", {
      latitude: 53.5461,
      longitude: -113.4938,
      amenities: ["helipad"],
    })
  );
  assert.match(out, /do not recognize/i);
});

test("get details surfaces accessibility first and the next steps", async () => {
  const out = textOf(await call("get_facility_details", { facility_id: FACILITY_RICH_ID }));
  assert.match(out, /Accessibility:/);
  assert.match(out, /accessible/i);
  assert.match(out, /never applies or reserves/i);
  assert.match(out, /Health Link at 811/);
  assert.match(out, /accommodation standards/i);
});

test("get details, minimal record, states no accessible features", async () => {
  const out = textOf(await call("get_facility_details", { facility_id: FACILITY_MINIMAL_ID }));
  assert.match(out, /no accessible features/i);
});

test("get details, unknown id, is friendly", async () => {
  const out = textOf(await call("get_facility_details", { facility_id: 1 }));
  assert.match(out, /could not find/i);
});

test("get details with photos returns image content", async () => {
  const res = await call("get_facility_details", {
    facility_id: FACILITY_RICH_ID,
    include_photos: true,
  });
  const images = (res.content || []).filter((c) => c.type === "image");
  assert.ok(images.length >= 1);
  assert.equal(images[0].mimeType, "image/jpeg");
});

test("explain care options is plain and offline", async () => {
  const out = textOf(await call("explain_care_options"));
  assert.match(out, /memory care/i);
  assert.match(out, /Health Link at 811/);
  assert.match(out, /never applies, reserves, or pays/i);
  assert.ok(!out.includes("\t"));
});
