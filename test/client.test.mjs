import { test } from "node:test";
import assert from "node:assert/strict";

import { NavigatorClient } from "../src/providers/navigator-client.mjs";
import { UpstreamError } from "../src/errors.mjs";
import { jsonResponse } from "./helpers.mjs";

function client(fetchImpl) {
  return new NavigatorClient({
    apiUrl: "https://alacapacity.api.alberta.ca/graphql",
    userAgent: "test",
    fetchImpl,
  });
}

test("HTTP error becomes UpstreamError", async () => {
  const c = client(async () => jsonResponse({}, 500));
  await assert.rejects(() => c.facility(1), UpstreamError);
});

test("GraphQL errors become UpstreamError", async () => {
  const c = client(async () => jsonResponse({ errors: [{ message: "Unauthorized" }] }));
  await assert.rejects(() => c.facility(1), /Unauthorized/);
});

test("network failure becomes UpstreamError", async () => {
  const c = client(async () => {
    throw new Error("ECONNREFUSED");
  });
  await assert.rejects(() => c.facility(1), /Could not reach/);
});

test("sends an honest User-Agent (no browser spoofing)", async () => {
  let seen;
  const c = new NavigatorClient({
    apiUrl: "https://x/graphql",
    userAgent: "OpenState-AlbertaAssistedLiving/0.1",
    fetchImpl: async (_url, opts) => {
      seen = opts.headers["User-Agent"];
      return jsonResponse({ data: { facility: null } });
    },
  });
  await c.facility(1);
  assert.match(seen, /OpenState-AlbertaAssistedLiving/);
  assert.doesNotMatch(seen, /Mozilla|Chrome/);
});

test("fetchImage refuses non-https and foreign hosts without a request", async () => {
  let calls = 0;
  const c = client(async () => {
    calls += 1;
    return jsonResponse({});
  });
  assert.equal(await c.fetchImage("https://evil.example.com/x.jpg"), null);
  assert.equal(await c.fetchImage("http://alamedia.alberta.ca/x.jpg"), null);
  assert.equal(calls, 0);
});
