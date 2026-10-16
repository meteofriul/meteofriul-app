import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
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
const CANDIDATE_PATH = path.join(ROOT_DIR, "scripts", "data", "municipality-photo-candidates.json");
const SELECTION_PATH = path.join(ROOT_DIR, "scripts", "data", "municipality-photo-selection.json");
const MANIFEST_PATH = path.join(
  ROOT_DIR,
  "frontend",
  "src",
  "data",
  "discover",
  "municipalityPhotos.json",
);
const CREDIT_PATH = path.join(
  ROOT_DIR,
  "frontend",
  "src",
  "data",
  "discover",
  "municipalityPhotoCredits.json",
);
const ASSET_DIR = path.join(ROOT_DIR, "frontend", "public", "municipalities", "photos");
const TEMP_DIR = path.join(os.tmpdir(), "meteo-friul-municipality-photo-sync");
const USER_AGENT = "MeteoFriulUI/3.0 (https://meteo-friul.web.app/; municipality photo sync)";
const WRITE = process.argv.includes("--write");
const REFRESH = process.argv.includes("--refresh");
const DOWNLOAD_CONCURRENCY = 3;

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8").replace(/^\uFEFF/, ""));
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function fail(message) {
  throw new Error(message);
}

function wait(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function fetchWithRetry(url, attempts = 5) {
  let lastError;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(url, { headers: { "User-Agent": USER_AGENT } });
      if (response.ok) return response;
      if (response.status !== 429 && response.status < 500) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      const retryAfter = Number.parseInt(response.headers.get("retry-after") || "", 10);
      await wait(Number.isFinite(retryAfter) ? retryAfter * 1000 : 900 * attempt);
    } catch (error) {
      lastError = error;
      if (attempt < attempts) await wait(700 * attempt);
    }
  }

  throw lastError || new Error(`download failed after ${attempts} attempts: ${url}`);
}

async function mapConcurrent(values, concurrency, mapper) {
  const results = new Array(values.length);
  let cursor = 0;

  async function worker() {
    while (cursor < values.length) {
      const index = cursor;
      cursor += 1;
      results[index] = await mapper(values[index], index);
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(concurrency, values.length) }, () => worker()),
  );
  return results;
}

function isValidWebp(filePath) {
  if (!fs.existsSync(filePath)) return false;
  const buffer = fs.readFileSync(filePath);
  return buffer.length >= 12
    && buffer.toString("ascii", 0, 4) === "RIFF"
    && buffer.toString("ascii", 8, 12) === "WEBP";
}

function normalizeLicense(license) {
  if (/public\s*domain/i.test(license)) return "Public Domain";
  if (/^cc0/i.test(license)) return "CC0 1.0";
  return String(license || "").trim();
}

function normalizeLicenseUrl(license, licenseUrl) {
  if (/public\s*domain/i.test(license)) {
    return "https://creativecommons.org/publicdomain/mark/1.0/";
  }
  if (/^cc0/i.test(license)) {
    return "https://creativecommons.org/publicdomain/zero/1.0/";
  }
  return String(licenseUrl || "").replace(/^http:/, "https:").trim();
}

function buildCandidateMap(catalog) {
  const result = new Map();

  for (const record of catalog.records) {
    const byFileName = new Map();
    for (const candidate of record.candidates) {
      if (!byFileName.has(candidate.fileName)) byFileName.set(candidate.fileName, candidate);
    }
    result.set(record.istatCode, byFileName);
  }

  return result;
}

function buildCredit(profile, selection, candidate, existingCredit) {
  const displayName = selection.creditDisplayName || {
    it: profile.municipality,
    fur: profile.municipality,
  };
  const subject = selection.creditSubject || {
    it: "Veduta del territorio comunale",
    fur: "Viodude dal teritori comunâl",
  };

  if (
    existingCredit?.fileName === selection.selectedFileName
    && existingCredit.reviewMethod === selection.reviewMethod
    && existingCredit.reviewedAt === selection.reviewedAt
    && JSON.stringify(existingCredit.displayName) === JSON.stringify(displayName)
    && JSON.stringify(existingCredit.subject) === JSON.stringify(subject)
  ) {
    return existingCredit;
  }

  const license = normalizeLicense(candidate.license);
  const licenseUrl = normalizeLicenseUrl(candidate.license, candidate.licenseUrl);
  if (!license) fail(`missing license for ${selection.istatCode}`);
  if (!licenseUrl) fail(`missing license URL for ${selection.istatCode}`);

  return {
    istatCode: selection.istatCode,
    municipality: profile.municipality,
    displayName,
    subject,
    fileName: candidate.fileName,
    localUrl: `/municipalities/photos/${selection.istatCode}-photo.webp`,
    sourcePageUrl: candidate.sourcePageUrl,
    assetUrl: candidate.assetUrl,
    author: String(candidate.author || "").trim() || "Autore non indicato nella fonte",
    license,
    licenseUrl,
    selectionMethod: candidate.selectionMethod,
    reviewMethod: selection.reviewMethod,
    reviewStatus: "approved",
    reviewedAt: selection.reviewedAt,
    modifications: {
      it: "Ridimensionata e convertita in WebP.",
      fur: "Ridimensionade e convertide in WebP.",
    },
  };
}

