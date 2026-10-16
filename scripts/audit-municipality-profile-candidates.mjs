import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { FIXED_FVG_PLACES } from "../frontend/src/data/fvgPlaces.js";

const ROOT_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DATA_DIR = path.join(ROOT_DIR, "frontend", "src", "data", "discover");
const EDITORIAL_PATH = path.join(DATA_DIR, "municipalityProfiles.json");
const FILE_PREFIX = "municipalityProfileCandidates.";
const FILE_SUFFIX = ".json";
const STRICT = process.argv.includes("--strict");
const REQUIRE_IT_REVIEWED = process.argv.includes("--require-it-reviewed");
const REQUIRE_BILINGUAL_REVIEWED = process.argv.includes("--require-bilingual-reviewed");
const ALLOW_PROMOTED = process.argv.includes("--allow-promoted");

const ALLOWED_SOURCE_TYPES = new Set([
  "official_municipality",
  "national_institution",
  "regional_institution",
  "cultural_institution",
  "wikipedia_reference",
]);

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8").replace(/^\uFEFF/, ""));
}

function normalizeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function containsMojibake(value) {
  return /[\u00c2\u00c3\ufffd]/u.test(JSON.stringify(value));
}

function addIssue(issues, fileName, profile, message) {
  issues.push({
    file: fileName,
    id: profile?.id || null,
    istatCode: profile?.istatCode || null,
    message,
  });
}

const canonicalByIstatCode = new Map(
  Object.values(FIXED_FVG_PLACES).map((place) => [place.istatCode, place]),
);
const editorialProfiles = readJson(EDITORIAL_PATH).profiles || [];
const editorialByIstatCode = new Map(
  editorialProfiles.map((profile) => [profile.istatCode, profile]),
);
const editorialIstatCodes = new Set(editorialProfiles.map((profile) => profile.istatCode));
const expectedProfiles = [...canonicalByIstatCode.values()]
  .filter((place) => !editorialIstatCodes.has(place.istatCode));
const expectedIstatCodes = new Set(expectedProfiles.map((place) => place.istatCode));

const fileNames = fs.readdirSync(DATA_DIR)
  .filter((fileName) => fileName.startsWith(FILE_PREFIX) && fileName.endsWith(FILE_SUFFIX))
  .sort((first, second) => first.localeCompare(second));

const issues = [];
const profiles = [];
const seenIds = new Set();
const seenIstatCodes = new Set();
const titleOwners = new Map();
const summaryOwners = new Map();
let promotedMatches = 0;

