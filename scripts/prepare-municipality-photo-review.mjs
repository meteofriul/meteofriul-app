import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CANDIDATE_PATH = path.join(
  ROOT_DIR,
  "scripts",
  "data",
  "municipality-photo-candidates.json",
);
const OUTPUT_DIR = path.join(os.tmpdir(), "meteo-friul-municipality-photo-review");
const USER_AGENT = "MeteoFriulUI/3.0 (https://meteo-friul.web.app/; municipality photo review)";
const DOWNLOAD_CONCURRENCY = 4;
const REFRESH = process.argv.includes("--refresh");
const ALL_CANDIDATES = process.argv.includes("--all-candidates");
const REVIEW_CODES = new Set(
  (process.argv.find((argument) => argument.startsWith("--codes=")) || "")
    .replace("--codes=", "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean),
);

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8").replace(/^\uFEFF/, ""));
}

function wait(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function fetchWithRetry(url, attempts = 4) {
  let lastError;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        headers: { "User-Agent": USER_AGENT },
      });

      if (response.status === 429 || response.status >= 500) {
        const retryAfter = Number.parseInt(response.headers.get("retry-after") || "", 10);
        await wait(Number.isFinite(retryAfter) ? retryAfter * 1000 : 750 * attempt);
        continue;
      }

      return response;
    } catch (error) {
      lastError = error;
      if (attempt < attempts) await wait(500 * attempt);
    }
  }

  if (lastError) throw lastError;
  throw new Error(`request failed after ${attempts} attempts: ${url}`);
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

function safeName(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLocaleLowerCase("it");
}

function extensionFor(candidate) {
  if (candidate.mime === "image/png") return ".png";
  if (candidate.mime === "image/webp") return ".webp";
  if (candidate.mime === "image/gif") return ".gif";
  return ".jpg";
}

function selectCandidate(record) {
  return record.candidates.find((candidate) => candidate.reviewStatus === "approved")
    || record.candidates.find((candidate) => candidate.licenseAccepted && candidate.score >= 65)
    || record.candidates.find((candidate) => candidate.licenseAccepted)
    || null;
}

const catalog = readJson(CANDIDATE_PATH);
const selected = catalog.records
  .filter((record) => REVIEW_CODES.size === 0 || REVIEW_CODES.has(record.istatCode))
  .flatMap((record) => {
    const candidates = ALL_CANDIDATES
      ? record.candidates.filter((candidate) => candidate.licenseAccepted)
      : [selectCandidate(record)].filter(Boolean);
    return candidates.map((selectedCandidate, candidateIndex) => ({
      ...record,
      candidateIndex,
      selectedCandidate,
    }));
  });

fs.mkdirSync(OUTPUT_DIR, { recursive: true });

const reviewRecords = await mapConcurrent(selected, DOWNLOAD_CONCURRENCY, async (record) => {
  const candidate = record.selectedCandidate;
  const fileName = [
    record.istatCode,
    record.province,
    safeName(record.municipality),
    ...(ALL_CANDIDATES ? [String(record.candidateIndex + 1).padStart(2, "0")] : []),
  ].join("-") + extensionFor(candidate);
  const filePath = path.join(OUTPUT_DIR, fileName);

  if (REFRESH || !fs.existsSync(filePath)) {
    const response = await fetchWithRetry(candidate.assetUrl);
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}: ${candidate.assetUrl}`);
    }
    fs.writeFileSync(filePath, Buffer.from(await response.arrayBuffer()));
  }

  return {
    istatCode: record.istatCode,
    municipality: record.municipality,
    province: record.province,
    status: record.status,
    candidateIndex: record.candidateIndex,
    localReviewPath: filePath,
    candidate,
  };
});

const reviewIndex = {
  generatedAt: new Date().toISOString(),
  outputDir: OUTPUT_DIR,
  records: reviewRecords,
};
const indexPath = path.join(OUTPUT_DIR, "index.json");
fs.writeFileSync(indexPath, `${JSON.stringify(reviewIndex, null, 2)}\n`, "utf8");

console.log(JSON.stringify({
  downloaded: reviewRecords.length,
  refreshed: REFRESH,
  allCandidates: ALL_CANDIDATES,
  indexPath,
  outputDir: OUTPUT_DIR,
}, null, 2));
