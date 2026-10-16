import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_SOURCE = "backend_dryrun_staging/exports/discover_daily_history_master_triage.json";
const DEFAULT_LOCAL_MEMORY = "frontend/src/data/discover/localMemory.json";
const DEFAULT_REVIEW_PACK = "frontend/src/data/discover/dailyHistoryReviewPack.json";
const DEFAULT_OUTPUT = "frontend/src/data/discover/dailyHistoryExpandedReview.json";
const MASTER_SOURCE_REF = "external/fvg/accadde_oggi_fvg_completo_esteso_metadata.json";
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function toPortablePath(filePath) {
  const relativePath = path.relative(REPO_ROOT, path.resolve(filePath));
  if (relativePath && !relativePath.startsWith("..") && !path.isAbsolute(relativePath)) {
    return relativePath.split(path.sep).join("/");
  }
  return `external/${path.basename(path.resolve(filePath))}`;
}

const ALLOWED_TRIAGE = new Set([
  "review_for_light_daily",
  "archive_candidate",
]);

const ALLOWED_CLASSES = new Set(["A", "B", "C"]);

const CATEGORY_PRIORITY = {
  arte_cultura: 1,
  luoghi_patrimonio: 2,
  scienza_territorio: 3,
  tradizione_costume: 4,
  memoria_storica: 5,
};

