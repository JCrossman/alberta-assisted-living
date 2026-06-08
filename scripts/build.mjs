/**
 * Build the .mcpb staging directory.
 *
 * Bundles src/index.mjs (server + MCP SDK + zod) into a single self-contained
 * dist/server/index.mjs with esbuild, copies the manifest, and writes a minimal
 * server package.json. The Alberta Navigator API is a plain public GraphQL
 * endpoint reachable with Node's built-in fetch, so there are NO native
 * dependencies to vendor - the bundle runs on Claude Desktop's bundled Node with
 * no install step and no prerequisites.
 *
 * Then: `mcpb pack dist <name>.mcpb`.
 */

import * as esbuild from "esbuild";
import { mkdirSync, copyFileSync, writeFileSync, rmSync } from "node:fs";

rmSync("dist", { recursive: true, force: true });
mkdirSync("dist/server", { recursive: true });

await esbuild.build({
  entryPoints: ["src/index.mjs"],
  bundle: true,
  platform: "node",
  format: "esm",
  target: "node18",
  outfile: "dist/server/index.mjs",
  // Some bundled dependencies are CommonJS and expect `require`; provide it in
  // the ESM output (the same shim the reference Node bundle uses).
  banner: {
    js: "import { createRequire as __createRequire } from 'node:module'; const require = __createRequire(import.meta.url);",
  },
});

copyFileSync("manifest.json", "dist/manifest.json");
writeFileSync(
  "dist/server/package.json",
  JSON.stringify(
    { name: "alberta-assisted-living-server", version: "0.1.0", private: true, type: "module" },
    null,
    2
  ) + "\n"
);

console.log("Built dist/ (manifest.json + server/index.mjs). Pack with: mcpb pack dist <name>.mcpb");
