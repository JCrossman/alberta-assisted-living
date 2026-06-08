/**
 * Plain-language, screen-reader-friendly formatting of facility data.
 *
 * Output rules (Constitution Art. 3): plain words, no tables, no emoji, nothing
 * that relies on layout to convey meaning. Accessibility is stated first in
 * details. Vacancy is always described as a snapshot (Art. 7.1).
 */

import { NAVIGATOR_NAME } from "./providers/navigator-provider.mjs";

export const INDEPENDENCE_NOTE =
  "The Open State is an independent public-interest tool built on Alberta's " +
  "public Assisted Living Navigator data. It is not operated by or endorsed by " +
  "the Government of Alberta.";

export function address(item) {
  const street = [item.addressLine1, item.addressLine2].filter(Boolean).join(", ");
  const place = [item.city, item.province, item.postalCode].filter(Boolean).join(", ");
  return [street, place].filter(Boolean).join(", ");
}

/** Describe currently reported open spaces. Only Type A-C report a live count. */
export function vacancyPhrase(beds) {
  if (!beds.hasVacancy) return "No open spaces reported right now";
  const parts = [];
  if (beds.typeAVacant) parts.push(`${beds.typeAVacant} Type A (long-term care)`);
  if (beds.typeBVacant) parts.push(`${beds.typeBVacant} Type B`);
  if (beds.typeBSecureVacant) parts.push(`${beds.typeBSecureVacant} Type B secure`);
  if (beds.typeCVacant) parts.push(`${beds.typeCVacant} Type C`);
  return `${beds.totalVacant} space(s) reported open now: ${parts.join(", ")}`;
}

export function summaryLine(s, { withDistance }) {
  const bits = [s.name];
  if (withDistance && s.distanceKm != null) bits.push(`${s.distanceKm.toFixed(1)} km away`);
  if (s.city) bits.push(s.city);
  let line = "- " + bits.join("; ") + ".";
  const addr = address(s);
  if (addr) line += ` ${addr}.`;
  if (s.phoneNumber) line += ` Phone: ${s.phoneNumber}.`;
  if (s.careTypes.length) line += " Care: " + s.careTypes.join(", ") + ".";
  line += " " + vacancyPhrase(s.beds) + ".";
  line += ` (facility id: ${s.id})`;
  return line;
}

export function money(value) {
  if (value == null) return null;
  if (value === 0) return "no charge";
  if (Number.isInteger(value)) return "$" + value.toLocaleString("en-US");
  return (
    "$" + value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  );
}

