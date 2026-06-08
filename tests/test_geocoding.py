"""Geocoding tests, run offline against a mocked Nominatim."""

from __future__ import annotations

import httpx

from alberta_assisted_living.config import Config
from alberta_assisted_living.geocoding import Geocoder


def test_geocode_resolves_known_place(geocoder):
    result = geocoder.geocode("Sherwood Park")
    assert result is not None
    assert round(result.latitude, 2) == 53.53
    assert "Alberta" in result.display_name


def test_geocode_unknown_returns_none(geocoder):
    assert geocoder.geocode("Atlantis") is None


def test_geocode_empty_returns_none(geocoder):
    assert geocoder.geocode("") is None
    assert geocoder.geocode("   ") is None


def test_geocode_disabled_returns_none():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=[]))
    g = Geocoder(
        config=Config(enable_geocoding=False),
        http_client=httpx.Client(transport=transport),
    )
    assert g.geocode("Sherwood Park") is None


def test_geocode_biases_to_alberta():
    """A bare place name is nudged toward Alberta, Canada in the query."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["q"] = request.url.params.get("q", "")
        return httpx.Response(200, json=[])

    g = Geocoder(config=Config(), http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    g.geocode("Camrose")
    assert "Alberta" in seen["q"]
    assert "Canada" in seen["q"]


def test_geocode_does_not_double_tag_when_province_present():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["q"] = request.url.params.get("q", "")
        return httpx.Response(200, json=[])

    g = Geocoder(config=Config(), http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    g.geocode("123 Main St, Calgary, Alberta")
    assert seen["q"] == "123 Main St, Calgary, Alberta"
