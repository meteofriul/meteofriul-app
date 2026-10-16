import { createHash } from "node:crypto";
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
const MANIFEST_PATH = path.join(
  ROOT_DIR,
  "frontend",
  "src",
  "data",
  "discover",
  "municipalityVisuals.json",
);
const SOURCE_CATALOG_PATH = path.join(
  ROOT_DIR,
  "scripts",
  "data",
  "municipality-coat-sources.json",
);
const ASSET_DIR = path.join(
  ROOT_DIR,
  "frontend",
  "public",
  "municipalities",
  "coats",
);

const USER_AGENT = "MeteoFriulUI/3.0 (https://meteo-friul.web.app/; municipality coat sync)";
const WRITE = process.argv.includes("--write");
const PROBE_FALLBACK = process.argv.includes("--probe-fallback");
const REQUEST_CONCURRENCY = 3;
const DOWNLOAD_CONCURRENCY = 1;
const DOWNLOAD_PAUSE_MS = 3000;
const THUMBNAIL_WIDTH = 330;

const WIKIDATA_QUERY = `
SELECT ?item ?istat ?article ?coat WHERE {
  ?item wdt:P635 ?istat .
  FILTER(
    STRSTARTS(?istat, "030")
    || STRSTARTS(?istat, "031")
    || STRSTARTS(?istat, "032")
    || STRSTARTS(?istat, "093")
  )
  OPTIONAL {
    ?article schema:about ?item;
      schema:isPartOf <https://it.wikipedia.org/>.
  }
  OPTIONAL { ?item wdt:P94 ?coat. }
}`;

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8").replace(/^\uFEFF/, ""));
}

function wait(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function fetchWithRetry(url, options = {}, attempts = 4) {
  let lastError;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          "User-Agent": USER_AGENT,
          ...(options.headers || {}),
        },
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
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
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

function decodeFileName(value) {
  const pathName = String(value || "").split("/").at(-1) || "";
  return decodeURIComponent(pathName).replaceAll("_", " ");
}

function canonicalFileName(value) {
  return String(value || "").trim().replaceAll(" ", "_");
}

function decodeHtml(value) {
  return String(value || "")
    .replaceAll("&amp;", "&")
    .replaceAll("&apos;", "'")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">");
}

function normalizeCoatFileName(value) {
  return decodeHtml(value)
    .replace(/<!--.*?-->/gs, "")
    .replace(/^\[\[(?:File|Immagine):/i, "")
    .replace(/\]\]$/, "")
    .split("|")[0]
    .trim();
}

