"""Alberta Assisted Living Navigator provider.

Implements the platform-agnostic :class:`FacilityProvider` interface for the
Government of Alberta's Assisted Living Navigator. Tools call this through the
interface and never touch the GraphQL client directly, so another province could
be added later behind the same interface without changing tool code.

What it delivers, against the verified API
(docs/alberta-assisted-living-api-findings.md):

- search facilities by name or text (``findAllBySearchTerm``);
- count matches (``countBySearchTerm``);
- search near a place, nearest first, with the full filter set - care level,
  room type, **accessibility (first-class)**, other amenities, and current
  vacancy (``facilitiesByBoundingBox``);
- full plain-language detail for one facility, including accessibility,
  capacity, room pricing, charges, services, accreditation and the official
  accommodation-standards reference (``facility``).

All read-only. Nothing applies for, reserves, or holds a space (Art. 1, 2).
The operator capacity-reporting queries and every mutation the API exposes are
deliberately *not* wrapped here: they require an operator login and/or change
records, neither of which belongs in a citizen-facing assistive tool.
"""

from __future__ import annotations

import math
from typing import Any, Optional

from alberta_assisted_living.config import Config
from alberta_assisted_living.providers.alberta_ala.client import NavigatorClient
from alberta_assisted_living.providers.base import (
    BedCounts,
    Charge,
    FacilityDetails,
    FacilityFilters,
    FacilityProvider,
    FacilitySummary,
    InvalidInputError,
    NamedItem,
    RoomPricing,
)

NAVIGATOR_NAME = "Alberta Assisted Living Navigator"

_VALID_SORTS = {"relevance", "name"}

# One degree of latitude is ~111 km; longitude shrinks with the cosine of the
# latitude. Good enough to centre a search box on a point (the server filters to
# the exact radius afterwards).
_KM_PER_DEGREE_LAT = 111.0

# FacilityFilters field -> GraphQL amenityFilter key.
_AMENITY_FILTER_MAP = {
    "accessible_building": "accessibleBuilding",
    "accessible_bathroom": "accessibleBathroom",
    "private_bathroom": "privateBathroom",
    "emergency_call_system": "emergencyCallSystem",
    "meals_included": "mealsIncluded",
    "housekeeping": "housekeeping",
    "laundry_service": "laundryService",
    "parking": "parking",
    "gardens": "gardens",
    "social_activities": "socialActivities",
    "hairdresser_barber": "hairdresserBarberServices",
    "small_pets_allowed": "smallPetsAllowed",
    "indoor_smoking_room": "indoorSmokingRoom",
    "safe_outdoor_smoking_area": "safeOutdoorSmokingArea",
}

# FacilityFilters field -> GraphQL levelOfCareFilter key.
_LEVEL_OF_CARE_MAP = {
    "type_a": "typeA",
    "type_b": "typeB",
    "type_b_secure": "typeBSecure",
    "type_c": "typeC",
    "supported_living": "supportedLiving",
    "seniors_lodge": "seniorsLodge",
}

# FacilityFilters field -> GraphQL roomTypeFilter key.
_ROOM_TYPE_MAP = {
    "private_room": "privateRoom",
    "shared_room": "sharedRoom",
    "one_bedroom": "oneBedroom",
    "multi_bedroom": "multiBedroom",
}


