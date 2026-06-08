"""MCP server for The Open State: Alberta Assisted Living (local, stdio).

Exposes a small set of plain-language tools a citizen can reach through their own
AI assistant to find continuing care, supportive living, and seniors' housing in
Alberta: search by name, find places near a location (filtering for
accessibility, care type, room type, amenities, and current vacancy), read a
facility's full details, and understand what the care options and funding routes
mean.

It is an independent, public-interest tool built on the Government of Alberta's
public Alberta Assisted Living Navigator data. It is not operated by or endorsed
by the Government of Alberta.

Design rules this file follows (from The Open State's CONSTITUTION.md):
- Tools are read-only. Nothing applies, reserves a space, pays, or stores
  credentials (Art. 1, 2). Placement into a publicly funded space happens through
  the citizen's own Alberta Health Services process; this tool only finds and
  explains options and points to the facility and AHS to act.
- Accessibility is the purpose, not a feature (Art. 3): accessible building and
  accessible bathroom are first-class search filters, accessibility is stated
  plainly in results, and output reads cleanly aloud for a screen reader - no
  tables or emoji.
- Honest about limits (Art. 7): vacancy is a point-in-time snapshot the operator
  reported, not a guarantee; we say so, and we point to the official
  accommodation-standards record rather than asking the citizen to take our word.
- Independent and not endorsed by the Government of Alberta (Art. 6.3); disclosed
  to the citizen.
"""

from __future__ import annotations

import logging
from typing import Optional, Union

from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from alberta_assisted_living.config import Config
from alberta_assisted_living.filters import build_filters
from alberta_assisted_living.geocoding import Geocoder
from alberta_assisted_living.providers.alberta_ala.provider import (
    NAVIGATOR_NAME,
    NavigatorProvider,
)
from alberta_assisted_living.providers.base import (
    BedCounts,
    FacilityDetails,
    FacilitySummary,
    InvalidInputError,
    UpstreamError,
)

logger = logging.getLogger(__name__)

mcp = FastMCP("Open State: Alberta Assisted Living")

_INDEPENDENCE_NOTE = (
    "The Open State is an independent public-interest tool built on Alberta's "
    "public Assisted Living Navigator data. It is not operated by or endorsed by "
    "the Government of Alberta."
)

# A photo is tens of KB; cap how many we ever fetch so a tool call stays light.
_MAX_VIEWABLE_PHOTOS = 3

_provider: Optional[NavigatorProvider] = None
_geocoder: Optional[Geocoder] = None


def get_provider() -> NavigatorProvider:
    """Build the Navigator provider on first use (avoids network at import)."""
    global _provider
    if _provider is None:
        _provider = NavigatorProvider(config=Config.from_env())
    return _provider


def get_geocoder() -> Geocoder:
    """Build the geocoder on first use."""
    global _geocoder
    if _geocoder is None:
        _geocoder = Geocoder(config=Config.from_env())
    return _geocoder


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    """Liveness probe, separate from /mcp and unauthenticated (for hosting)."""
    return JSONResponse({"status": "ok", "service": "alberta-assisted-living"})


@mcp.custom_route("/", methods=["GET"])
async def root(_request: Request) -> PlainTextResponse:
    """Friendly note for a human who opens the public URL in a browser."""
    return PlainTextResponse(
        "The Open State: Alberta Assisted Living - an independent, public-interest "
        "tool for finding continuing care, supportive living, and seniors' housing "
        "in Alberta through your own AI assistant. It is not operated by or "
        "endorsed by the Government of Alberta.\n\n"
        "This is a Model Context Protocol (MCP) server. Connect an MCP client to "
        "the /mcp endpoint. Health: /health\n"
    )


def _readonly(title: str) -> ToolAnnotations:
    # Read-only tools that reach an external service (the live Navigator API).
    return ToolAnnotations(title=title, readOnlyHint=True, openWorldHint=True)


