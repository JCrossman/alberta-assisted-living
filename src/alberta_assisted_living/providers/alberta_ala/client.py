"""Thin HTTP client for the Alberta Assisted Living Navigator GraphQL API.

Speaks to the public, unauthenticated endpoint behind
https://alnavigator.alberta.ca (``alacapacity.api.alberta.ca/graphql``). The
endpoint contract here was verified live and recorded in
docs/alberta-assisted-living-api-findings.md.

This client only *reads* public facility data. It never logs in, applies,
reserves a space, or handles citizen credentials (Constitution Articles 1, 2).
We reach the service through its own data interface, the way the Navigator's own
web app does, and identify ourselves honestly rather than impersonate a browser
(Art. 10.2, 10.3) - the API accepts an honest User-Agent.

Failures surface as a typed :class:`UpstreamError` so callers can fail visibly
rather than guess (Constitution Art. 7.2).
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from alberta_assisted_living.providers.base import UpstreamError
from alberta_assisted_living.tls import verify_setting

# The Navigator's own image host (used to validate photo URLs before fetching).
IMAGE_HOST = "alamedia.alberta.ca"

# --- GraphQL documents (verified against the live API) ----------------------
# Field sets match what the Navigator's web app requests, so we ask for exactly
# the public data the service already serves to its own front end.

_SUMMARY_FIELDS = """
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
"""

SEARCH_QUERY = (
    """
query SearchFacilitiesByName($searchTerm: String!, $fetchFacilityArgs: FetchFacilityArgs, $sortBy: FacilitySearchSortBy) {
  findAllBySearchTerm(searchTerm: $searchTerm, fetchFacilityArgs: $fetchFacilityArgs, sortBy: $sortBy) {
"""
    + _SUMMARY_FIELDS
    + """
  }
}
"""
)

COUNT_QUERY = """
query CountFacilitiesByName($searchTerm: String!, $fetchFacilityArgs: FetchFacilityArgs) {
  countBySearchTerm(searchTerm: $searchTerm, fetchFacilityArgs: $fetchFacilityArgs)
}
"""

BOUNDING_BOX_QUERY = (
    """
query GetFacilitiesByBoundingBox($coordinateA: CoordinateDto!, $coordinateB: CoordinateDto!, $fetchFacilityArgs: FetchFacilityArgs, $radiusKm: Int) {
  facilitiesByBoundingBox(coordinateA: $coordinateA, coordinateB: $coordinateB, fetchFacilityArgs: $fetchFacilityArgs, radiusKm: $radiusKm) {
"""
    + _SUMMARY_FIELDS
    + """
  }
}
"""
)

# Full facility detail. Mirrors the Navigator web app's own ``getFacility`` query.
FACILITY_QUERY = """
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
}
"""


class NavigatorClient:
    """Read-only GraphQL client for the Alberta Assisted Living Navigator."""

    def __init__(
        self,
        *,
        api_url: str,
        user_agent: str,
        timeout: float = 30.0,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._api_url = api_url
        # An injected client (e.g. with a MockTransport) makes the provider fully
        # testable offline, with no live network calls in CI.
        self._client = http_client or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            verify=verify_setting(),
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json",
                "Accept-Language": "en-CA,en;q=0.9",
                "Content-Type": "application/json",
            },
        )

    # -- low-level ----------------------------------------------------------

    def execute(
        self,
        query: str,
        variables: dict[str, Any],
        operation_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """POST a GraphQL query and return its ``data`` object.

        Raises :class:`UpstreamError` on a network failure, an HTTP error, or a
        GraphQL ``errors`` payload, so the caller can report the problem plainly
        (Constitution Art. 7.2) instead of acting on a half-result.
        """
        payload: dict[str, Any] = {"query": query, "variables": variables}
        if operation_name:
            payload["operationName"] = operation_name
        try:
            resp = self._client.post(self._api_url, json=payload)
        except httpx.HTTPError as exc:  # network / timeout
            raise UpstreamError(
                f"Could not reach the Alberta Assisted Living Navigator ({exc})."
            ) from exc

        if resp.status_code >= 400:
            raise UpstreamError(
                "The Alberta Assisted Living Navigator returned an error "
                f"(HTTP {resp.status_code})."
            )
        try:
            body = resp.json()
        except ValueError as exc:
            raise UpstreamError(
                "The Alberta Assisted Living Navigator returned an unexpected "
                "(non-JSON) response."
            ) from exc

        if body.get("errors"):
            message = "; ".join(
                str(e.get("message", "")) for e in body["errors"] if e.get("message")
            )
            raise UpstreamError(
                "The Alberta Assisted Living Navigator rejected the request"
                + (f": {message}" if message else ".")
            )
        data = body.get("data")
        if data is None:
            raise UpstreamError(
                "The Alberta Assisted Living Navigator returned no data."
            )
        return data

    def fetch_image(self, url: str) -> Optional[tuple[bytes, str]]:
        """Fetch a facility photo by absolute URL, returning ``(bytes, format)``.

        Best-effort: a photo that does not load must never fail the surrounding
        tool call. Only ``https`` URLs on the Navigator's own image host are
        fetched, so this can never be turned into a general-purpose URL fetcher
        (SSRF guard; Constitution Art. 9.3 - treat external content carefully).
        """
        if not url.startswith("https://"):
            return None
        host = httpx.URL(url).host
        if host != IMAGE_HOST:
            return None
        try:
            resp = self._client.get(url)
        except httpx.HTTPError:
            return None
        if resp.status_code != 200:
            return None
        content_type = resp.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            return None
        fmt = content_type.split("/", 1)[1].split(";")[0].strip() or "jpeg"
        return resp.content, fmt

    # -- typed endpoints ----------------------------------------------------

    def find_all_by_search_term(
        self, search_term: str, sort_by: str, fetch_args: Optional[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        data = self.execute(
            SEARCH_QUERY,
            {"searchTerm": search_term, "sortBy": sort_by, "fetchFacilityArgs": fetch_args},
            operation_name="SearchFacilitiesByName",
        )
        return data.get("findAllBySearchTerm") or []

    def count_by_search_term(
        self, search_term: str, fetch_args: Optional[dict[str, Any]] = None
    ) -> int:
        data = self.execute(
            COUNT_QUERY,
            {"searchTerm": search_term, "fetchFacilityArgs": fetch_args},
            operation_name="CountFacilitiesByName",
        )
        return int(data.get("countBySearchTerm") or 0)

    def facilities_by_bounding_box(
        self,
        *,
        coordinate_a: dict[str, float],
        coordinate_b: dict[str, float],
        radius_km: int,
        fetch_args: Optional[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        data = self.execute(
            BOUNDING_BOX_QUERY,
            {
                "coordinateA": coordinate_a,
                "coordinateB": coordinate_b,
                "radiusKm": radius_km,
                "fetchFacilityArgs": fetch_args,
            },
            operation_name="GetFacilitiesByBoundingBox",
        )
        return data.get("facilitiesByBoundingBox") or []

    def facility(self, facility_id: int) -> Optional[dict[str, Any]]:
        data = self.execute(
            FACILITY_QUERY, {"id": facility_id}, operation_name="getFacility"
        )
        return data.get("facility")

    def close(self) -> None:
        self._client.close()
