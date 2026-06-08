/**
 * Alberta Assisted Living Navigator provider.
 *
 * Maps the Navigator's GraphQL responses into normalized plain objects and
 * builds searches. The MCP tools depend only on this layer, never on the raw
 * GraphQL shapes, so another province could be added behind the same interface.
 *
 * All read-only. Nothing applies for, reserves, or holds a space (Art. 1, 2).
 * The operator capacity-reporting queries and every mutation the API exposes are
 * deliberately not used here: they require an operator login and/or change
 * records, neither of which belongs in a citizen-facing assistive tool.
 */

import { InvalidInputError } from "../errors.mjs";
import { NavigatorClient } from "./navigator-client.mjs";

export const NAVIGATOR_NAME = "Alberta Assisted Living Navigator";

const VALID_SORTS = new Set(["relevance", "name"]);

// One degree of latitude is ~111 km; longitude shrinks with the cosine of the
// latitude. Good enough to centre a search box on a point (the server filters to
// the exact radius afterwards).
const KM_PER_DEGREE_LAT = 111.0;

// FacilityFilters field -> GraphQL amenityFilter key.
const AMENITY_FILTER_MAP = {
  accessibleBuilding: "accessibleBuilding",
  accessibleBathroom: "accessibleBathroom",
  privateBathroom: "privateBathroom",
  emergencyCallSystem: "emergencyCallSystem",
  mealsIncluded: "mealsIncluded",
  housekeeping: "housekeeping",
  laundryService: "laundryService",
  parking: "parking",
  gardens: "gardens",
  socialActivities: "socialActivities",
  hairdresserBarber: "hairdresserBarberServices",
  smallPetsAllowed: "smallPetsAllowed",
  indoorSmokingRoom: "indoorSmokingRoom",
  safeOutdoorSmokingArea: "safeOutdoorSmokingArea",
};

const LEVEL_OF_CARE_MAP = {
  typeA: "typeA",
  typeB: "typeB",
  typeBSecure: "typeBSecure",
  typeC: "typeC",
  supportedLiving: "supportedLiving",
  seniorsLodge: "seniorsLodge",
};

const ROOM_TYPE_MAP = {
  privateRoom: "privateRoom",
  sharedRoom: "sharedRoom",
  oneBedroom: "oneBedroom",
  multiBedroom: "multiBedroom",
};

/** Compute the (north-east, south-west) corners of a box around a point. */
export function boundingBox(latitude, longitude, radiusKm) {
  const dLat = radiusKm / KM_PER_DEGREE_LAT;
  const cosLat = Math.cos((latitude * Math.PI) / 180) || 1e-9;
  const dLng = radiusKm / (KM_PER_DEGREE_LAT * cosLat);
  return {
    coordinateA: { latitude: latitude + dLat, longitude: longitude + dLng }, // NE
    coordinateB: { latitude: latitude - dLat, longitude: longitude - dLng }, // SW
  };
}

/**
 * Turn a filters object into the GraphQL FetchFacilityArgs. Only fields set to
 * `true` are sent, each as `[true]` (the platform's "require this" encoding).
 *
 * `hasVacancy` is intentionally NOT mapped to the API's `hasPotentialVacancy`
 * argument: verified live, that flag does not narrow the result set, so relying
 * on it would let "open space now" lie. Vacancy is filtered in `searchNear` on
 * the real reported counts instead (Constitution Art. 7.1).
 */
export function buildFetchArgs(filters) {
  if (!filters) return null;
  const args = {};

  const amenity = {};
  for (const [field, gql] of Object.entries(AMENITY_FILTER_MAP)) {
    if (filters[field] === true) amenity[gql] = [true];
  }
  if (Object.keys(amenity).length) args.amenityFilter = amenity;

  const level = {};
  for (const [field, gql] of Object.entries(LEVEL_OF_CARE_MAP)) {
    if (filters[field] === true) level[gql] = [true];
  }
  if (Object.keys(level).length) args.levelOfCareFilter = level;

  const room = {};
  for (const [field, gql] of Object.entries(ROOM_TYPE_MAP)) {
    if (filters[field] === true) room[gql] = [true];
  }
  if (Object.keys(room).length) args.roomTypeFilter = room;

  return Object.keys(args).length ? args : null;
}

function num(value) {
  return Number(value || 0);
}

function bedCounts(raw) {
  const beds = {
    typeAFunded: num(raw.typeAFundedBedCount),
    typeBFunded: num(raw.typeBFundedBedCount),
    typeBSecureFunded: num(raw.typeBSecureFundedBedCount),
    typeCFunded: num(raw.typeCFundedBedCount),
    typeAVacant: num(raw.typeAVacantBedCount),
    typeBVacant: num(raw.typeBVacantBedCount),
    typeBSecureVacant: num(raw.typeBSecureVacantBedCount),
    typeCVacant: num(raw.typeCVacantBedCount),
    supportedLiving: num(raw.supportedLivingBedCount),
    seniorLodge: num(raw.seniorLodgeBedCount),
  };
  beds.totalFunded =
    beds.typeAFunded + beds.typeBFunded + beds.typeBSecureFunded + beds.typeCFunded;
  beds.totalVacant =
    beds.typeAVacant + beds.typeBVacant + beds.typeBSecureVacant + beds.typeCVacant;
  beds.hasVacancy = beds.totalVacant > 0;
  return beds;
}