def _problem(exc: Exception) -> str:
    """Turn an error into a plain-language message for the citizen (Art. 7.2)."""
    if isinstance(exc, (InvalidInputError, UpstreamError)):
        # InvalidInputError names the valid options; UpstreamError is already a
        # plain sentence. Pass either straight through.
        return str(exc)
    logger.warning("Unexpected error serving a tool call: %r", exc, exc_info=exc)
    return (
        "Sorry, something went wrong while reaching the Alberta Assisted Living "
        "Navigator. Please try again in a moment."
    )


# -- formatting (plain language, screen-reader friendly) --------------------


def _address(item: Union[FacilitySummary, FacilityDetails]) -> str:
    street = ", ".join(p for p in [item.address_line1, item.address_line2] if p)
    place = ", ".join(p for p in [item.city, item.province, item.postal_code] if p)
    return ", ".join(p for p in [street, place] if p)


def _vacancy_phrase(beds: BedCounts) -> str:
    """Describe currently reported open spaces in plain words.

    Only Type A-C report a live vacant count; supportive living and seniors
    lodge report funded capacity only. Vacancy is a snapshot, stated as such."""
    if not beds.has_vacancy:
        return "No open spaces reported right now"
    parts = []
    if beds.type_a_vacant:
        parts.append(f"{beds.type_a_vacant} Type A (long-term care)")
    if beds.type_b_vacant:
        parts.append(f"{beds.type_b_vacant} Type B")
    if beds.type_b_secure_vacant:
        parts.append(f"{beds.type_b_secure_vacant} Type B secure")
    if beds.type_c_vacant:
        parts.append(f"{beds.type_c_vacant} Type C")
    return f"{beds.total_vacant} space(s) reported open now: " + ", ".join(parts)


def _summary_line(s: FacilitySummary, *, with_distance: bool) -> str:
    bits = [s.name]
    if with_distance and s.distance_km is not None:
        bits.append(f"{s.distance_km:.1f} km away")
    if s.city:
        bits.append(s.city)
    line = "- " + "; ".join(bits) + "."
    address = _address(s)
    if address:
        line += f" {address}."
    if s.phone_number:
        line += f" Phone: {s.phone_number}."
    care = s.care_types
    if care:
        line += " Care: " + ", ".join(care) + "."
    line += " " + _vacancy_phrase(s.beds) + "."
    line += f" (facility id: {s.id})"
    return line


