import { test } from "node:test";
import assert from "node:assert/strict";

import { boundingBox, buildFetchArgs } from "../src/providers/navigator-provider.mjs";
import { makeProvider, FACILITY_MINIMAL_ID, FACILITY_RICH_ID } from "./helpers.mjs";

test("searchByName maps the summary shape", async () => {
  const provider = makeProvider();
  const results = await provider.searchByName("Villa Marguerite");
  assert.equal(results.length, 1);
  const s = results[0];
  assert.equal(s.id, FACILITY_RICH_ID);
  assert.equal(s.name, "Villa Marguerite");
  assert.equal(s.city, "Edmonton");
  assert.equal(s.phoneNumber, "780-451-1114");
  assert.equal(s.beds.typeBFunded, 145);
  assert.equal(s.beds.typeBSecureFunded, 94);
  assert.equal(s.beds.typeBVacant, 3);
  assert.equal(s.beds.hasVacancy, true);
  assert.ok(s.careTypes.includes("Type B (designated supportive living)"));
});

test("searchByName returns empty for no match", async () => {
  const provider = makeProvider();
  assert.deepEqual(await provider.searchByName("nonexistent place"), []);
});

test("countByName", async () => {
  const provider = makeProvider();
  assert.equal(await provider.countByName("Villa"), 1);
  assert.equal(await provider.countByName("nothing"), 0);
});

test("searchNear sorts nearest-first and limits", async () => {
  const provider = makeProvider();
  const results = await provider.searchNear({
    latitude: 53.5461,
    longitude: -113.4938,
    radiusKm: 25,
    limit: 3,
  });
  assert.equal(results.length, 3);
  const d = results.map((r) => r.distanceKm).filter((x) => x != null);
  assert.deepEqual(d, [...d].sort((a, b) => a - b));
});

test("searchNear passes the accessibility filter to the API", async () => {
  const provider = makeProvider();
  const unfiltered = await provider.searchNear({
    latitude: 53.5461,
    longitude: -113.4938,
    radiusKm: 25,
    limit: 100,
  });
  const filtered = await provider.searchNear({
    latitude: 53.5461,
    longitude: -113.4938,
    radiusKm: 25,
    filters: { accessibleBuilding: true },
    limit: 100,
  });
  assert.ok(filtered.length < unfiltered.length);
});

test("has_vacancy is filtered client-side on real counts", async () => {
  const provider = makeProvider();
  const withVacancy = await provider.searchNear({
    latitude: 53.5461,
    longitude: -113.4938,
    radiusKm: 25,
    filters: { hasVacancy: true },
    limit: 100,
  });
  assert.ok(withVacancy.every((s) => s.beds.hasVacancy));
});

test("getDetails (minimal record)", async () => {
  const provider = makeProvider();
  const d = await provider.getDetails(FACILITY_MINIMAL_ID);
  assert.equal(d.name, "Canora Place Supportive Living");
  assert.equal(d.operatorName, "George Spady Centre Society (The)");
  assert.equal(d.beds.supportedLiving, 28);
  assert.equal(d.accessible, false);
  assert.ok(d.charges.some((c) => c.name === "Television"));
  assert.match(d.accommodationStandardsUrl, /standardsandlicensing/);
});

test("getDetails (rich record) surfaces accessibility", async () => {
  const provider = makeProvider();
  const d = await provider.getDetails(FACILITY_RICH_ID);
  assert.equal(d.name, "Villa Marguerite");
  assert.equal(d.operatorType, "Private");
  assert.equal(d.accessible, true);
  assert.ok(d.accessibilityNotes.some((n) => n.toLowerCase().includes("accessible")));
  assert.ok(d.amenities.includes("Accessible (wheelchairs, scooters)"));
  assert.ok(d.roomTypes.includes("Accessible bathroom"));
  assert.equal(d.numberOfSpacesPrivateRoom, 228);
  assert.equal(d.accreditationStatus, "Accredited");
  assert.equal(d.hasSmokingPolicy, true);
  assert.ok(d.siteServices.some((s) => s.title === "Housekeeping"));
  assert.ok(d.securityServices.some((s) => s.title === "Emergency call system"));
  assert.ok(d.careTypes.some((c) => c.includes("Type B")));
});

test("getDetails unknown id throws InvalidInputError", async () => {
  const provider = makeProvider();
  await assert.rejects(() => provider.getDetails(1), /could not find/i);
});

test("boundingBox corners and half-height", () => {
  const { coordinateA, coordinateB } = boundingBox(53.5461, -113.4938, 10);
  assert.ok(coordinateA.latitude > coordinateB.latitude);
  assert.ok(coordinateA.longitude > coordinateB.longitude);
  const halfHeight = (coordinateA.latitude - coordinateB.latitude) / 2;
  assert.ok(Math.abs(halfHeight - 10 / 111.0) < 1e-9);
});

test("buildFetchArgs maps filters and omits has_vacancy", () => {
  assert.equal(buildFetchArgs(null), null);
  assert.equal(buildFetchArgs({}), null);
  const args = buildFetchArgs({
    accessibleBuilding: true,
    typeBSecure: true,
    privateRoom: true,
    hasVacancy: true,
  });
  assert.deepEqual(args.amenityFilter, { accessibleBuilding: [true] });
  assert.deepEqual(args.levelOfCareFilter, { typeBSecure: [true] });
  assert.deepEqual(args.roomTypeFilter, { privateRoom: [true] });
  assert.equal("hasPotentialVacancy" in args, false);
});

test("fetchImage returns bytes for the navigator host", async () => {
  const provider = makeProvider();
  const out = await provider.fetchImage("https://alamedia.alberta.ca/facility/x/p.jpg");
  assert.ok(out);
  assert.equal(out.mimeType, "image/jpeg");
});

test("fetchImage rejects a foreign host (SSRF guard)", async () => {
  const provider = makeProvider();
  assert.equal(await provider.fetchImage("https://evil.example.com/p.jpg"), null);
  assert.equal(await provider.fetchImage("http://alamedia.alberta.ca/p.jpg"), null);
});
