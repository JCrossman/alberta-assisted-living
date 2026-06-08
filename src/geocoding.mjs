/**
 * Turn a place name or address into coordinates, so a citizen can search by
 * words instead of latitude and longitude.
 *
 * Uses OpenStreetMap's Nominatim (free, no API key), biased to Alberta, Canada.
 *
 * Constitution notes:
 * - Accessibility is the purpose (Art. 3): typing coordinates is a barrier;
 *   place names are not.
 * - Data minimization (Art. 5): only the place text the citizen provided is
 *   sent, and only when they ask for a location search. The tool layer discloses
 *   this.
 * - Respect the systems we use (Art. 7.3): honest User-Agent, light use.
 * - Fail safely and visibly (Art. 7.2): an unresolvable place returns null and
 *   the caller asks the citizen to refine it, rather than guessing a location.
 *
 * Geocoding can be turned off (ALA_ENABLE_GEOCODING=false); then a location
 * search requires explicit coordinates.
 */

export class Geocoder {
  constructor({ config, fetchImpl } = {}) {
    this.config = config;
    this._fetch = fetchImpl || globalThis.fetch;
  }

  /**
   * Resolve `place` to { latitude, longitude, displayName }, or null if it
   * cannot be found (or geocoding is disabled / errors).
   */
  async geocode(place) {
    if (!this.config.enableGeocoding) return null;
    const text = (place || "").trim();
    if (!text) return null;

    // Nudge bare place names toward Alberta so "St. Albert" resolves locally.
    // An address that already names a province/country is left alone.
    let query = text;
    const lowered = text.toLowerCase();
    const words = lowered.split(/\s+/);
    if (!lowered.includes("alberta") && !words.includes("ab") && !lowered.includes("canada")) {
      query = `${text}, Alberta, Canada`;
    }

    const url = new URL(this.config.geocoderUrl);
    url.searchParams.set("q", query);
    url.searchParams.set("format", "json");
    url.searchParams.set("limit", "1");
    url.searchParams.set("countrycodes", "ca");
    url.searchParams.set("addressdetails", "0");

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.config.geocoderTimeoutMs);
    let resp;
    try {
      resp = await this._fetch(url.toString(), {
        signal: controller.signal,
        headers: {
          "User-Agent": this.config.geocoderUserAgent,
          Accept: "application/json",
          "Accept-Language": "en-CA,en;q=0.9",
        },
      });
    } catch {
      return null;
    } finally {
      clearTimeout(timer);
    }
    if (!resp.ok) return null;
    let results;
    try {
      results = await resp.json();
    } catch {
      return null;
    }
    if (!Array.isArray(results) || results.length === 0) return null;
    const top = results[0];
    const latitude = Number(top.lat);
    const longitude = Number(top.lon);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
    return { latitude, longitude, displayName: String(top.display_name || query) };
  }
}
