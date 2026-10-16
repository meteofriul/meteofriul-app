import fs from "node:fs";
import path from "node:path";

import {
  getDiscoverEditorialPolicyAudit,
  getDiscoverEditorialReadiness,
} from "../frontend/src/domain/discover/discoverEditorialPolicy.js";

const DEFAULT_OUTPUT = "backend_dryrun_staging/exports/discover_daily_history_master_triage.json";

const CATEGORY_RULES = [
  {
    category: "memoria_storica",
    keywords: ["assedio", "battaglia", "guerra", "rivolta", "disastro", "terremoto", "resistenza", "occupazione", "liberazione", "trattato"],
    score: 26,
  },
  {
    category: "arte_cultura",
    keywords: ["poeta", "scrittore", "pittore", "scultore", "architetto", "musicista", "teatro", "letteratura", "friulano", "vocabolario", "lingua"],
    score: 22,
  },
  {
    category: "luoghi_patrimonio",
    keywords: ["basilica", "mosaico", "aquileia", "cividale", "patriarcato", "castello", "museo", "archeolog"],
    score: 20,
  },
  {
    category: "scienza_territorio",
    keywords: ["fisico", "matematico", "astronomo", "geologo", "ricerca", "universita", "sincrotrone"],
    score: 16,
  },
  {
    category: "tradizione_costume",
    keywords: ["festa", "sagra", "santo", "tradizione", "costume", "rito", "processione"],
    score: 14,
  },
  {
    category: "sport_spettacolo",
    keywords: ["calciatore", "allenatore", "sport", "olimp", "attore", "cantante", "televis"],
    score: -4,
  },
  {
    category: "rumore_istituzionale",
    keywords: ["societa", "azienda", "autostrada", "strada regionale", "ente di decentramento", "comune italiano", "trasporto pubblico", "denominazione di origine"],
    score: -34,
  },
];

const CORE_PLACES = new Set([
  "aquileia",
  "cividale del friuli",
  "gorizia",
  "grado",
  "pordenone",
  "sacile",
  "san daniele del friuli",
  "san vito al tagliamento",
  "spilimbergo",
  "tolmezzo",
  "trieste",
  "udine",
]);

const EVENT_ACTION_KEYWORDS = [
  "apertura",
  "assedio",
  "battaglia",
  "fondazione",
  "fondato",
  "fondata",
  "inaugurazione",
  "istituzione",
  "istituito",
  "istituita",
  "liberazione",
  "nascita",
  "rivolta",
  "terremoto",
  "trattato",
];

const ENTITY_NOISE_KEYWORDS = [
  "azienda",
  "biblioteca",
  "castello",
  "casa editrice",
  "chiesa",
  "comune italiano",
  "denominazione di origine",
  "edificio",
  "ente di decentramento",
  "ente pubblico",
  "loggia",
  "museo",
  "palazzo",
  "partito",
  "periodico",
  "premio",
  "quotidiano",
  "riconoscimento",
  "societa",
  "societa calcistica",
  "sinagoga",
  "strada regionale",
  "trasporto pubblico",
  "universita",
];

function parseArgs(argv) {
  const args = {
    source: "",
    output: DEFAULT_OUTPUT,
    topPerDay: 8,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--source") {
      args.source = argv[index + 1];
      index += 1;
    } else if (arg === "--output") {
      args.output = argv[index + 1];
      index += 1;
    } else if (arg === "--top-per-day") {
      args.topPerDay = Number.parseInt(argv[index + 1], 10);
      index += 1;
    }
  }

  if (!args.source) {
    throw new Error("Missing required --source <daily-history-master.json> argument.");
  }

  return args;
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(path.resolve(filePath), "utf8").replace(/^\uFEFF/, ""));
}

function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLocaleLowerCase("it-IT");
}