const REVIEW_DECISIONS = {
  Q29517411: ["archive_after_review", "publisher_record_not_daily_copy"],
  Q246373: ["hold_strong_source", "war_occupation_sensitive_topic"],
  Q1465751: ["archive_after_review", "historical_profile_needs_context"],
  Q46734: ["archive_after_review", "ancient_history_needs_short_context"],
  Q78781: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q79091: ["archive_after_review", "business_profile_not_daily_priority"],
  Q596351: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q246149: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q3659878: ["archive_after_review", "writer_profile_with_patriotic_context"],
  Q3779415: ["hold_strong_source", "porzus_resistance_sensitive_topic"],
  Q927898: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q268220: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q11876912: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q274404: ["copy_candidate", "strong_cultural_profile"],
  Q211396: ["archive_after_review", "ancient_history_needs_short_context"],
  Q3846948: ["hold_strong_source", "war_memory_sensitive_topic"],
  Q105337272: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q17352060: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q134933701: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q58816013: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q3645802: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q3766597: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q29616920: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q3731891: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q388090: ["copy_candidate", "strong_art_profile"],
  Q3067860: ["archive_after_review", "patriotic_profile_needs_context"],
  Q2527720: ["archive_after_review", "profile_more_context_than_daily_copy"],
  Q240383: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q3766624: ["archive_after_review", "patriotic_profile_needs_context"],
  Q738539: ["copy_candidate", "strong_cultural_profile"],
  Q136700264: ["copy_candidate", "local_music_profile"],
  Q18638739: ["archive_after_review", "music_profile_lower_daily_priority"],
  Q3779449: ["archive_after_review", "border_history_needs_context"],
  Q23857090: ["copy_candidate", "local_architecture_profile"],
  Q86496916: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q23309411: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q72396975: ["hold_strong_source", "resistance_memory_sensitive_topic"],
  Q3609973: ["copy_candidate", "writer_and_screen_profile"],
  Q3083090: ["copy_candidate", "art_profile_with_gorizia_context"],
  Q532760: ["copy_candidate", "strong_art_profile"],
  Q1494084: ["hold_bad_source", "ambiguous_disambiguation_page"],
  Q981101: ["copy_candidate", "contemporary_music_profile"],
  Q602794: ["copy_candidate", "architecture_profile_with_gorizia_context"],
  Q974735: ["archive_after_review", "weak_local_fit_needs_context"],
  Q3772850: ["archive_after_review", "cross_border_art_profile_needs_context"],
  Q3547989: ["copy_candidate", "local_philosophy_profile"],
  Q855258: ["copy_candidate", "strong_poetry_profile"],
  Q107094210: ["hold_strong_source", "military_profile_sensitive_topic"],
  Q10993506: ["copy_candidate", "strong_friulian_poetry_profile"],
  Q21208736: ["copy_candidate", "local_art_profile"],
  Q3820169: ["copy_candidate", "local_writer_artist_profile"],
  Q3830505: ["archive_after_review", "literary_profile_lower_daily_priority"],
  Q2591921: ["archive_after_review", "ecclesiastical_history_needs_context"],
  Q27986842: ["archive_after_review", "political_profile_lower_daily_priority"],
  Q3767101: ["archive_after_review", "entertainment_profile_lower_daily_priority"],
  Q3876555: ["archive_after_review", "ecclesiastical_history_needs_context"],
  Q7313382: ["archive_after_review", "sports_profile_lower_daily_priority"],
  Q3903088: ["copy_candidate", "strong_poetry_profile"],
  Q382053: ["copy_candidate", "strong_architecture_profile"],
  Q3618871: ["copy_candidate", "science_and_natural_history_profile"],
  Q842033: ["copy_candidate", "local_art_profile"],
  Q3548105: ["copy_candidate", "local_friulian_culture_profile"],
  Q3341616: ["copy_candidate", "art_profile_with_local_context"],
  Q1705206: ["copy_candidate", "grado_art_profile"],
  Q67413: ["archive_after_review", "science_profile_weak_local_fit"],
  Q15229393: ["copy_candidate", "aquileia_archaeology_profile"],
  Q108620032: ["archive_after_review", "political_profile_lower_daily_priority"],
  Q104155857: ["archive_after_review", "institutional_record_not_daily_copy"],
  Q332742: ["archive_after_review", "sports_profile_lower_daily_priority"],
  Q2381425: ["archive_after_review", "science_profile_possible_archive"],
  Q2903363: ["archive_after_review", "science_territory_profile_possible_archive"],
  Q3702596: ["archive_after_review", "science_profile_possible_archive"],
  Q556293: ["archive_after_review", "ecclesiastical_profile_lower_daily_priority"],
  Q2705256: ["archive_after_review", "sports_profile_lower_daily_priority"],
  Q605191: ["archive_after_review", "music_profile_possible_archive"],
  Q3720262: ["archive_after_review", "music_profile_possible_archive"],
  Q976377: ["archive_after_review", "sports_profile_lower_daily_priority"],
  Q43303860: ["archive_after_review", "sports_profile_lower_daily_priority"],
  Q2640578: ["archive_after_review", "weak_local_fit_sports_profile"],
  Q7396805: ["archive_after_review", "major_history_event_needs_context"],
};

function parseArgs(argv) {
  const args = {
    source: DEFAULT_SOURCE,
    localMemory: DEFAULT_LOCAL_MEMORY,
    reviewPack: DEFAULT_REVIEW_PACK,
    output: DEFAULT_OUTPUT,
    limit: 80,
    maxPerPlace: 10,
    maxPerCategory: 28,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--source") {
      args.source = argv[index + 1];
      index += 1;
    } else if (arg === "--local-memory") {
      args.localMemory = argv[index + 1];
      index += 1;
    } else if (arg === "--review-pack") {
      args.reviewPack = argv[index + 1];
      index += 1;
    } else if (arg === "--output") {
      args.output = argv[index + 1];
      index += 1;
    } else if (arg === "--limit") {
      args.limit = Number.parseInt(argv[index + 1], 10);
      index += 1;
    } else if (arg === "--max-per-place") {
      args.maxPerPlace = Number.parseInt(argv[index + 1], 10);
      index += 1;
    } else if (arg === "--max-per-category") {
      args.maxPerCategory = Number.parseInt(argv[index + 1], 10);
      index += 1;
    }
  }

  return args;
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(path.resolve(filePath), "utf8").replace(/^\uFEFF/, ""));
}