class NavigatorProvider(FacilityProvider):
    """Alberta Assisted Living Navigator, via its public GraphQL API."""

    name = "alberta_navigator"

    def __init__(
        self,
        client: Optional[NavigatorClient] = None,
        *,
        config: Optional[Config] = None,
    ) -> None:
        self._config = config or Config.from_env()
        self._client = client or NavigatorClient(
            api_url=self._config.api_url,
            user_agent=self._config.user_agent,
            timeout=self._config.http_timeout_seconds,
        )

    # -- interface ----------------------------------------------------------

    def search_by_name(
        self, search_term: str, *, sort_by: str = "relevance", limit: int = 25
    ) -> list[FacilitySummary]:
        sort = sort_by if sort_by in _VALID_SORTS else "relevance"
        raw = self._client.find_all_by_search_term(search_term, sort, None)
        summaries = [_to_summary(r, self.name) for r in raw]
        return summaries[: max(0, limit)] if limit else summaries

    def count_by_name(self, search_term: str) -> int:
        return self._client.count_by_search_term(search_term)

    def search_near(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_km: int,
        filters: Optional[FacilityFilters] = None,
        limit: int = 25,
    ) -> list[FacilitySummary]:
        radius = self._clamp_radius(radius_km)
        coordinate_a, coordinate_b = _bounding_box(latitude, longitude, radius)
        fetch_args = _build_fetch_args(filters)
        raw = self._client.facilities_by_bounding_box(
            coordinate_a=coordinate_a,
            coordinate_b=coordinate_b,
            radius_km=radius,
            fetch_args=fetch_args,
        )
        summaries = [_to_summary(r, self.name) for r in raw]
        # Vacancy is filtered here, on the actual reported vacant counts, rather
        # than via the API's hasPotentialVacancy flag - which (verified live) does
        # not narrow the result set. Doing it client-side keeps the promise the
        # tool makes ("an open space now") truthful (Constitution Art. 7.1).
        if filters is not None and filters.has_vacancy is True:
            summaries = [s for s in summaries if s.beds.has_vacancy]
        # The API does not guarantee distance ordering; sort nearest-first so the
        # citizen sees the closest options at the top.
        summaries.sort(key=lambda s: (s.distance_km is None, s.distance_km or 0.0))
        return summaries[: max(0, limit)] if limit else summaries

    def get_details(self, facility_id: int) -> FacilityDetails:
        raw = self._client.facility(facility_id)
        if not raw:
            raise InvalidInputError(
                f"I could not find a facility with id {facility_id}. Use a search "
                "first to get a valid facility id."
            )
        return _to_details(raw, self.name)

    def fetch_image(self, url: str) -> Optional[tuple[bytes, str]]:
        return self._client.fetch_image(url)

    # -- helpers ------------------------------------------------------------

    def _clamp_radius(self, radius_km: int) -> int:
        if radius_km <= 0:
            return self._config.default_radius_km
        return min(radius_km, self._config.max_radius_km)


# -- module-level pure helpers ---------------------------------------------


def _bounding_box(
    latitude: float, longitude: float, radius_km: int
) -> tuple[dict[str, float], dict[str, float]]:
    """Return the (north-east, south-west) corners of a box around a point.

    Matches the corner order the Navigator's web app sends (coordinateA is the
    higher-latitude / higher-longitude corner). The server filters to the actual
    ``radiusKm`` circle and reports each facility's distance from the centre.
    """
    d_lat = radius_km / _KM_PER_DEGREE_LAT
    cos_lat = math.cos(math.radians(latitude)) or 1e-9
    d_lng = radius_km / (_KM_PER_DEGREE_LAT * cos_lat)
    north_east = {"latitude": latitude + d_lat, "longitude": longitude + d_lng}
    south_west = {"latitude": latitude - d_lat, "longitude": longitude - d_lng}
    return north_east, south_west


def _build_fetch_args(filters: Optional[FacilityFilters]) -> Optional[dict[str, Any]]:
    """Turn a :class:`FacilityFilters` into the GraphQL ``FetchFacilityArgs``.

    Only fields the citizen set to ``True`` are sent, each as ``[true]`` (the
    platform's "require this" encoding). An empty filter sends nothing, so the
    search behaves as if unfiltered.
    """
    if filters is None or filters.is_empty():
        return None

    args: dict[str, Any] = {}

    amenity = {
        gql: [True]
        for field, gql in _AMENITY_FILTER_MAP.items()
        if getattr(filters, field) is True
    }
    if amenity:
        args["amenityFilter"] = amenity

    level = {
        gql: [True]
        for field, gql in _LEVEL_OF_CARE_MAP.items()
        if getattr(filters, field) is True
    }
    if level:
        args["levelOfCareFilter"] = level

    room = {
        gql: [True]
        for field, gql in _ROOM_TYPE_MAP.items()
        if getattr(filters, field) is True
    }
    if room:
        args["roomTypeFilter"] = room

    # NOTE: ``has_vacancy`` is deliberately *not* sent as the API's
    # ``hasPotentialVacancy`` argument. Verified live, that flag does not reduce
    # the result set, so relying on it would let "open space now" lie. Vacancy is
    # filtered in the provider on the real reported counts instead (Art. 7.1).

    return args or None