for (const fileName of fileNames) {
  const payload = readJson(path.join(DATA_DIR, fileName));

  if (payload.schemaVersion !== 1) {
    addIssue(issues, fileName, null, "schemaVersion must be 1");
  }
  if (!Array.isArray(payload.profiles)) {
    addIssue(issues, fileName, null, "profiles must be an array");
    continue;
  }

  for (const profile of payload.profiles) {
    profiles.push(profile);
    const canonical = canonicalByIstatCode.get(profile.istatCode);

    if (containsMojibake(profile)) {
      addIssue(issues, fileName, profile, "profile contains mojibake or replacement characters");
    }

    if (!profile.id || seenIds.has(profile.id)) {
      addIssue(issues, fileName, profile, "id is missing or duplicated");
    }
    if (profile.id) seenIds.add(profile.id);

    if (!canonical) {
      addIssue(issues, fileName, profile, "istatCode is not in the canonical FVG registry");
    } else {
      if (canonical.name !== profile.municipality) {
        addIssue(issues, fileName, profile, `municipality must be ${canonical.name}`);
      }
      if (canonical.province !== profile.province) {
        addIssue(issues, fileName, profile, `province must be ${canonical.province}`);
      }
    }

    if (editorialIstatCodes.has(profile.istatCode)) {
      if (!ALLOW_PROMOTED) {
        addIssue(issues, fileName, profile, "candidate overlaps an existing editorial profile");
      } else if (JSON.stringify(editorialByIstatCode.get(profile.istatCode)) !== JSON.stringify(profile)) {
        addIssue(issues, fileName, profile, "candidate differs from its promoted editorial profile");
      } else {
        promotedMatches += 1;
      }
    }
    if (seenIstatCodes.has(profile.istatCode)) {
      addIssue(issues, fileName, profile, "istatCode is duplicated across candidate files");
    }
    if (profile.istatCode) seenIstatCodes.add(profile.istatCode);

    const title = normalizeText(profile.title?.it);
    const summary = normalizeText(profile.summary?.it);
    if (!title || title === "pending_review") {
      addIssue(issues, fileName, profile, "title.it is missing");
    }
    if (!summary || summary === "pending_review") {
      addIssue(issues, fileName, profile, "summary.it is missing");
    }
    if (summary.length > 720) {
      addIssue(issues, fileName, profile, "summary.it exceeds 720 characters");
    }
    if (title.startsWith("Un primo sguardo a ")) {
      addIssue(issues, fileName, profile, "title.it still uses the registry fallback");
    }
    if (summary.includes("La scheda presenta la località")) {
      addIssue(issues, fileName, profile, "summary.it still uses the registry fallback");
    }
    if ((summary.match(/[.!?](?:\s|$)/g) || []).length < 2) {
      addIssue(issues, fileName, profile, "summary.it must contain two complete sentences");
    }

    const normalizedTitle = title.toLocaleLowerCase("it");
    const normalizedSummary = summary.toLocaleLowerCase("it");
    if (titleOwners.has(normalizedTitle)) {
      addIssue(issues, fileName, profile, `title.it duplicates ${titleOwners.get(normalizedTitle)}`);
    } else if (normalizedTitle) {
      titleOwners.set(normalizedTitle, profile.id);
    }
    if (summaryOwners.has(normalizedSummary)) {
      addIssue(issues, fileName, profile, `summary.it duplicates ${summaryOwners.get(normalizedSummary)}`);
    } else if (normalizedSummary) {
      summaryOwners.set(normalizedSummary, profile.id);
    }
    if (!ALLOWED_SOURCE_TYPES.has(profile.source?.type)) {
      addIssue(issues, fileName, profile, "source.type is not allowed");
    }
    if (!normalizeText(profile.source?.label)) {
      addIssue(issues, fileName, profile, "source.label is missing");
    }
    if (!/^https:\/\//.test(String(profile.source?.url || ""))) {
      addIssue(issues, fileName, profile, "source.url must use HTTPS");
    }
    if (profile.editorialStatus === "source_collected") {
      if (profile.languageStatus?.it !== "editorial_candidate") {
        addIssue(issues, fileName, profile, "source_collected profile must keep IT as editorial_candidate");
      }
      if (profile.languageStatus?.fur !== "not_started") {
        addIssue(issues, fileName, profile, "source_collected profile must keep FUR as not_started");
      }
    } else if (profile.editorialStatus === "it_reviewed") {
      if (profile.languageStatus?.it !== "approved") {
        addIssue(issues, fileName, profile, "it_reviewed profile must have approved IT");
      }
      if (profile.languageStatus?.fur !== "not_started") {
        addIssue(issues, fileName, profile, "it_reviewed profile must keep FUR as not_started");
      }
      if (!/^\d{4}-\d{2}-\d{2}$/.test(String(profile.review?.itReviewedAt || ""))) {
        addIssue(issues, fileName, profile, "it_reviewed profile must record itReviewedAt");
      }
      if (profile.review?.method !== "source_cross_check") {
        addIssue(issues, fileName, profile, "it_reviewed profile must record source_cross_check");
      }
    } else if (profile.editorialStatus === "reviewed") {
      if (profile.languageStatus?.it !== "approved" || profile.languageStatus?.fur !== "approved") {
        addIssue(issues, fileName, profile, "reviewed profile must have approved IT and FUR");
      }
      if (!/^\d{4}-\d{2}-\d{2}$/.test(String(profile.review?.itReviewedAt || ""))) {
        addIssue(issues, fileName, profile, "reviewed profile must retain itReviewedAt");
      }
      if (profile.review?.method !== "source_cross_check") {
        addIssue(issues, fileName, profile, "reviewed profile must retain source_cross_check");
      }
      const furTitle = normalizeText(profile.title?.fur);
      const furSummary = normalizeText(profile.summary?.fur);
      if (!furTitle || !furSummary) {
        addIssue(issues, fileName, profile, "reviewed profile must contain bilingual title and summary");
      }
      if (furSummary.length > 720) {
        addIssue(issues, fileName, profile, "summary.fur exceeds 720 characters");
      }
      if ((furSummary.match(/[.!?](?:\s|$)/g) || []).length < 2) {
        addIssue(issues, fileName, profile, "summary.fur must contain two complete sentences");
      }
      if (furSummary && furSummary === summary) {
        addIssue(issues, fileName, profile, "summary.fur still duplicates the Italian copy");
      }
      if (!/^\d{4}-\d{2}-\d{2}$/.test(String(profile.review?.furReviewedAt || ""))) {
        addIssue(issues, fileName, profile, "reviewed profile must record furReviewedAt");
      }
      if (profile.review?.furMethod !== "linguistic_review") {
        addIssue(issues, fileName, profile, "reviewed profile must record linguistic_review");
      }
      if (profile.readyForUi !== true) {
        addIssue(issues, fileName, profile, "reviewed bilingual profile must be ready for UI");
      }
    } else {
      addIssue(issues, fileName, profile, "editorialStatus must be source_collected, it_reviewed or reviewed");
    }
    if (profile.editorialStatus !== "reviewed" && profile.readyForUi !== false) {
      addIssue(issues, fileName, profile, "profile must remain unavailable until bilingual review");
    }
    if (!Array.isArray(profile.milestones)) {
      addIssue(issues, fileName, profile, "milestones must be an array");
    } else {
      if (profile.milestones.length > 3) {
        addIssue(issues, fileName, profile, "milestones cannot exceed three entries");
      }
      for (const milestone of profile.milestones) {
        if (!milestone?.id || (!milestone?.year && !milestone?.century) || !normalizeText(milestone?.label?.it)) {
          addIssue(issues, fileName, profile, "milestone identity, period or Italian label is incomplete");
        }
        if (profile.editorialStatus === "reviewed" && !normalizeText(milestone?.label?.fur)) {
          addIssue(issues, fileName, profile, "reviewed milestone is missing its FUR label");
        }
      }
    }
  }
}