def _money(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    if value == 0:
        return "no charge"
    if float(value).is_integer():
        return f"${int(value):,}"
    return f"${value:,.2f}"


def _format_details(d: FacilityDetails) -> str:
    lines: list[str] = [f"{d.name} ({NAVIGATOR_NAME})."]
    lines.append(_INDEPENDENCE_NOTE)
    lines.append("")

    # Accessibility first (Constitution Art. 3).
    if d.accessible:
        lines.append("Accessibility: this facility reports accessible features.")
        for note in d.accessibility_notes:
            lines.append(f"- {note}")
    else:
        lines.append(
            "Accessibility: no accessible features are listed for this facility. "
            "Confirm directly with the site, as listings can be incomplete."
        )
    lines.append("")

    # Location and contact.
    address = _address(d)
    if address:
        lines.append(f"Address: {address}.")
    contact = []
    if d.phone_number:
        contact.append(f"phone {d.phone_number}")
    if d.site_email:
        contact.append(f"email {d.site_email}")
    if d.fax_number:
        contact.append(f"fax {d.fax_number}")
    if contact:
        lines.append("Contact: " + ", ".join(contact) + ".")
    if d.operator_name:
        operator = d.operator_name
        if d.operator_type:
            operator += f" ({d.operator_type} operator)"
        lines.append(f"Run by: {operator}.")
    if d.operator_website:
        lines.append(f"Operator website: {d.operator_website}")
    if d.virtual_tour_website:
        lines.append(f"Virtual tour: {d.virtual_tour_website}")
    if d.status:
        lines.append(f"Status: {d.status}.")

    # Care types and capacity.
    lines.append("")
    if d.care_types:
        lines.append("Care types offered: " + ", ".join(d.care_types) + ".")
    lines.append(_vacancy_phrase(d.beds) + ".")
    if d.beds.total_funded:
        lines.append(f"Funded spaces (operating capacity): {d.beds.total_funded}.")
    if d.beds.supported_living:
        lines.append(f"Supportive living spaces: {d.beds.supported_living}.")
    if d.beds.senior_lodge:
        lines.append(f"Seniors lodge spaces: {d.beds.senior_lodge}.")

    # Rooms.
    rooms = []
    if d.number_of_spaces_private_room:
        rooms.append(f"{d.number_of_spaces_private_room} private room(s)")
    if d.number_of_spaces_shared_room:
        rooms.append(f"{d.number_of_spaces_shared_room} shared room(s)")
    if d.number_of_spaces_one_bedroom:
        rooms.append(f"{d.number_of_spaces_one_bedroom} one-bedroom suite(s)")
    if d.number_of_spaces_multi_bedroom:
        rooms.append(f"{d.number_of_spaces_multi_bedroom} multi-bedroom suite(s)")
    if d.number_of_spaces_accessible:
        rooms.append(f"{d.number_of_spaces_accessible} accessible space(s)")
    if rooms:
        lines.append("Rooms: " + ", ".join(rooms) + ".")
    if d.room_types:
        lines.append("Room options: " + ", ".join(d.room_types) + ".")

    # Pricing.
    if d.room_pricings:
        lines.append("")
        lines.append("Room pricing:")
        for p in d.room_pricings:
            lo, hi = _money(p.minimum_fee), _money(p.maximum_fee)
            if lo and hi and lo != hi:
                price = f"{lo} to {hi}"
            else:
                price = lo or hi or "fee not listed"
            extra = []
            if p.rent_geared_to_income:
                extra.append("rent geared to income")
            if p.funding:
                extra.append(p.funding.lower())
            tail = f" ({'; '.join(extra)})" if extra else ""
            lines.append(f"- {p.room_type}: {price}{tail}.")

    # Amenities and services.
    if d.amenities:
        lines.append("")
        lines.append("Amenities: " + ", ".join(d.amenities) + ".")
    for label, items in (
        ("Food services", d.food_services),
        ("On-site services", d.site_services),
        ("Security", d.security_services),
        ("Transportation", d.transportation_services),
    ):
        if items:
            lines.append(f"{label}: " + ", ".join(i.title for i in items) + ".")
    if d.has_smoking_policy is not None:
        lines.append(
            "Has a smoking policy." if d.has_smoking_policy else "No smoking policy listed."
        )

    # Charges.
    if d.charges:
        listed = [c for c in d.charges if c.amount and c.amount > 0]
        if listed:
            lines.append("")
            lines.append("Extra charges:")
            for c in listed:
                amount = _money(c.amount) or ""
                freq = f" {c.frequency}" if c.frequency else ""
                mand = "mandatory" if c.is_mandatory else "optional"
                fund = f", {c.funding.lower()}" if c.funding else ""
                lines.append(f"- {c.name}: {amount}{freq} ({mand}{fund}).")

    # Trust and verification (point to the source of truth, Art. 6.3 / 7.1).
    lines.append("")
    if d.accreditation_status:
        acc = f"Accreditation: {d.accreditation_status}"
        if d.accreditation_organization_name:
            acc += f" by {d.accreditation_organization_name}"
        lines.append(acc + ".")
        if d.accreditation_organization_url:
            lines.append(f"Accreditation details: {d.accreditation_organization_url}")
    if d.accommodation_standards_url:
        lines.append(
            "Official accommodation standards and licensing record: "
            + d.accommodation_standards_url
        )
    if d.photos:
        lines.append(f"Photos available: {len(d.photos)} (ask to see them).")

    # How to act - we never apply on the citizen's behalf (Art. 2).
    lines.append("")
    lines.append(
        "To take the next step, contact the facility directly using the phone "
        "number above. Publicly funded spaces (shown as 'Accessed Through AHS "
        "Case Manager') are arranged through an Alberta Health Services case "
        "manager, not booked directly - call Health Link at 811 to start. This "
        "tool never applies or reserves a space for you."
    )
    return "\n".join(lines)


# -- tools ------------------------------------------------------------------


@mcp.tool(annotations=_readonly("Search assisted living by name"))
def search_facilities_by_name(
    search_term: str, sort_by: str = "relevance", limit: int = 25
) -> str:
    """Find Alberta assisted living and continuing care facilities by name.

    Use this when a citizen names a place (for example "Villa Marguerite") or a
    word that appears in facility names. It returns matching facilities with their
    city, address, phone, the care types they offer, any currently reported
    vacancy, and a facility id the other tools need. To search by location
    instead of name (for example "near Sherwood Park"), use find_facilities_near.

    `sort_by` may be "relevance" (default) or "name". `limit` caps how many are
    listed.
    """
    try:
        results = get_provider().search_by_name(
            search_term, sort_by=sort_by, limit=limit
        )
    except Exception as exc:  # noqa: BLE001 - surface a friendly message
        return _problem(exc)

    if not results:
        return (
            f'I could not find an Alberta facility matching "{search_term}". '
            "Try a different name, or search by location with find_facilities_near."
        )
    lines = [
        f'Found {len(results)} facility(ies) matching "{search_term}". '
        + _INDEPENDENCE_NOTE,
        "",
    ]
    for s in results:
        lines.append(_summary_line(s, with_distance=False))
    lines += [
        "",
        "Ask for full details on any of these with get_facility_details and its "
        "facility id. Vacancy figures are a snapshot the operator reported; "
        "confirm with the facility.",
    ]
    return "\n".join(lines)


@mcp.tool(annotations=_readonly("Find assisted living near a place"))
def find_facilities_near(
    location: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: int = 25,
    care_types: Optional[list[str]] = None,
    room_types: Optional[list[str]] = None,
    accessible_building: bool = False,
    accessible_bathroom: bool = False,
    amenities: Optional[list[str]] = None,
    only_with_vacancy: bool = False,
    limit: int = 25,
) -> str:
    """Find assisted living near a place, nearest first, with accessibility first.

    Use this when a citizen wants options near a location - "assisted living near
    my mom in Sherwood Park", "memory care within 10 km of downtown Calgary with
    a private room". Give either `location` (a town, address, or landmark, which
    is looked up to coordinates) or an explicit `latitude` and `longitude`.
    `radius_km` is how far to look (default 25).

    Filters (all optional):
    - `accessible_building` / `accessible_bathroom`: set true to return only
      facilities that report these accessible features. Use these for wheelchair
      or mobility needs.
    - `care_types`: words like "long-term care", "memory care", "supportive
      living", "seniors lodge", "type b". See explain_care_options for what these
      mean.
    - `room_types`: "private room", "shared room", "one bedroom", "multi bedroom".
    - `amenities`: words like "private bathroom", "meals", "emergency call
      system", "pets", "gardens", "social activities", "parking", "laundry".
    - `only_with_vacancy`: set true to keep only facilities reporting an open
      space now (a snapshot, not a guarantee).

    When you pass a `location`, that text is sent to OpenStreetMap to look up
    coordinates. Results state distance from your location. This tool never
    applies or reserves a space.
    """
    config = Config.from_env()
    centre_label = location or ""

    # Resolve the search centre: explicit coordinates win; otherwise geocode the
    # place name. Fail visibly rather than guess a location (Art. 7.2).
    if latitude is not None and longitude is not None:
        lat, lng = latitude, longitude
        if not centre_label:
            centre_label = f"{lat:.4f}, {lng:.4f}"
    elif location:
        if not config.enable_geocoding:
            return (
                "Location lookup is turned off on this server, so I need exact "
                "coordinates. Please provide latitude and longitude."
            )
        resolved = get_geocoder().geocode(location)
        if resolved is None:
            return (
                f'I could not find the location "{location}". Try a nearby town or '
                "a full street address, or give me latitude and longitude."
            )
        lat, lng = resolved.latitude, resolved.longitude
        centre_label = resolved.display_name
    else:
        return (
            "Tell me where to search: a place name or address (for example "
            '"Sherwood Park" or "9810 165 Street, Edmonton"), or latitude and '
            "longitude."
        )

    try:
        filters = build_filters(
            care_types=care_types,
            room_types=room_types,
            amenities=amenities,
            accessible_building=accessible_building,
            accessible_bathroom=accessible_bathroom,
            only_with_vacancy=only_with_vacancy,
        )
        results = get_provider().search_near(
            latitude=lat,
            longitude=lng,
            radius_km=radius_km,
            filters=filters,
            limit=limit,
        )
    except Exception as exc:  # noqa: BLE001
        return _problem(exc)

    applied = _describe_filters(
        accessible_building, accessible_bathroom, care_types, room_types,
        amenities, only_with_vacancy,
    )
    radius = min(radius_km, config.max_radius_km) if radius_km > 0 else config.default_radius_km
    header = (
        f"Facilities within about {radius} km of {centre_label}"
        + (f", {applied}" if applied else "")
        + f". {_INDEPENDENCE_NOTE}"
    )
    if not results:
        return (
            header
            + "\n\nI did not find any facilities matching that within the radius. "
            "Try widening radius_km, removing a filter, or a nearby town."
        )
    lines = [header, "", f"Found {len(results)}, nearest first:"]
    for s in results:
        lines.append(_summary_line(s, with_distance=True))
    lines += [
        "",
        "Ask for full details on any of these with get_facility_details and its "
        "facility id, including the full accessibility information. Vacancy is a "
        "snapshot the operator reported; confirm with the facility.",
    ]
    return "\n".join(lines)


def _describe_filters(
    accessible_building: bool,
    accessible_bathroom: bool,
    care_types: Optional[list[str]],
    room_types: Optional[list[str]],
    amenities: Optional[list[str]],
    only_with_vacancy: bool,
) -> str:
    """A short plain-language summary of which filters were applied."""
    parts: list[str] = []
    access = []
    if accessible_building:
        access.append("accessible building")
    if accessible_bathroom:
        access.append("accessible bathroom")
    if access:
        parts.append("filtered to " + " and ".join(access))
    if care_types:
        parts.append("care: " + ", ".join(care_types))
    if room_types:
        parts.append("rooms: " + ", ".join(room_types))
    if amenities:
        parts.append("amenities: " + ", ".join(amenities))
    if only_with_vacancy:
        parts.append("with an open space now")
    return "; ".join(parts)


@mcp.tool(annotations=_readonly("Get facility details"))
def get_facility_details(
    facility_id: int, include_photos: bool = False
) -> Union[str, list]:
    """Get full, plain-language detail about one Alberta facility.

    Use this after a search gives you a facility id. It returns accessibility
    (stated first), location and contact, who runs it, the care types and funded
    or vacant spaces, room options and pricing, amenities and on-site services,
    extra charges, accreditation, and a link to the official accommodation
    standards and licensing record.

    Set `include_photos=True` when the citizen wants to *see* the place: the tool
    then returns the actual photos as viewable images (up to three) alongside the
    text. Left off, the text still says how many photos exist.
    """
    try:
        details = get_provider().get_details(facility_id)
    except Exception as exc:  # noqa: BLE001
        return _problem(exc)

    text = _format_details(details)

    images: list[Image] = []
    if details.photos and include_photos:
        provider = get_provider()
        for url in details.photos[:_MAX_VIEWABLE_PHOTOS]:
            fetched = provider.fetch_image(url)
            if fetched is not None:
                data, fmt = fetched
                images.append(Image(data=data, format=fmt))

    if images:
        from mcp.types import TextContent

        note = f"\n\nShowing {len(images)} photo(s) of this facility."
        return [
            TextContent(type="text", text=text + note),
            *(img.to_image_content() for img in images),
        ]
    return text


@mcp.tool(
    annotations=ToolAnnotations(
        title="Explain Alberta care options", readOnlyHint=True, openWorldHint=False
    )
)
def explain_care_options() -> str:
    """Explain Alberta's assisted living and continuing care options in plain words.

    Use this when a citizen is unsure what the care types, funding routes, or
    search filters mean - for example a newcomer, or a family member starting to
    look for care for a parent. It needs no input and makes no network call.
    """
    return (
        "Alberta's Assisted Living Navigator lists places that offer housing and "
        "care for seniors and adults who need support. Here is what the terms "
        "generally mean. This is plain-language guidance; confirm specifics with "
        "the facility and with Alberta Health Services (AHS).\n"
        "\n" + _INDEPENDENCE_NOTE + "\n"
        "\n"
        "Care types (least to most care):\n"
        "- Seniors lodge: housing for seniors who manage most daily activities on "
        "their own, with meals, housekeeping, and social programs. Income-tested.\n"
        "- Supportive living: your own space plus services and some personal care; "
        "the amount of care varies by site.\n"
        "- Type C: enhanced supportive living, lodge-style, with more services.\n"
        "- Type B (designated supportive living): publicly funded supportive "
        "living with care staff on site, for people who need regular help.\n"
        "- Type B secure: a secure setting for people living with dementia or "
        "memory loss who need a safe, enclosed environment (memory care).\n"
        "- Type A (long-term care, also called facility living): 24-hour nursing "
        "care for people with complex health needs.\n"
        "\n"
        "How you get a space (funding):\n"
        "- Accessed Through AHS Case Manager: a publicly funded space. You do not "
        "apply directly; an AHS case manager assesses needs and arranges "
        "placement. To start, call Health Link at 811 or ask a doctor or social "
        "worker for a referral.\n"
        "- Accessed Through Site Directly: a private space you arrange and pay for "
        "with the operator yourself.\n"
        "\n"
        "Filters you can use when searching near a place:\n"
        "- Accessibility (most important for mobility needs): 'accessible "
        "building' and 'accessible bathroom' return only places reporting those "
        "features.\n"
        "- Care types: the streams listed above (for example 'memory care', "
        "'long-term care', 'supportive living').\n"
        "- Room types: private room, shared room, one bedroom, multi bedroom.\n"
        "- Amenities: private bathroom, meals included, emergency call system, "
        "housekeeping, laundry, parking, gardens, social activities, hairdresser "
        "or barber, small pets allowed, and smoking options.\n"
        "- Open space now: keep only places reporting a vacancy. Vacancy is a "
        "snapshot the operator reported, not a guarantee - always confirm.\n"
        "\n"
        "Next steps are always taken by you: this tool finds and explains "
        "options, but never applies, reserves, or pays for anything."
    )


def main() -> None:
    """Run the MCP server. Defaults to stdio; HTTP is selected via env."""
    config = Config.from_env()
    if config.transport == "http":
        if config.rate_limit_rps > 0:
            from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

            mcp.add_middleware(
                RateLimitingMiddleware(
                    max_requests_per_second=config.rate_limit_rps,
                    burst_capacity=config.rate_limit_burst,
                    global_limit=True,
                )
            )
        mcp.run(
            transport="http",
            host=config.host,
            port=config.port,
            path=config.mcp_path,
            stateless_http=config.stateless_http,
        )
    else:
        mcp.run()


if __name__ == "__main__":
    main()