function getArticleTitle(articleUrl) {
  if (!articleUrl) return "";
  const url = new URL(articleUrl);
  return decodeURIComponent(url.pathname.replace(/^\/wiki\//, "")).replaceAll("_", " ");
}

function buildMunicipalityArticleUrl(municipality) {
  const title = String(municipality || "").trim().replaceAll(" ", "_");
  return `https://it.wikipedia.org/wiki/${encodeURIComponent(title)}`;
}

function buildThumbnailUrl(fileName, repository) {
  const canonicalName = canonicalFileName(fileName);
  const hash = createHash("md5").update(canonicalName).digest("hex");
  const encodedName = encodeURIComponent(canonicalName);
  const svgSuffix = canonicalName.toLocaleLowerCase("en").endsWith(".svg") ? ".png" : "";
  return [
    "https://upload.wikimedia.org/wikipedia",
    repository,
    "thumb",
    hash[0],
    hash.slice(0, 2),
    encodedName,
    `${THUMBNAIL_WIDTH}px-${encodedName}${svgSuffix}`,
  ].join("/");
}

function buildSourceUrl(fileName, repository) {
  const host = repository === "commons" ? "commons.wikimedia.org" : "it.wikipedia.org";
  return `https://${host}/wiki/File:${encodeURIComponent(canonicalFileName(fileName))}`;
}

function buildFileCandidates(municipality) {
  const names = [
    `${municipality}-Stemma.png`,
    `${municipality}-Stemma.svg`,
    `Stemma di ${municipality}.png`,
    `Stemma di ${municipality}.svg`,
    `Coat of arms of ${municipality}.svg`,
    `Coat of arms of ${municipality}.png`,
  ];
  const candidates = [];

  for (const fileName of names) {
    const svg = fileName.toLocaleLowerCase("en").endsWith(".svg");
    const repositories = svg ? ["commons", "it"] : ["it", "commons"];
    for (const repository of repositories) {
      candidates.push({ fileName, repository, selectionMethod: "verified_filename_pattern" });
    }
  }

  return candidates;
}

function extractArticleCoat(html) {
  const rawField = html.match(/"Stemma":\{"wt":"([^"]*)"/i)?.[1]
    || html.match(/&quot;Stemma&quot;:\{&quot;wt&quot;:&quot;([^&]*)&quot;/i)?.[1]
    || "";
  const fileName = normalizeCoatFileName(rawField);
  if (!fileName) return null;

  const canonicalName = canonicalFileName(fileName);
  const imageMatches = [
    ...html.matchAll(/\/\/upload\.wikimedia\.org\/wikipedia\/(it|commons)\/[^"'\s<]+/gi),
  ]
    .map((match) => {
      const url = decodeHtml(match[0]).replace(/^\/\//, "https://").split("?")[0];
      let decodedUrl = url;
      try {
        decodedUrl = decodeURIComponent(url);
      } catch {
        // Keep the encoded URL when a page contains an incomplete escape sequence.
      }
      const width = Number.parseInt(decodedUrl.match(/\/(\d+)px-/)?.[1] || "0", 10);
      return { repository: match[1].toLocaleLowerCase("en"), url, decodedUrl, width };
    })
    .filter((candidate) => candidate.decodedUrl.includes(`/${canonicalName}`))
    .sort((first, second) => second.width - first.width);

  const image = imageMatches[0];
  if (!image) return null;

  return {
    fileName,
    repository: image.repository,
    selectionMethod: "wikipedia_infobox",
    assetUrl: image.url,
    sourceUrl: buildSourceUrl(fileName, image.repository),
  };
}

async function fetchArticleCoat(articleUrl) {
  if (!articleUrl) return null;
  const response = await fetchWithRetry(articleUrl, {}, 5);
  if (!response.ok) return null;
  return extractArticleCoat(await response.text());
}

async function probeCandidate(candidate) {
  const assetUrl = buildThumbnailUrl(candidate.fileName, candidate.repository);
  let response;
  try {
    response = await fetchWithRetry(assetUrl, { method: "HEAD" }, 4);
  } catch {
    return null;
  }
  const contentType = response.headers.get("content-type") || "";
  if (!response.ok || !contentType.startsWith("image/")) return null;

  return {
    ...candidate,
    assetUrl,
    sourceUrl: buildSourceUrl(candidate.fileName, candidate.repository),
    contentType,
    contentLength: Number.parseInt(response.headers.get("content-length") || "0", 10),
  };
}

async function resolveProfileAsset(profile, wikidata) {
  if (wikidata?.coatFile) {
    return {
      fileName: wikidata.coatFile,
      repository: "commons",
      selectionMethod: "wikidata_p94",
      assetUrl: buildThumbnailUrl(wikidata.coatFile, "commons"),
      sourceUrl: buildSourceUrl(wikidata.coatFile, "commons"),
    };
  }

  const articleUrls = [
    buildMunicipalityArticleUrl(profile.municipality),
    wikidata?.articleUrl,
  ].filter((value, index, values) => value && values.indexOf(value) === index);
  for (const articleUrl of articleUrls) {
    const articleCoat = await fetchArticleCoat(articleUrl);
    if (articleCoat) return articleCoat;
  }

  if (!PROBE_FALLBACK) return null;

  const seen = new Set();
  for (const candidate of buildFileCandidates(profile.municipality)) {
    const key = `${candidate.repository}:${canonicalFileName(candidate.fileName)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const resolved = await probeCandidate(candidate);
    if (resolved) return resolved;
  }

  return null;
}

function detectImageExtension(image, contentType = "") {
  if (image.length > 4 && image.subarray(0, 4).toString("hex") === "89504e47") return "png";
  if (image.length > 3 && image.subarray(0, 3).toString("hex") === "ffd8ff") return "jpg";
  if (image.length > 4 && image.subarray(0, 4).toString("ascii") === "GIF8") return "gif";
  if (
    image.length > 12
    && image.subarray(0, 4).toString("ascii") === "RIFF"
    && image.subarray(8, 12).toString("ascii") === "WEBP"
  ) return "webp";
  if (contentType.includes("svg") && image.subarray(0, 256).toString("utf8").includes("<svg")) {
    return "svg";
  }
  return "";
}

async function downloadAsset(record, destinationBase) {
  for (const extension of ["png", "jpg", "gif", "webp", "svg"]) {
    const existingPath = `${destinationBase}.${extension}`;
    if (!fs.existsSync(existingPath)) continue;
    const existing = fs.readFileSync(existingPath);
    if (existing.length > 128 && detectImageExtension(existing)) {
      return { status: "reused", extension };
    }
  }

  await wait(DOWNLOAD_PAUSE_MS);
  const response = await fetchWithRetry(record.assetUrl, {}, 8);
  const contentType = response.headers.get("content-type") || "";
  if (!response.ok || !contentType.startsWith("image/")) {
    throw new Error(`invalid image response for ${record.municipality}`);
  }
  const image = Buffer.from(await response.arrayBuffer());
  const extension = detectImageExtension(image, contentType);
  if (image.length <= 128 || !extension) {
    throw new Error(`invalid image payload for ${record.municipality}`);
  }
  fs.writeFileSync(`${destinationBase}.${extension}`, image);
  return { status: "downloaded", extension };
}

const profiles = readJson(PROFILE_PATH).profiles || [];
const profileByIstat = new Map(profiles.map((profile) => [profile.istatCode, profile]));
let resolved = [];
let unresolved = [];
let sourceCatalogUsed = false;

if (fs.existsSync(SOURCE_CATALOG_PATH)) {
  const sourceCatalog = readJson(SOURCE_CATALOG_PATH);
  const catalogCodes = new Set(sourceCatalog.visuals?.map((record) => record.istatCode) || []);
  const catalogIsComplete = sourceCatalog.schemaVersion === 1
    && sourceCatalog.visuals?.length === profiles.length
    && profiles.every((profile) => catalogCodes.has(profile.istatCode));
  if (catalogIsComplete) {
    resolved = sourceCatalog.visuals;
    unresolved = sourceCatalog.unresolved || [];
    sourceCatalogUsed = true;
    console.error(`loaded ${resolved.length} verified sources from cache`);
  }
}

if (!sourceCatalogUsed) {
  const queryUrl = new URL("https://query.wikidata.org/sparql");
  queryUrl.searchParams.set("format", "json");
  queryUrl.searchParams.set("query", WIKIDATA_QUERY);
  const wikidataPayload = await fetchJson(queryUrl);
  const wikidataByIstat = new Map();

  for (const row of wikidataPayload.results.bindings) {
    const istatCode = row.istat?.value;
    if (!profileByIstat.has(istatCode)) continue;
    const current = wikidataByIstat.get(istatCode) || {};
    wikidataByIstat.set(istatCode, {
      itemUrl: row.item?.value || current.itemUrl || "",
      articleUrl: row.article?.value || current.articleUrl || "",
      articleTitle: getArticleTitle(row.article?.value) || current.articleTitle || "",
      coatFile: decodeFileName(row.coat?.value) || current.coatFile || "",
    });
  }

  let completedLookups = 0;
  const lookups = await mapConcurrent(
    profiles,
    REQUEST_CONCURRENCY,
    async (profile) => {
      const lookup = {
        profile,
        wikidata: wikidataByIstat.get(profile.istatCode) || {},
        asset: await resolveProfileAsset(profile, wikidataByIstat.get(profile.istatCode)),
      };
      completedLookups += 1;
      if (completedLookups % 25 === 0 || completedLookups === profiles.length) {
        console.error(`checked ${completedLookups}/${profiles.length}`);
      }
      return lookup;
    },
  );

  for (const lookup of lookups) {
    if (!lookup.asset) {
      unresolved.push({
        istatCode: lookup.profile.istatCode,
        municipality: lookup.profile.municipality,
        province: lookup.profile.province,
        articleTitle: lookup.wikidata.articleTitle || "",
      });
      continue;
    }

    resolved.push({
      istatCode: lookup.profile.istatCode,
      municipality: lookup.profile.municipality,
      province: lookup.profile.province,
      articleTitle: lookup.wikidata.articleTitle || "",
      wikidataItemUrl: lookup.wikidata.itemUrl || "",
      fileName: lookup.asset.fileName,
      repository: lookup.asset.repository,
      sourceUrl: lookup.asset.sourceUrl,
      selectionMethod: lookup.asset.selectionMethod,
      assetUrl: lookup.asset.assetUrl,
      contentType: lookup.asset.contentType,
      contentLength: lookup.asset.contentLength,
    });
  }

  if (WRITE && unresolved.length === 0) {
    fs.mkdirSync(path.dirname(SOURCE_CATALOG_PATH), { recursive: true });
    fs.writeFileSync(SOURCE_CATALOG_PATH, `${JSON.stringify({
      schemaVersion: 1,
      generatedAt: new Date().toISOString(),
      visuals: resolved,
      unresolved,
    }, null, 2)}\n`, "utf8");
    console.error(`cached ${resolved.length} verified sources`);
  }
}

if (WRITE) {
  fs.mkdirSync(ASSET_DIR, { recursive: true });
  const downloadCounts = { downloaded: 0, reused: 0 };
  await mapConcurrent(resolved, DOWNLOAD_CONCURRENCY, async (record, index) => {
    const destinationBase = path.join(ASSET_DIR, `${record.istatCode}-coat`);
    const result = await downloadAsset(record, destinationBase);
    const fileName = `${record.istatCode}-coat.${result.extension}`;
    downloadCounts[result.status] += 1;
    record.localUrl = `/municipalities/coats/${fileName}`;
    if ((index + 1) % 25 === 0 || index + 1 === resolved.length) {
      console.error(`saved ${index + 1}/${resolved.length}`);
    }
  });

  const manifest = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    sourcePolicy: {
      primary: "Wikidata P94",
      fallback: "Italian Wikipedia municipality infobox",
      localAssets: true,
    },
    coverage: {
      profiles: profiles.length,
      resolved: resolved.length,
      unresolved: unresolved.length,
    },
    visuals: resolved
      .sort((first, second) => first.istatCode.localeCompare(second.istatCode))
      .map((record) => ({
        istatCode: record.istatCode,
        localUrl: record.localUrl,
      })),
    unresolved,
    downloads: downloadCounts,
  };

  fs.writeFileSync(MANIFEST_PATH, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
}

function countBy(records, key) {
  return records.reduce((counts, record) => {
    const value = record[key] || "missing";
    counts[value] = (counts[value] || 0) + 1;
    return counts;
  }, {});
}

console.log(JSON.stringify({
  profiles: profiles.length,
  resolved: resolved.length,
  unresolved: unresolved.length,
  bySelectionMethod: countBy(resolved, "selectionMethod"),
  byRepository: countBy(resolved, "repository"),
  unresolvedProfiles: unresolved,
  write: WRITE,
  probeFallback: PROBE_FALLBACK,
  sourceCatalogUsed,
}, null, 2));

if (unresolved.length) process.exitCode = 1;
