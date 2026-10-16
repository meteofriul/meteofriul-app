import fs from "node:fs";
import path from "node:path";

const DEFAULT_SOURCE = "backend_dryrun_staging/exports/discover_daily_history_master_triage.json";
const DEFAULT_LOCAL_MEMORY = "frontend/src/data/discover/localMemory.json";
const DEFAULT_REVIEW_PACK = "frontend/src/data/discover/dailyHistoryReviewPack.json";
const DEFAULT_EXPANDED_REVIEW = "frontend/src/data/discover/dailyHistoryExpandedReview.json";
const DEFAULT_REVIEW_WAVE_DIR = "frontend/src/data/discover";
const DEFAULT_OUTPUT = "frontend/src/data/discover/dailyHistoryBacklogAudit.json";

const ALLOWED_TRIAGE = new Set(["review_for_light_daily", "archive_candidate"]);
const ALLOWED_CLASSES = new Set(["A", "B", "C"]);
const READY_LOCAL_MEMORY_SOURCE_TYPES = new Set(["verified_source", "editorial_note"]);

const CATEGORY_PRIORITY = {
  arte_cultura: 1,
  luoghi_patrimonio: 2,
  scienza_territorio: 3,
  tradizione_costume: 4,
  memoria_storica: 5,
};

function parseArgs(argv) {
  const args = {
    source: DEFAULT_SOURCE,
    localMemory: DEFAULT_LOCAL_MEMORY,
    reviewPack: DEFAULT_REVIEW_PACK,
    expandedReview: DEFAULT_EXPANDED_REVIEW,
    reviewWaveDir: DEFAULT_REVIEW_WAVE_DIR,
    output: DEFAULT_OUTPUT,
    nextLimit: 120,
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
    } else if (arg === "--expanded-review") {
      args.expandedReview = argv[index + 1];
      index += 1;
    } else if (arg === "--review-wave-dir") {
      args.reviewWaveDir = argv[index + 1];
      index += 1;
    } else if (arg === "--output") {
      args.output = argv[index + 1];
      index += 1;
    } else if (arg === "--next-limit") {
      args.nextLimit = Number.parseInt(argv[index + 1], 10);
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

function calendarDateAnchors() {
  return Array.from({ length: 366 }, (_, index) => {
    const date = new Date(Date.UTC(2024, 0, index + 1));
    const month = String(date.getUTCMonth() + 1).padStart(2, "0");
    const day = String(date.getUTCDate()).padStart(2, "0");
    return `${month}-${day}`;
  });
}

function readyPrimaryDateAnchors(source) {
  return new Set(recordsFrom(source)
    .filter((record) => (
      record?.readyForUi === true
      && record.primaryUse === "discover"
      && record.editorialStatus === "ready_for_discover"
      && READY_LOCAL_MEMORY_SOURCE_TYPES.has(record.source?.type)
      && record.dailyRole !== "secondary"
    ))
    .flatMap((record) => record.dateAnchors || []));
}

function decisionsFrom(source) {
  return [
    ...recordsFrom(source),
    ...(source?.keepDaily || []),
    ...(source?.hold || []),
    ...(source?.excluded || []),
  ];
}

function readItalianReviewWaves(directoryPath) {
  const absoluteDirectory = path.resolve(directoryPath);
  if (!fs.existsSync(absoluteDirectory)) return [];

  return fs.readdirSync(absoluteDirectory)
    .filter((name) => /^discoverDailyItalianReviewWave\d*\.json$/.test(name))
    .sort((first, second) => first.localeCompare(second, "it-IT", { numeric: true }))
    .map((name) => ({
      name,
      source: readJson(path.join(absoluteDirectory, name)),
    }));
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
  return new Set(sources.flatMap((source) => decisionsFrom(source)).flatMap((record) => {
    const idMatch = String(record.id || record.sourceCandidateId || "").match(/-(Q\d+)$/);
    return [
      record.wikidataId,
      record.source?.wikidataId,
      idMatch?.[1],
    ];
  }).filter(Boolean));
}

function collectKnownSourceCandidateIds(...sources) {
  return new Set(sources.flatMap((source) => decisionsFrom(source)).flatMap((record) => [
    record.sourceCandidateId,
    record.candidateId,
    String(record.id || "").startsWith("master-fvg-") ? record.id : null,
  ]).filter(Boolean));
}

function isKnownCandidate(candidate, knownWikidataIds, knownSourceCandidateIds) {
  return knownWikidataIds.has(candidate.wikidataId)
    || knownSourceCandidateIds.has(candidate.sourceCandidateId);
}

function countBy(records, keyFn) {
  return records.reduce((acc, record) => {
    const key = keyFn(record) || "missing";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function textValue(value) {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") return value.it || value.fur || Object.values(value).find(Boolean) || "";
  return "";
}

function titleFrom(candidate) {
  return textValue(candidate.title || candidate.sourceTitle || candidate.label || candidate.name).trim();
}

function normalizedText(candidate) {
  return [
    titleFrom(candidate),
    candidate.sourceTitle,
    candidate.detailPreview,
    candidate.place,
    candidate.category,
  ].filter(Boolean).join(" ").toLowerCase();
}

function suggestedLaneFor(candidate) {
  const text = normalizedText(candidate);
  const sensitivePatterns = [
    "militare",
    "guerra",
    "partigian",
    "nazist",
    "fascist",
    "resistenza",
    "esercito",
    "aviatore",
    "generale",
    "ufficiale",
    "battaglia",
    "cimitero militare",
    "medaglia d'oro",
    "terrorista",
    "territorio libero",
  ];
  const lowPriorityPatterns = [
    "calciatore",
    "cestista",
    "baseball",
    "ciclista",
    "velocista",
    "allenatore",
    "partito politico",
    "politico",
  ];

  if (sensitivePatterns.some((pattern) => text.includes(pattern))) {
    return ["hold_strong_source", "sensitive_history_or_military_keyword"];
  }
  if (lowPriorityPatterns.some((pattern) => text.includes(pattern))) {
    return ["archive_low_priority", "sport_or_political_profile"];
  }
  if (candidate.publicationTriage === "archive_candidate") {
    return ["archive_review", "source_triaged_as_archive"];
  }
  return ["light_review", "candidate_can_start_copy_review"];
}

function isEligible(candidate) {
  if (!candidate.wikidataId) return false;
  if (String(candidate.type || "").trim().toLocaleLowerCase("it-IT") === "morte") return false;
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

function candidateDigest(candidate, knownWikidataIds, knownSourceCandidateIds) {
  const [suggestedReviewLane, suggestedLaneReason] = suggestedLaneFor(candidate);

  return {
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
    publicationTriage: candidate.publicationTriage,
    alreadyQueuedOrKnown: isKnownCandidate(candidate, knownWikidataIds, knownSourceCandidateIds),
    suggestedReviewLane,
    suggestedLaneReason,
  };
}

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b), "it-IT"));
}

function pickOnePerDay(candidates, limit) {
  const selected = [];
  const usedDays = new Set();

  for (const candidate of [...candidates].sort(sortCandidates)) {
    if (selected.length >= limit) break;
    if (usedDays.has(candidate.sourceDayKey)) continue;
    selected.push(candidate);
    usedDays.add(candidate.sourceDayKey);
  }

  return selected;
}

function daySummary(day, knownWikidataIds, knownSourceCandidateIds) {
  const candidates = (day.candidates || []).map((candidate) => ({
    ...candidate,
    sourceDayKey: candidate.sourceDayKey || day.dayKey,
    dateAnchor: candidate.dateAnchor || day.dateAnchor,
  }));
  const eligible = candidates.filter(isEligible);
  const unqueued = eligible.filter((candidate) => (
    !isKnownCandidate(candidate, knownWikidataIds, knownSourceCandidateIds)
  ));

  return {
    dayKey: day.dayKey,
    dateAnchor: day.dateAnchor,
    totalCandidates: candidates.length,
    eligibleCandidates: eligible.length,
    unqueuedEligibleCandidates: unqueued.length,
    categories: countBy(eligible, (candidate) => candidate.category),
    editorialClasses: countBy(eligible, (candidate) => candidate.editorialClass),
    places: uniqueSorted(eligible.map((candidate) => candidate.place)).slice(0, 8),
    topUnqueued: unqueued.sort(sortCandidates).slice(0, 5).map((candidate) => (
      candidateDigest(candidate, knownWikidataIds, knownSourceCandidateIds)
    )),
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const source = readJson(args.source);
  const localMemory = readJson(args.localMemory);
  const reviewPack = readJson(args.reviewPack);
  const expandedReview = readJson(args.expandedReview);
  const reviewWaves = readItalianReviewWaves(args.reviewWaveDir);
  const reviewedSources = reviewWaves.map((wave) => wave.source);
  const knownWikidataIds = collectKnownWikidataIds(
    localMemory,
    reviewPack,
    expandedReview,
    ...reviewedSources,
  );
  const knownSourceCandidateIds = collectKnownSourceCandidateIds(
    localMemory,
    reviewPack,
    expandedReview,
    ...reviewedSources,
  );
  const days = source.days || [];
  const candidates = candidatesFrom(source);
  const eligible = candidates.filter(isEligible);
  const unqueuedEligible = eligible.filter((candidate) => (
    !isKnownCandidate(candidate, knownWikidataIds, knownSourceCandidateIds)
  ));
  const dayAudits = days.map((day) => daySummary(
    day,
    knownWikidataIds,
    knownSourceCandidateIds,
  ));
  const emptyDays = dayAudits
    .filter((day) => day.eligibleCandidates === 0)
    .map((day) => day.dateAnchor || day.dayKey);
  const emptyUnqueuedDays = dayAudits
    .filter((day) => day.unqueuedEligibleCandidates === 0)
    .map((day) => day.dateAnchor || day.dayKey);
  const nextReviewCandidates = [...unqueuedEligible]
    .sort(sortCandidates)
    .slice(0, args.nextLimit)
    .map((candidate) => candidateDigest(candidate, knownWikidataIds, knownSourceCandidateIds));
  const nextLightReviewCandidates = [...unqueuedEligible]
    .filter((candidate) => suggestedLaneFor(candidate)[0] === "light_review");
  const nextLightReviewOnePerDay = pickOnePerDay(nextLightReviewCandidates, args.nextLimit)
    .map((candidate) => candidateDigest(candidate, knownWikidataIds, knownSourceCandidateIds));
  const eligibleDigests = eligible.map((candidate) => (
    candidateDigest(candidate, knownWikidataIds, knownSourceCandidateIds)
  ));
  const readyPrimaryAnchors = readyPrimaryDateAnchors(localMemory);
  const missingPrimaryDateAnchors = calendarDateAnchors()
    .filter((dateAnchor) => !readyPrimaryAnchors.has(dateAnchor));
  const missingPrimaryDateAnchorSet = new Set(missingPrimaryDateAnchors);
  const primaryGapDayAudits = dayAudits
    .filter((day) => missingPrimaryDateAnchorSet.has(day.dateAnchor || day.dayKey));
  const nextPrimaryGapCandidates = primaryGapDayAudits
    .filter((day) => day.unqueuedEligibleCandidates > 0 && day.topUnqueued.length > 0)
    .map((day) => day.topUnqueued[0]);

  const payload = {
    schemaVersion: 1,
    purpose: "Audit backlog Accadde oggi FVG. Non letto dalla UI.",
    sourceInput: {
      triageOutput: path.resolve(args.source),
      excludedLocalMemory: path.resolve(args.localMemory),
      excludedReviewPack: path.resolve(args.reviewPack),
      excludedExpandedReview: path.resolve(args.expandedReview),
      excludedItalianReviewWaves: reviewWaves.map((wave) => wave.name),
    },
    policy: {
      noAutomaticPublication: true,
      tracksCalendarCoverage: true,
      keepsQueuedAndUnqueuedSeparate: true,
      nextReviewCandidatesAreSuggestionsOnly: true,
      primaryGapCandidatesAreSuggestionsOnly: true,
      excludesDeaths: true,
    },
    summary: {
      sourceDays: days.length,
      sourceCandidates: candidates.length,
      eligibleCandidates: eligible.length,
      knownOrQueuedWikidataIds: knownWikidataIds.size,
      knownOrQueuedSourceCandidateIds: knownSourceCandidateIds.size,
      unqueuedEligibleCandidates: unqueuedEligible.length,
      coveredDays: dayAudits.filter((day) => day.eligibleCandidates > 0).length,
      emptyDays,
      coveredUnqueuedDays: dayAudits.filter((day) => day.unqueuedEligibleCandidates > 0).length,
      emptyUnqueuedDays,
      byPublicationTriage: countBy(candidates, (candidate) => candidate.publicationTriage),
      byEligibleEditorialClass: countBy(eligible, (candidate) => candidate.editorialClass),
      byEligibleCategory: countBy(eligible, (candidate) => candidate.category),
      byEligibleType: countBy(eligible, (candidate) => candidate.type),
      bySuggestedReviewLane: countBy(eligibleDigests, (candidate) => candidate.suggestedReviewLane),
      nextReviewCandidates: nextReviewCandidates.length,
      nextLightReviewCandidates: nextLightReviewOnePerDay.length,
      nextLightReviewOnePerDay: true,
      readyPrimaryDays: readyPrimaryAnchors.size,
      missingPrimaryDays: missingPrimaryDateAnchors.length,
      missingPrimaryDaysWithUnqueuedCandidates: primaryGapDayAudits
        .filter((day) => day.unqueuedEligibleCandidates > 0).length,
      missingPrimaryDaysWithoutUnqueuedCandidates: primaryGapDayAudits
        .filter((day) => day.unqueuedEligibleCandidates === 0).length,
      nextPrimaryGapCandidates: nextPrimaryGapCandidates.length,
    },
    nextReviewCandidates,
    nextLightReviewCandidates: nextLightReviewOnePerDay,
    missingPrimaryDateAnchors,
    nextPrimaryGapCandidates,
    days: dayAudits,
  };

  const outputPath = path.resolve(args.output);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");

  console.log(`Backlog audit written: ${outputPath}`);
  console.log(JSON.stringify(payload.summary, null, 2));
}

main();
