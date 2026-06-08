/**
 * Map plain words a citizen would say onto the Navigator's facility filters.
 *
 * The search filters (care level, room type, amenities) are exposed to the
 * assistant as lists of everyday words - "memory care", "private room",
 * "meals", "wheelchair accessible" - not the platform's internal field names.
 *
 * An unrecognized word raises InvalidInputError naming the valid options, so the
 * assistant can correct course instead of silently dropping a filter the citizen
 * cares about (Constitution Art. 7.1).
 */

import { InvalidInputError } from "./errors.mjs";

const CARE_TYPE_WORDS = {
  "type a": "typeA",
  a: "typeA",
  "long-term care": "typeA",
  "long term care": "typeA",
  ltc: "typeA",
  "nursing home": "typeA",
  "facility living": "typeA",
  "type b": "typeB",
  b: "typeB",
  "designated supportive living": "typeB",
  dsl: "typeB",
  "type b secure": "typeBSecure",
  "b secure": "typeBSecure",
  secure: "typeBSecure",
  "secure space": "typeBSecure",
  "memory care": "typeBSecure",
  dementia: "typeBSecure",
  "dementia care": "typeBSecure",
  "type c": "typeC",
  c: "typeC",
  "supportive living": "supportedLiving",
  "supported living": "supportedLiving",
  sl: "supportedLiving",
  "seniors lodge": "seniorsLodge",
  "senior lodge": "seniorsLodge",
  lodge: "seniorsLodge",
};

const ROOM_TYPE_WORDS = {
  "private room": "privateRoom",
  private: "privateRoom",
  "shared room": "sharedRoom",
  shared: "sharedRoom",
  "semi-private": "sharedRoom",
  "semi private": "sharedRoom",
  "one bedroom": "oneBedroom",
  "1 bedroom": "oneBedroom",
  "one-bedroom": "oneBedroom",
  "1-bedroom": "oneBedroom",
  "multi bedroom": "multiBedroom",
  "multi-bedroom": "multiBedroom",
  "two bedroom": "multiBedroom",
  "2 bedroom": "multiBedroom",
};

const AMENITY_WORDS = {
  // Accessibility (also first-class boolean params; accepted here for convenience
  // so "wheelchair accessible" in an amenities list works too).
  accessible: "accessibleBuilding",
  "accessible building": "accessibleBuilding",
  wheelchair: "accessibleBuilding",
  "wheelchair accessible": "accessibleBuilding",
  "accessible bathroom": "accessibleBathroom",
  "private bathroom": "privateBathroom",
  ensuite: "privateBathroom",
  "en-suite": "privateBathroom",
  "en suite": "privateBathroom",
  "emergency call system": "emergencyCallSystem",
  "emergency call": "emergencyCallSystem",
  "call system": "emergencyCallSystem",
  "call bell": "emergencyCallSystem",
  "meals included": "mealsIncluded",
  meals: "mealsIncluded",
  food: "mealsIncluded",
  housekeeping: "housekeeping",
  cleaning: "housekeeping",
  laundry: "laundryService",
  "laundry service": "laundryService",
  parking: "parking",
  gardens: "gardens",
  garden: "gardens",
  "outdoor space": "gardens",
  "social activities": "socialActivities",
  activities: "socialActivities",
  social: "socialActivities",
  hairdresser: "hairdresserBarber",
  barber: "hairdresserBarber",
  salon: "hairdresserBarber",
  pets: "smallPetsAllowed",
  "small pets": "smallPetsAllowed",
  "pet friendly": "smallPetsAllowed",
  "pet-friendly": "smallPetsAllowed",
  "indoor smoking room": "indoorSmokingRoom",
  "indoor smoking": "indoorSmokingRoom",
  "outdoor smoking area": "safeOutdoorSmokingArea",
  "outdoor smoking": "safeOutdoorSmokingArea",
  "smoking area": "safeOutdoorSmokingArea",
};

function resolve(words, table, label, into) {
  for (const word of words || []) {
    const key = (word || "").trim().toLowerCase();
    if (!key) continue;
    const field = table[key];
    if (!field) {
      const options = [...new Set(Object.keys(table))].sort().join(", ");
      throw new InvalidInputError(
        `I do not recognize the ${label} ${JSON.stringify(word)}. ` +
          `Valid ${label} words include: ${options}.`
      );
    }
    into[field] = true;
  }
}

/**
 * Build a filters object from plain words and the first-class flags. Returns a
 * plain object whose keys are the camelCase filter fields the provider reads.
 */
export function buildFilters({
  careTypes = null,
  roomTypes = null,
  amenities = null,
  accessibleBuilding = false,
  accessibleBathroom = false,
  onlyWithVacancy = false,
} = {}) {
  const filters = {};
  resolve(careTypes, CARE_TYPE_WORDS, "care type", filters);
  resolve(roomTypes, ROOM_TYPE_WORDS, "room type", filters);
  resolve(amenities, AMENITY_WORDS, "amenity", filters);
  if (accessibleBuilding) filters.accessibleBuilding = true;
  if (accessibleBathroom) filters.accessibleBathroom = true;
  if (onlyWithVacancy) filters.hasVacancy = true;
  return filters;
}

export function isEmptyFilters(filters) {
  return !filters || Object.keys(filters).length === 0;
}