function normalizeDisplay(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim();
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function includesKeyword(text, keyword) {
  const normalizedKeyword = normalizeText(keyword);
  if (!normalizedKeyword) return false;

  const pattern = new RegExp(`(^|[^a-z0-9])${escapeRegExp(normalizedKeyword)}([^a-z0-9]|$)`, "u");
  return pattern.test(text);
}

function parseYear(value) {
  const parsed = Number.parseInt(String(value || "").trim(), 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseNumber(value) {
  const parsed = Number.parseInt(String(value || "").trim(), 10);
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizeWikidataId(record) {
  if (record.wikidataId) return String(record.wikidataId).toUpperCase();
  const rawUrl = String(record.LinkWikidata || record.wikidataUrl || "");
  const match = rawUrl.match(/\/entity\/(Q\d+)/i);
  return match ? match[1].toUpperCase() : null;
}

function getDayKey(record) {
  const raw = normalizeDisplay(record.dayKey || record.GiornoMese);
  return /^\d{2}-\d{2}$/.test(raw) ? raw : null;
}

function getTitle(record) {
  return normalizeDisplay(record.Descrizione_Base || record.title || record.Descrizione || record.wikipediaTitle);
}

function getDetail(record) {
  return normalizeDisplay(record.rawExtract || record.detail || record.Descrizione_Estesa || "");
}

function getCategoryMatch(record) {
  const text = normalizeText(`${getTitle(record)} ${getDetail(record)} ${record.Luogo || record.place}`);
  let best = { category: "altro", score: 0, matchedKeywords: [] };

  for (const rule of CATEGORY_RULES) {
    const matchedKeywords = rule.keywords.filter((keyword) => includesKeyword(text, keyword));
    if (!matchedKeywords.length) continue;
    if (rule.score > best.score || best.category === "altro") {
      best = {
        category: rule.category,
        score: rule.score,
        matchedKeywords,
      };
    }
  }

  return best;
}

function getTypeScore(type) {
  if (type === "Evento") return 32;
  if (type === "Nascita" || type === "Morte") return 8;
  return 4;
}

function getPlaceScore(place) {
  const normalized = normalizeText(place);
  if (CORE_PLACES.has(normalized)) return 16;
  if (normalized.includes("friuli") || normalized.includes("venezia giulia")) return 8;
  if (normalized) return 5;
  return 0;
}

function getNarrativeScore(record) {
  const detail = getDetail(record);
  const title = getTitle(record);
  let score = 0;
  if (detail.length >= 80) score += 8;
  if (detail.length >= 220) score += 4;
  if (title.length > 120) score -= 5;
  if (!detail) score -= 8;
  return score;
}

function getSourceScore(record) {
  let score = 0;
  if (record.wikipediaUrl) score += 5;
  if (record.rawExtract) score += 6;
  if (record.sourceType === "wikidata+wikipedia") score += 4;
  return score;
}

function getNoisePenalty(record) {
  const text = normalizeText(`${getTitle(record)} ${getDetail(record)}`);
  const type = normalizeDisplay(record.Tipo || record.type);
  let penalty = 0;
  if (includesKeyword(text, "calciatore") || includesKeyword(text, "allenatore")) penalty -= 16;
  if (ENTITY_NOISE_KEYWORDS.some((keyword) => includesKeyword(text, keyword))) penalty -= 24;
  if (type === "Evento" && !EVENT_ACTION_KEYWORDS.some((keyword) => includesKeyword(text, keyword))) {
    penalty -= 30;
  }
  if (includesKeyword(text, "lista di")) penalty -= 12;
  return penalty;
}

function buildEditorialClass(score) {
  if (score >= 78) return "A";
  if (score >= 58) return "B";
  if (score >= 38) return "C";
  return "D";
}

function getSuggestedSurface(className, readiness) {
  if (readiness.status === "needs_strong_source") return "strong_memory_source_work";
  if (readiness.status === "light_candidate" && (className === "A" || className === "B")) return "light_daily_rubric_candidate";
  if (className === "A" || className === "B") return "memory_candidate";
  if (className === "C") return "discover_archive_candidate";
  return "discard_or_deep_archive";
}

function getPublicationTriage(candidate) {
  if (candidate.needsStrongSource) return "needs_strong_source";
  if (candidate.suggestedSurface === "light_daily_rubric_candidate") return "review_for_light_daily";
  if (candidate.suggestedSurface === "memory_candidate") return "review_for_memory";
  if (candidate.suggestedSurface === "discover_archive_candidate") return "archive_candidate";
  return "discard_or_deep_archive";
}

function buildCandidate(record, index) {
  const dayKey = getDayKey(record);
  const type = normalizeDisplay(record.Tipo || record.type);
  const place = normalizeDisplay(record.Luogo || record.place || "Friuli Venezia Giulia");
  const category = getCategoryMatch(record);
  const siteLinks = parseNumber(record.PunteggioSitelinks || record.siteLinksScore);
  const score = (
    getTypeScore(type) +
    getPlaceScore(place) +
    category.score +
    Math.min(18, Math.round(siteLinks / 5)) +
    getNarrativeScore(record) +
    getSourceScore(record) +
    getNoisePenalty(record)
  );
  const editorialClass = buildEditorialClass(score);
  const normalizedRecord = {
    id: `master-fvg-${dayKey || "unknown"}-${normalizeWikidataId(record) || index}`,
    sourceCandidateId: `master-fvg-${dayKey || "unknown"}-${normalizeWikidataId(record) || index}`,
    sourceDayKey: dayKey,
    dateAnchor: dayKey ? `${dayKey.slice(3, 5)}-${dayKey.slice(0, 2)}` : null,
    title: { it: getTitle(record) },
    sourceTitle: normalizeDisplay(record.wikipediaTitle || getTitle(record)),
    year: parseYear(record.Anno || record.year),
    place,
    category: category.category,
    reviewStatus: "source_lead_found",
    editorialStatus: "candidate_for_review",
    readyForUi: false,
  };
  const readiness = getDiscoverEditorialReadiness(normalizedRecord);

  return {
    ...normalizedRecord,
    type,
    wikidataId: normalizeWikidataId(record),
    wikipediaUrl: normalizeDisplay(record.wikipediaUrl),
    sourceType: normalizeDisplay(record.sourceType),
    score,
    editorialClass,
    matchedKeywords: category.matchedKeywords,
    detailPreview: getDetail(record).slice(0, 360),
    editorialReadiness: readiness.status,
    suggestedSurface: getSuggestedSurface(editorialClass, readiness),
    canPublishLight: readiness.canPublishLight,
    needsStrongSource: readiness.needsStrongSource,
    reasons: [
      `${type || "Tipo non definito"}: ${getTypeScore(type)} punti base`,
      `${place}: ${getPlaceScore(place)} punti luogo`,
      `Categoria ${category.category}: ${category.score} punti`,
      `Visibilita Wikidata: ${Math.min(18, Math.round(siteLinks / 5))} punti`,
      `Fonte/metadati: ${getSourceScore(record)} punti`,
      `Narrativa: ${getNarrativeScore(record)} punti`,
      `Rumore: ${getNoisePenalty(record)} punti`,
      `Policy: ${readiness.status}`,
    ],
  };
}

function groupByDay(records) {
  return records.reduce((acc, record) => {
    if (!record.sourceDayKey) return acc;
    if (!acc[record.sourceDayKey]) acc[record.sourceDayKey] = [];
    acc[record.sourceDayKey].push(record);
    return acc;
  }, {});
}

function countBy(records, keyFn) {
  return records.reduce((acc, record) => {
    const key = keyFn(record) || "missing";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function topEntries(counts, limit = 20) {
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "it-IT"))
    .slice(0, limit)
    .map(([name, count]) => ({ name, count }));
}

function buildLeapYearDayKeys() {
  const keys = [];
  for (let month = 1; month <= 12; month += 1) {
    const daysInMonth = new Date(Date.UTC(2024, month, 0)).getUTCDate();
    for (let day = 1; day <= daysInMonth; day += 1) {
      keys.push(`${String(day).padStart(2, "0")}-${String(month).padStart(2, "0")}`);
    }
  }
  return keys;
}

function buildSummary(candidates, days) {
  const coveredDays = Object.keys(days).sort();
  const missingDays = buildLeapYearDayKeys().filter((dayKey) => !coveredDays.includes(dayKey));
  const policyAudit = getDiscoverEditorialPolicyAudit(candidates);
  const candidatesWithTriage = candidates.map((candidate) => ({
    ...candidate,
    publicationTriage: getPublicationTriage(candidate),
  }));
  const daysWithReviewLightCandidate = Object.values(days).filter((records) => (
    records.some((record) => getPublicationTriage(record) === "review_for_light_daily")
  ));
  const daysWithStrongSourceWork = Object.values(days).filter((records) => (
    records.some((record) => getPublicationTriage(record) === "needs_strong_source")
  ));
  const daysWithoutDailyCandidate = Object.values(days).filter((records) => (
    !records.some((record) => (
      getPublicationTriage(record) === "review_for_light_daily" ||
      getPublicationTriage(record) === "needs_strong_source"
    ))
  ));

  return {
    totalRecords: candidates.length,
    coveredDays: coveredDays.length,
    missingDays,
    byType: countBy(candidates, (record) => record.type),
    byEditorialClass: countBy(candidates, (record) => record.editorialClass),
    byCategory: countBy(candidates, (record) => record.category),
    byRawEditorialPolicyReadiness: policyAudit.byReadiness,
    bySuggestedSurface: countBy(candidates, (record) => record.suggestedSurface),
    byPublicationTriage: countBy(candidatesWithTriage, (record) => record.publicationTriage),
    dayTriage: {
      daysWithReviewLightCandidate: daysWithReviewLightCandidate.length,
      daysWithStrongSourceWork: daysWithStrongSourceWork.length,
      daysWithoutDailyCandidate: daysWithoutDailyCandidate.length,
    },
    topPlaces: topEntries(countBy(candidates, (record) => record.place), 25),
    rawPolicyLightCandidateRecords: policyAudit.lightCandidateRecordIds.length,
    rawPolicyStrongSourceRequiredRecords: policyAudit.strongSourceRequiredRecordIds.length,
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const raw = readJson(args.source);
  const sourceRecords = Array.isArray(raw) ? raw : raw.records || [];
  const candidates = sourceRecords
    .map(buildCandidate)
    .filter((candidate) => candidate.sourceDayKey && candidate.title.it);
  const grouped = groupByDay(candidates);
  const days = Object.entries(grouped)
    .sort(([a], [b]) => a.localeCompare(b, "it-IT"))
    .map(([dayKey, records]) => ({
      dayKey,
      dateAnchor: `${dayKey.slice(3, 5)}-${dayKey.slice(0, 2)}`,
      candidates: records
        .sort((a, b) => b.score - a.score || (a.year || 0) - (b.year || 0))
        .slice(0, args.topPerDay)
        .map((candidate) => ({
          ...candidate,
          publicationTriage: getPublicationTriage(candidate),
        })),
    }));

  const payload = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    source: {
      file: path.basename(args.source),
      sourceKind: "wikidata_wikipedia_master",
      rule: "Master completo come archivio sorgente. Lo scoring orienta la review, non pubblica contenuti.",
    },
    policy: {
      noAutomaticPublication: true,
      lightRubricAllowedOnlyAfterHumanReview: true,
      strongSourceRequiredForSensitiveHistory: true,
    },
    scoringModel: {
      version: 1,
      topPerDay: args.topPerDay,
      editorialClasses: {
        A: "Molto promettente, da review.",
        B: "Buon candidato, da lavorare.",
        C: "Archivio/riserva.",
        D: "Rumore o archivio profondo.",
      },
    },
    summary: buildSummary(candidates, grouped),
    days,
  };

  const outputPath = path.resolve(args.output);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");

  console.log(`Triaged ${candidates.length} records across ${days.length} days.`);
  console.log(`Output: ${outputPath}`);
  console.log(JSON.stringify(payload.summary, null, 2));
}

main();
