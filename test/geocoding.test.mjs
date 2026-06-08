import { test } from "node:test";
import assert from "node:assert/strict";

import { loadConfig } from "../src/config.mjs";
import { Geocoder } from "../src/geocoding.mjs";
import { makeGeocoder, jsonResponse } from "./helpers.mjs";

test("resolves a known place", async () => {
  const result = await makeGeocoder().geocode("Sherwood Park");
  assert.ok(result);
  assert.equal(Math.round(result.latitude * 100) / 100, 53.53);
  assert.match(result.displayName, /Alberta/);
});

test("unknown place returns null", async () => {
  assert.equal(await makeGeocoder().geocode("Atlantis"), null);
});

test("empty input returns null", async () => {
  const g = makeGeocoder();
  assert.equal(await g.geocode(""), null);
  assert.equal(await g.geocode("   "), null);
});

test("disabled geocoding returns null", async () => {
  const config = { ...loadConfig(), enableGeocoding: false };
  const g = new Geocoder({ config, fetchImpl: async () => jsonResponse([]) });
  assert.equal(await g.geocode("Sherwood Park"), null);
});

test("biases a bare place name to Alberta, Canada", async () => {
  let seen;
  const g = new Geocoder({
    config: loadConfig(),
    fetchImpl: async (url) => {
      seen = new URL(url).searchParams.get("q");
      return jsonResponse([]);
    },
  });
  await g.geocode("Camrose");
  assert.match(seen, /Alberta/);
  assert.match(seen, /Canada/);
});

test("does not double-tag when a province is already present", async () => {
  let seen;
  const g = new Geocoder({
    config: loadConfig(),
    fetchImpl: async (url) => {
      seen = new URL(url).searchParams.get("q");
      return jsonResponse([]);
    },
  });
  await g.geocode("123 Main St, Calgary, Alberta");
  assert.equal(seen, "123 Main St, Calgary, Alberta");
});
