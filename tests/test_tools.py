"""Tests for the MCP tool layer (server.py), run offline against the fixtures.

We check plain-language, screen-reader-friendly output, that accessibility is
surfaced first-class, that the independence disclosure is present, that the
prepare-only / never-acts promise is stated, and that failures are reported
plainly.
"""

from __future__ import annotations

import pytest

from alberta_assisted_living import server

# Facility ids present in the recorded fixtures (see conftest.py).
FACILITY_MINIMAL_ID = 70042229  # Canora Place Supportive Living
FACILITY_RICH_ID = 70039781  # Villa Marguerite


@pytest.fixture
def tools(provider, geocoder, monkeypatch):
    """Point the server's tools at the mock-backed provider and geocoder."""
    monkeypatch.setattr(server, "_provider", provider)
    monkeypatch.setattr(server, "_geocoder", geocoder)
    return server


def test_search_by_name_lists_and_discloses_independence(tools):
    out = tools.search_facilities_by_name.fn("Villa Marguerite")
    assert "Villa Marguerite" in out
    assert f"facility id: {FACILITY_RICH_ID}" in out
    assert "not operated by or endorsed by the Government of Alberta" in out
    # No tabs/tables - reads cleanly with a screen reader.
    assert "\t" not in out


def test_search_by_name_no_match_is_friendly(tools):
    out = tools.search_facilities_by_name.fn("Narnia Manor")
    assert "could not find" in out.lower()


def test_find_near_requires_a_location(tools):
    out = tools.find_facilities_near.fn()
    assert "tell me where to search" in out.lower()


def test_find_near_geocodes_place_name(tools):
    out = tools.find_facilities_near.fn(location="Sherwood Park")
    assert "Sherwood Park" in out
    assert "km away" in out
    assert "nearest first" in out.lower()


def test_find_near_unresolvable_location_fails_visibly(tools):
    out = tools.find_facilities_near.fn(location="Atlantis")
    assert "could not find the location" in out.lower()


def test_find_near_with_explicit_coordinates(tools):
    out = tools.find_facilities_near.fn(latitude=53.5461, longitude=-113.4938)
    assert "km away" in out


def test_find_near_accessibility_filter_is_described(tools):
    out = tools.find_facilities_near.fn(
        latitude=53.5461, longitude=-113.4938, accessible_building=True
    )
    assert "accessible building" in out.lower()


def test_find_near_unknown_filter_word_is_friendly(tools):
    out = tools.find_facilities_near.fn(
        latitude=53.5461, longitude=-113.4938, amenities=["helipad"]
    )
    assert "do not recognize" in out.lower()


def test_get_details_surfaces_accessibility_first_and_next_steps(tools):
    out = tools.get_facility_details.fn(FACILITY_RICH_ID)
    assert "Accessibility:" in out
    assert "accessible" in out.lower()
    # Never-acts promise + AHS route are stated (Constitution Art. 2).
    assert "never applies or reserves" in out.lower()
    assert "Health Link at 811" in out
    # Official standards record is offered for verification.
    assert "accommodation standards" in out.lower()


def test_get_details_minimal_states_no_accessible_features(tools):
    out = tools.get_facility_details.fn(FACILITY_MINIMAL_ID)
    assert "no accessible features" in out.lower()


def test_get_details_unknown_id_is_friendly(tools):
    out = tools.get_facility_details.fn(1)
    assert "could not find" in out.lower()


def test_get_details_with_photos_returns_images(tools):
    result = tools.get_facility_details.fn(FACILITY_RICH_ID, include_photos=True)
    # Villa Marguerite has images; expect text + at least one image content block.
    assert isinstance(result, list)
    assert len(result) >= 2


def test_explain_care_options_is_plain_and_offline(tools):
    out = tools.explain_care_options.fn()
    assert "memory care" in out.lower()
    assert "Health Link at 811" in out
    assert "never applies, reserves, or pays" in out.lower()
    assert "\t" not in out
