"""Map plain words a citizen would say onto the Navigator's facility filters.

The search filters (care level, room type, amenities) are exposed to the
assistant as lists of everyday words - "memory care", "private room", "meals",
"wheelchair accessible" - rather than the platform's internal field names. This
module resolves those words into a :class:`FacilityFilters`.

When a word matches nothing, we raise :class:`InvalidInputError` naming the valid
options, so the assistant can correct course instead of silently dropping a
filter the citizen cares about (Constitution Art. 7.1).
"""

from __future__ import annotations

from typing import Optional

from alberta_assisted_living.providers.base import FacilityFilters, InvalidInputError

# Everyday phrase -> FacilityFilters field. Lowercased on lookup. Several
# spellings map to the same field so common phrasings all work.
_CARE_TYPE_WORDS = {
    "type a": "type_a",
    "a": "type_a",
    "long-term care": "type_a",
    "long term care": "type_a",
    "ltc": "type_a",
    "nursing home": "type_a",
    "facility living": "type_a",
    "type b": "type_b",
    "b": "type_b",
    "designated supportive living": "type_b",
    "dsl": "type_b",
    "type b secure": "type_b_secure",
    "b secure": "type_b_secure",
    "secure": "type_b_secure",
    "secure space": "type_b_secure",
    "memory care": "type_b_secure",
    "dementia": "type_b_secure",
    "dementia care": "type_b_secure",
    "type c": "type_c",
    "c": "type_c",
    "supportive living": "supported_living",
    "supported living": "supported_living",
    "sl": "supported_living",
    "seniors lodge": "seniors_lodge",
    "senior lodge": "seniors_lodge",
    "lodge": "seniors_lodge",
}

_ROOM_TYPE_WORDS = {
    "private room": "private_room",
    "private": "private_room",
    "shared room": "shared_room",
    "shared": "shared_room",
    "semi-private": "shared_room",
    "semi private": "shared_room",
    "one bedroom": "one_bedroom",
    "1 bedroom": "one_bedroom",
    "one-bedroom": "one_bedroom",
    "1-bedroom": "one_bedroom",
    "multi bedroom": "multi_bedroom",
    "multi-bedroom": "multi_bedroom",
    "two bedroom": "multi_bedroom",
    "2 bedroom": "multi_bedroom",
}

_AMENITY_WORDS = {
    # Accessibility (also first-class boolean params; accepted here for
    # convenience so "wheelchair accessible" in an amenities list works too).
    "accessible": "accessible_building",
    "accessible building": "accessible_building",
    "wheelchair": "accessible_building",
    "wheelchair accessible": "accessible_building",
    "accessible bathroom": "accessible_bathroom",
    "private bathroom": "private_bathroom",
    "ensuite": "private_bathroom",
    "en-suite": "private_bathroom",
    "en suite": "private_bathroom",
    "emergency call system": "emergency_call_system",
    "emergency call": "emergency_call_system",
    "call system": "emergency_call_system",
    "call bell": "emergency_call_system",
    "meals included": "meals_included",
    "meals": "meals_included",
    "food": "meals_included",
    "housekeeping": "housekeeping",
    "cleaning": "housekeeping",
    "laundry": "laundry_service",
    "laundry service": "laundry_service",
    "parking": "parking",
    "gardens": "gardens",
    "garden": "gardens",
    "outdoor space": "gardens",
    "social activities": "social_activities",
    "activities": "social_activities",
    "social": "social_activities",
    "hairdresser": "hairdresser_barber",
    "barber": "hairdresser_barber",
    "salon": "hairdresser_barber",
    "pets": "small_pets_allowed",
    "small pets": "small_pets_allowed",
    "pet friendly": "small_pets_allowed",
    "pet-friendly": "small_pets_allowed",
    "indoor smoking room": "indoor_smoking_room",
    "indoor smoking": "indoor_smoking_room",
    "outdoor smoking area": "safe_outdoor_smoking_area",
    "outdoor smoking": "safe_outdoor_smoking_area",
    "smoking area": "safe_outdoor_smoking_area",
}


def _resolve(words: Optional[list[str]], table: dict[str, str], label: str) -> dict[str, bool]:
    selected: dict[str, bool] = {}
    for word in words or []:
        key = (word or "").strip().lower()
        if not key:
            continue
        field = table.get(key)
        if field is None:
            options = ", ".join(sorted(set(table.keys())))
            raise InvalidInputError(
                f"I do not recognize the {label} {word!r}. "
                f"Valid {label} words include: {options}."
            )
        selected[field] = True
    return selected


def build_filters(
    *,
    care_types: Optional[list[str]] = None,
    room_types: Optional[list[str]] = None,
    amenities: Optional[list[str]] = None,
    accessible_building: bool = False,
    accessible_bathroom: bool = False,
    only_with_vacancy: bool = False,
) -> FacilityFilters:
    """Build a :class:`FacilityFilters` from plain words and the first-class flags."""
    fields: dict[str, bool] = {}
    fields.update(_resolve(care_types, _CARE_TYPE_WORDS, "care type"))
    fields.update(_resolve(room_types, _ROOM_TYPE_WORDS, "room type"))
    fields.update(_resolve(amenities, _AMENITY_WORDS, "amenity"))
    if accessible_building:
        fields["accessible_building"] = True
    if accessible_bathroom:
        fields["accessible_bathroom"] = True
    if only_with_vacancy:
        fields["has_vacancy"] = True
    return FacilityFilters(**fields)
