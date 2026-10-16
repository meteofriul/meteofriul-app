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
const APPROVED_PHOTOS_PATH = path.join(
  ROOT_DIR,
  "frontend",
  "src",
  "data",
  "discover",
  "municipalityPhotoCredits.json",
);
const COAT_SOURCE_PATH = path.join(
  ROOT_DIR,
  "scripts",
  "data",
  "municipality-coat-sources.json",
);
const CURATED_CANDIDATE_PATH = path.join(
  ROOT_DIR,
  "scripts",
  "data",
  "municipality-photo-curated-candidates.json",
);
const OUTPUT_PATH = path.join(
  ROOT_DIR,
  "scripts",
  "data",
  "municipality-photo-candidates.json",
);

const USER_AGENT = "MeteoFriulUI/3.0 (https://meteo-friul.web.app/; municipality photo candidate audit)";
const WRITE = process.argv.includes("--write");
const SEARCH_FALLBACK = process.argv.includes("--search-fallback");
const SEARCH_CODES = new Set(
  (process.argv.find((argument) => argument.startsWith("--search-codes=")) || "")
    .replace("--search-codes=", "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean),
);
const REQUEST_CONCURRENCY = 3;
const WIKIDATA_BATCH_SIZE = 45;
const COMMONS_BATCH_SIZE = 20;
const MAX_CANDIDATES_PER_MUNICIPALITY = 10;

const ACCEPTED_LICENSE_PATTERN = /^(?:cc0|public domain|pd|cc by(?:-sa)?)(?:\s|$)/i;
const REJECTED_SUBJECT_PATTERN = /(?:stemma|coat[ _-]?of[ _-]?arms|gonfalone|bandiera|flag|logo|locator|location map|mappa|map of|comune di .*\.svg)/i;
const PREFERRED_SUBJECT_PATTERN = /(?:panoram|vedut|piazz|centro stor|castell|duomo|municip|cityscape|skyline|borgo|chiesa|palazzo|village|town|aerial)/i;
const SUPPORTED_PHOTO_MIMES = new Set(["image/jpeg", "image/png", "image/webp"]);

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8").replace(/^\uFEFF/, ""));
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
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

async function fetchJson(url) {
  const response = await fetchWithRetry(url);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}: ${url}`);
  return response.json();
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

function chunks(values, size) {
  const result = [];
  for (let index = 0; index < values.length; index += size) {
    result.push(values.slice(index, index + size));
  }
  return result;
}

function stripHtml(value) {
  return String(value || "")
    .replace(/<[^>]*>/g, " ")
    .replaceAll("&amp;", "&")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .replaceAll("&nbsp;", " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("it")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function containsNormalizedPhrase(value, phrase) {
  const haystack = ` ${normalize(value)} `;
  const needle = ` ${normalize(phrase)} `;
  return needle.trim().length > 0 && haystack.includes(needle);
}

function extractWikidataId(value) {
  return String(value || "").match(/\/entity\/(Q\d+)/i)?.[1]?.toUpperCase() || "";
}

function fileTitle(fileName) {
  return `File:${String(fileName || "").replace(/^File:/i, "").trim()}`;
}

function commonsPageUrl(fileName) {
  return `https://commons.wikimedia.org/wiki/${encodeURIComponent(fileTitle(fileName).replaceAll(" ", "_"))}`;
}

function metadataValue(metadata, key) {
  return stripHtml(metadata?.[key]?.value || "");
}

function candidateScore(candidate, municipality) {
  const haystack = normalize(`${candidate.fileName} ${candidate.description}`);
  const exactMunicipalityMatch = containsNormalizedPhrase(
    `${candidate.fileName} ${candidate.description}`,
    municipality,
  );
  const aspectRatio = candidate.height > 0 ? candidate.width / candidate.height : 0;
  let score = candidate.selectionMethod === "curated_commons"
    ? 145
    : candidate.selectionMethod === "wikidata_p18"
      ? 100
      : 45;

  if (candidate.licenseAccepted) score += 25;
  else score -= 150;
  if (candidate.width >= 1600) score += 10;
  else if (candidate.width >= 1000) score += 6;
  else if (candidate.width && candidate.width < 700) score -= 20;
  if (aspectRatio >= 1.2 && aspectRatio <= 2.6) score += 10;
  else if (aspectRatio > 0 && aspectRatio < 0.85) score -= 6;
  if (exactMunicipalityMatch) score += 12;
  else if (candidate.selectionMethod === "commons_search") score -= 180;
  if (PREFERRED_SUBJECT_PATTERN.test(haystack)) score += 8;
  if (REJECTED_SUBJECT_PATTERN.test(candidate.fileName)) score -= 120;
  if (!SUPPORTED_PHOTO_MIMES.has(candidate.mime)) score -= 180;
  if (!candidate.author) score -= 10;

  return score;
}

