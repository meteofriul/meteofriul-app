import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const ROOT = process.cwd();
const SAINTS_PATH = path.join(ROOT, "frontend/src/data/almanac/saints.json");
const PROFILES_PATH = path.join(ROOT, "frontend/src/data/almanac/saintProfiles.json");
const BATCH_DIRECTORY = path.join(ROOT, "scripts/data/saint-profiles");
const BATCH_FILES = [
  "month-01-02.json",
  "month-03-04.json",
  "month-05-06.json",
  "month-07-08.json",
  "month-07-21-28.json",
  "month-09-10.json",
  "month-11-12.json",
];

const DAY_KEY_PATTERN = /^\d{2}-\d{2}$/;
const ITALIAN_REMNANT_PATTERN = /\b(?:ricordat[oaie]|vescovo|sacerdote|martire|vergine|chiesa|nella|nelle|della|delle|dello|furono|mor[iì]|nacque|secondo|presso|durante|imperatore|citt[aà])\b/giu;
const write = process.argv.includes("--write");

async function readJson(filePath) {
  return JSON.parse(await fs.readFile(filePath, "utf8"));
}

function validateProfile(dayKey, profile, saint, sourceLabel) {
  const errors = [];
  const descriptionIt = String(profile?.description_it || "").trim();
  const descriptionFur = String(profile?.description_fur || "").trim();
  const descriptionItStatus = profile?.description_it_status;
  const descriptionFurStatus = profile?.description_fur_status;

  if (!DAY_KEY_PATTERN.test(dayKey)) errors.push("invalid day key");
  if (!saint) errors.push("day is absent from saints.json");
  if (descriptionIt.length > 260) errors.push("Italian description exceeds 260 characters");
  if (/\r|\n/.test(descriptionIt)) errors.push("Italian description must stay on one line");
  if (descriptionIt && descriptionItStatus !== "curated") {
    errors.push("verified Italian description must use curated status");
  }
  if (!descriptionIt && descriptionItStatus !== "pending_source") {
    errors.push("missing Italian description must use pending_source status");
  }
  if (descriptionIt) {
    if (!descriptionFur) errors.push("curated Italian description requires Friulian copy");
    if (descriptionFurStatus !== "curated") {
      errors.push("verified Friulian description must use curated status");
    }
    if (descriptionFur.length > 300) errors.push("Friulian description exceeds 300 characters");
    if (/\r|\n/.test(descriptionFur)) errors.push("Friulian description must stay on one line");
    if (descriptionFur.localeCompare(descriptionIt, "it", { sensitivity: "base" }) === 0) {
      errors.push("Friulian description cannot duplicate the Italian copy");
    }
  } else {
    if (descriptionFur) errors.push("record without source cannot have Friulian copy");
    if (descriptionFurStatus !== "pending_review") {
      errors.push("record without source must keep Friulian status pending_review");
    }
  }
  if (/[ÃÂ�]/.test(descriptionIt + descriptionFur)) {
    errors.push("description contains mojibake");
  }
  if (profile?.profile_source !== "CEI - Martirologio Romano") {
    errors.push("unexpected profile source");
  }
  const expectedMonthDay = dayKey.replace("-", "");
  const sourceUrlMatch = String(profile?.profile_source_url || "").match(
    /^https:\/\/www\.chiesacattolica\.it\/santo-del-giorno\/\?data-liturgia=(\d{8})$/,
  );
  if (!sourceUrlMatch || !sourceUrlMatch[1].endsWith(expectedMonthDay)) {
    errors.push("profile URL is not an official CEI page for the same month and day");
  }
  const expectedReviewStatus = descriptionIt ? "approved_it" : "pending_source";
  if (profile?.profile_review_status !== expectedReviewStatus) {
    errors.push(`review status must be ${expectedReviewStatus}`);
  }

  if (errors.length) {
    throw new Error(`${sourceLabel} ${dayKey}: ${errors.join("; ")}`);
  }
}

const saints = await readJson(SAINTS_PATH);
const calendarKeys = Object.keys(saints).filter((key) => DAY_KEY_PATTERN.test(key)).sort();
const merged = {};
const owners = new Map();

for (const fileName of BATCH_FILES) {
  const filePath = path.join(BATCH_DIRECTORY, fileName);
  const batch = await readJson(filePath);

  for (const [dayKey, profile] of Object.entries(batch)) {
    validateProfile(dayKey, profile, saints[dayKey], fileName);
    if (owners.has(dayKey)) {
      throw new Error(`${dayKey} is duplicated by ${owners.get(dayKey)} and ${fileName}`);
    }
    owners.set(dayKey, fileName);
    merged[dayKey] = profile;
  }
}

const missing = calendarKeys.filter((dayKey) => !merged[dayKey]);
const unexpected = Object.keys(merged).filter((dayKey) => !calendarKeys.includes(dayKey));
if (missing.length || unexpected.length) {
  throw new Error([
    missing.length ? `missing dates: ${missing.join(", ")}` : "",
    unexpected.length ? `unexpected dates: ${unexpected.join(", ")}` : "",
  ].filter(Boolean).join("; "));
}

const sortedProfiles = Object.fromEntries(
  calendarKeys.map((dayKey) => [dayKey, merged[dayKey]]),
);
const unresolvedIt = calendarKeys.filter((dayKey) => !sortedProfiles[dayKey].description_it);
const unresolvedFur = calendarKeys.filter((dayKey) => !sortedProfiles[dayKey].description_fur);
const possibleItalianRemnants = calendarKeys.flatMap((dayKey) => {
  const descriptionFur = sortedProfiles[dayKey].description_fur || "";
  const matches = [...descriptionFur.matchAll(ITALIAN_REMNANT_PATTERN)].map((match) => match[0]);
  return matches.length ? [{ dayKey, matches: [...new Set(matches)] }] : [];
});

if (write) {
  await fs.writeFile(PROFILES_PATH, `${JSON.stringify(sortedProfiles, null, 2)}\n`, "utf8");
}

console.log(JSON.stringify({
  batches: BATCH_FILES.length,
  calendarDays: calendarKeys.length,
  profiles: Object.keys(sortedProfiles).length,
  unresolvedIt: unresolvedIt.length,
  unresolvedItDates: unresolvedIt,
  unresolvedFur: unresolvedFur.length,
  unresolvedFurDates: unresolvedFur,
  possibleItalianRemnants,
  wroteCatalog: write,
}, null, 2));
