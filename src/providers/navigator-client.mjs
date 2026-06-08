/**
 * Thin HTTP client for the Alberta Assisted Living Navigator GraphQL API.
 *
 * Speaks to the public, unauthenticated endpoint behind
 * https://alnavigator.alberta.ca (alacapacity.api.alberta.ca/graphql). The
 * contract here was verified live and recorded in
 * docs/alberta-assisted-living-api-findings.md.
 *
 * Read-only. It never logs in, applies, reserves a space, or handles citizen
 * credentials (Constitution Articles 1, 2). It reaches the service through its
 * own data interface, the way the Navigator's web app does, and identifies
 * itself honestly rather than impersonate a browser (Art. 10.2, 10.3).
 *
 * Failures surface as a typed UpstreamError so callers can fail visibly rather
 * than guess (Constitution Art. 7.2).
 */

import { UpstreamError } from "../errors.mjs";

/** The Navigator's own image host (used to validate photo URLs before fetching). */
const IMAGE_HOST = "alamedia.alberta.ca";

// Field set requested for search and map results. Matches what the Navigator's
// web app asks for, so we read exactly the public data it already serves.
const SUMMARY_FIELDS = `
    id
    name
    city
    latitude
    longitude
    addressLine1
    addressLine2
    country
    phoneNumber
    postalCode
    province
    typeAFundedBedCount
    typeBFundedBedCount
    typeBSecureFundedBedCount
    typeCFundedBedCount
    typeAVacantBedCount
    typeBVacantBedCount
    typeBSecureVacantBedCount
    typeCVacantBedCount
    supportedLivingBedCount
    seniorLodgeBedCount
    distanceKm
    fundingTypeId
    titleImage {
      imageUrl
      altText
    }
`;

export const SEARCH_QUERY = `
query SearchFacilitiesByName($searchTerm: String!, $fetchFacilityArgs: FetchFacilityArgs, $sortBy: FacilitySearchSortBy) {
  findAllBySearchTerm(searchTerm: $searchTerm, fetchFacilityArgs: $fetchFacilityArgs, sortBy: $sortBy) {
${SUMMARY_FIELDS}
  }
}`;

export const COUNT_QUERY = `
query CountFacilitiesByName($searchTerm: String!, $fetchFacilityArgs: FetchFacilityArgs) {
  countBySearchTerm(searchTerm: $searchTerm, fetchFacilityArgs: $fetchFacilityArgs)
}`;

export const BOUNDING_BOX_QUERY = `
query GetFacilitiesByBoundingBox($coordinateA: CoordinateDto!, $coordinateB: CoordinateDto!, $fetchFacilityArgs: FetchFacilityArgs, $radiusKm: Int) {
  facilitiesByBoundingBox(coordinateA: $coordinateA, coordinateB: $coordinateB, fetchFacilityArgs: $fetchFacilityArgs, radiusKm: $radiusKm) {
${SUMMARY_FIELDS}
  }
}`;

// Full facility detail. Mirrors the Navigator web app's own getFacility query.
export const FACILITY_QUERY = `
query getFacility($id: Int!) {
  facility(id: $id) {
    id
    name
    addressLine1
    addressLine2
    operator_type
    amenityTypes { id title }
    ahsFundedSiteTypes { id title }
    buildDate
    city
    corridor
    country
    description
    accreditationStatus { id title }
    accomodationsStandardsUrl
    accreditationOrganizationName
    accreditationOrganizationUrl
    facilityCharges {
      id
      amount
      amountDescription
      isMandatory
      frequency
      refundAmount
      refundType
      fundingType { id title }
      chargeType { id title description active code }
    }
    faxNumber
    foodServiceTypes { id title fundingType { id title } }
    fundingType { id title }
    hasSmokingPolicy
    images { imageUrl altText }
    latitude
    longitude
    nonAhsFundedSiteTypes { id title }
    numberOfSpacesAccessibleB
    numberOfSpacesMultiBedroom
    numberOfSpacesOneBedroom
    numberOfSpacesPrivateRoom
    numberOfSpacesSharedRoom
    operatorWebsite
    operator_name
    organizationId
    phoneNumber
    postalCode
    province
    roomPricings {
      id
      fundingType { id title }
      roomType { id title displayOrder }
      maximumFee
      minimumFee
      rentGearedIncome
    }
    roomTypes { id title }
    securityServiceTypes { id title }
    seniorLodgeBedCount
    seniorLodgeDesignation
    serviceTypes { id title fundingType { id title } }
    siteEmail
    status
    supportedLivingBedCount
    titleImage { imageUrl altText }
    transportationServiceTypes { id title }
    typeAFundedBedCount
    typeBFundedBedCount
    typeBSecureFundedBedCount
    typeCFundedBedCount
    typeAVacantBedCount
    typeBVacantBedCount
    typeBSecureVacantBedCount
    typeCVacantBedCount
    vacancyType { id title }
    virtualTourWebsite
    zoneId
  }
}`;