const missingProfiles = expectedProfiles
  .filter((place) => !seenIstatCodes.has(place.istatCode))
  .map((place) => ({
    istatCode: place.istatCode,
    municipality: place.name,
    province: place.province,
  }));
const unexpectedIstatCodes = [...seenIstatCodes]
  .filter((istatCode) => (
    !expectedIstatCodes.has(istatCode)
    && !(ALLOW_PROMOTED && editorialIstatCodes.has(istatCode))
  ));
const byProvince = profiles.reduce((counts, profile) => {
  counts[profile.province] = (counts[profile.province] || 0) + 1;
  return counts;
}, {});
const bySourceType = profiles.reduce((counts, profile) => {
  const sourceType = profile.source?.type || "missing";
  counts[sourceType] = (counts[sourceType] || 0) + 1;
  return counts;
}, {});
const byEditorialStatus = profiles.reduce((counts, profile) => {
  const editorialStatus = profile.editorialStatus || "missing";
  counts[editorialStatus] = (counts[editorialStatus] || 0) + 1;
  return counts;
}, {});
const pendingItalianReview = profiles.filter((profile) => (
  profile.editorialStatus !== "it_reviewed" && profile.editorialStatus !== "reviewed"
));
const pendingFurReview = profiles.filter((profile) => profile.editorialStatus !== "reviewed");

const report = {
  candidateFiles: fileNames.length,
  candidateProfiles: profiles.length,
  expectedProfiles: expectedProfiles.length,
  byProvince,
  bySourceType,
  byEditorialStatus,
  promotedMatches,
  issues,
  missingProfiles,
  unexpectedIstatCodes,
  pendingItalianReview: pendingItalianReview.length,
  pendingFurReview: pendingFurReview.length,
  strict: STRICT,
  requireItReviewed: REQUIRE_IT_REVIEWED,
  requireBilingualReviewed: REQUIRE_BILINGUAL_REVIEWED,
  allowPromoted: ALLOW_PROMOTED,
};

console.log(JSON.stringify(report, null, 2));

if (
  issues.length
  || unexpectedIstatCodes.length
  || (STRICT && missingProfiles.length)
  || (REQUIRE_IT_REVIEWED && pendingItalianReview.length)
  || (REQUIRE_BILINGUAL_REVIEWED && pendingFurReview.length)
) {
  process.exitCode = 1;
}
