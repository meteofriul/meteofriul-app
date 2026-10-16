import fs from "node:fs";

const REVIEW_PATH = process.argv[2] || "frontend/src/data/discover/discoverDailyItalianReviewWave.json";
const LOCAL_MEMORY_PATH = "frontend/src/data/discover/localMemory.json";

const HISTORY_IDS = new Set([
  "profile-review-0317-bruno-pincherle",
  "profile-review-0329-tarcisio-petracco",
  "wave-history-0423-eccidio-via-ghega",
  "wave-history-0531-strage-peteano",
  "wave-history-0701-decimazione-cercivento",
  "wave-history-0403-eccidio-opicina",
  "wave-history-0804-attentato-siot",
]);

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8").replace(/^\uFEFF/, ""));
}

function slugify(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 52);
}

function normalizeArea(value) {
  return slugify(value).replace(/-/g, "_");
}

function toRuntimeDateKey(dateIt) {
  const match = String(dateIt || "").match(/^(\d{2})-(\d{2})$/);
  if (!match) throw new Error(`Invalid Italian date: ${dateIt}`);
  return `${match[2]}-${match[1]}`;
}

function formatRecordForLocalMemory(record) {
  return JSON.stringify(record, null, 2)
    .split("\n")
    .map((line) => `    ${line}`)
    .join("\n");
}

function appendRecordsPreservingFile(filePath, newRecords) {
  if (!newRecords.length) return;

  const text = fs.readFileSync(filePath, "utf8");
  const marker = "\n  ]\n}\n";
  const index = text.lastIndexOf(marker);
  if (index === -1) {
    throw new Error(`Cannot find records array closing marker in ${filePath}`);
  }

  const block = newRecords.map(formatRecordForLocalMemory).join(",\n");
  fs.writeFileSync(filePath, `${text.slice(0, index)},\n${block}${text.slice(index)}`, "utf8");
}

function buildRecord(candidate, reviewedAt) {
  const dateAnchor = toRuntimeDateKey(candidate.dateIt);
  const compactDate = dateAnchor.replace("-", "");
  const municipalityArea = normalizeArea(candidate.municipality);
  const localityArea = normalizeArea(candidate.locality);
  const provinceArea = String(candidate.province || "").toLowerCase();

  return {
    id: `memory-it-ready-${compactDate}-${slugify(candidate.titleIt)}`,
    candidateId: candidate.id,
    primaryUse: "discover",
    recommendedSurface: "discover",
    category: candidate.canonicalCategory || (HISTORY_IDS.has(candidate.id) ? "storia" : "cultura"),
    dailyRole: candidate.dailyRole || "primary",
    dateAnchors: [dateAnchor],
    rotationTags: [
      "memoria",
      municipalityArea,
      provinceArea,
    ].filter(Boolean),
    areas: [...new Set([
      localityArea,
      municipalityArea,
      provinceArea,
      "friuli_venezia_giulia",
    ].filter(Boolean))],
    priority: Number.isFinite(Number(candidate.priority)) ? Number(candidate.priority) : 54,
    title: {
      it: candidate.titleIt,
      fur: "pending_review",
    },
    summary: {
      it: candidate.copyIt,
      fur: "pending_review",
    },
    source: {
      label: candidate.sourceLabel,
      type: "verified_source",
      ...(candidate.wikidataId ? { wikidataId: candidate.wikidataId } : {}),
      entityId: candidate.sourceEntityId || candidate.wikidataId,
      url: candidate.sourceUrl,
      confidence: "strong_editorial_review",
      note: "Fonte e copy IT approvati nella revisione Scopri. Pubblicazione bloccata fino alla revisione FUR.",
    },
    editorialStatus: "source_verified",
    languageStatus: {
      it: "approved",
      fur: "human_review_needed",
    },
    editorialReview: {
      reviewedAt,
      note: "Record canonico IT approvato; FUR e readyForUi restano bloccanti.",
    },
    readyForUi: false,
  };
}

const review = readJson(REVIEW_PATH);
const localMemory = readJson(LOCAL_MEMORY_PATH);
const candidates = review.keepDaily || [];
const existingRecords = localMemory.records || [];
const reviewedAt = /^\d{4}-\d{2}-\d{2}$/.test(String(review.generatedAt || ""))
  ? review.generatedAt
  : new Date().toISOString().slice(0, 10);

if (candidates.length !== review.summary.keepDaily) {
  throw new Error("Review summary and candidate count do not match.");
}

if (candidates.some((candidate) => (
  candidate.readyForUi !== false
  || candidate.sourceStatus !== "pass"
  || (!candidate.wikidataId && !candidate.sourceEntityId)
  || !candidate.copyIt
))) {
  throw new Error("The Italian review contains a candidate that is not ready for canonical staging.");
}

const knownCandidateIds = new Set(existingRecords.map((record) => record.candidateId).filter(Boolean));
const knownEntityIds = new Set(existingRecords.flatMap((record) => [
  record.source?.wikidataId,
  record.source?.entityId,
]).filter(Boolean));
const knownPrimaryDates = new Set(
  existingRecords
    .filter((record) => record.dailyRole !== "secondary" && record.primaryUse === "discover")
    .flatMap((record) => record.dateAnchors || []),
);
const newRecords = [];

for (const candidate of candidates) {
  const candidateEntityId = candidate.sourceEntityId || candidate.wikidataId;
  if (knownCandidateIds.has(candidate.id) || knownEntityIds.has(candidateEntityId)) continue;

  const record = buildRecord(candidate, reviewedAt);
  if (record.dailyRole !== "secondary" && record.dateAnchors.some((dateKey) => knownPrimaryDates.has(dateKey))) {
    throw new Error(`Candidate collides with a canonical primary date: ${candidate.id}`);
  }
  newRecords.push(record);
  if (record.dailyRole !== "secondary") {
    for (const dateKey of record.dateAnchors) knownPrimaryDates.add(dateKey);
  }
}

appendRecordsPreservingFile(LOCAL_MEMORY_PATH, newRecords);

console.log(JSON.stringify({
  promotedToCanonicalStaging: newRecords.length,
  ids: newRecords.map((record) => record.id),
  readyForUi: 0,
  furApproved: 0,
}, null, 2));
