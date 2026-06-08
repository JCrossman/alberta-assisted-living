/**
 * MCP server for The Open State: Alberta Assisted Living (Node, local stdio).
 *
 * Plain-language tools a citizen can reach through their own AI assistant to find
 * continuing care, supportive living, and seniors' housing in Alberta: search by
 * name, find places near a location (filtering for accessibility, care type,
 * room type, amenities, and current vacancy), read a facility's full details, and
 * understand what the care options and funding routes mean.
 *
 * Independent and built on the Government of Alberta's public Assisted Living
 * Navigator data; not operated by or endorsed by the Government of Alberta.
 *
 * Design rules (from The Open State CONSTITUTION.md):
 * - Read-only. Nothing applies, reserves a space, pays, or stores credentials
 *   (Art. 1, 2). Placement into a publicly funded space happens through the
 *   citizen's own AHS process; this tool finds and explains, and points to the
 *   facility and AHS to act.
 * - Accessibility is the purpose (Art. 3): accessible building / bathroom are
 *   first-class filters, accessibility is stated first, output reads cleanly
 *   aloud.
 * - Honest about limits (Art. 7): vacancy is a snapshot; failures are reported
 *   plainly, never guessed.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

import { InvalidInputError, UpstreamError } from "./errors.mjs";
import { buildFilters } from "./filters.mjs";
import {
  CARE_OPTIONS_GUIDE,
  INDEPENDENCE_NOTE,
  describeFilters,
  formatDetails,
  summaryLine,
} from "./format.mjs";

// A photo is tens of KB; cap how many we ever fetch so a tool call stays light.
const MAX_VIEWABLE_PHOTOS = 3;

const READONLY_OPEN = { readOnlyHint: true, openWorldHint: true };

function text(s) {
  return { content: [{ type: "text", text: s }] };
}

/** Turn an error into a plain-language message for the citizen (Art. 7.2). */
function problem(err) {
  if (err instanceof InvalidInputError || err instanceof UpstreamError) {
    return err.message;
  }
  // Logs go to stderr; stdout is the MCP protocol channel.
  console.error("Unexpected error serving a tool call:", err);
  return (
    "Sorry, something went wrong while reaching the Alberta Assisted Living " +
    "Navigator. Please try again in a moment."
  );
}

/**
 * Build the MCP server and register the tools against an injected provider and
 * geocoder (so the same code is exercised by the offline tests and at runtime).
 */