async function downloadAndConvert(item) {
  const outputPath = path.join(ASSET_DIR, `${item.selection.istatCode}-photo.webp`);
  if (!REFRESH && !item.sourceChanged && isValidWebp(outputPath)) {
    return { status: "reused", outputPath };
  }

  const response = await fetchWithRetry(item.candidate.assetUrl);
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.startsWith("image/")) {
    fail(`unexpected content type for ${item.selection.istatCode}: ${contentType}`);
  }

  const inputPath = path.join(TEMP_DIR, `${item.selection.istatCode}.source`);
  fs.writeFileSync(inputPath, Buffer.from(await response.arrayBuffer()));

  const conversion = spawnSync("magick", [
    inputPath,
    "-auto-orient",
    "-resize",
    "960x960>",
    "-strip",
    "-quality",
    "76",
    outputPath,
  ], { encoding: "utf8" });
  fs.rmSync(inputPath, { force: true });

  if (conversion.status !== 0) {
    fail(`ImageMagick failed for ${item.selection.istatCode}: ${conversion.stderr || conversion.stdout}`);
  }
  if (!isValidWebp(outputPath)) fail(`invalid converted WebP: ${item.selection.istatCode}`);

  return { status: "downloaded", outputPath };
}

const profiles = readJson(PROFILE_PATH).profiles;
const catalog = readJson(CANDIDATE_PATH);
const selectionCatalog = readJson(SELECTION_PATH);
const currentManifest = readJson(MANIFEST_PATH);
const currentCredits = readJson(CREDIT_PATH);
const candidatesByCode = buildCandidateMap(catalog);
const selectionByCode = new Map(
  selectionCatalog.records.map((selection) => [selection.istatCode, selection]),
);
const currentPhotosByCode = new Map(
  currentManifest.photos.map((photo) => [photo.istatCode, photo]),
);
const currentCreditsByCode = new Map(
  currentCredits.photos.map((photo) => [photo.istatCode, photo]),
);
const items = [];
const runtimePhotos = [];
const credits = [];

for (const profile of profiles) {
  const selection = selectionByCode.get(profile.istatCode);
  if (!selection) fail(`missing selection for ${profile.istatCode}`);

  const candidate = candidatesByCode.get(profile.istatCode)?.get(selection.selectedFileName);
  if (!candidate) fail(`selected candidate not found for ${profile.istatCode}`);
  if (!candidate.assetUrl || !candidate.sourcePageUrl) {
    fail(`selected candidate has incomplete source data: ${profile.istatCode}`);
  }

  const existingPhoto = currentPhotosByCode.get(profile.istatCode);
  const existingCredit = currentCreditsByCode.get(profile.istatCode);
  runtimePhotos.push({
    istatCode: profile.istatCode,
    localUrl: `/municipalities/photos/${profile.istatCode}-photo.webp`,
    objectPosition: selection.objectPosition || existingPhoto?.objectPosition || "50% 50%",
  });
  credits.push(buildCredit(
    profile,
    selection,
    candidate,
    existingCredit,
  ));
  items.push({
    profile,
    selection,
    candidate,
    sourceChanged: existingCredit?.fileName !== selection.selectedFileName,
  });
}

if (items.length !== profiles.length) fail("photo sync does not cover every municipality profile");

if (!WRITE) {
  console.log(JSON.stringify({
    write: false,
    profiles: profiles.length,
    selected: items.length,
    existingAssets: items.filter((item) => isValidWebp(
      path.join(ASSET_DIR, `${item.selection.istatCode}-photo.webp`),
    )).length,
  }, null, 2));
  process.exit(0);
}

fs.mkdirSync(ASSET_DIR, { recursive: true });
fs.mkdirSync(TEMP_DIR, { recursive: true });
let completed = 0;
const results = await mapConcurrent(items, DOWNLOAD_CONCURRENCY, async (item) => {
  const result = await downloadAndConvert(item);
  completed += 1;
  if (completed % 10 === 0 || completed === items.length) {
    console.log(`municipality photos: ${completed}/${items.length}`);
  }
  return result;
});

const missingAssets = runtimePhotos.filter((photo) => !isValidWebp(
  path.join(ROOT_DIR, "frontend", "public", photo.localUrl.replace(/^\//, "")),
));
if (missingAssets.length > 0) {
  fail(`sync finished with ${missingAssets.length} missing or invalid local assets`);
}

writeJson(MANIFEST_PATH, {
  schemaVersion: 1,
  generatedAt: selectionCatalog.generatedAt,
  sourcePolicy: currentManifest.sourcePolicy,
  coverage: {
    profiles: profiles.length,
    resolved: runtimePhotos.length,
    unresolved: profiles.length - runtimePhotos.length,
  },
  photos: runtimePhotos,
});
writeJson(CREDIT_PATH, {
  schemaVersion: 1,
  generatedAt: selectionCatalog.generatedAt,
  selectionPolicy: currentCredits.selectionPolicy,
  photos: credits,
});

fs.rmSync(TEMP_DIR, { recursive: true, force: true });

console.log(JSON.stringify({
  downloaded: results.filter((result) => result.status === "downloaded").length,
  reused: results.filter((result) => result.status === "reused").length,
  photos: runtimePhotos.length,
  manifestPath: MANIFEST_PATH,
  creditPath: CREDIT_PATH,
}, null, 2));
