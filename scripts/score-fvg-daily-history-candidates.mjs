import fs from "node:fs";
import path from "node:path";

const DEFAULT_SOURCE = "backend_dryrun_staging/exports/discover_daily_history_wikidata_source.json";
const DEFAULT_EXTENDED_SOURCE = "backend_dryrun_staging/exports/discover_daily_history_wikidata_extended_source.json";
const DEFAULT_OUTPUT = "backend_dryrun_staging/exports/discover_daily_history_ranked_candidates.json";

const CATEGORY_RULES = [
  {
    category: "archeologia",
    keywords: ["basilica", "mosaico", "archeolog", "romano"],
    bonus: 24,
  },
  {
    category: "storia",
    keywords: ["guerra", "fronte", "resistenza", "disastro", "vajont", "redipuglia", "asburg", "litorale", "assedio", "battaglia", "rivolta", "patriarc"],
    bonus: 22,
  },
  {
    category: "lingua_cultura",
    keywords: ["scrittore", "poeta", "lingu", "friulan", "vocabolario", "music", "artista", "fotografo", "grafico", "teatro", "letter"],
    bonus: 20,
  },
  {
    category: "scienza",
    keywords: ["fisico", "matematico", "scienzi", "astronom", "ricerca", "sincrotrone", "geolog"],
    bonus: 16,
  },
  {
    category: "tradizioni",
    keywords: ["santo", "santa", "festa", "sagra", "tradizion", "costume", "rito"],
    bonus: 14,
  },
  {
    category: "sport",
    keywords: ["calciatore", "allenatore", "sport", "olimp", "canoista", "cestista", "mondiale", "nuoto"],
    bonus: 2,
  },
  {
    category: "istituzioni",
    keywords: ["ente di decentramento", "provincia", "comune italiano", "autostrada", "trasporto pubblico", "societa", "azienda", "compagnia", "cooperativa", "assicurazioni", "denominazione di origine", "tipologia della denominazione"],
    bonus: -32,
  },
];

const EVENT_KEYWORDS = [
  "assedio",
  "battaglia",
  "rivolta",
  "terremoto",
  "disastro",
  "strage",
  "incendio",
  "processo",
  "trattato",
  "fondazione",
  "apertura",
  "inaugurazione",
  "istituzione",
  "annessione",
  "occupazione",
  "liberazione di",
];

const ENTITY_NOISE_KEYWORDS = [
  "societa pubblica",
  "societa per azioni",
  "compagnia telematica",
  "trasporto pubblico",
  "cooperativa di consumatori",
  "denominazione di origine",
  "tipologia della denominazione",
  "autostrada",
  "strada regionale",
  "museo statale",
  "istituto di ricerca",
  "sede rai",
  "palazzo di",
  "chiesa di",
  "edificio religioso",
  "centro di ricerca",
  "campionati europei",
  "corsa per",
  "friuli-venezia giulia -",
];

const FVG_CORE_PLACES = new Set([
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

function parseArgs(argv) {
  const args = {
    source: DEFAULT_SOURCE,
    extendedSource: DEFAULT_EXTENDED_SOURCE,
    output: DEFAULT_OUTPUT,
    topPerDay: 5,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--source") {
      args.source = argv[index + 1];
      index += 1;
    } else if (arg === "--extended-source") {
      args.extendedSource = argv[index + 1];
      index += 1;
    } else if (arg === "--output") {
      args.output = argv[index + 1];
      index += 1;
    } else if (arg === "--top-per-day") {
      args.topPerDay = Number.parseInt(argv[index + 1], 10);
      index += 1;
    }
  }

  return args;
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(path.resolve(filePath), "utf8").replace(/^\uFEFF/, ""));
}

function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/\s+/g, " ")
    .trim();
}