export function formatDetails(d) {
  const lines = [`${d.name} (${NAVIGATOR_NAME}).`, INDEPENDENCE_NOTE, ""];

  // Accessibility first (Constitution Art. 3).
  if (d.accessible) {
    lines.push("Accessibility: this facility reports accessible features.");
    for (const note of d.accessibilityNotes) lines.push(`- ${note}`);
  } else {
    lines.push(
      "Accessibility: no accessible features are listed for this facility. " +
        "Confirm directly with the site, as listings can be incomplete."
    );
  }
  lines.push("");

  // Location and contact.
  const addr = address(d);
  if (addr) lines.push(`Address: ${addr}.`);
  const contact = [];
  if (d.phoneNumber) contact.push(`phone ${d.phoneNumber}`);
  if (d.siteEmail) contact.push(`email ${d.siteEmail}`);
  if (d.faxNumber) contact.push(`fax ${d.faxNumber}`);
  if (contact.length) lines.push("Contact: " + contact.join(", ") + ".");
  if (d.operatorName) {
    let operator = d.operatorName;
    if (d.operatorType) operator += ` (${d.operatorType} operator)`;
    lines.push(`Run by: ${operator}.`);
  }
  if (d.operatorWebsite) lines.push(`Operator website: ${d.operatorWebsite}`);
  if (d.virtualTourWebsite) lines.push(`Virtual tour: ${d.virtualTourWebsite}`);
  if (d.status) lines.push(`Status: ${d.status}.`);

  // Care types and capacity.
  lines.push("");
  if (d.careTypes.length) lines.push("Care types offered: " + d.careTypes.join(", ") + ".");
  lines.push(vacancyPhrase(d.beds) + ".");
  if (d.beds.totalFunded) lines.push(`Funded spaces (operating capacity): ${d.beds.totalFunded}.`);
  if (d.beds.supportedLiving) lines.push(`Supportive living spaces: ${d.beds.supportedLiving}.`);
  if (d.beds.seniorLodge) lines.push(`Seniors lodge spaces: ${d.beds.seniorLodge}.`);

  // Rooms.
  const rooms = [];
  if (d.numberOfSpacesPrivateRoom) rooms.push(`${d.numberOfSpacesPrivateRoom} private room(s)`);
  if (d.numberOfSpacesSharedRoom) rooms.push(`${d.numberOfSpacesSharedRoom} shared room(s)`);
  if (d.numberOfSpacesOneBedroom) rooms.push(`${d.numberOfSpacesOneBedroom} one-bedroom suite(s)`);
  if (d.numberOfSpacesMultiBedroom)
    rooms.push(`${d.numberOfSpacesMultiBedroom} multi-bedroom suite(s)`);
  if (d.numberOfSpacesAccessible) rooms.push(`${d.numberOfSpacesAccessible} accessible space(s)`);
  if (rooms.length) lines.push("Rooms: " + rooms.join(", ") + ".");
  if (d.roomTypes.length) lines.push("Room options: " + d.roomTypes.join(", ") + ".");

  // Pricing.
  if (d.roomPricings.length) {
    lines.push("");
    lines.push("Room pricing:");
    for (const p of d.roomPricings) {
      const lo = money(p.minimumFee);
      const hi = money(p.maximumFee);
      let price;
      if (lo && hi && lo !== hi) price = `${lo} to ${hi}`;
      else price = lo || hi || "fee not listed";
      const extra = [];
      if (p.rentGearedToIncome) extra.push("rent geared to income");
      if (p.funding) extra.push(p.funding.toLowerCase());
      const tail = extra.length ? ` (${extra.join("; ")})` : "";
      lines.push(`- ${p.roomType}: ${price}${tail}.`);
    }
  }

  // Amenities and services.
  if (d.amenities.length) {
    lines.push("");
    lines.push("Amenities: " + d.amenities.join(", ") + ".");
  }
  const serviceGroups = [
    ["Food services", d.foodServices],
    ["On-site services", d.siteServices],
    ["Security", d.securityServices],
    ["Transportation", d.transportationServices],
  ];
  for (const [label, items] of serviceGroups) {
    if (items.length) lines.push(`${label}: ` + items.map((i) => i.title).join(", ") + ".");
  }
  if (d.hasSmokingPolicy != null) {
    lines.push(d.hasSmokingPolicy ? "Has a smoking policy." : "No smoking policy listed.");
  }

  // Charges (only those with a real amount).
  const listed = d.charges.filter((c) => c.amount && c.amount > 0);
  if (listed.length) {
    lines.push("");
    lines.push("Extra charges:");
    for (const c of listed) {
      const amount = money(c.amount) || "";
      const freq = c.frequency ? ` ${c.frequency}` : "";
      const mand = c.isMandatory ? "mandatory" : "optional";
      const fund = c.funding ? `, ${c.funding.toLowerCase()}` : "";
      lines.push(`- ${c.name}: ${amount}${freq} (${mand}${fund}).`);
    }
  }

  // Trust and verification (point to the source of truth, Art. 6.3 / 7.1).
  lines.push("");
  if (d.accreditationStatus) {
    let acc = `Accreditation: ${d.accreditationStatus}`;
    if (d.accreditationOrganizationName) acc += ` by ${d.accreditationOrganizationName}`;
    lines.push(acc + ".");
    if (d.accreditationOrganizationUrl)
      lines.push(`Accreditation details: ${d.accreditationOrganizationUrl}`);
  }
  if (d.accommodationStandardsUrl) {
    lines.push(
      "Official accommodation standards and licensing record: " + d.accommodationStandardsUrl
    );
  }
  if (d.photos.length) lines.push(`Photos available: ${d.photos.length} (ask to see them).`);

  // How to act - we never apply on the citizen's behalf (Art. 2).
  lines.push("");
  lines.push(
    "To take the next step, contact the facility directly using the phone number " +
      "above. Publicly funded spaces (shown as 'Accessed Through AHS Case Manager') " +
      "are arranged through an Alberta Health Services case manager, not booked " +
      "directly - call Health Link at 811 to start. This tool never applies or " +
      "reserves a space for you."
  );
  return lines.join("\n");
}

