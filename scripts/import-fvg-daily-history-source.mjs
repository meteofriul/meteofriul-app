import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_OUTPUT = "backend_dryrun_staging/exports/discover_daily_history_wikidata_source.json";
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function parseArgs(argv) {
  const args = {
    source: null,
    output: DEFAULT_OUTPUT,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--source") {
      args.source = argv[index + 1];
      index += 1;
    } else if (arg === "--output") {
      args.output = argv[index + 1];
      index += 1;
    }
  }

  return args;
}

function toPortableSourceRef(filePath) {
  const absolutePath = path.resolve(filePath);
  const relativePath = path.relative(REPO_ROOT, absolutePath);
  if (relativePath && !relativePath.startsWith("..") && !path.isAbsolute(relativePath)) {
    return relativePath.split(path.sep).join("/");
  }
  return `external/fvg/${path.basename(absolutePath)}`;
}

function normalizeYear(year) {
  const parsed = Number.parseInt(String(year || "").trim(), 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeWikidataId(url) {
  const value = String(url || "").trim();
  const match = value.match(/\/entity\/(Q\d+)$/i);
  return match ? match[1].toUpperCase() : null;
}

function normalizeText(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeNumber(value) {
  const parsed = Number.parseInt(String(value || "").trim(), 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeImportance(value) {
  const raw = normalizeText(value);
  const labelMatch = raw.match(/\(([^)]+)\)/);
  return {
    raw,
    label: labelMatch ? labelMatch[1] : raw || null,
  };
}

function splitDescription(sourceRecord) {
  const value = normalizeText(sourceRecord.Descrizione_Estesa || sourceRecord.Descrizione);
  const marker = " Approfondimento: ";
  const markerIndex = value.indexOf(marker);
  if (markerIndex === -1) {
    return {
      title: value,
      detail: "",
      full: value,
    };
  }

  return {
    title: value.slice(0, markerIndex).trim(),
    detail: value.slice(markerIndex + marker.length).trim(),
    full: value,
  };
}

function getReviewBucket(record) {
  if (record.type === "Evento") return "event_story_candidate";
  if (record.type === "Nascita" || record.type === "Morte") return "biography_candidate";
  return "raw_candidate";
}

function getDestinationHint(record) {
  if (record.type === "Evento") return "memoria_del_giorno_candidate";
  return "scopri_archive_or_memory_candidate";
}

function getDayKey(value) {
  const raw = String(value || "").trim();
  const match = raw.match(/^(\d{2})-(\d{2})$/);
  if (!match) return null;
  return `${match[1]}-${match[2]}`;
}

function buildRecord(sourceRecord, index) {
  const dayKey = getDayKey(sourceRecord.GiornoMese);
  const type = normalizeText(sourceRecord.Tipo);
  const year = normalizeYear(sourceRecord.Anno);
  const wikidataUrl = normalizeText(sourceRecord.LinkWikidata);
  const wikidataId = normalizeWikidataId(wikidataUrl);
  const place = normalizeText(sourceRecord.Luogo) || "Friuli-Venezia Giulia";
  const description = splitDescription(sourceRecord);
  const siteLinksScore = normalizeNumber(sourceRecord.PunteggioSitelinks);
  const importance = normalizeImportance(sourceRecord.Importanza);

  return {
    id: `wikidata-fvg-${dayKey || "unknown"}-${wikidataId || index}`,
    dayKey,
    year,
    place,
    type,
    title: description.title,
    description: description.full,
    detail: description.detail,
    siteLinksScore,
    importance,
    wikidataId,
    wikidataUrl,
    reviewStatus: "raw_wikidata_candidate",
    reviewBucket: getReviewBucket({ type }),
    destinationHint: getDestinationHint({ type }),
    needsEditorialRewrite: true,
    readyForUi: false,
  };
}

function countBy(records, keyGetter) {
  return records.reduce((acc, record) => {
    const key = keyGetter(record) || "unknown";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function getTopEntries(counts, limit = 20) {
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "it"))
    .slice(0, limit)
    .map(([name, count]) => ({ name, count }));
}

function buildLeapYearDayKeys() {
  const days = [];
  for (let month = 1; month <= 12; month += 1) {
    const daysInMonth = new Date(Date.UTC(2024, month, 0)).getUTCDate();
    for (let day = 1; day <= daysInMonth; day += 1) {
      days.push(`${String(day).padStart(2, "0")}-${String(month).padStart(2, "0")}`);
    }
  }
  return days;
}

function buildSummary(records) {
  const coveredDays = [...new Set(records.map((record) => record.dayKey).filter(Boolean))].sort();
  const allDays = buildLeapYearDayKeys();
  const missingDays = allDays.filter((dayKey) => !coveredDays.includes(dayKey));
  const byType = countBy(records, (record) => record.type);
  const byPlace = countBy(records, (record) => record.place);
  const byDestinationHint = countBy(records, (record) => record.destinationHint);
  const byImportance = countBy(records, (record) => record.importance?.label);

  return {
    totalRecords: records.length,
    coveredDays: coveredDays.length,
    missingDays,
    byType,
    byImportance,
    byDestinationHint,
    topPlaces: getTopEntries(byPlace, 25),
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.source) {
    throw new Error("Missing required --source <path> for the external FVG history dataset.");
  }
  const sourcePath = path.resolve(args.source);
  const outputPath = path.resolve(args.output);
  const raw = JSON.parse(fs.readFileSync(sourcePath, "utf8").replace(/^\uFEFF/, ""));
  const records = raw.map(buildRecord).filter((record) => record.dayKey && record.description);

  const payload = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    source: {
      label: "Wikidata FVG accadde oggi",
      originalPath: toPortableSourceRef(args.source),
      sourceKind: "wikidata_sparql_export",
      sourceStatus: "raw_external_candidate_pool",
      selectionModel: records.length <= 400 && payloadHasOneRecordPerCoveredDay(records)
        ? "preselected_one_record_per_day"
        : "multi_record_raw_pool",
      publicationRule: "Do not publish directly. Use as a source index for editorial review, rewrite, FUR review and source confirmation.",
    },
    summary: buildSummary(records),
    records,
  };

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  console.log(`Imported ${records.length} records to ${outputPath}`);
  console.log(`Covered days: ${payload.summary.coveredDays}`);
}

function payloadHasOneRecordPerCoveredDay(records) {
  const byDay = countBy(records, (record) => record.dayKey);
  return Object.values(byDay).every((count) => count === 1);
}

main();
