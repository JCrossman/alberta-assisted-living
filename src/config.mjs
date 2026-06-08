/**
 * Runtime configuration for The Open State: Alberta Assisted Living.
 *
 * All settings come from environment variables with safe defaults so the server
 * runs with no setup. Nothing here stores or reads citizen credentials
 * (Constitution Art. 1).
 *
 * The Navigator API is public and unauthenticated, so - unlike some booking
 * platforms - we identify ourselves honestly (Art. 7.3, 10.2) rather than
 * impersonate a browser. The default User-Agent names this tool and the
 * movement; verified to receive HTTP 200 from the live API.
 */

/** Public GraphQL endpoint behind https://alnavigator.alberta.ca. */
export const DEFAULT_API_URL = "https://alacapacity.api.alberta.ca/graphql";

/** Keyless geocoder (OpenStreetMap Nominatim) for "near me" searches. */
export const DEFAULT_GEOCODER_URL = "https://nominatim.openstreetmap.org/search";

/** Honest identification (Constitution Art. 7.3, 10.2). */
const DEFAULT_USER_AGENT =
  "OpenState-AlbertaAssistedLiving/0.1 " +
  "(+https://github.com/JCrossman/alberta-assisted-living; Civic Access Protocol)";

export const DEFAULT_RADIUS_KM = 25;
export const MAX_RADIUS_KM = 200;

function envBool(name, dflt) {
  const raw = process.env[name];
  if (raw === undefined) return dflt;
  return ["1", "true", "yes", "on"].includes(raw.trim().toLowerCase());
}

function envNum(name, dflt) {
  const raw = process.env[name];
  const n = raw === undefined ? NaN : Number(raw);
  return Number.isFinite(n) ? n : dflt;
}

/** Build configuration from environment variables (all optional). */
export function loadConfig() {
  const userAgent = process.env.ALA_USER_AGENT || DEFAULT_USER_AGENT;
  return {
    apiUrl: process.env.ALA_API_URL || DEFAULT_API_URL,
    userAgent,
    httpTimeoutMs: envNum("ALA_HTTP_TIMEOUT_MS", 30000),
    enableGeocoding: envBool("ALA_ENABLE_GEOCODING", true),
    geocoderUrl: process.env.ALA_GEOCODER_URL || DEFAULT_GEOCODER_URL,
    geocoderUserAgent: process.env.ALA_GEOCODER_USER_AGENT || userAgent,
    geocoderTimeoutMs: envNum("ALA_GEOCODER_TIMEOUT_MS", 20000),
    defaultRadiusKm: envNum("ALA_DEFAULT_RADIUS_KM", DEFAULT_RADIUS_KM),
    maxRadiusKm: envNum("ALA_MAX_RADIUS_KM", MAX_RADIUS_KM),
  };
}
