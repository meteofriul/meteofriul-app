import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PROFILE_PATH = path.join(
  ROOT_DIR,
  "frontend",
  "src",
  "data",
  "discover",
  "municipalityProfiles.json",
);
const PHOTO_MANIFEST_PATH = path.join(
  ROOT_DIR,
  "frontend",
  "src",
  "data",
  "discover",
  "municipalityPhotos.json",
);
const SOURCE_CATALOG_PATH = path.join(
  ROOT_DIR,
  "frontend",
  "src",
  "data",
  "discover",
  "municipalityPhotoCredits.json",
);

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8").replace(/^\uFEFF/, ""));
}

function fail(message) {
  throw new Error(message);
}

function validateWebp(filePath) {
  if (!fs.existsSync(filePath)) fail(`missing local photo: ${filePath}`);

  const buffer = fs.readFileSync(filePath);
  if (buffer.length < 12) fail(`empty or invalid photo: ${filePath}`);
  if (buffer.toString("ascii", 0, 4) !== "RIFF" || buffer.toString("ascii", 8, 12) !== "WEBP") {
    fail(`photo is not a WebP file: ${filePath}`);
  }

  return buffer.length;
}

const profiles = readJson(PROFILE_PATH).profiles;
const manifest = readJson(PHOTO_MANIFEST_PATH);
const catalog = readJson(SOURCE_CATALOG_PATH);
const profileCodes = new Set(profiles.map((profile) => profile.istatCode));
const manifestCodes = new Set();
const sourceCodes = new Set();
let totalBytes = 0;

for (const photo of manifest.photos) {
  if (!profileCodes.has(photo.istatCode)) fail(`unknown ISTAT code: ${photo.istatCode}`);
  if (manifestCodes.has(photo.istatCode)) fail(`duplicate manifest code: ${photo.istatCode}`);
  if (!/^\d{6}$/.test(photo.istatCode)) fail(`invalid ISTAT code: ${photo.istatCode}`);
  if (!/^\d+% \d+%$/.test(photo.objectPosition)) {
    fail(`invalid object position for ${photo.istatCode}: ${photo.objectPosition}`);
  }

  const relativeAssetPath = photo.localUrl.replace(/^\//, "");
  totalBytes += validateWebp(path.join(ROOT_DIR, "frontend", "public", relativeAssetPath));
  manifestCodes.add(photo.istatCode);
}

for (const source of catalog.photos) {
  if (sourceCodes.has(source.istatCode)) fail(`duplicate source code: ${source.istatCode}`);
  if (source.reviewStatus !== "approved") fail(`unapproved source: ${source.istatCode}`);

  for (const field of ["author", "license", "licenseUrl", "sourcePageUrl", "assetUrl", "localUrl"]) {
    if (!String(source[field] || "").trim()) fail(`missing ${field} for ${source.istatCode}`);
  }
  for (const field of ["displayName", "subject", "modifications"]) {
    for (const language of ["it", "fur"]) {
      if (!String(source[field]?.[language] || "").trim()) {
        fail(`missing ${field}.${language} for ${source.istatCode}`);
      }
    }
  }

  sourceCodes.add(source.istatCode);
}

if (manifestCodes.size !== manifest.coverage.resolved) {
  fail(`manifest coverage mismatch: ${manifestCodes.size} != ${manifest.coverage.resolved}`);
}
if (manifestCodes.size !== profiles.length) {
  fail(`incomplete municipality photo coverage: ${manifestCodes.size} != ${profiles.length}`);
}
if (sourceCodes.size !== profiles.length) {
  fail(`incomplete municipality photo credit coverage: ${sourceCodes.size} != ${profiles.length}`);
}
if (manifest.coverage.profiles !== profiles.length) {
  fail(`profile coverage mismatch: ${manifest.coverage.profiles} != ${profiles.length}`);
}
if (manifest.coverage.unresolved !== 0) {
  fail(`municipality photo coverage still has ${manifest.coverage.unresolved} unresolved profiles`);
}
if (manifest.coverage.unresolved !== profiles.length - manifestCodes.size) {
  fail("unresolved coverage does not match the current profile/photo counts");
}
if ([...manifestCodes].some((code) => !sourceCodes.has(code))) {
  fail("one or more runtime photos have no source metadata");
}
if ([...sourceCodes].some((code) => !manifestCodes.has(code))) {
  fail("one or more source records are not present in the runtime manifest");
}

console.log(JSON.stringify({
  bytes: totalBytes,
  photos: manifestCodes.size,
  profiles: profiles.length,
}, null, 2));
