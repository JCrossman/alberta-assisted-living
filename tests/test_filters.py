"""Filter-resolution tests: plain words map onto the right filter fields."""

from __future__ import annotations

import pytest

from alberta_assisted_living.filters import build_filters
from alberta_assisted_living.providers.base import InvalidInputError


def test_first_class_accessibility_flags():
    f = build_filters(accessible_building=True, accessible_bathroom=True)
    assert f.accessible_building is True
    assert f.accessible_bathroom is True


def test_care_type_words():
    f = build_filters(care_types=["memory care", "long-term care"])
    assert f.type_b_secure is True
    assert f.type_a is True


def test_room_and_amenity_words():
    f = build_filters(
        room_types=["private room"],
        amenities=["meals", "pets", "emergency call"],
    )
    assert f.private_room is True
    assert f.meals_included is True
    assert f.small_pets_allowed is True
    assert f.emergency_call_system is True


def test_amenity_word_accepts_accessibility_synonyms():
    f = build_filters(amenities=["wheelchair accessible"])
    assert f.accessible_building is True


def test_only_with_vacancy():
    assert build_filters(only_with_vacancy=True).has_vacancy is True


def test_unknown_word_raises_with_options():
    with pytest.raises(InvalidInputError) as exc:
        build_filters(amenities=["helipad"])
    assert "helipad" in str(exc.value)
    assert "amenity" in str(exc.value).lower()


def test_empty_filters_is_empty():
    assert build_filters().is_empty() is True


def test_case_insensitive_and_whitespace():
    f = build_filters(care_types=["  Memory Care "])
    assert f.type_b_secure is True
