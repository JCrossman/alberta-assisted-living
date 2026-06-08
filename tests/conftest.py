"""Test fixtures: serve recorded Navigator responses offline.

A MockTransport routes the GraphQL client's requests to JSON fixtures captured
from the live Alberta Assisted Living Navigator API (see
docs/alberta-assisted-living-api-findings.md), so provider and tool tests run
with no live network calls (architecture rule: "No live calls in CI").
"""

from __future__ import annotations

import json
import pathlib

import httpx
import pytest

from alberta_assisted_living.config import Config
from alberta_assisted_living.geocoding import Geocoder
from alberta_assisted_living.providers.alberta_ala.client import NavigatorClient
from alberta_assisted_living.providers.alberta_ala.provider import NavigatorProvider

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "alberta_ala"

# Facility ids present in the recorded fixtures.
FACILITY_MINIMAL_ID = 70042229  # Canora Place Supportive Living
FACILITY_RICH_ID = 70039781  # Villa Marguerite


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def _graphql_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content.decode())
    op = body.get("operationName")
    variables = body.get("variables") or {}

    if op == "SearchFacilitiesByName":
        term = (variables.get("searchTerm") or "").lower()
        if "villa" in term or "marguerite" in term:
            return httpx.Response(200, json=_load("search_results.json"))
        return httpx.Response(200, json=_load("search_empty.json"))

    if op == "CountFacilitiesByName":
        term = (variables.get("searchTerm") or "").lower()
        count = 1 if ("villa" in term or "marguerite" in term) else 0
        return httpx.Response(200, json={"data": {"countBySearchTerm": count}})

    if op == "GetFacilitiesByBoundingBox":
        data = _load("bounding_box.json")
        # If an accessibleBuilding filter is set, return a reduced set so a test
        # can assert the filter is honoured end to end.
        args = variables.get("fetchFacilityArgs") or {}
        amenity = (args or {}).get("amenityFilter") or {}
        if amenity.get("accessibleBuilding"):
            facs = data["data"]["facilitiesByBoundingBox"][:2]
            data = {"data": {"facilitiesByBoundingBox": facs}}
        return httpx.Response(200, json=data)

    if op == "getFacility":
        fid = variables.get("id")
        if fid == FACILITY_MINIMAL_ID:
            return httpx.Response(200, json=_load("facility_minimal.json"))
        if fid == FACILITY_RICH_ID:
            return httpx.Response(200, json=_load("facility_rich.json"))
        return httpx.Response(200, json={"data": {"facility": None}})

    return httpx.Response(400, json={"errors": [{"message": f"unexpected op {op}"}]})


def _handler(request: httpx.Request) -> httpx.Response:
    if request.method == "POST":
        return _graphql_handler(request)
    # Image fetch: a minimal valid JPEG (SOI + EOI) so image tests run offline.
    if request.url.host == "alamedia.alberta.ca":
        return httpx.Response(
            200, content=b"\xff\xd8\xff\xd9", headers={"content-type": "image/jpeg"}
        )
    return httpx.Response(404, json={"error": "unexpected request"})


@pytest.fixture
def mock_client() -> NavigatorClient:
    transport = httpx.MockTransport(_handler)
    return NavigatorClient(
        api_url="https://alacapacity.api.alberta.ca/graphql",
        user_agent="test",
        http_client=httpx.Client(transport=transport),
    )


@pytest.fixture
def provider(mock_client: NavigatorClient) -> NavigatorProvider:
    return NavigatorProvider(client=mock_client, config=Config())


def _geocode_handler(request: httpx.Request) -> httpx.Response:
    q = (request.url.params.get("q") or "").lower()
    if "sherwood park" in q:
        return httpx.Response(
            200,
            json=[
                {
                    "lat": "53.5256963",
                    "lon": "-113.296631",
                    "display_name": "Sherwood Park, Strathcona County, Alberta, Canada",
                }
            ],
        )
    return httpx.Response(200, json=[])


@pytest.fixture
def geocoder() -> Geocoder:
    transport = httpx.MockTransport(_geocode_handler)
    return Geocoder(config=Config(), http_client=httpx.Client(transport=transport))
