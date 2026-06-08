"""Client tests: error handling and the image-fetch SSRF guard."""

from __future__ import annotations

import httpx
import pytest

from alberta_assisted_living.providers.alberta_ala.client import NavigatorClient
from alberta_assisted_living.providers.base import UpstreamError


def _client(handler) -> NavigatorClient:
    return NavigatorClient(
        api_url="https://alacapacity.api.alberta.ca/graphql",
        user_agent="test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_http_error_becomes_upstream_error():
    client = _client(lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(UpstreamError):
        client.facility(1)


def test_graphql_errors_become_upstream_error():
    client = _client(
        lambda r: httpx.Response(200, json={"errors": [{"message": "Unauthorized"}]})
    )
    with pytest.raises(UpstreamError) as exc:
        client.facility(1)
    assert "Unauthorized" in str(exc.value)


def test_non_json_becomes_upstream_error():
    client = _client(lambda r: httpx.Response(200, text="not json"))
    with pytest.raises(UpstreamError):
        client.facility(1)


def test_fetch_image_rejects_foreign_host():
    """Only the Navigator's own image host may be fetched (SSRF guard)."""
    called = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        return httpx.Response(200, content=b"x", headers={"content-type": "image/jpeg"})

    client = _client(handler)
    # An off-host URL must be refused without any network call.
    assert client.fetch_image("https://evil.example.com/x.jpg") is None
    assert called["n"] == 0
    # A non-https URL is refused too.
    assert client.fetch_image("http://alamedia.alberta.ca/x.jpg") is None
    assert called["n"] == 0


def test_fetch_image_allows_navigator_host():
    client = _client(
        lambda r: httpx.Response(
            200, content=b"\xff\xd8\xff\xd9", headers={"content-type": "image/jpeg"}
        )
    )
    result = client.fetch_image("https://alamedia.alberta.ca/facility/x/photo.jpg")
    assert result is not None
    data, fmt = result
    assert fmt == "jpeg"
    assert data.startswith(b"\xff\xd8")