export class NavigatorClient {
  /**
   * @param {object} opts
   * @param {string} opts.apiUrl
   * @param {string} opts.userAgent
   * @param {number} [opts.timeoutMs]
   * @param {typeof fetch} [opts.fetchImpl] injectable for offline tests
   */
  constructor({ apiUrl, userAgent, timeoutMs = 30000, fetchImpl }) {
    this.apiUrl = apiUrl;
    this.userAgent = userAgent;
    this.timeoutMs = timeoutMs;
    this._fetch = fetchImpl || globalThis.fetch;
  }

  async _withTimeout(run) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      return await run(controller.signal);
    } finally {
      clearTimeout(timer);
    }
  }

  /**
   * POST a GraphQL query and return its `data` object. Raises UpstreamError on a
   * network failure, an HTTP error, or a GraphQL `errors` payload, so the caller
   * can report the problem plainly (Art. 7.2) instead of acting on a half-result.
   */
  async execute(query, variables, operationName) {
    let resp;
    try {
      resp = await this._withTimeout((signal) =>
        this._fetch(this.apiUrl, {
          method: "POST",
          signal,
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
            "Accept-Language": "en-CA,en;q=0.9",
            "User-Agent": this.userAgent,
          },
          body: JSON.stringify({ query, variables, operationName }),
        })
      );
    } catch (err) {
      throw new UpstreamError(
        `Could not reach the Alberta Assisted Living Navigator (${err.message}).`
      );
    }

    if (!resp.ok) {
      throw new UpstreamError(
        `The Alberta Assisted Living Navigator returned an error (HTTP ${resp.status}).`
      );
    }
    let body;
    try {
      body = await resp.json();
    } catch {
      throw new UpstreamError(
        "The Alberta Assisted Living Navigator returned an unexpected (non-JSON) response."
      );
    }
    if (body.errors && body.errors.length) {
      const message = body.errors.map((e) => e?.message).filter(Boolean).join("; ");
      throw new UpstreamError(
        "The Alberta Assisted Living Navigator rejected the request" +
          (message ? `: ${message}` : ".")
      );
    }
    if (body.data == null) {
      throw new UpstreamError("The Alberta Assisted Living Navigator returned no data.");
    }
    return body.data;
  }

  /**
   * Fetch a facility photo by absolute URL, returning { data: Buffer, format }.
   * Best-effort: returns null on any problem. Only https URLs on the Navigator's
   * own image host are fetched, so this can never be a general-purpose URL
   * fetcher (SSRF guard; Constitution Art. 9.3).
   */
  async fetchImage(url) {
    let parsed;
    try {
      parsed = new URL(url);
    } catch {
      return null;
    }
    if (parsed.protocol !== "https:" || parsed.host !== IMAGE_HOST) return null;
    let resp;
    try {
      resp = await this._withTimeout((signal) => this._fetch(url, { signal }));
    } catch {
      return null;
    }
    if (!resp.ok) return null;
    const contentType = resp.headers.get("content-type") || "";
    if (!contentType.startsWith("image/")) return null;
    const format = contentType.split("/")[1].split(";")[0].trim() || "jpeg";
    const data = Buffer.from(await resp.arrayBuffer());
    return { data, format, mimeType: `image/${format}` };
  }

  // -- typed endpoints ----------------------------------------------------

  async findAllBySearchTerm(searchTerm, sortBy, fetchArgs) {
    const data = await this.execute(
      SEARCH_QUERY,
      { searchTerm, sortBy, fetchFacilityArgs: fetchArgs ?? null },
      "SearchFacilitiesByName"
    );
    return data.findAllBySearchTerm || [];
  }

  async countBySearchTerm(searchTerm, fetchArgs = null) {
    const data = await this.execute(
      COUNT_QUERY,
      { searchTerm, fetchFacilityArgs: fetchArgs },
      "CountFacilitiesByName"
    );
    return Number(data.countBySearchTerm || 0);
  }

  async facilitiesByBoundingBox({ coordinateA, coordinateB, radiusKm, fetchArgs }) {
    const data = await this.execute(
      BOUNDING_BOX_QUERY,
      {
        coordinateA,
        coordinateB,
        radiusKm,
        fetchFacilityArgs: fetchArgs ?? null,
      },
      "GetFacilitiesByBoundingBox"
    );
    return data.facilitiesByBoundingBox || [];
  }

  async facility(id) {
    const data = await this.execute(FACILITY_QUERY, { id }, "getFacility");
    return data.facility || null;
  }
}
