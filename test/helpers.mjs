/**
 * Offline test helpers: serve recorded Navigator responses via a mock fetch, so
 * provider and tool tests run with no live network calls (architecture rule:
 * "No live calls in CI").
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { loadConfig } from "../src/config.mjs";
import { Geocoder } from "../src/geocoding.mjs";
import { NavigatorClient } from "../src/providers/navigator-client.mjs";
import { NavigatorProvider } from "../src/providers/navigator-provider.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const FIXTURES = join(HERE, "fixtures", "alberta_ala");

// Facility ids present in the recorded fixtures.
export const FACILITY_MINIMAL_ID = 70042229; // Canora Place Supportive Living
export const FACILITY_RICH_ID = 70039781; // Villa Marguerite

export function loadFixture(name) {
  return JSON.parse(readFileSync(join(FIXTURES, `${name}.json`), "utf8"));
}

function jsonResponse(obj, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => "application/json; charset=utf-8" },
    json: async () => obj,
  };
}

function imageResponse() {
  const bytes = new Uint8Array([0xff, 0xd8, 0xff, 0xd9]); // minimal JPEG (SOI+EOI)
  return {
    ok: true,
    status: 200,
    headers: { get: (h) => (h.toLowerCase() === "content-type" ? "image/jpeg" : null) },
    arrayBuffer: async () => bytes.buffer,
    json: async () => {
      throw new Error("not json");
    },
  };
}

/** A fetch that routes GraphQL POSTs and image GETs to the recorded fixtures. */
export function fixtureFetch(url, options = {}) {
  if ((options.method || "GET").toUpperCase() === "POST") {
    const body = JSON.parse(options.body);
    const op = body.operationName;
    const variables = body.variables || {};
    if (op === "SearchFacilitiesByName") {
      const term = (variables.searchTerm || "").toLowerCase();
      const hit = term.includes("villa") || term.includes("marguerite");
      return Promise.resolve(jsonResponse(loadFixture(hit ? "search_results" : "search_empty")));
    }
    if (op === "CountFacilitiesByName") {
      const term = (variables.searchTerm || "").toLowerCase();
      const count = term.includes("villa") || term.includes("marguerite") ? 1 : 0;
      return Promise.resolve(jsonResponse({ data: { countBySearchTerm: count } }));
    }
    if (op === "GetFacilitiesByBoundingBox") {
      const data = loadFixture("bounding_box");
      const amenity = ((variables.fetchFacilityArgs || {}).amenityFilter) || {};
      if (amenity.accessibleBuilding) {
        return Promise.resolve(
          jsonResponse({
            data: { facilitiesByBoundingBox: data.data.facilitiesByBoundingBox.slice(0, 2) },
          })
        );
      }
      return Promise.resolve(jsonResponse(data));
    }
    if (op === "getFacility") {
      const id = variables.id;
      if (id === FACILITY_MINIMAL_ID) return Promise.resolve(jsonResponse(loadFixture("facility_minimal")));
      if (id === FACILITY_RICH_ID) return Promise.resolve(jsonResponse(loadFixture("facility_rich")));
      return Promise.resolve(jsonResponse({ data: { facility: null } }));
    }
    return Promise.resolve(jsonResponse({ errors: [{ message: `unexpected op ${op}` }] }, 400));
  }
  // GET: image fetch.
  if (String(url).includes("alamedia.alberta.ca")) {
    return Promise.resolve(imageResponse());
  }
  return Promise.resolve(jsonResponse({ error: "unexpected" }, 404));
}

export function makeProvider() {
  const config = loadConfig();
  const client = new NavigatorClient({
    apiUrl: config.apiUrl,
    userAgent: "test",
    fetchImpl: fixtureFetch,
  });
  return new NavigatorProvider({ config, client });
}

export function makeGeocoder() {
  const config = loadConfig();
  const geoFetch = (url) => {
    const q = new URL(url).searchParams.get("q")?.toLowerCase() || "";
    if (q.includes("sherwood park")) {
      return Promise.resolve(
        jsonResponse([
          {
            lat: "53.5256963",
            lon: "-113.296631",
            display_name: "Sherwood Park, Strathcona County, Alberta, Canada",
          },
        ])
      );
    }
    return Promise.resolve(jsonResponse([]));
  };
  return new Geocoder({ config, fetchImpl: geoFetch });
}

export { jsonResponse };