async function fetchWikidataImages(qids) {
  const byQid = new Map();

  await mapConcurrent(chunks(qids, WIKIDATA_BATCH_SIZE), REQUEST_CONCURRENCY, async (batch) => {
    const params = new URLSearchParams({
      action: "wbgetentities",
      format: "json",
      ids: batch.join("|"),
      props: "claims",
      origin: "*",
    });
    const data = await fetchJson(`https://www.wikidata.org/w/api.php?${params}`);

    for (const [qid, entity] of Object.entries(data.entities || {})) {
      const claims = [...(entity.claims?.P18 || [])]
        .sort((left, right) => {
          const rank = { preferred: 0, normal: 1, deprecated: 2 };
          return (rank[left.rank] ?? 1) - (rank[right.rank] ?? 1);
        })
        .map((claim) => claim.mainsnak?.datavalue?.value)
        .filter(Boolean);
      byQid.set(qid, [...new Set(claims)]);
    }
  });

  return byQid;
}

async function fetchCommonsMetadata(fileNames) {
  const byFileName = new Map();
  const uniqueNames = [...new Set(fileNames.filter(Boolean))];

  await mapConcurrent(chunks(uniqueNames, COMMONS_BATCH_SIZE), REQUEST_CONCURRENCY, async (batch) => {
    const params = new URLSearchParams({
      action: "query",
      format: "json",
      formatversion: "2",
      prop: "imageinfo",
      titles: batch.map(fileTitle).join("|"),
      iiprop: "url|size|mime|extmetadata",
      iiurlwidth: "1280",
      iiextmetadatalanguage: "it",
      iiextmetadatafilter: "Artist|LicenseShortName|LicenseUrl|ImageDescription|ObjectName|Credit|UsageTerms|AttributionRequired",
      origin: "*",
    });
    const data = await fetchJson(`https://commons.wikimedia.org/w/api.php?${params}`);

    for (const page of data.query?.pages || []) {
      const image = page.imageinfo?.[0];
      if (!image) continue;
      const normalizedFileName = String(page.title || "").replace(/^File:/i, "");
      const metadata = image.extmetadata || {};
      const license = metadataValue(metadata, "LicenseShortName") || metadataValue(metadata, "UsageTerms");
      const record = {
        fileName: normalizedFileName,
        sourcePageUrl: commonsPageUrl(normalizedFileName),
        assetUrl: image.thumburl || image.url || "",
        originalAssetUrl: image.url || "",
        mime: image.mime || "",
        width: Number(image.width || 0),
        height: Number(image.height || 0),
        author: metadataValue(metadata, "Artist"),
        credit: metadataValue(metadata, "Credit"),
        description: metadataValue(metadata, "ImageDescription") || metadataValue(metadata, "ObjectName"),
        license,
        licenseUrl: metadataValue(metadata, "LicenseUrl"),
        licenseAccepted: ACCEPTED_LICENSE_PATTERN.test(license),
        attributionRequired: metadataValue(metadata, "AttributionRequired"),
      };
      byFileName.set(normalizedFileName, record);
    }
  });

  return byFileName;
}

async function searchCommons(municipality) {
  const queries = [
    `incategory:${JSON.stringify(municipality)} filetype:bitmap`,
    `intitle:${JSON.stringify(municipality)} filetype:bitmap`,
    `${JSON.stringify(municipality)} ${JSON.stringify("Friuli Venezia Giulia")} filetype:bitmap`,
  ];
  const titles = [];

  for (const query of queries) {
    const params = new URLSearchParams({
      action: "query",
      format: "json",
      formatversion: "2",
      list: "search",
      srnamespace: "6",
      srlimit: "10",
      srsearch: query,
      origin: "*",
    });
    const data = await fetchJson(`https://commons.wikimedia.org/w/api.php?${params}`);
    for (const result of data.query?.search || []) {
      titles.push(String(result.title || "").replace(/^File:/i, ""));
    }
    if (titles.length >= 10) break;
  }

  return [...new Set(titles)].slice(0, 12);
}

function approvedCandidate(photo) {
  return {
    fileName: photo.fileName,
    sourcePageUrl: photo.sourcePageUrl,
    assetUrl: photo.assetUrl,
    author: photo.author,
    license: photo.license,
    licenseUrl: photo.licenseUrl,
    selectionMethod: photo.selectionMethod,
    reviewStatus: "approved",
    score: 1000,
  };
}

const profiles = readJson(PROFILE_PATH).profiles;
const coatSourceCatalog = readJson(COAT_SOURCE_PATH);
const coatSources = Array.isArray(coatSourceCatalog)
  ? coatSourceCatalog
  : coatSourceCatalog.visuals;
