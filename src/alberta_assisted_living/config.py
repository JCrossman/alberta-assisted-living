"""Runtime configuration for The Open State: Alberta Assisted Living.

All settings come from environment variables with safe local defaults so the
server runs with no setup. Nothing here stores or reads citizen credentials
(Constitution Art. 1).

The Alberta Assisted Living Navigator API is public and unauthenticated, so -
unlike some booking platforms - we can identify ourselves honestly (Art. 7.3,
10.2) rather than impersonate a browser. The default User-Agent names this tool
and the movement; verified to receive HTTP 200 from the live API.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# The public GraphQL endpoint behind https://alnavigator.alberta.ca (the Alberta
# Assisted Living Navigator). Verified live; see
# docs/alberta-assisted-living-api-findings.md.
DEFAULT_API_URL = "https://alacapacity.api.alberta.ca/graphql"

# OpenStreetMap Nominatim turns a place name / address into coordinates so a
# citizen can search "near my mom in Sherwood Park" instead of typing latitude
# and longitude. Keyless and free; its usage policy requires an honest,
# identifying User-Agent and light request rates - both respected here (Art. 7.3).
DEFAULT_GEOCODER_URL = "https://nominatim.openstreetmap.org/search"

# Honest identification (Constitution Art. 7.3, 10.2). The Navigator API accepts
# this; no browser impersonation is needed. Configurable so an operator can set
# whatever an official relationship allows.
_DEFAULT_USER_AGENT = (
    "OpenState-AlbertaAssistedLiving/0.1 "
    "(+https://github.com/JCrossman/alberta-assisted-living; Civic Access Protocol)"
)

# Searches are centred on a point and a radius. Keep the radius sane: a tiny
# radius finds nothing useful, a huge one returns the whole province at once.
DEFAULT_RADIUS_KM = 25
MAX_RADIUS_KM = 200


@dataclass(frozen=True)
class Config:
    """Process configuration, read once from the environment."""

    # "stdio" for local use in Claude Desktop / Claude Code, or "http" for a
    # hosted Streamable HTTP deployment. The tool definitions are identical in
    # both; only the transport switch changes.
    transport: str = "stdio"

    # Upstream API (the Navigator's public GraphQL endpoint).
    api_url: str = DEFAULT_API_URL
    user_agent: str = _DEFAULT_USER_AGENT
    http_timeout_seconds: float = 30.0

    # Geocoding (place name / address -> coordinates) for "near me" searches.
    enable_geocoding: bool = True
    geocoder_url: str = DEFAULT_GEOCODER_URL
    # Nominatim's policy asks for a contactable User-Agent; reuse ours by default.
    geocoder_user_agent: str = _DEFAULT_USER_AGENT
    geocoder_timeout_seconds: float = 20.0

    # Search radius bounds for the "near me" tool.
    default_radius_km: int = DEFAULT_RADIUS_KM
    max_radius_km: int = MAX_RADIUS_KM

    # Remote serving (http transport). Ignored under stdio.
    host: str = "127.0.0.1"
    port: int = 8000
    mcp_path: str = "/mcp"
    # Stateless HTTP so multiple replicas do not break sessions when hosted.
    stateless_http: bool = True
    # Global request rate limit for HTTP serving (upstream politeness, Art. 7.3).
    # A single shared bucket: hosted, all Claude traffic arrives from one IP
    # range, so per-client limiting would not bite. <= 0 disables. Applied only
    # under the http transport.
    rate_limit_rps: float = 5.0
    rate_limit_burst: int = 20

    @classmethod
    def from_env(cls) -> "Config":
        """Build configuration from environment variables (all optional)."""
        return cls(
            transport=os.getenv("ALA_TRANSPORT", "stdio"),
            api_url=os.getenv("ALA_API_URL", DEFAULT_API_URL),
            user_agent=os.getenv("ALA_USER_AGENT", _DEFAULT_USER_AGENT),
            http_timeout_seconds=float(os.getenv("ALA_HTTP_TIMEOUT", "30")),
            enable_geocoding=_env_bool("ALA_ENABLE_GEOCODING", True),
            geocoder_url=os.getenv("ALA_GEOCODER_URL", DEFAULT_GEOCODER_URL),
            geocoder_user_agent=os.getenv(
                "ALA_GEOCODER_USER_AGENT",
                os.getenv("ALA_USER_AGENT", _DEFAULT_USER_AGENT),
            ),
            geocoder_timeout_seconds=float(os.getenv("ALA_GEOCODER_TIMEOUT", "20")),
            default_radius_km=int(os.getenv("ALA_DEFAULT_RADIUS_KM", str(DEFAULT_RADIUS_KM))),
            max_radius_km=int(os.getenv("ALA_MAX_RADIUS_KM", str(MAX_RADIUS_KM))),
            host=os.getenv("ALA_HOST", "127.0.0.1"),
            port=int(os.getenv("ALA_PORT", "8000")),
            mcp_path=os.getenv("ALA_MCP_PATH", "/mcp"),
            stateless_http=_env_bool("ALA_STATELESS_HTTP", True),
            rate_limit_rps=float(os.getenv("ALA_RATE_LIMIT_RPS", "5")),
            rate_limit_burst=int(os.getenv("ALA_RATE_LIMIT_BURST", "20")),
        )


def _env_bool(name: str, default: bool) -> bool:
    """Parse a boolean environment variable; accept the usual truthy spellings."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
