"""Provider abstraction for The Open State: Alberta Assisted Living.

This module is the boundary the rest of the system depends on. MCP tools call
the :class:`FacilityProvider` interface only; they never talk to a data platform
directly. Each platform (the Alberta Assisted Living Navigator now; another
province later) is wrapped by one concrete provider that maps its native data
into the normalized shapes defined here.

Keeping this layer platform-agnostic is what lets a new service be added without
touching tool code (see The Open State's docs/01-architecture.md, "Provider
abstraction").

Constitution notes that bind every provider:
- Everything here is read-only. Nothing logs in, applies, books a bed, or
  submits anything on a citizen's behalf (Articles 1, 2). Placement into a
  publicly funded space happens through the citizen's own Alberta Health
  Services process; this tool only finds and explains options.
- No citizen credentials are accepted, stored, or transmitted (Article 1).
- Accessibility (accessible building, accessible bathroom, accessible spaces) is
  a first-class, filterable, plainly stated field because reaching accessible
  housing is the purpose, not an add-on (Article 3).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar, Optional


class InvalidInputError(ValueError):
    """A tool argument was malformed or could not be resolved.

    Raised when a citizen-supplied value cannot be used as given - for example a
    care type or amenity word that matches nothing known. Distinct from
    :class:`UpstreamError` (the data platform failed): this is a problem with the
    request, so the message names the valid options rather than guessing one
    (Constitution Art. 7.1).
    """


class UpstreamError(RuntimeError):
    """The data platform returned an error or an unusable response."""


@dataclass(frozen=True, slots=True)
class NamedItem:
    """A small id/title pair from the platform's taxonomy.

    The Navigator describes amenities, services, room types, care types and the
    like as ``{id, title}`` records. We carry the human ``title`` (plain
    language, Art. 3.2) and keep the ``id`` for reference.
    """

    id: int
    title: str
    # Some items (charges, food, services) are tied to how they are funded -
    # "Accessed Through AHS Case Manager" vs "Accessed Through Site Directly".
    funding: Optional[str] = None


@dataclass(frozen=True, slots=True)
class Charge:
    """An optional or mandatory charge a facility lists for a service."""

    name: str
    amount: Optional[float]
    description: Optional[str]
    is_mandatory: bool
    frequency: Optional[str]
    funding: Optional[str]


@dataclass(frozen=True, slots=True)
class RoomPricing:
    """A fee range for a kind of room, and how it is funded."""

    room_type: str
    minimum_fee: Optional[float]
    maximum_fee: Optional[float]
    rent_geared_to_income: Optional[bool]
    funding: Optional[str]


@dataclass(frozen=True, slots=True)
class BedCounts:
    """Funded and currently vacant space counts, by accommodation type.

    The Navigator reports beds as *funded* (the operating capacity for that care
    type) and *vacant* (how many of those are open right now). "Type A/B/B-Secure
    /C" are Alberta continuing-care space designations; "supportive living" and
    "seniors lodge" are separate streams. Vacancy is a point-in-time snapshot the
    operator reports, not a guarantee (surfaced honestly per Art. 7.1).
    """

    type_a_funded: int = 0
    type_b_funded: int = 0
    type_b_secure_funded: int = 0
    type_c_funded: int = 0
    type_a_vacant: int = 0
    type_b_vacant: int = 0
    type_b_secure_vacant: int = 0
    type_c_vacant: int = 0
    supported_living: int = 0
    senior_lodge: int = 0

    @property
    def total_funded(self) -> int:
        return (
            self.type_a_funded
            + self.type_b_funded
            + self.type_b_secure_funded
            + self.type_c_funded
        )

    @property
    def total_vacant(self) -> int:
        return (
            self.type_a_vacant
            + self.type_b_vacant
            + self.type_b_secure_vacant
            + self.type_c_vacant
        )

    @property
    def has_vacancy(self) -> bool:
        return self.total_vacant > 0


@dataclass(frozen=True, slots=True)
class FacilitySummary:
    """One facility as it appears in a search or map result.

    This is the single shape every provider returns from ``search_by_name`` and
    ``search_near``, so the tools and the citizen's assistant see every platform
    identically. Map each platform's native fields into this; do not leak
    platform-specific shapes above the provider layer.

    The summary endpoints do not carry amenity detail, so accessibility is not
    known here field-by-field; it is offered as a search *filter* and stated in
    full by ``get_details`` (Constitution Art. 3, with Art. 7.1 honesty about
    what a given endpoint actually returns).
    """

    provider: str
    id: int
    name: str
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone_number: Optional[str] = None
    beds: BedCounts = field(default_factory=BedCounts)
    # Distance from the search centre, when the search had one ("near me").
    distance_km: Optional[float] = None
    title_image_url: Optional[str] = None

    @property
    def care_types(self) -> tuple[str, ...]:
        """Plain-language list of the care streams this facility funds."""
        labels: list[str] = []
        b = self.beds
        if b.type_a_funded:
            labels.append("Type A (long-term care)")
        if b.type_b_funded:
            labels.append("Type B (designated supportive living)")
        if b.type_b_secure_funded:
            labels.append("Type B secure (memory care)")
        if b.type_c_funded:
            labels.append("Type C (supportive living)")
        if b.supported_living:
            labels.append("Supportive living")
        if b.senior_lodge:
            labels.append("Seniors lodge")
        return tuple(labels)


@dataclass(frozen=True, slots=True)
class FacilityDetails:
    """Rich, plain-language detail about a single facility.

    Returned by ``get_details``. Accessibility is surfaced explicitly and in
    plain words (``accessible`` plus ``accessibility_notes``), not buried in a
    list of codes (Constitution Art. 3). Official, verifiable references
    (accommodation standards and licensing, accreditation) are carried so the
    tool can point a citizen to the source of truth rather than ask them to take
    its word (Art. 6.3, 7.1).
    """

    provider: str
    id: int
    name: str
    accessible: bool
    status: Optional[str] = None
    description: Optional[str] = None

    # Location and contact.
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone_number: Optional[str] = None
    fax_number: Optional[str] = None
    site_email: Optional[str] = None

    # Who runs it.
    operator_name: Optional[str] = None
    operator_type: Optional[str] = None
    operator_website: Optional[str] = None
    virtual_tour_website: Optional[str] = None

    # Capacity and rooms.
    beds: BedCounts = field(default_factory=BedCounts)
    number_of_spaces_private_room: Optional[int] = None
    number_of_spaces_shared_room: Optional[int] = None
    number_of_spaces_one_bedroom: Optional[int] = None
    number_of_spaces_multi_bedroom: Optional[int] = None
    number_of_spaces_accessible: Optional[int] = None
    room_types: tuple[str, ...] = ()
    room_pricings: tuple[RoomPricing, ...] = ()

    # What it offers.
    care_types: tuple[str, ...] = ()
    amenities: tuple[str, ...] = ()
    food_services: tuple[NamedItem, ...] = ()
    site_services: tuple[NamedItem, ...] = ()
    security_services: tuple[NamedItem, ...] = ()
    transportation_services: tuple[NamedItem, ...] = ()
    charges: tuple[Charge, ...] = ()
    accessibility_notes: tuple[str, ...] = ()
    has_smoking_policy: Optional[bool] = None
    senior_lodge_designation: Optional[str] = None

    # Trust and verification.
    accreditation_status: Optional[str] = None
    accreditation_organization_name: Optional[str] = None
    accreditation_organization_url: Optional[str] = None
    accommodation_standards_url: Optional[str] = None

    # Media.
    photos: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FacilityFilters:
    """Filters a citizen can apply to a facility search.

    Every field is tri-state: ``None`` means "do not filter on this", ``True``
    means "require it". They map onto the platform's own filter inputs. Care
    levels and room types narrow *what kind* of place; amenities narrow *what it
    offers*; ``has_vacancy`` keeps only places reporting an open space now.

    ``accessible_building`` and ``accessible_bathroom`` are first-class here, not
    folded into a generic amenities bag, because filtering for accessible housing
    is the core purpose (Constitution Art. 3.3).
    """

    # Care levels.
    type_a: Optional[bool] = None
    type_b: Optional[bool] = None
    type_b_secure: Optional[bool] = None
    type_c: Optional[bool] = None
    supported_living: Optional[bool] = None
    seniors_lodge: Optional[bool] = None
    # Room types.
    private_room: Optional[bool] = None
    shared_room: Optional[bool] = None
    one_bedroom: Optional[bool] = None
    multi_bedroom: Optional[bool] = None
    # Accessibility (first-class).
    accessible_building: Optional[bool] = None
    accessible_bathroom: Optional[bool] = None
    # Other amenities.
    private_bathroom: Optional[bool] = None
    emergency_call_system: Optional[bool] = None
    meals_included: Optional[bool] = None
    housekeeping: Optional[bool] = None
    laundry_service: Optional[bool] = None
    parking: Optional[bool] = None
    gardens: Optional[bool] = None
    social_activities: Optional[bool] = None
    hairdresser_barber: Optional[bool] = None
    small_pets_allowed: Optional[bool] = None
    indoor_smoking_room: Optional[bool] = None
    safe_outdoor_smoking_area: Optional[bool] = None
    # Vacancy.
    has_vacancy: Optional[bool] = None

    def is_empty(self) -> bool:
        """True when no filter is set (so we can skip sending an empty filter)."""
        return all(getattr(self, f.name) is None for f in self.__dataclass_fields__.values())  # type: ignore[attr-defined]


class FacilityProvider(ABC):
    """The interface every assisted-living data platform is wrapped behind.

    Concrete providers implement these methods and return the normalized shapes
    above. Tool code depends only on this class, never on a specific platform, so
    a new service can be added without changing the tools.

    Every method here is read-only and free of consequential side effects:
    nothing logs in, applies, reserves, or stores citizen data (Constitution
    Articles 1 and 2).
    """

    #: Short, stable machine name for this provider.
    name: ClassVar[str]

    @abstractmethod
    def search_by_name(
        self, search_term: str, *, sort_by: str = "relevance", limit: int = 25
    ) -> list[FacilitySummary]:
        """Find facilities whose name or text matches a plain-language query."""

    @abstractmethod
    def count_by_name(self, search_term: str) -> int:
        """Count facilities matching a search term, without fetching them all."""

    @abstractmethod
    def search_near(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_km: int,
        filters: Optional[FacilityFilters] = None,
        limit: int = 25,
    ) -> list[FacilitySummary]:
        """Find facilities within ``radius_km`` of a point, nearest first.

        Applies the citizen's ``filters`` (care type, room type, accessibility
        and other amenities, current vacancy). Read-only; reserves nothing.
        """

    @abstractmethod
    def get_details(self, facility_id: int) -> FacilityDetails:
        """Get full, plain-language detail for one facility."""

    @abstractmethod
    def fetch_image(self, url: str) -> Optional[tuple[bytes, str]]:
        """Fetch one facility photo as ``(bytes, format)``, or ``None``."""