const approvedPhotos = readJson(APPROVED_PHOTOS_PATH).photos;
const curatedCatalog = fs.existsSync(CURATED_CANDIDATE_PATH)
  ? readJson(CURATED_CANDIDATE_PATH)
  : { records: [] };
const approvedByCode = new Map(approvedPhotos.map((photo) => [photo.istatCode, photo]));
const curatedByCode = new Map(
  curatedCatalog.records.map((record) => [record.istatCode, record.fileNames || []]),
);
const qidByCode = new Map(
  coatSources.map((source) => [source.istatCode, extractWikidataId(source.wikidataItemUrl)]),
);
const qids = [...new Set([...qidByCode.values()].filter(Boolean))];
const p18ByQid = await fetchWikidataImages(qids);
const allP18FileNames = profiles.flatMap((profile) => {
  const qid = qidByCode.get(profile.istatCode);
  return p18ByQid.get(qid) || [];
});
const p18Metadata = await fetchCommonsMetadata(allP18FileNames);
const curatedMetadata = await fetchCommonsMetadata(
  curatedCatalog.records.flatMap((record) => record.fileNames || []),
);

const records = await mapConcurrent(profiles, REQUEST_CONCURRENCY, async (profile) => {
  const approved = approvedByCode.get(profile.istatCode);
  const wikidataId = qidByCode.get(profile.istatCode) || "";
  const p18Files = p18ByQid.get(wikidataId) || [];
  let candidates = p18Files
    .map((fileName) => p18Metadata.get(fileName))
    .filter(Boolean)
    .map((candidate) => ({ ...candidate, selectionMethod: "wikidata_p18" }));

  candidates.push(
    ...(curatedByCode.get(profile.istatCode) || [])
      .map((fileName) => curatedMetadata.get(fileName))
      .filter(Boolean)
      .map((candidate) => ({ ...candidate, selectionMethod: "curated_commons" })),
  );

  const needsFallback = !candidates.some((candidate) => candidate.licenseAccepted);
  if (SEARCH_FALLBACK && (needsFallback || SEARCH_CODES.has(profile.istatCode))) {
    const searchFiles = await searchCommons(profile.municipality);
    const searchMetadata = await fetchCommonsMetadata(searchFiles);
    candidates.push(
      ...searchFiles
        .map((fileName) => searchMetadata.get(fileName))
        .filter(Boolean)
        .filter((candidate) => SUPPORTED_PHOTO_MIMES.has(candidate.mime))
        .filter((candidate) => containsNormalizedPhrase(
          `${candidate.fileName} ${candidate.description}`,
          profile.municipality,
        ))
        .map((candidate) => ({ ...candidate, selectionMethod: "commons_search" })),
    );
  }

  candidates = candidates
    .map((candidate) => ({
      ...candidate,
      score: candidateScore(candidate, profile.municipality),
      reviewStatus: "candidate",
    }))
    .sort((left, right) => right.score - left.score)
    .slice(0, MAX_CANDIDATES_PER_MUNICIPALITY);

  if (approved) {
    candidates = [
      approvedCandidate(approved),
      ...candidates.filter((candidate) => candidate.fileName !== approved.fileName),
    ].slice(0, MAX_CANDIDATES_PER_MUNICIPALITY);
  }

  const bestCandidate = candidates.find((candidate) => (
    candidate.reviewStatus === "approved"
      || (candidate.licenseAccepted && candidate.score >= 65)
  ));

  return {
    istatCode: profile.istatCode,
    municipality: profile.municipality,
    province: profile.province,
    wikidataId,
    status: approved ? "approved" : bestCandidate ? "candidate_found" : "unresolved",
    candidates,
  };
});

const summary = records.reduce((result, record) => {
  result[record.status] += 1;
  return result;
}, { approved: 0, candidate_found: 0, unresolved: 0 });

const output = {
  schemaVersion: 1,
  generatedAt: new Date().toISOString(),
  policy: {
    automaticPublication: false,
    acceptedLicenses: "CC0, Public Domain, CC BY and CC BY-SA",
    primarySource: "Wikidata P18",
    curatedSource: "Reviewed Wikimedia Commons category candidates",
    fallbackSource: SEARCH_FALLBACK ? "Wikimedia Commons search" : "disabled",
    maxCandidatesPerMunicipality: MAX_CANDIDATES_PER_MUNICIPALITY,
  },
  coverage: {
    profiles: profiles.length,
    ...summary,
  },
  records,
};

if (WRITE) writeJson(OUTPUT_PATH, output);

console.log(JSON.stringify({
  outputPath: WRITE ? OUTPUT_PATH : null,
  searchFallback: SEARCH_FALLBACK,
  ...output.coverage,
}, null, 2));