/** Plain-language care streams derived from the bed counts (summary fallback). */
export function careTypesFromBeds(beds) {
  const labels = [];
  if (beds.typeAFunded) labels.push("Type A (long-term care)");
  if (beds.typeBFunded) labels.push("Type B (designated supportive living)");
  if (beds.typeBSecureFunded) labels.push("Type B secure (memory care)");
  if (beds.typeCFunded) labels.push("Type C (supportive living)");
  if (beds.supportedLiving) labels.push("Supportive living");
  if (beds.seniorLodge) labels.push("Seniors lodge");
  return labels;
}

function titleImageUrl(raw) {
  return raw.titleImage && raw.titleImage.imageUrl ? raw.titleImage.imageUrl : null;
}

function toSummary(raw) {
  const beds = bedCounts(raw);
  return {
    id: Number(raw.id),
    name: raw.name || "",
    addressLine1: raw.addressLine1 || null,
    addressLine2: raw.addressLine2 || null,
    city: raw.city || null,
    province: raw.province || null,
    postalCode: raw.postalCode || null,
    country: raw.country || null,
    latitude: raw.latitude ?? null,
    longitude: raw.longitude ?? null,
    phoneNumber: raw.phoneNumber || null,
    beds,
    careTypes: careTypesFromBeds(beds),
    distanceKm: raw.distanceKm ?? null,
    titleImageUrl: titleImageUrl(raw),
  };
}

function titles(items) {
  return (items || []).filter((i) => i && i.title).map((i) => i.title);
}

function namedItems(items) {
  return (items || [])
    .filter((i) => i && i.title)
    .map((i) => ({
      id: Number(i.id || 0),
      title: i.title,
      funding: i.fundingType ? i.fundingType.title : null,
    }));
}

function charges(items) {
  return (items || [])
    .filter(Boolean)
    .map((c) => {
      const ct = c.chargeType || {};
      return {
        name: ct.title || "Charge",
        amount: c.amount ?? null,
        description: c.amountDescription || ct.description || null,
        isMandatory: Boolean(c.isMandatory),
        frequency: c.frequency || null,
        funding: c.fundingType ? c.fundingType.title : null,
      };
    });
}

function roomPricings(items) {
  return (items || [])
    .filter(Boolean)
    .map((p) => ({
      roomType: (p.roomType && p.roomType.title) || "Room",
      minimumFee: p.minimumFee ?? null,
      maximumFee: p.maximumFee ?? null,
      rentGearedToIncome: p.rentGearedIncome ?? null,
      funding: p.fundingType ? p.fundingType.title : null,
    }));
}

function careTypes(raw) {
  const labels = [];
  for (const item of [...(raw.ahsFundedSiteTypes || []), ...(raw.nonAhsFundedSiteTypes || [])]) {
    if (item && item.title) labels.push(item.title);
  }
  if (labels.length) return [...new Set(labels)];
  return careTypesFromBeds(bedCounts(raw));
}

/**
 * Decide if a facility is accessible and collect plain accessibility notes. The
 * Navigator marks accessibility through amenities ("Accessible (wheelchairs,
 * scooters)"), room types ("Accessible bathroom") and a count of accessible
 * spaces. Any of these makes the facility accessible; we state exactly which
 * signals were found (Art. 3, with Art. 7.1 honesty - we report what the data
 * says, not an assumption).
 */
function accessibility(raw) {
  const notes = [];
  let accessible = false;
  for (const title of titles(raw.amenityTypes)) {
    if (title.toLowerCase().includes("accessible")) {
      accessible = true;
      notes.push(title);
    }
  }
  for (const title of titles(raw.roomTypes)) {
    if (title.toLowerCase().includes("accessible")) {
      accessible = true;
      notes.push(`Room option: ${title}`);
    }
  }
  const spaces = raw.numberOfSpacesAccessibleB;
  if (spaces) {
    accessible = true;
    notes.push(`${spaces} accessible space(s) reported`);
  }
  return { accessible, notes: [...new Set(notes)] };
}

function photos(raw) {
  const urls = [];
  for (const image of raw.images || []) {
    if (image && image.imageUrl) urls.push(image.imageUrl);
  }
  const title = titleImageUrl(raw);
  if (title && !urls.includes(title)) urls.unshift(title);
  return urls;
}

