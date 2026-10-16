import { execFileSync } from "node:child_process";
import fs from "node:fs";

const BASELINE_ARG = process.argv.find((arg) => arg.startsWith("--baseline-ref="));
const BASELINE_REF = BASELINE_ARG?.slice("--baseline-ref=".length);
const FILES = [
  "frontend/src/data/discover/municipalityProfileCandidates.go-ts.json",
  "frontend/src/data/discover/municipalityProfileCandidates.pn.json",
  "frontend/src/data/discover/municipalityProfileCandidates.ud-a-l.json",
  "frontend/src/data/discover/municipalityProfileCandidates.ud-m-r.json",
  "frontend/src/data/discover/municipalityProfileCandidates.ud-s-z.json",
];

if (!BASELINE_REF) {
  throw new Error("Pass --baseline-ref=<commit> for the approved Italian baseline.");
}

function parseJson(value) {
  return JSON.parse(String(value).replace(/^\uFEFF/, ""));
}

function readBaseline(filePath) {
  return parseJson(execFileSync(
    "git",
    ["show", `${BASELINE_REF}:${filePath}`],
    { encoding: "utf8", maxBuffer: 20 * 1024 * 1024 },
  ));
}

function readCurrent(filePath) {
  return parseJson(fs.readFileSync(filePath, "utf8"));
}

function stripTranslationChanges(profile) {
  const clone = structuredClone(profile);

  if (clone.title) delete clone.title.fur;
  if (clone.summary) delete clone.summary.fur;
  for (const milestone of clone.milestones || []) {
    if (milestone.label) delete milestone.label.fur;
  }
  if (clone.languageStatus) delete clone.languageStatus.fur;
  delete clone.editorialStatus;
  delete clone.readyForUi;
  if (clone.review) {
    delete clone.review.furReviewedAt;
    delete clone.review.furMethod;
  }

  return clone;
}

const issues = [];
let comparedProfiles = 0;

for (const filePath of FILES) {
  const baseline = readBaseline(filePath);
  const current = readCurrent(filePath);
  const baselineProfiles = baseline.profiles || [];
  const currentProfiles = current.profiles || [];

  if (baseline.schemaVersion !== current.schemaVersion || baseline.scope !== current.scope) {
    issues.push(`${filePath}: root identity changed`);
  }
  if (baselineProfiles.length !== currentProfiles.length) {
    issues.push(`${filePath}: profile count changed`);
  }

  const currentById = new Map(currentProfiles.map((profile) => [profile.id, profile]));
  for (const baselineProfile of baselineProfiles) {
    const currentProfile = currentById.get(baselineProfile.id);
    comparedProfiles += 1;

    if (!currentProfile) {
      issues.push(`${filePath}: missing ${baselineProfile.id}`);
      continue;
    }

    const expected = JSON.stringify(stripTranslationChanges(baselineProfile));
    const actual = JSON.stringify(stripTranslationChanges(currentProfile));
    if (expected !== actual) {
      issues.push(`${filePath}: non-FUR content changed for ${baselineProfile.id}`);
    }
  }
}

console.log(JSON.stringify({
  baselineRef: BASELINE_REF,
  files: FILES.length,
  comparedProfiles,
  issues,
}, null, 2));

if (issues.length) process.exitCode = 1;