def _bed_counts(raw: dict[str, Any]) -> BedCounts:
    def n(key: str) -> int:
        return int(raw.get(key) or 0)

    return BedCounts(
        type_a_funded=n("typeAFundedBedCount"),
        type_b_funded=n("typeBFundedBedCount"),
        type_b_secure_funded=n("typeBSecureFundedBedCount"),
        type_c_funded=n("typeCFundedBedCount"),
        type_a_vacant=n("typeAVacantBedCount"),
        type_b_vacant=n("typeBVacantBedCount"),
        type_b_secure_vacant=n("typeBSecureVacantBedCount"),
        type_c_vacant=n("typeCVacantBedCount"),
        supported_living=n("supportedLivingBedCount"),
        senior_lodge=n("seniorLodgeBedCount"),
    )


def _title_image_url(raw: dict[str, Any]) -> Optional[str]:
    image = raw.get("titleImage")
    if isinstance(image, dict):
        return image.get("imageUrl")
    return None


def _to_summary(raw: dict[str, Any], provider: str) -> FacilitySummary:
    distance = raw.get("distanceKm")
    return FacilitySummary(
        provider=provider,
        id=int(raw["id"]),
        name=raw.get("name") or "",
        address_line1=raw.get("addressLine1") or None,
        address_line2=raw.get("addressLine2") or None,
        city=raw.get("city") or None,
        province=raw.get("province") or None,
        postal_code=raw.get("postalCode") or None,
        country=raw.get("country") or None,
        latitude=raw.get("latitude"),
        longitude=raw.get("longitude"),
        phone_number=raw.get("phoneNumber") or None,
        beds=_bed_counts(raw),
        distance_km=float(distance) if distance is not None else None,
        title_image_url=_title_image_url(raw),
    )


def _titles(items: Optional[list[dict[str, Any]]]) -> tuple[str, ...]:
    return tuple(i["title"] for i in (items or []) if i and i.get("title"))


def _named_items(items: Optional[list[dict[str, Any]]]) -> tuple[NamedItem, ...]:
    out: list[NamedItem] = []
    for i in items or []:
        if not i or not i.get("title"):
            continue
        funding = (i.get("fundingType") or {}).get("title")
        out.append(NamedItem(id=int(i.get("id") or 0), title=i["title"], funding=funding))
    return tuple(out)


def _charges(items: Optional[list[dict[str, Any]]]) -> tuple[Charge, ...]:
    out: list[Charge] = []
    for c in items or []:
        if not c:
            continue
        charge_type = c.get("chargeType") or {}
        name = charge_type.get("title") or "Charge"
        out.append(
            Charge(
                name=name,
                amount=c.get("amount"),
                description=c.get("amountDescription") or charge_type.get("description"),
                is_mandatory=bool(c.get("isMandatory")),
                frequency=(c.get("frequency") or None),
                funding=(c.get("fundingType") or {}).get("title"),
            )
        )
    return tuple(out)


def _room_pricings(items: Optional[list[dict[str, Any]]]) -> tuple[RoomPricing, ...]:
    out: list[RoomPricing] = []
    for p in items or []:
        if not p:
            continue
        out.append(
            RoomPricing(
                room_type=(p.get("roomType") or {}).get("title") or "Room",
                minimum_fee=p.get("minimumFee"),
                maximum_fee=p.get("maximumFee"),
                rent_geared_to_income=p.get("rentGearedIncome"),
                funding=(p.get("fundingType") or {}).get("title"),
            )
        )
    return tuple(out)


def _care_types(raw: dict[str, Any]) -> tuple[str, ...]:
    """Plain-language care streams, from the AHS/non-AHS site-type lists with a
    fall back to the bed counts (some records carry counts but no site-type list)."""
    labels: list[str] = []
    for item in (raw.get("ahsFundedSiteTypes") or []) + (
        raw.get("nonAhsFundedSiteTypes") or []
    ):
        if item and item.get("title"):
            labels.append(item["title"])
    if labels:
        # De-duplicate while preserving order.
        seen: set[str] = set()
        return tuple(x for x in labels if not (x in seen or seen.add(x)))
    # Fall back to the bed-count-derived labels.
    return FacilitySummary(provider=raw.get("provider", ""), id=0, name="", beds=_bed_counts(raw)).care_types


