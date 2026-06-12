#!/usr/bin/env node
/**
 * Constitution drift check.
 *
 * Compares the upstream Civic Access Protocol constitution (in the private
 * `the-open-state` repo) against the version this implementation was last
 * verified against, pinned in `constitution.lock`. The comparison is the file's
 * **git blob SHA**, which GitHub returns directly and which changes iff the
 * content changes.
 *
 * Exit codes / GITHUB_OUTPUT `status`:
 *   0  sync   - upstream matches the pin; nothing to do.
 *   1  drift  - upstream changed; re-review COMPLIANCE.md and re-pin. Writes an
 *               issue body to constitution-drift.md.
 *   2  error  - could not read upstream (network or GitHub API rate limit, or
 *               the path/branch moved).
 *
 * The source repo is public, so no token is required. A token is optional and
 * only raises the GitHub API rate limit: set `CONSTITUTION_REPO_TOKEN` or
 * `GH_TOKEN` (the workflow passes the built-in GITHUB_TOKEN as GH_TOKEN). For
 * local/offline runs, set `CONSTITUTION_SOURCE_FILE` to a local copy of
 * CONSTITUTION.md and the git blob SHA is computed locally instead of fetched.
 */

import { readFileSync, appendFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const lock = JSON.parse(readFileSync(join(ROOT, "constitution.lock"), "utf8"));
const { repo, path, ref, url } = lock.source;
const pinned = lock.blob_sha;

function setOutput(key, value) {
  if (process.env.GITHUB_OUTPUT) appendFileSync(process.env.GITHUB_OUTPUT, `${key}=${value}\n`);
}
function stepSummary(md) {
  if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, md + "\n");
}
function gitBlobSha(buf) {
  // git blob object hash: sha1("blob <byteLength>\0" + bytes)
  return createHash("sha1").update(`blob ${buf.length}\0`).update(buf).digest("hex");
}

async function currentBlobSha() {
  const localFile = process.env.CONSTITUTION_SOURCE_FILE;
  if (localFile) return gitBlobSha(readFileSync(localFile));

  const token = process.env.CONSTITUTION_REPO_TOKEN || process.env.GH_TOKEN;
  const api =
    `https://api.github.com/repos/${repo}/contents/${encodeURIComponent(path)}` +
    `?ref=${encodeURIComponent(ref)}`;
  const headers = {
    Accept: "application/vnd.github+json",
    "User-Agent": "open-state-constitution-sync",
    "X-GitHub-Api-Version": "2022-11-28",
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const resp = await fetch(api, { headers });
  if ([401, 403, 404, 429].includes(resp.status)) {
    const msg =
      `Could not read ${repo}/${path}@${ref} (HTTP ${resp.status}). ${repo} is ` +
      `public, so this is most likely a GitHub API rate limit (a 404 can also mean ` +
      `the path or branch moved). No token is required, but one raises the rate ` +
      `limit: the workflow passes the built-in GITHUB_TOKEN; for local runs set ` +
      `GH_TOKEN or CONSTITUTION_REPO_TOKEN, or set CONSTITUTION_SOURCE_FILE to a ` +
      `local copy. See README "Staying in sync with the Constitution".`;
    throw new Error(msg);
  }
  if (!resp.ok) throw new Error(`Unexpected HTTP ${resp.status} from the GitHub API.`);
  const body = await resp.json();
  if (!body.sha) throw new Error("GitHub API response did not include a blob sha.");
  return body.sha;
}

try {
  const current = await currentBlobSha();

  if (current === pinned) {
    console.log(
      `In sync: ${repo}/${path}@${ref} blob ${pinned} matches the pin ` +
        `(verified ${lock.verified_date}).`
    );
    setOutput("status", "sync");
    process.exit(0);
  }

  const md = [
    "## :warning: Constitution drift detected",
    "",
    `\`${repo}/${path}@${ref}\` has changed since this implementation's compliance ` +
      "was last verified.",
    "",
    `- Pinned blob: \`${pinned}\` (verified ${lock.verified_date})`,
    `- Current blob: \`${current}\``,
    `- Source: ${url}`,
    "",
    "**Action required:** re-review [`COMPLIANCE.md`](COMPLIANCE.md) against the " +
      'new text. The constitution\'s revisions "must strengthen, not weaken," so the ' +
      "task is to confirm this implementation still satisfies every MUST / MUST NOT " +
      "(Articles 1–10), update any wording, then bump `blob_sha`, `sha256`, " +
      "`commit_at_verification`, and `verified_date` in `constitution.lock`.",
    "",
    "_Opened automatically by the constitution-sync workflow._",
  ].join("\n");

  console.error(md);
  stepSummary(md);
  writeFileSync(join(ROOT, "constitution-drift.md"), md + "\n");
  setOutput("status", "drift");
  setOutput("current_sha", current);
  process.exit(1);
} catch (err) {
  console.error("Constitution check could not run:", err.message);
  stepSummary(`## Constitution sync error\n\n${err.message}`);
  setOutput("status", "error");
  process.exit(2);
}
