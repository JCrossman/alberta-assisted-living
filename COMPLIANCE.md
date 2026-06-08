# Civic Access Protocol — compliance mapping

How this implementation meets every binding commitment in The Open State
[`CONSTITUTION.md`](https://github.com/JCrossman/the-open-state/blob/main/CONSTITUTION.md).
An implementation is Civic Access Protocol compliant only if it satisfies every
**MUST** / **MUST NOT** in Articles 1–10.

This service reads a **public, unauthenticated** government dataset and is
**read-only**, which makes most credential and consequential-action risks
structurally absent rather than merely mitigated.

| Article | Commitment | How this implementation meets it |
|---|---|---|
| **1. Citizen sovereignty over credentials** | Never store/transmit/expose citizen government credentials; never authenticate as the citizen on a server they don't control. | The Navigator read API needs **no credentials at all**. This server holds, asks for, and transmits none. It never logs in anywhere. The operator-login queries and mutations are never called. |
| **2. The human decides** | Consequential actions must be confirmed by the citizen; may prepare, must not auto-complete; no booking-race automation. | Every tool is **read-only** — search and read detail. There is no apply/reserve/pay path in the code at all. Output explains the next step (call the facility; for public funding, AHS via Health Link 811) and states plainly: *"This tool never applies or reserves a space for you."* No contested, time-limited resource is automated. |
| **3. Accessibility is the purpose** | Usable by people with disabilities, seniors, newcomers; plain language; accessibility attributes first-class, filterable, clearly stated; carried through to action. | `accessible_building` and `accessible_bathroom` are **first-class filters**; accessibility is stated **first** in every detail view and surfaced in results; `explain_care_options` turns government jargon into plain language for newcomers. Output is screen-reader-friendly (no tables, no emoji, no reliance on layout). The path to action (phone, AHS) is plain and direct. |
| **4. Assistant freedom** | Usable from any assistant; no dependence on one client's memory; tools take explicit parameters; no mandatory new destination. | Standard MCP over stdio/HTTP — any MCP client works. Tools are stateless and take **explicit parameters** (e.g. `latitude`/`longitude` accepted directly). The tool adds nothing the citizen is forced to keep using; it points back to the citizen's own public services. |
| **5. Data minimization & citizen control** | Collect the minimum; store per-citizen data encrypted/isolated; allow view/export/delete; protect sensitive data. | The server is **stateless** and stores **nothing** — no database, no logs of citizen queries, no profiles. The only outbound data is the place text the citizen chose to search (sent to OpenStreetMap to geocode), disclosed in the tool description and disableable (`ALA_ENABLE_GEOCODING=false`). Nothing about health or disability is stored. |
| **6. No exploitation of the citizen** | No monetizing citizen data; no lock-in; transparent independence. | No data collection, so nothing to monetize. No account, no lock-in. Every output carries the disclosure that the tool is **independent and not endorsed by the Government of Alberta** (Art. 6.3). |
| **7. Honesty about limits** | Distinguish verified from assumed; fail safely and visibly; respect the upstream. | Known limits are flagged in `README.md` and `docs/`. Vacancy is always labelled a snapshot; `hasPotentialVacancy` was found not to work and is **replaced by truthful client-side filtering**. Failures (unreachable API, unresolved location, unknown filter word) return plain messages, never guesses. Honest `User-Agent`, TLS verified (Node honours `NODE_EXTRA_CA_CERTS` for proxy CAs), interactive low-volume use, no upstream hammering. |
| **8. Openness** | Method stays documented and free; shareable/forkable; buildable for public-sector adoption. | MIT-licensed, documented end to end (`README.md`, `COMPLIANCE.md`, `docs/alberta-assisted-living-api-findings.md`), with offline tests (`node --test`). Built on a clean provider/client boundary, so the pattern transfers to other services/provinces. |
| **9. Security & the law** | Comply with PIPEDA / Alberta PIPA; no token passthrough; treat external content as untrusted. | No personal data is collected or stored, so privacy-law exposure is minimal by construction. No inbound token is ever forwarded upstream (there are no upstream credentials). Retrieved content is treated as untrusted: image fetches are restricted to the Navigator's own host (SSRF guard), and the read-only design means external data can't trigger a consequential action. |
| **10. Assistive technology, not a bot** | Operate in the citizen's session, at their direction, through the service's own interfaces; honest identity; don't defeat human-gating. | Acts only when the citizen asks, through the Navigator's **own public data interface** (Art. 10.3), identifying itself honestly — no browser impersonation, no `Origin` spoofing. It impersonates no one and defeats no gate (there is none on the public read API). |

## Summary

Every **MUST** and **MUST NOT** in Articles 1–10 is satisfied. The strongest
guarantees come from the design itself: **no credentials**, **read-only**, and
**stateless**. The areas needing active care — accessibility-first presentation
(Art. 3), honesty about vacancy and limits (Art. 7), and honest identification
(Art. 10) — are addressed in code and documented here and in `docs/`.
