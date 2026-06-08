"""Turn a place name or address into coordinates, so a citizen can search by
words instead of latitude and longitude.

A citizen says "near my mother in Sherwood Park" or gives a street address; the
"near me" search needs a point. This module asks OpenStreetMap's Nominatim
service - free, no API key - to resolve that text to a coordinate, biased to
Alberta, Canada.

Constitution notes:
- Accessibility is the purpose (Art. 3): typing coordinates is a barrier; place
  names are not. Geocoding removes that barrier.
- Data minimization (Art. 5): only the place text the citizen provided is sent,
  and only when they ask for a location search. The tool layer discloses this.
- Respect the systems we use (Art. 7.3): we identify ourselves honestly and call
  Nominatim lightly, in line with its usage policy.
- Fail safely and visibly (Art. 7.2): if a place cannot be resolved we return
  ``None`` and the caller asks the citizen to refine it, rather than guessing a
  location.

Geocoding can be turned off entirely (``ALA_ENABLE_GEOCODING=false``); then a
location search requires explicit coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from alberta_assisted_living.config import Config
from alberta_assisted_living.tls import verify_setting


@dataclass(frozen=True, slots=True)
class GeocodeResult:
    """A resolved location."""

    latitude: float
    longitude: float
    display_name: str


class Geocoder:
    """Resolve a place name / address to coordinates via Nominatim."""

    def __init__(
        self, *, config: Config, http_client: Optional[httpx.Client] = None
    ) -> None:
        self._config = config
        self._client = http_client or httpx.Client(
            timeout=config.geocoder_timeout_seconds,
            follow_redirects=True,
            verify=verify_setting(),
            headers={
                "User-Agent": config.geocoder_user_agent,
                "Accept": "application/json",
                "Accept-Language": "en-CA,en;q=0.9",
            },
        )

    def geocode(self, place: str) -> Optional[GeocodeResult]:
        """Resolve ``place`` to a coordinate, or ``None`` if it cannot be found.

        Returns ``None`` (rather than raising) for an unresolvable place or any
        geocoder problem, so a location search degrades to asking the citizen to
        refine the place instead of failing the whole request.
        """
        if not self._config.enable_geocoding:
            return None
        text = (place or "").strip()
        if not text:
            return None

        # Nudge bare place names toward Alberta so "St. Albert" resolves locally
        # rather than to a like-named place elsewhere. An address that already
        # names a province/country is left alone.
        query = text
        lowered = text.lower()
        if "alberta" not in lowered and "ab" not in lowered.split() and "canada" not in lowered:
            query = f"{text}, Alberta, Canada"

        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "countrycodes": "ca",
            "addressdetails": 0,
        }
        try:
            resp = self._client.get(self._config.geocoder_url, params=params)
        except httpx.HTTPError:
            return None
        if resp.status_code != 200:
            return None
        try:
            results = resp.json()
        except ValueError:
            return None
        if not results:
            return None
        top = results[0]
        try:
            return GeocodeResult(
                latitude=float(top["lat"]),
                longitude=float(top["lon"]),
                display_name=str(top.get("display_name") or query),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def close(self) -> None:
        self._client.close()
