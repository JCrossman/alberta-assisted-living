"""Provider tests: GraphQL responses map correctly to the normalized shapes."""

from __future__ import annotations

import math

from alberta_assisted_living.providers.alberta_ala.provider import (
    _bounding_box,
    _build_fetch_args,
)
from alberta_assisted_living.providers.base import FacilityFilters

# Facility ids present in the recorded fixtures (see conftest.py).
FACILITY_MINIMAL_ID = 70042229  # Canora Place Supportive Living
FACILITY_RICH_ID = 70039781  # Villa Marguerite


def test_search_by_name_maps_summary(provider):
    results = provider.search_by_name("Villa Marguerite")
    assert len(results) == 1
    s = results[0]
    assert s.id == FACILITY_RICH_ID
    assert s.name == "Villa Marguerite"
    assert s.city == "Edmonton"
    assert s.province == "AB"
    assert s.phone_number == "780-451-1114"
    # Funded Type B and Type B secure beds; some Type B vacancy reported.
    assert s.beds.type_b_funded == 145
    assert s.beds.type_b_secure_funded == 94
    assert s.beds.type_b_vacant == 3
    assert s.beds.has_vacancy is True
    assert "Type B (designated supportive living)" in s.care_types


def test_search_by_name_empty(provider):
    assert provider.search_by_name("nonexistent place") == []


def test_count_by_name(provider):
    assert provider.count_by_name("Villa") == 1
    assert provider.count_by_name("nothing") == 0


def test_search_near_sorts_and_limits(provider):
    results = provider.search_near(
        latitude=53.5461, longitude=-113.4938, radius_km=25, limit=3
    )
    assert len(results) == 3
    distances = [r.distance_km for r in results if r.distance_km is not None]
    assert distances == sorted(distances)


def test_search_near_passes_accessibility_filter(provider):
    """The accessible-building filter reaches the API and changes the result set."""
    unfiltered = provider.search_near(
        latitude=53.5461, longitude=-113.4938, radius_km=25, limit=100
    )
    filtered = provider.search_near(
        latitude=53.5461,
        longitude=-113.4938,
        radius_km=25,
        filters=FacilityFilters(accessible_building=True),
        limit=100,
    )
    assert len(filtered) < len(unfiltered)


def test_get_details_minimal(provider):
    d = provider.get_details(FACILITY_MINIMAL_ID)
    assert d.name == "Canora Place Supportive Living"
    assert d.city == "Edmonton"
    assert d.operator_name == "George Spady Centre Society (The)"
    assert d.beds.supported_living == 28
    # This record lists no accessible features.
    assert d.accessible is False
    # Charges are present (TV, Internet, etc.) but all $0 here.
    assert any(c.name == "Television" for c in d.charges)
    # Official standards link is surfaced for verification.
    assert d.accommodation_standards_url and "standardsandlicensing" in d.accommodation_standards_url


def test_get_details_rich_accessibility(provider):
    d = provider.get_details(FACILITY_RICH_ID)
    assert d.name == "Villa Marguerite"
    assert d.operator_type == "Private"
    # Rich record marks accessibility via amenities and room types.
    assert d.accessible is True
    assert any("accessible" in note.lower() for note in d.accessibility_notes)
    assert "Accessible (wheelchairs, scooters)" in d.amenities
    assert "Accessible bathroom" in d.room_types
    assert d.number_of_spaces_private_room == 228
    assert d.accreditation_status == "Accredited"
    assert d.has_smoking_policy is True
    # Services parsed with their funding context.
    assert any(s.title == "Housekeeping" for s in d.site_services)
    assert any(s.title == "Emergency call system" for s in d.security_services)


def test_care_types_from_site_type_lists(provider):
    d = provider.get_details(FACILITY_RICH_ID)
    # ahsFundedSiteTypes => Type B and Type B (Secure Space).
    assert any("Type B" in c for c in d.care_types)


def test_bounding_box_corners_and_radius():
    ne, sw = _bounding_box(53.5461, -113.4938, 10)
    # North-east corner has the larger latitude and longitude.
    assert ne["latitude"] > sw["latitude"]
    assert ne["longitude"] > sw["longitude"]
    # Half-height of the box is ~radius / 111 km per degree of latitude.
    assert math.isclose((ne["latitude"] - sw["latitude"]) / 2, 10 / 111.0, rel_tol=1e-6)


def test_build_fetch_args_empty_is_none():
    assert _build_fetch_args(None) is None
    assert _build_fetch_args(FacilityFilters()) is None


def test_build_fetch_args_maps_filters():
    args = _build_fetch_args(
        FacilityFilters(
            accessible_building=True,
            type_b_secure=True,
            private_room=True,
            has_vacancy=True,
        )
    )
    assert args["amenityFilter"] == {"accessibleBuilding": [True]}
    assert args["levelOfCareFilter"] == {"typeBSecure": [True]}
    assert args["roomTypeFilter"] == {"privateRoom": [True]}
    # Vacancy is filtered client-side on real counts, not via the (no-op) API
    # flag, so it must not be sent as a fetch argument.
    assert "hasPotentialVacancy" not in args


def test_has_vacancy_filter_is_client_side(provider):
    """only-with-vacancy keeps only facilities with a real reported vacancy."""
    everything = provider.search_near(
        latitude=53.5461, longitude=-113.4938, radius_km=25, limit=100
    )
    with_vacancy = provider.search_near(
        latitude=53.5461,
        longitude=-113.4938,
        radius_km=25,
        filters=FacilityFilters(has_vacancy=True),
        limit=100,
    )
    assert all(s.beds.has_vacancy for s in with_vacancy)
    assert len(with_vacancy) <= len(everything)


def test_get_details_unknown_id_raises(provider):
    from alberta_assisted_living.providers.base import InvalidInputError

    try:
        provider.get_details(1)
    except InvalidInputError as exc:
        assert "could not find" in str(exc).lower()
    else:
        raise AssertionError("expected InvalidInputError for unknown id")
