import { test } from "node:test";
import assert from "node:assert/strict";

import { buildFilters, isEmptyFilters } from "../src/filters.mjs";
import { InvalidInputError } from "../src/errors.mjs";

test("first-class accessibility flags", () => {
  const f = buildFilters({ accessibleBuilding: true, accessibleBathroom: true });
  assert.equal(f.accessibleBuilding, true);
  assert.equal(f.accessibleBathroom, true);
});

test("care-type words map to fields", () => {
  const f = buildFilters({ careTypes: ["memory care", "long-term care"] });
  assert.equal(f.typeBSecure, true);
  assert.equal(f.typeA, true);
});

test("room and amenity words", () => {
  const f = buildFilters({
    roomTypes: ["private room"],
    amenities: ["meals", "pets", "emergency call"],
  });
  assert.equal(f.privateRoom, true);
  assert.equal(f.mealsIncluded, true);
  assert.equal(f.smallPetsAllowed, true);
  assert.equal(f.emergencyCallSystem, true);
});

test("amenity word accepts accessibility synonyms", () => {
  const f = buildFilters({ amenities: ["wheelchair accessible"] });
  assert.equal(f.accessibleBuilding, true);
});

test("only-with-vacancy", () => {
  assert.equal(buildFilters({ onlyWithVacancy: true }).hasVacancy, true);
});

test("unknown word throws with options", () => {
  assert.throws(
    () => buildFilters({ amenities: ["helipad"] }),
    (err) => err instanceof InvalidInputError && /helipad/.test(err.message) && /amenity/i.test(err.message)
  );
});

test("empty filters", () => {
  assert.equal(isEmptyFilters(buildFilters({})), true);
});

test("case-insensitive and trimmed", () => {
  const f = buildFilters({ careTypes: ["  Memory Care "] });
  assert.equal(f.typeBSecure, true);
});