function titleCaseReason(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function matchCategory(record) {
  const haystack = normalizeText(`${record.title} ${record.description} ${record.detail}`);
  let best = {
    category: "altro",
    bonus: 0,
    matchedKeywords: [],
  };

  for (const rule of CATEGORY_RULES) {
    const matchedKeywords = rule.keywords.filter((keyword) => haystack.includes(normalizeText(keyword)));
    if (!matchedKeywords.length) continue;
    if (rule.bonus > best.bonus || best.category === "altro") {
      best = {
        category: rule.category,
        bonus: rule.bonus,
        matchedKeywords,
      };
    }
  }

  return best;
}

function getTypeScore(type) {
  if (type === "Evento") return 32;
  if (type === "Morte") return 10;
  if (type === "Nascita") return 8;
  return 4;
}

function getPlaceScore(place) {
  const normalized = normalizeText(place);
  if (FVG_CORE_PLACES.has(normalized)) return 14;
  if (normalized.includes("friuli-venezia giulia")) return 8;
  if (normalized.includes("provincia") || normalized.includes("ente di decentramento")) return -8;
  if (normalized) return 6;
  return 0;
}

function getNarrativeScore(record) {
  const text = normalizeText(`${record.title} ${record.detail}`);
  let score = 0;
  if (record.detail && record.detail.length >= 70) score += 7;
  if (text.includes("approfondimento")) score -= 2;
  if (text.includes("comune italiano")) score -= 12;
  if (text.includes("ente locale")) score -= 12;
  if (text.includes("politico italiano") && record.siteLinksScore < 20) score -= 8;
  if (text.includes("calciatore") && record.siteLinksScore < 35) score -= 8;
  if (text.includes("santo") || text.includes("patriarca") || text.includes("friul")) score += 8;
  return score;
}

function getNoisePenalty(record) {
  const text = normalizeText(`${record.title} ${record.detail}`);
  let penalty = 0;

  if (ENTITY_NOISE_KEYWORDS.some((keyword) => text.includes(normalizeText(keyword)))) {
    penalty -= 28;
  }
  if (record.type === "Evento" && !EVENT_KEYWORDS.some((keyword) => text.includes(normalizeText(keyword)))) {
    penalty -= 16;
  }
  if ((record.type === "Nascita" || record.type === "Morte") && text.includes("calciatore")) {
    penalty -= 14;
  }
  if ((record.type === "Nascita" || record.type === "Morte") && text.includes("dirigente sportivo")) {
    penalty -= 14;
  }
  if (!record.detail && !Number.isFinite(record.siteLinksScore)) {
    penalty -= 4;
  }

  return penalty;
}

function getSiteLinksScore(record) {
  const value = Number.isFinite(record.siteLinksScore) ? record.siteLinksScore : 0;
  return Math.min(18, Math.round(value / 5));
}

function getEditorialClass(score) {
  if (score >= 72) return "A";
  if (score >= 52) return "B";
  if (score >= 34) return "C";
  return "D";
}

function getSuggestedSurface(record, editorialClass) {
  if (editorialClass === "A" || editorialClass === "B") return "memoria_del_giorno_candidate";
  if (editorialClass === "C") return "scopri_archive_candidate";
  return "discard_or_deep_archive";
}

function getScore(record, extendedRecordIds) {
  const category = matchCategory(record);
  const extendedBaselineBonus = extendedRecordIds.has(record.id) ? 6 : 0;
  const score = (
    getTypeScore(record.type) +
    getPlaceScore(record.place) +
    getSiteLinksScore(record) +
    getNarrativeScore(record) +
    getNoisePenalty(record) +
    category.bonus +
    extendedBaselineBonus
  );

  const reasons = [
    `${record.type || "tipo non definito"}: ${getTypeScore(record.type)} punti base`,
    `${record.place || "luogo non definito"}: ${getPlaceScore(record.place)} punti luogo`,
    `visibilita Wikidata: ${getSiteLinksScore(record)} punti`,
  ];

  if (category.category !== "altro") {
    reasons.push(`categoria ${category.category}: ${category.bonus} punti`);
  }
  if (extendedBaselineBonus) {
    reasons.push("presente nella proposta estesa: +6");
  }
  const noisePenalty = getNoisePenalty(record);
  if (noisePenalty) {
    reasons.push(`penalita rumore: ${noisePenalty}`);
  }

  return {
    score,
    category: category.category,
    matchedKeywords: category.matchedKeywords,
    reasons: reasons.map(titleCaseReason),
  };
}

function groupByDay(records) {
  return records.reduce((acc, record) => {
    if (!record.dayKey) return acc;
    if (!acc[record.dayKey]) acc[record.dayKey] = [];
    acc[record.dayKey].push(record);
    return acc;
  }, {});
}

function getExtendedRecordIds(extendedSource) {
  if (!extendedSource?.records) return new Set();
  return new Set(extendedSource.records.map((record) => record.id));
}

function rankRecord(record, extendedRecordIds) {
  const scored = getScore(record, extendedRecordIds);
  const editorialClass = getEditorialClass(scored.score);
  return {
    id: record.id,
    dayKey: record.dayKey,
    year: record.year,
    place: record.place,
    type: record.type,
    title: record.title,
    detail: record.detail,
    wikidataId: record.wikidataId,
    wikidataUrl: record.wikidataUrl,
    score: scored.score,
    editorialClass,
    category: scored.category,
    matchedKeywords: scored.matchedKeywords,
    suggestedSurface: getSuggestedSurface(record, editorialClass),
    reasons: scored.reasons,
    reviewStatus: "ranked_candidate_needs_human_review",
    readyForUi: false,
  };
}

function buildSummary(days) {
  const topCandidates = days.map((day) => day.candidates[0]).filter(Boolean);
  const countByClass = topCandidates.reduce((acc, candidate) => {
    acc[candidate.editorialClass] = (acc[candidate.editorialClass] || 0) + 1;
    return acc;
  }, {});
  const countByType = topCandidates.reduce((acc, candidate) => {
    acc[candidate.type] = (acc[candidate.type] || 0) + 1;
    return acc;
  }, {});
  const countBySurface = topCandidates.reduce((acc, candidate) => {
    acc[candidate.suggestedSurface] = (acc[candidate.suggestedSurface] || 0) + 1;
    return acc;
  }, {});

  return {
    days: days.length,
    topCandidateClassCounts: countByClass,
    topCandidateTypeCounts: countByType,
    topCandidateSurfaceCounts: countBySurface,
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const source = readJson(args.source);
  const extendedSource = fs.existsSync(path.resolve(args.extendedSource))
    ? readJson(args.extendedSource)
    : null;
  const extendedRecordIds = getExtendedRecordIds(extendedSource);
  const grouped = groupByDay(source.records || []);
  const days = Object.entries(grouped)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([dayKey, records]) => {
      const candidates = records
        .map((record) => rankRecord(record, extendedRecordIds))
        .sort((a, b) => b.score - a.score || (a.year || 0) - (b.year || 0))
        .slice(0, args.topPerDay);

      return {
        dayKey,
        candidates,
      };
    });

  const payload = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    source: {
      primary: path.resolve(args.source),
      complementaryBaseline: extendedSource ? path.resolve(args.extendedSource) : null,
      rule: "5000-record corpus first, Meteo Friul scoring second, 365-day extended file as complementary baseline only, human review before publication.",
    },
    scoringModel: {
      version: 1,
      publicationRule: "Scores rank candidates only. They do not publish content.",
      topPerDay: args.topPerDay,
      editorialClasses: {
        A: "Strong memory candidate.",
        B: "Good candidate, likely needs copy/source refinement.",
        C: "Archive or reserve candidate.",
        D: "Noise or deep archive.",
      },
    },
    summary: buildSummary(days),
    days,
  };

  const outputPath = path.resolve(args.output);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  console.log(`Ranked ${days.length} days to ${outputPath}`);
  console.log(JSON.stringify(payload.summary, null, 2));
}

main();
