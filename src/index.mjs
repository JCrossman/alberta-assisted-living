/**
 * Entry point: wire up the real provider and geocoder and serve over stdio.
 *
 * This is the file the .mcpb bundle runs (esbuild bundles it into
 * server/index.mjs). Keeping wiring here means server.mjs stays import-safe for
 * tests, which build the server with mocked dependencies.
 */

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { loadConfig } from "./config.mjs";
import { Geocoder } from "./geocoding.mjs";
import { NavigatorProvider } from "./providers/navigator-provider.mjs";
import { createServer } from "./server.mjs";

async function main() {
  const config = loadConfig();
  const provider = new NavigatorProvider({ config });
  const geocoder = new Geocoder({ config });
  const server = createServer({ provider, geocoder, config });
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error("Fatal error starting Alberta Assisted Living MCP server:", err);
  process.exit(1);
});