function recordsFrom(source) {
  if (Array.isArray(source)) return source;
  return Array.isArray(source?.records) ? source.records : [];
}

function candidatesFrom(source) {
  return (source.days || []).flatMap((day) => (
    (day.candidates || []).map((candidate) => ({
      ...candidate,
      sourceDayKey: candidate.sourceDayKey || day.dayKey,
      dateAnchor: candidate.dateAnchor || day.dateAnchor,
    }))
  ));
}

function collectKnownWikidataIds(...sources) {
  return new Set(sources.flatMap((source) => recordsFrom(source)).flatMap((record) => [
    record.wikidataId,
    record.source?.wikidataId,
  ]).filter(Boolean));
}

function countBy(records, keyFn) {
  return records.reduce((acc, record) => {
    const key = keyFn(record) || "missing";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function classifyCandidate(candidate) {
  if (candidate.publicationTriage === "review_for_light_daily") {
    return "light_daily_review";
  }
  if (candidate.publicationTriage === "archive_candidate") {
    return "archive_review";
  }
  return "discarded_by_policy";
}

function textValue(value) {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") return value.it || value.fur || Object.values(value).find(Boolean) || "";
  return "";
}

function titleFrom(candidate) {
  return textValue(candidate.title || candidate.sourceTitle || candidate.label || candidate.name).trim();
}

function decisionFor(candidate, extractionClass) {
  const [reviewStatus, reason] = REVIEW_DECISIONS[candidate.wikidataId] || ["extracted_for_review", "pending_editorial_review"];
  const editorialStatusByReview = {
    copy_candidate: "light_copy_candidate",
    archive_after_review: "archive_candidate_after_review",
    hold_strong_source: "hold_requires_strong_source",
    hold_bad_source: "hold_source_not_usable",
    extracted_for_review: extractionClass === "light_daily_review"
      ? "light_candidate_for_review"
      : "archive_candidate_for_review",
  };

  return {
    reviewStatus,
    editorialStatus: editorialStatusByReview[reviewStatus] || "candidate_for_review",
    reason,
  };
}

function isCandidateAllowed(candidate, knownWikidataIds) {
  if (!candidate.wikidataId) return false;
  if (knownWikidataIds.has(candidate.wikidataId)) return false;
  if (!ALLOWED_TRIAGE.has(candidate.publicationTriage)) return false;
  if (!ALLOWED_CLASSES.has(candidate.editorialClass)) return false;
  return true;
}

function sortCandidates(first, second) {
  const firstClass = first.editorialClass || "Z";
  const secondClass = second.editorialClass || "Z";
  if (firstClass !== secondClass) return firstClass.localeCompare(secondClass, "it-IT");
  if (second.score !== first.score) return second.score - first.score;
  const categoryDiff = (CATEGORY_PRIORITY[first.category] || 99) - (CATEGORY_PRIORITY[second.category] || 99);
  if (categoryDiff) return categoryDiff;
  return String(first.sourceDayKey).localeCompare(String(second.sourceDayKey), "it-IT");
}

function pickCandidates(candidates, args) {
  const selected = [];
  const byPlace = new Map();
  const byCategory = new Map();
  const usedDays = new Set();

  for (const candidate of candidates) {
    if (selected.length >= args.limit) break;
    if (usedDays.has(candidate.sourceDayKey)) continue;

    const placeCount = byPlace.get(candidate.place) || 0;
    const categoryCount = byCategory.get(candidate.category) || 0;
    if (placeCount >= args.maxPerPlace) continue;
    if (categoryCount >= args.maxPerCategory) continue;

    selected.push(candidate);
    usedDays.add(candidate.sourceDayKey);
    byPlace.set(candidate.place, placeCount + 1);
    byCategory.set(candidate.category, categoryCount + 1);
  }

  return selected;
}

function toRecord(candidate, index) {
  const extractionClass = classifyCandidate(candidate);
  const decision = decisionFor(candidate, extractionClass);

  return {
    id: `daily-history-expanded-${candidate.dateAnchor}-${String(index + 1).padStart(3, "0")}`,
    sourceCandidateId: candidate.sourceCandidateId,
    wikidataId: candidate.wikidataId,
    sourceDayKey: candidate.sourceDayKey,
    dateAnchor: candidate.dateAnchor,
    title: titleFrom(candidate),
    sourceTitle: candidate.sourceTitle,
    year: candidate.year,
    place: candidate.place,
    type: candidate.type,
    category: candidate.category,
    score: candidate.score,
    editorialClass: candidate.editorialClass,
    extractionClass,
    reviewStatus: decision.reviewStatus,
    editorialStatus: decision.editorialStatus,
    languageStatus: {
      it: "not_started",
      fur: "not_started",
    },
    source: {
      type: "master_triage_candidate",
      label: "Master Accadde oggi FVG esteso",
      path: MASTER_SOURCE_REF,
      wikipediaUrl: candidate.wikipediaUrl || null,
      wikidataId: candidate.wikidataId || null,
      confidence: "candidate_only",
    },
    reviewGuidance: {
      allowedSurface: extractionClass === "light_daily_review"
        ? "possible_daily_memory_after_review"
        : "possible_discover_archive_after_review",
      copyTone: "breve, umano, non enciclopedico",
      doNotPublishAutomatically: true,
      needsHumanSelection: true,
      sourceReminder: "Non cercare fonti infinite per rubriche leggere; richiedere fonte forte solo se il tema e' delicato.",
      preliminaryDecision: decision.reviewStatus,
      preliminaryReason: decision.reason,
    },
    detailPreview: candidate.detailPreview,
    readyForUi: false,
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const source = readJson(args.source);
  const localMemory = readJson(args.localMemory);
  const reviewPack = readJson(args.reviewPack);
  const knownWikidataIds = collectKnownWikidataIds(localMemory, reviewPack);
  const available = candidatesFrom(source)
    .filter((candidate) => isCandidateAllowed(candidate, knownWikidataIds))
    .sort(sortCandidates);
  const selected = pickCandidates(available, args);
  const records = selected.map(toRecord);
  const payload = {
    schemaVersion: 1,
    purpose: "Pacchetto ampio di estrazione Accadde oggi. Non letto dalla UI.",
    sourceInput: {
      triageOutput: toPortablePath(args.source),
      excludedLocalMemory: toPortablePath(args.localMemory),
      excludedReviewPack: toPortablePath(args.reviewPack),
    },
    policy: {
      noAutomaticPublication: true,
      excludesAlreadyKnownWikidataIds: true,
      oneCandidatePerDay: true,
      balancedByPlace: true,
      sourceResearchBudget: "short_for_light_cards_strong_only_for_sensitive_topics",
    },
    summary: {
      knownWikidataIds: knownWikidataIds.size,
      availableAfterExclusion: available.length,
      selectedRecords: records.length,
      byExtractionClass: countBy(records, (record) => record.extractionClass),
      byReviewStatus: countBy(records, (record) => record.reviewStatus),
      byPostReviewEditorialStatus: countBy(records, (record) => record.editorialStatus),
      byEditorialClass: countBy(records, (record) => record.editorialClass),
      byCategory: countBy(records, (record) => record.category),
      byPlace: countBy(records, (record) => record.place),
      byType: countBy(records, (record) => record.type),
      readyForUiRecords: records.filter((record) => record.readyForUi === true).length,
    },
    records,
  };

  const outputPath = path.resolve(args.output);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");

  console.log(`Selected ${records.length} expanded review candidates from ${available.length} available records.`);
  console.log(`Output: ${outputPath}`);
  console.log(JSON.stringify(payload.summary, null, 2));
}

main();
