# Alberta Assisted Living Navigator — verified API findings

What the public Navigator API actually does, recorded from real traffic and live
probing rather than assumed (The Open State AGENTS.md: *"When the spec and
reality disagree, reality wins. Flag the discrepancy."*). This is the contract
`src/providers/` (the Node GraphQL client and provider) is built against.

## Source

- **Front end:** `https://alnavigator.alberta.ca` (the Alberta Assisted Living
  Navigator).
- **Data API:** `https://alacapacity.api.alberta.ca/graphql` — a single GraphQL
  endpoint (`POST`). Backend is Express behind Cloudflare.
- Findings were derived from a captured HAR of a real session and confirmed with
  live read-only queries (GraphQL introspection plus sample calls).

## Authentication — none (for the read surface)

The citizen-facing queries require **no authentication**: no API key, no
`Authorization` header, no cookie. The only access control on the API is browser
**CORS**, which restricts `Origin: https://alnavigator.alberta.ca`. CORS is
enforced by browsers, not servers, so a server-side client is not subject to it
and receives `HTTP 200` with an honest `User-Agent` and no `Origin` header
(verified). We therefore do **not** spoof a browser; we identify ourselves
honestly (Constitution Art. 7.3, 10.2).

Some queries and **all mutations** *do* require an operator login and return
`Unauthorized` without one (see below). Those are out of scope by design.

## Operations

### Read queries

| Query | Args | Returns | Used? |
|---|---|---|---|
| `findAllBySearchTerm` | `searchTerm: String!`, `fetchFacilityArgs`, `sortBy: FacilitySearchSortBy` | `[FacilityMapItem]` (summary shape) | ✅ `search_by_name` |
| `countBySearchTerm` | `searchTerm: String!`, `fetchFacilityArgs` | `Int` | ✅ `count_by_name` |
| `facilitiesByBoundingBox` | `coordinateA: CoordinateDto!`, `coordinateB: CoordinateDto!`, `fetchFacilityArgs`, `radiusKm: Int` | `[FacilityMapItem]` (summary shape) | ✅ `search_near` |
| `facility` | `id: Int!` | `FacilityEntity` (full detail) | ✅ `get_details` |
| `facilitiesForSitemap` | — | `[{id, name, ...}]` (961 facilities) | ➖ not wrapped (search/near cover discovery) |
| `capacityReport` / `capacityReports` / `count` / `getFirstWeekReportId` / `user` | various | capacity-reporting data | ❌ **`Unauthorized`** — operator-only |

### Mutations (all out of scope)

`generateCapacityReports`, `submitAndCompleteCapacityReport`,
`updateAllFacilityVacantBedCounts`, `updateCapacityReport`. These are how
operators report their capacity; they require a login and **change records**. A
citizen-facing assistive tool never calls them (Constitution Art. 2, 10).

## `FetchFacilityArgs` — the filters

Available on `findAllBySearchTerm`, `countBySearchTerm`, and
`facilitiesByBoundingBox`:

- `amenityFilter: AmenityFilter` — each field is `[Boolean!]`; send `[true]` to
  require it. Fields: `accessibleBuilding`, `accessibleBathroom`,
  `privateBathroom`, `emergencyCallSystem`, `mealsIncluded`, `housekeeping`,
  `laundryService`, `parking`, `gardens`, `socialActivities`,
  `hairdresserBarberServices`, `smallPetsAllowed`, `indoorSmokingRoom`,
  `safeOutdoorSmokingArea`.
- `levelOfCareFilter: LevelOfCareFilter` — `typeA`, `typeB`, `typeBSecure`,
  `typeC`, `supportedLiving`, `seniorsLodge` (each `[Boolean!]`).
- `roomTypeFilter: RoomTypeFilter` — `privateRoom`, `sharedRoom`, `oneBedroom`,
  `multiBedroom` (each `[Boolean!]`).
- `hasPotentialVacancy: Boolean` — **does not narrow results** (see quirks).
- `skip: Int`, `take: Int` — pagination (see quirks for the `take` cap).

`FacilitySearchSortBy` enum: `relevance`, `name`.

**Verified filter behaviour** (200 km box centred on Edmonton, 532 facilities
unfiltered): `amenityFilter.accessibleBuilding=[true]` → 224;
`levelOfCareFilter.seniorsLodge=[true]` → 69. Filters work and compose.

## Geometry — `facilitiesByBoundingBox`

- `coordinateA` is the **north-east** corner, `coordinateB` the **south-west**
  corner (matches the front end). `CoordinateDto` is `{latitude, longitude}`.
- `radiusKm` filters to a circle inside the box; each result carries
  `distanceKm` measured **from the box centre**. So to search "within R km of a
  point", centre a box of half-size R on the point and pass `radiusKm = R`
  (implemented in `boundingBox()` in `src/providers/navigator-provider.mjs`).
  Verified: a 5 km box returns
  distances 0.6–5.0 km; a 25 km box, 0.6–24.8 km.
- Results are **not** guaranteed to be distance-sorted; we sort client-side.

## Data shapes

**Summary** (`findAllBySearchTerm`, `facilitiesByBoundingBox`): `id`, `name`,
address parts, `city`, `province`, `postalCode`, `country`, `latitude`,
`longitude`, `phoneNumber`, the eight `type{A,B,BSecure,C}{Funded,Vacant}BedCount`
fields, `supportedLivingBedCount`, `seniorLodgeBedCount`, `distanceKm`,
`fundingTypeId`, `titleImage{imageUrl, altText}`.

**Detail** (`facility`): everything in the summary plus `description`, `status`,
`operator_name`/`operator_type`/`operatorWebsite`, `amenityTypes`, `roomTypes`,
`roomPricings` (min/max fee, rent-geared-to-income, funding), `facilityCharges`
(amount, frequency, mandatory, funding, charge type), `foodServiceTypes`,
`serviceTypes`, `securityServiceTypes`, `transportationServiceTypes`,
`ahsFundedSiteTypes`/`nonAhsFundedSiteTypes` (care-type labels),
`numberOfSpaces{PrivateRoom,SharedRoom,OneBedroom,MultiBedroom,AccessibleB}`,
`accreditationStatus`/`accreditationOrganizationName`/`...Url`,
`accomodationsStandardsUrl` (the official standards & licensing record),
`hasSmokingPolicy`, `seniorLodgeDesignation`, `images`, `vacancyType`,
`siteEmail`, `faxNumber`, `virtualTourWebsite`.

### Funding types

Two values appear throughout (`fundingType.title`): **"Accessed Through AHS Case
Manager"** (publicly funded; placement via an AHS case manager) and **"Accessed
Through Site Directly"** (arranged privately with the operator). The tool
explains this to citizens and never tries to "apply" for either.

### Care types / bed counts

`typeA` = long-term care; `typeB` = designated supportive living; `typeBSecure`
= secure/memory care; `typeC` = supportive living (enhanced); plus
`supportedLiving` and `seniorLodge` streams. Each has a *funded* count
(operating capacity) and, for Type A–C, a *vacant* count.

### Images

Hosted on `alamedia.alberta.ca`. The client only fetches photos from that host
(SSRF guard).

## Quirks and limits (flagged, not worked around silently)

1. **`hasPotentialVacancy` is effectively a no-op.** Setting it `true` did not
   reduce the 532-facility result set. To honour an "open space now" request
   truthfully (Art. 7.1), vacancy is filtered **client-side** on the real
   `*VacantBedCount` fields, and `hasPotentialVacancy` is not sent.
2. **`take` has a cap.** `take: 1000` → `Bad Request`; `take: 50`/`100` are
   fine. For `facilitiesByBoundingBox`, `take` does not appear to limit the
   result count anyway (returned all 532 with `take: 50`). We do not paginate;
   we fetch within the radius and limit client-side after sorting by distance.
3. **Vacancy is a snapshot**, self-reported by operators (`createdBy: SYSTEM`,
   `sharepoint` provenance seen on records). Stated as such in every output.
4. **Supportive living and seniors lodge report funded capacity only** — no live
   vacant count — so "open space now" only ever reflects Type A–C.
5. **Postal-code geocoding is unreliable.** Nominatim lacks full Canadian
   postal-code coverage; towns and street addresses resolve well. Failure is
   surfaced plainly and the citizen is asked to refine.

## Politeness

Interactive, low-volume use over stdio. Honest `User-Agent`, TLS certificate
verification always on (Node defaults, with `NODE_EXTRA_CA_CERTS` honoured for
proxy CAs), and no calls to operator/write endpoints (Constitution Art. 7.3).