def _accessibility(raw: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """Decide if a facility is accessible and collect plain accessibility notes.

    The Navigator marks accessibility through amenities ("Accessible
    (wheelchairs, scooters)"), room types ("Accessible bathroom") and a count of
    accessible spaces. We treat any of these as making the facility accessible
    and state exactly which signals were found (Constitution Art. 3, with Art.
    7.1 honesty - we report what the data says, not an assumption)."""
    notes: list[str] = []
    accessible = False

    for title in _titles(raw.get("amenityTypes")):
        if "accessible" in title.lower():
            accessible = True
            notes.append(title)
    for title in _titles(raw.get("roomTypes")):
        if "accessible" in title.lower():
            accessible = True
            notes.append(f"Room option: {title}")

    spaces = raw.get("numberOfSpacesAccessibleB")
    if spaces:
        accessible = True
        notes.append(f"{spaces} accessible space(s) reported")

    # De-duplicate notes while preserving order.
    seen: set[str] = set()
    unique = tuple(x for x in notes if not (x in seen or seen.add(x)))
    return accessible, unique


def _photos(raw: dict[str, Any]) -> tuple[str, ...]:
    urls: list[str] = []
    for image in raw.get("images") or []:
        if image and image.get("imageUrl"):
            urls.append(image["imageUrl"])
    title = _title_image_url(raw)
    if title and title not in urls:
        urls.insert(0, title)
    return tuple(urls)


def _to_details(raw: dict[str, Any], provider: str) -> FacilityDetails:
    accessible, notes = _accessibility(raw)
    return FacilityDetails(
        provider=provider,
        id=int(raw["id"]),
        name=raw.get("name") or "",
        accessible=accessible,
        status=raw.get("status") or None,
        description=(raw.get("description") or None),
        address_line1=raw.get("addressLine1") or None,
        address_line2=raw.get("addressLine2") or None,
        city=raw.get("city") or None,
        province=raw.get("province") or None,
        postal_code=raw.get("postalCode") or None,
        country=raw.get("country") or None,
        latitude=raw.get("latitude"),
        longitude=raw.get("longitude"),
        phone_number=raw.get("phoneNumber") or None,
        fax_number=raw.get("faxNumber") or None,
        site_email=raw.get("siteEmail") or None,
        operator_name=raw.get("operator_name") or None,
        operator_type=raw.get("operator_type") or None,
        operator_website=raw.get("operatorWebsite") or None,
        virtual_tour_website=raw.get("virtualTourWebsite") or None,
        beds=_bed_counts(raw),
        number_of_spaces_private_room=raw.get("numberOfSpacesPrivateRoom"),
        number_of_spaces_shared_room=raw.get("numberOfSpacesSharedRoom"),
        number_of_spaces_one_bedroom=raw.get("numberOfSpacesOneBedroom"),
        number_of_spaces_multi_bedroom=raw.get("numberOfSpacesMultiBedroom"),
        number_of_spaces_accessible=raw.get("numberOfSpacesAccessibleB"),
        room_types=_titles(raw.get("roomTypes")),
        room_pricings=_room_pricings(raw.get("roomPricings")),
        care_types=_care_types(raw),
        amenities=_titles(raw.get("amenityTypes")),
        food_services=_named_items(raw.get("foodServiceTypes")),
        site_services=_named_items(raw.get("serviceTypes")),
        security_services=_named_items(raw.get("securityServiceTypes")),
        transportation_services=_named_items(raw.get("transportationServiceTypes")),
        charges=_charges(raw.get("facilityCharges")),
        accessibility_notes=notes,
        has_smoking_policy=raw.get("hasSmokingPolicy"),
        senior_lodge_designation=raw.get("seniorLodgeDesignation") or None,
        accreditation_status=(raw.get("accreditationStatus") or {}).get("title"),
        accreditation_organization_name=raw.get("accreditationOrganizationName") or None,
        accreditation_organization_url=raw.get("accreditationOrganizationUrl") or None,
        accommodation_standards_url=raw.get("accomodationsStandardsUrl") or None,
        photos=_photos(raw),
    )