function toDetails(raw) {
  const { accessible, notes } = accessibility(raw);
  return {
    id: Number(raw.id),
    name: raw.name || "",
    accessible,
    accessibilityNotes: notes,
    status: raw.status || null,
    description: raw.description || null,
    addressLine1: raw.addressLine1 || null,
    addressLine2: raw.addressLine2 || null,
    city: raw.city || null,
    province: raw.province || null,
    postalCode: raw.postalCode || null,
    country: raw.country || null,
    latitude: raw.latitude ?? null,
    longitude: raw.longitude ?? null,
    phoneNumber: raw.phoneNumber || null,
    faxNumber: raw.faxNumber || null,
    siteEmail: raw.siteEmail || null,
    operatorName: raw.operator_name || null,
    operatorType: raw.operator_type || null,
    operatorWebsite: raw.operatorWebsite || null,
    virtualTourWebsite: raw.virtualTourWebsite || null,
    beds: bedCounts(raw),
    numberOfSpacesPrivateRoom: raw.numberOfSpacesPrivateRoom ?? null,
    numberOfSpacesSharedRoom: raw.numberOfSpacesSharedRoom ?? null,
    numberOfSpacesOneBedroom: raw.numberOfSpacesOneBedroom ?? null,
    numberOfSpacesMultiBedroom: raw.numberOfSpacesMultiBedroom ?? null,
    numberOfSpacesAccessible: raw.numberOfSpacesAccessibleB ?? null,
    roomTypes: titles(raw.roomTypes),
    roomPricings: roomPricings(raw.roomPricings),
    careTypes: careTypes(raw),
    amenities: titles(raw.amenityTypes),
    foodServices: namedItems(raw.foodServiceTypes),
    siteServices: namedItems(raw.serviceTypes),
    securityServices: namedItems(raw.securityServiceTypes),
    transportationServices: namedItems(raw.transportationServiceTypes),
    charges: charges(raw.facilityCharges),
    hasSmokingPolicy: raw.hasSmokingPolicy ?? null,
    seniorLodgeDesignation: raw.seniorLodgeDesignation || null,
    accreditationStatus: raw.accreditationStatus ? raw.accreditationStatus.title : null,
    accreditationOrganizationName: raw.accreditationOrganizationName || null,
    accreditationOrganizationUrl: raw.accreditationOrganizationUrl || null,
    accommodationStandardsUrl: raw.accomodationsStandardsUrl || null,
    photos: photos(raw),
  };
}

export class NavigatorProvider {
  constructor({ config, client } = {}) {
    this.config = config;
    this.client =
      client ||
      new NavigatorClient({
        apiUrl: config.apiUrl,
        userAgent: config.userAgent,
        timeoutMs: config.httpTimeoutMs,
      });
  }

  async searchByName(searchTerm, { sortBy = "relevance", limit = 25 } = {}) {
    const sort = VALID_SORTS.has(sortBy) ? sortBy : "relevance";
    const raw = await this.client.findAllBySearchTerm(searchTerm, sort, null);
    const summaries = raw.map(toSummary);
    return limit ? summaries.slice(0, Math.max(0, limit)) : summaries;
  }

  async countByName(searchTerm) {
    return this.client.countBySearchTerm(searchTerm);
  }

  async searchNear({ latitude, longitude, radiusKm, filters = null, limit = 25 }) {
    const radius = this._clampRadius(radiusKm);
    const { coordinateA, coordinateB } = boundingBox(latitude, longitude, radius);
    const fetchArgs = buildFetchArgs(filters);
    const raw = await this.client.facilitiesByBoundingBox({
      coordinateA,
      coordinateB,
      radiusKm: radius,
      fetchArgs,
    });
    let summaries = raw.map(toSummary);
    // Vacancy is filtered here, on the actual reported vacant counts, rather than
    // via the API's hasPotentialVacancy flag - which (verified live) does not
    // narrow the result set. Doing it client-side keeps the promise the tool
    // makes ("an open space now") truthful (Constitution Art. 7.1).
    if (filters && filters.hasVacancy === true) {
      summaries = summaries.filter((s) => s.beds.hasVacancy);
    }
    // The API does not guarantee distance ordering; sort nearest-first.
    summaries.sort(
      (a, b) =>
        (a.distanceKm == null ? Infinity : a.distanceKm) -
        (b.distanceKm == null ? Infinity : b.distanceKm)
    );
    return limit ? summaries.slice(0, Math.max(0, limit)) : summaries;
  }

  async getDetails(facilityId) {
    const raw = await this.client.facility(facilityId);
    if (!raw) {
      throw new InvalidInputError(
        `I could not find a facility with id ${facilityId}. Use a search first to ` +
          "get a valid facility id."
      );
    }
    return toDetails(raw);
  }

  async fetchImage(url) {
    return this.client.fetchImage(url);
  }

  _clampRadius(radiusKm) {
    if (!radiusKm || radiusKm <= 0) return this.config.defaultRadiusKm;
    return Math.min(radiusKm, this.config.maxRadiusKm);
  }
}

// Exported for unit tests.
export const _internal = { toSummary, toDetails, bedCounts, accessibility };