export function describeFilters({
  accessibleBuilding,
  accessibleBathroom,
  careTypes,
  roomTypes,
  amenities,
  onlyWithVacancy,
}) {
  const parts = [];
  const access = [];
  if (accessibleBuilding) access.push("accessible building");
  if (accessibleBathroom) access.push("accessible bathroom");
  if (access.length) parts.push("filtered to " + access.join(" and "));
  if (careTypes && careTypes.length) parts.push("care: " + careTypes.join(", "));
  if (roomTypes && roomTypes.length) parts.push("rooms: " + roomTypes.join(", "));
  if (amenities && amenities.length) parts.push("amenities: " + amenities.join(", "));
  if (onlyWithVacancy) parts.push("with an open space now");
  return parts.join("; ");
}

export const CARE_OPTIONS_GUIDE =
  "Alberta's Assisted Living Navigator lists places that offer housing and care " +
  "for seniors and adults who need support. Here is what the terms generally mean. " +
  "This is plain-language guidance; confirm specifics with the facility and with " +
  "Alberta Health Services (AHS).\n" +
  "\n" +
  INDEPENDENCE_NOTE +
  "\n" +
  "\n" +
  "Care types (least to most care):\n" +
  "- Seniors lodge: housing for seniors who manage most daily activities on their " +
  "own, with meals, housekeeping, and social programs. Income-tested.\n" +
  "- Supportive living: your own space plus services and some personal care; the " +
  "amount of care varies by site.\n" +
  "- Type C: enhanced supportive living, lodge-style, with more services.\n" +
  "- Type B (designated supportive living): publicly funded supportive living with " +
  "care staff on site, for people who need regular help.\n" +
  "- Type B secure: a secure setting for people living with dementia or memory loss " +
  "who need a safe, enclosed environment (memory care).\n" +
  "- Type A (long-term care, also called facility living): 24-hour nursing care for " +
  "people with complex health needs.\n" +
  "\n" +
  "How you get a space (funding):\n" +
  "- Accessed Through AHS Case Manager: a publicly funded space. You do not apply " +
  "directly; an AHS case manager assesses needs and arranges placement. To start, " +
  "call Health Link at 811 or ask a doctor or social worker for a referral.\n" +
  "- Accessed Through Site Directly: a private space you arrange and pay for with " +
  "the operator yourself.\n" +
  "\n" +
  "Filters you can use when searching near a place:\n" +
  "- Accessibility (most important for mobility needs): 'accessible building' and " +
  "'accessible bathroom' return only places reporting those features.\n" +
  "- Care types: the streams listed above (for example 'memory care', 'long-term " +
  "care', 'supportive living').\n" +
  "- Room types: private room, shared room, one bedroom, multi bedroom.\n" +
  "- Amenities: private bathroom, meals included, emergency call system, " +
  "housekeeping, laundry, parking, gardens, social activities, hairdresser or " +
  "barber, small pets allowed, and smoking options.\n" +
  "- Open space now: keep only places reporting a vacancy. Vacancy is a snapshot " +
  "the operator reported, not a guarantee - always confirm.\n" +
  "\n" +
  "Next steps are always taken by you: this tool finds and explains options, but " +
  "never applies, reserves, or pays for anything.";
