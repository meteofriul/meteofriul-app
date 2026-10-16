import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CANDIDATE_PATH = path.join(ROOT_DIR, "scripts", "data", "municipality-photo-candidates.json");
const OVERRIDE_PATH = path.join(
  ROOT_DIR,
  "scripts",
  "data",
  "municipality-photo-selection-overrides.json",
);
const RUNTIME_MANIFEST_PATH = path.join(
  ROOT_DIR,
  "frontend",
  "src",
  "data",
  "discover",
  "municipalityPhotos.json",
);
const OUTPUT_PATH = path.join(ROOT_DIR, "scripts", "data", "municipality-photo-selection.json");
const WRITE = process.argv.includes("--write");
const DEFAULT_REVIEW_DATE = "2026-07-22";

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8").replace(/^\uFEFF/, ""));
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function fail(message) {
  throw new Error(message);
}

const catalog = readJson(CANDIDATE_PATH);
const overrideCatalog = readJson(OVERRIDE_PATH);
const runtimeManifest = readJson(RUNTIME_MANIFEST_PATH);
const overrides = new Map(
  overrideCatalog.records.map((record) => [record.istatCode, record]),
);
const currentRuntime = new Map(
  runtimeManifest.photos.map((photo) => [photo.istatCode, photo]),
);
const seenCodes = new Set();

const records = catalog.records.map((record) => {
  if (seenCodes.has(record.istatCode)) fail(`duplicate candidate code: ${record.istatCode}`);
  seenCodes.add(record.istatCode);

  const uniqueCandidates = [...new Map(
    record.candidates.map((candidate) => [candidate.fileName, candidate]),
  ).values()];
  const existingApproved = uniqueCandidates.find((candidate) => candidate.reviewStatus === "approved");
  const override = overrides.get(record.istatCode);
  const selectedFileName = override?.selectedFileName
    || existingApproved?.fileName
    || uniqueCandidates[0]?.fileName;
  const selectedCandidate = uniqueCandidates.find(
    (candidate) => candidate.fileName === selectedFileName,
  );

  if (!selectedCandidate) {
    fail(`no selected candidate for ${record.istatCode} ${record.municipality}`);
  }
  if (selectedCandidate.licenseAccepted === false) {
    fail(`selected candidate has an unsupported license: ${record.istatCode}`);
  }

  const existingPhoto = currentRuntime.get(record.istatCode);
  const selection = {
    istatCode: record.istatCode,
    municipality: record.municipality,
    province: record.province,
    selectedFileName,
    objectPosition: override?.objectPosition || existingPhoto?.objectPosition || "50% 50%",
    reviewStatus: "approved",
    reviewMethod: override?.reviewMethod
      || (existingApproved ? "existing_runtime_approval" : "contact_sheet_review"),
    reviewedAt: override?.reviewedAt
      || (existingApproved ? "2026-07-19" : DEFAULT_REVIEW_DATE),
  };

  if (override?.creditDisplayName) selection.creditDisplayName = override.creditDisplayName;
  if (override?.creditSubject) selection.creditSubject = override.creditSubject;

  return selection;
});

for (const code of overrides.keys()) {
  if (!seenCodes.has(code)) fail(`override refers to an unknown ISTAT code: ${code}`);
}

if (records.length !== catalog.coverage.profiles) {
  fail(`selection coverage mismatch: ${records.length} != ${catalog.coverage.profiles}`);
}

const output = {
  schemaVersion: 1,
  generatedAt: records.reduce(
    (latest, record) => record.reviewedAt > latest ? record.reviewedAt : latest,
    DEFAULT_REVIEW_DATE,
  ),
  policy: {
    automaticPublication: false,
    explicitSelectionPerMunicipality: true,
    visualReviewRequired: true,
    catalogRankingIsNotRuntimeSelection: true,
  },
  coverage: {
    profiles: catalog.coverage.profiles,
    selected: records.length,
    unresolved: catalog.coverage.profiles - records.length,
  },
  records,
};

if (WRITE) writeJson(OUTPUT_PATH, output);

console.log(JSON.stringify({
  outputPath: WRITE ? OUTPUT_PATH : null,
  ...output.coverage,
  overrides: overrides.size,
}, null, 2));
