import fs from "node:fs";

const REVIEW_PATH = process.argv[2];
const ARCHIVE_PATH = "frontend/src/data/discover/municipalityProfiles.json";

if (!REVIEW_PATH) {
  throw new Error("Pass the reviewed municipality profile JSON path.");
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8").replace(/^\uFEFF/, ""));
}

function assertReviewedProfile(profile) {
  if (!profile?.id || !profile?.istatCode || !profile?.municipality || !profile?.province) {
    throw new Error(`Incomplete municipality identity: ${profile?.id || "unknown"}`);
  }
  if (profile.editorialStatus !== "reviewed") {
    throw new Error(`Profile is not reviewed: ${profile.id}`);
  }
  if (profile.readyForUi !== true) {
    throw new Error(`Profile is not ready for UI: ${profile.id}`);
  }
  if (profile.languageStatus?.it !== "approved" || profile.languageStatus?.fur !== "approved") {
    throw new Error(`Both IT and FUR must be approved: ${profile.id}`);
  }
  if (!profile.title?.it || !profile.title?.fur || !profile.summary?.it || !profile.summary?.fur) {
    throw new Error(`Bilingual title or summary is missing: ${profile.id}`);
  }
  if (!profile.source?.label || !/^https:\/\//.test(String(profile.source?.url || ""))) {
    throw new Error(`Verified HTTPS source is missing: ${profile.id}`);
  }
}

const review = readJson(REVIEW_PATH);
const archive = readJson(ARCHIVE_PATH);
const reviewedProfiles = review.profiles || [];
const existingProfiles = archive.profiles || [];

if (!reviewedProfiles.length) {
  throw new Error("The review file contains no profiles.");
}

for (const profile of reviewedProfiles) assertReviewedProfile(profile);

const duplicateReviewCodes = reviewedProfiles
  .map((profile) => profile.istatCode)
  .filter((code, index, codes) => codes.indexOf(code) !== index);
if (duplicateReviewCodes.length) {
  throw new Error(`Duplicate ISTAT codes in review: ${[...new Set(duplicateReviewCodes)].join(", ")}`);
}

const reviewedByIstatCode = new Map(
  reviewedProfiles.map((profile) => [profile.istatCode, profile]),
);
const mergedProfiles = existingProfiles
  .filter((profile) => !reviewedByIstatCode.has(profile.istatCode))
  .concat(reviewedProfiles)
  .sort((first, second) => first.istatCode.localeCompare(second.istatCode));

const nextArchive = {
  ...archive,
  generatedAt: new Date().toISOString().slice(0, 10),
  profiles: mergedProfiles,
};

fs.writeFileSync(ARCHIVE_PATH, `${JSON.stringify(nextArchive, null, 2)}\n`, "utf8");

console.log(JSON.stringify({
  promoted: reviewedProfiles.length,
  totalEditorialProfiles: mergedProfiles.length,
  ids: reviewedProfiles.map((profile) => profile.id),
}, null, 2));