export function createServer({ provider, geocoder, config }) {
  const server = new McpServer({
    name: "Open State: Alberta Assisted Living",
    version: "0.1.0",
  });

  server.registerTool(
    "search_facilities_by_name",
    {
      title: "Search assisted living by name",
      description:
        "Find Alberta assisted living and continuing care facilities by name. Use " +
        'when a citizen names a place (for example "Villa Marguerite") or a word ' +
        "that appears in facility names. Returns each facility's city, address, " +
        "phone, care types, any currently reported vacancy, and a facility id the " +
        "other tools need. To search by location instead, use find_facilities_near. " +
        'sort_by may be "relevance" (default) or "name".',
      inputSchema: {
        search_term: z.string().describe("Name or text to search for."),
        sort_by: z.enum(["relevance", "name"]).default("relevance"),
        limit: z.number().int().positive().max(100).default(25),
      },
      annotations: { title: "Search assisted living by name", ...READONLY_OPEN },
    },
    async ({ search_term, sort_by, limit }) => {
      let results;
      try {
        results = await provider.searchByName(search_term, { sortBy: sort_by, limit });
      } catch (err) {
        return text(problem(err));
      }
      if (!results.length) {
        return text(
          `I could not find an Alberta facility matching "${search_term}". Try a ` +
            "different name, or search by location with find_facilities_near."
        );
      }
      const lines = [
        `Found ${results.length} facility(ies) matching "${search_term}". ` + INDEPENDENCE_NOTE,
        "",
      ];
      for (const s of results) lines.push(summaryLine(s, { withDistance: false }));
      lines.push(
        "",
        "Ask for full details on any of these with get_facility_details and its " +
          "facility id. Vacancy figures are a snapshot the operator reported; confirm " +
          "with the facility."
      );
      return text(lines.join("\n"));
    }
  );

  server.registerTool(
    "find_facilities_near",
    {
      title: "Find assisted living near a place",
      description:
        "Find assisted living near a place, nearest first, with accessibility first. " +
        'Give either location (a town, address, or landmark) or explicit latitude ' +
        "and longitude. radius_km is how far to look (default 25). Filters (all " +
        "optional): accessible_building / accessible_bathroom (true to return only " +
        "facilities reporting these - use for wheelchair or mobility needs); " +
        'care_types (words like "long-term care", "memory care", "supportive ' +
        'living", "seniors lodge"); room_types ("private room", "shared room", "one ' +
        'bedroom", "multi bedroom"); amenities (words like "private bathroom", ' +
        '"meals", "emergency call system", "pets", "gardens", "parking", "laundry"); ' +
        "only_with_vacancy (true to keep only facilities reporting an open space now, " +
        "a snapshot not a guarantee). When you pass location, that text is sent to " +
        "OpenStreetMap to look up coordinates. This tool never applies or reserves a " +
        "space.",
      inputSchema: {
        location: z.string().optional().describe("Town, address, or landmark."),
        latitude: z.number().optional(),
        longitude: z.number().optional(),
        radius_km: z.number().int().positive().max(200).default(25),
        care_types: z.array(z.string()).optional(),
        room_types: z.array(z.string()).optional(),
        accessible_building: z.boolean().default(false),
        accessible_bathroom: z.boolean().default(false),
        amenities: z.array(z.string()).optional(),
        only_with_vacancy: z.boolean().default(false),
        limit: z.number().int().positive().max(100).default(25),
      },
      annotations: { title: "Find assisted living near a place", ...READONLY_OPEN },
    },
    async (args) => {
      const {
        location,
        latitude,
        longitude,
        radius_km,
        care_types,
        room_types,
        accessible_building,
        accessible_bathroom,
        amenities,
        only_with_vacancy,
        limit,
      } = args;

      let lat;
      let lng;
      let centreLabel = location || "";

      if (latitude != null && longitude != null) {
        lat = latitude;
        lng = longitude;
        if (!centreLabel) centreLabel = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
      } else if (location) {
        if (!config.enableGeocoding) {
          return text(
            "Location lookup is turned off on this server, so I need exact " +
              "coordinates. Please provide latitude and longitude."
          );
        }
        const resolved = await geocoder.geocode(location);
        if (!resolved) {
          return text(
            `I could not find the location "${location}". Try a nearby town or a ` +
              "full street address, or give me latitude and longitude."
          );
        }
        lat = resolved.latitude;
        lng = resolved.longitude;
        centreLabel = resolved.displayName;
      } else {
        return text(
          "Tell me where to search: a place name or address (for example " +
            '"Sherwood Park" or "9810 165 Street, Edmonton"), or latitude and longitude.'
        );
      }

      let results;
      try {
        const filters = buildFilters({
          careTypes: care_types,
          roomTypes: room_types,
          amenities,
          accessibleBuilding: accessible_building,
          accessibleBathroom: accessible_bathroom,
          onlyWithVacancy: only_with_vacancy,
        });
        results = await provider.searchNear({
          latitude: lat,
          longitude: lng,
          radiusKm: radius_km,
          filters,
          limit,
        });
      } catch (err) {
        return text(problem(err));
      }

      const applied = describeFilters({
        accessibleBuilding: accessible_building,
        accessibleBathroom: accessible_bathroom,
        careTypes: care_types,
        roomTypes: room_types,
        amenities,
        onlyWithVacancy: only_with_vacancy,
      });
      const radius =
        radius_km > 0 ? Math.min(radius_km, config.maxRadiusKm) : config.defaultRadiusKm;
      const header =
        `Facilities within about ${radius} km of ${centreLabel}` +
        (applied ? `, ${applied}` : "") +
        `. ${INDEPENDENCE_NOTE}`;

      if (!results.length) {
        return text(
          header +
            "\n\nI did not find any facilities matching that within the radius. Try " +
            "widening radius_km, removing a filter, or a nearby town."
        );
      }
      const lines = [header, "", `Found ${results.length}, nearest first:`];
      for (const s of results) lines.push(summaryLine(s, { withDistance: true }));
      lines.push(
        "",
        "Ask for full details on any of these with get_facility_details and its " +
          "facility id, including the full accessibility information. Vacancy is a " +
          "snapshot the operator reported; confirm with the facility."
      );
      return text(lines.join("\n"));
    }
  );

  server.registerTool(
    "get_facility_details",
    {
      title: "Get facility details",
      description:
        "Get full, plain-language detail about one Alberta facility: accessibility " +
        "(stated first), location and contact, who runs it, care types and funded or " +
        "vacant spaces, room options and pricing, amenities and on-site services, " +
        "extra charges, accreditation, and a link to the official accommodation " +
        "standards and licensing record. Set include_photos=true to also return the " +
        "actual photos as viewable images (up to three). Use a facility id from a " +
        "search.",
      inputSchema: {
        facility_id: z.number().int().describe("Facility id from a search result."),
        include_photos: z.boolean().default(false),
      },
      annotations: { title: "Get facility details", ...READONLY_OPEN },
    },
    async ({ facility_id, include_photos }) => {
      let details;
      try {
        details = await provider.getDetails(facility_id);
      } catch (err) {
        return text(problem(err));
      }

      const body = formatDetails(details);
      const content = [];

      if (include_photos && details.photos.length) {
        const images = [];
        for (const url of details.photos.slice(0, MAX_VIEWABLE_PHOTOS)) {
          const fetched = await provider.fetchImage(url);
          if (fetched) {
            images.push({
              type: "image",
              data: fetched.data.toString("base64"),
              mimeType: fetched.mimeType,
            });
          }
        }
        if (images.length) {
          content.push({
            type: "text",
            text: body + `\n\nShowing ${images.length} photo(s) of this facility.`,
          });
          content.push(...images);
          return { content };
        }
      }
      return text(body);
    }
  );

  server.registerTool(
    "explain_care_options",
    {
      title: "Explain Alberta care options",
      description:
        "Explain Alberta's assisted living and continuing care options in plain " +
        "words: the care types, funding routes (including AHS placement), and what " +
        "each search filter means. Useful for a newcomer or a family member starting " +
        "to look for care. Needs no input and makes no network call.",
      inputSchema: {},
      annotations: { title: "Explain Alberta care options", readOnlyHint: true, openWorldHint: false },
    },
    async () => text(CARE_OPTIONS_GUIDE)
  );

  return server;
}
