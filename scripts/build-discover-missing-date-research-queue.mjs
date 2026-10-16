import fs from "node:fs";
import path from "node:path";

const DEFAULT_MASTER = "backend_dryrun_staging/exports/discover_daily_history_master_triage.json";
const DEFAULT_LOCAL_MEMORY = "frontend/src/data/discover/localMemory.json";
const DEFAULT_REVIEW_PACK = "frontend/src/data/discover/dailyHistoryReviewPack.json";
const DEFAULT_EXPANDED_REVIEW = "frontend/src/data/discover/dailyHistoryExpandedReview.json";
const DEFAULT_SECOND_PASS_REVIEW = "frontend/src/data/discover/discoverMissingDateSecondPassReview.json";
const DEFAULT_REVIEW_WAVE_DIR = "frontend/src/data/discover";
const DEFAULT_OUTPUT = "frontend/src/data/discover/discoverMissingDateResearchQueue.json";

const READY_SOURCE_TYPES = new Set(["verified_source", "editorial_note"]);
const ELIGIBLE_TRIAGE = new Set(["review_for_light_daily", "archive_candidate"]);

function parseArgs(argv) {
  const args = {
    master: DEFAULT_MASTER,
    localMemory: DEFAULT_LOCAL_MEMORY,
    reviewPack: DEFAULT_REVIEW_PACK,
    expandedReview: DEFAULT_EXPANDED_REVIEW,
    secondPassReview: DEFAULT_SECOND_PASS_REVIEW,
    reviewWaveDir: DEFAULT_REVIEW_WAVE_DIR,
    output: DEFAULT_OUTPUT,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    const nextValue = argv[index + 1];

    if (argument === "--master") args.master = nextValue;
    else if (argument === "--local-memory") args.localMemory = nextValue;
    else if (argument === "--review-pack") args.reviewPack = nextValue;
    else if (argument === "--expanded-review") args.expandedReview = nextValue;
    else if (argument === "--second-pass-review") args.secondPassReview = nextValue;
    else if (argument === "--review-wave-dir") args.reviewWaveDir = nextValue;
    else if (argument === "--output") args.output = nextValue;
    else continue;

    index += 1;
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

function toItalianDate(dateAnchor) {
  const [month, day] = String(dateAnchor).split("-");
  return `${day}-${month}`;
}

function readyPrimaryDateAnchors(localMemory) {
  return new Set(recordsFrom(localMemory)
    .filter((record) => (
      record?.readyForUi === true
      && record.primaryUse === "discover"
      && record.editorialStatus === "ready_for_discover"
      && READY_SOURCE_TYPES.has(record.source?.type)
      && record.dailyRole !== "secondary"
    ))
    .flatMap((record) => record.dateAnchors || []));
}

function readySecondaryMemoriesByDate(localMemory, missingDateSet, reviewIndex) {
  const result = new Map();

  for (const record of recordsFrom(localMemory).filter((item) => (
    item?.readyForUi === true
    && item.primaryUse === "discover"
    && item.editorialStatus === "ready_for_discover"
    && READY_SOURCE_TYPES.has(item.source?.type)
    && item.dailyRole === "secondary"
  ))) {
    const review = secondPassReviewFor(record, reviewIndex);

    for (const dateAnchor of record.dateAnchors || []) {
      if (!missingDateSet.has(dateAnchor)) continue;
      if (!result.has(dateAnchor)) result.set(dateAnchor, []);
      result.get(dateAnchor).push({
        id: record.id,
        candidateId: record.candidateId || "",
        title: record.title?.it || "",
        sourceLabel: record.source?.label || "",
        secondPassReview: review ? {
          decision: review.decision,
          reason: review.reason,
        } : null,
      });
    }
  }

  return result;
}

function readReviewWaves(directoryPath) {
  const absoluteDirectory = path.resolve(directoryPath);
  if (!fs.existsSync(absoluteDirectory)) return [];

  return fs.readdirSync(absoluteDirectory)
    .filter((name) => /^discoverDailyItalianReviewWave\d*\.json$/.test(name))
    .sort((first, second) => first.localeCompare(second, "it-IT", { numeric: true }))
    .map((name) => ({ name, source: readJson(path.join(absoluteDirectory, name)) }));
}

function identityKeys(record) {
  const ids = [record?.sourceCandidateId, record?.candidateId];
  if (String(record?.id || "").startsWith("master-fvg-")) ids.push(record.id);

  const wikidataIds = [
    record?.wikidataId,
    record?.source?.wikidataId,
    String(record?.id || "").match(/-(Q\d+)$/)?.[1],
  ].filter(Boolean);

  return [
    ...ids.filter(Boolean).map((id) => `candidate:${id}`),
    ...wikidataIds.map((id) => `wikidata:${id}`),
  ];
}

function decisionReason(record) {
  return String(
    record?.reason
      || record?.exclusionReason
      || record?.holdReason
      || record?.reviewGuidance?.preliminaryReason
      || record?.editorialDecision?.reason
      || "",
  ).trim();
}

function decisionStatus(record, lane) {
  return String(
    record?.reviewStatus
      || record?.editorialStatus
      || record?.sourceStatus
      || lane,
  );
}

function addDecision(decisionIndex, record, sourceFile, lane) {
  const keys = identityKeys(record);
  if (!keys.length) return;

  const decision = {
    sourceFile,
    lane,
    status: decisionStatus(record, lane),
    reason: decisionReason(record),
  };

  for (const key of keys) {
    if (!decisionIndex.has(key)) decisionIndex.set(key, []);
    const decisions = decisionIndex.get(key);
    const fingerprint = JSON.stringify(decision);
    if (!decisions.some((item) => JSON.stringify(item) === fingerprint)) decisions.push(decision);
  }
}

function indexReviewSource(decisionIndex, source, sourceFile) {
  const lanes = [
    ["records", recordsFrom(source)],
    ["keep_daily", source?.keepDaily || []],
    ["hold", source?.hold || []],
    ["excluded", source?.excluded || []],
  ];

  for (const [lane, records] of lanes) {
    for (const record of records) addDecision(decisionIndex, record, sourceFile, lane);
  }
}

function decisionsFor(candidate, decisionIndex) {
  const decisions = identityKeys(candidate)
    .flatMap((key) => decisionIndex.get(key) || []);
  const seen = new Set();

  return decisions.filter((decision) => {
    const fingerprint = JSON.stringify(decision);
    if (seen.has(fingerprint)) return false;
    seen.add(fingerprint);
    return true;
  });
}

function indexSecondPassReview(source) {
  const index = new Map();

  for (const record of recordsFrom(source)) {
    for (const key of identityKeys(record)) index.set(key, record);
  }

  return index;
}

function secondPassReviewFor(candidate, reviewIndex) {
  for (const key of identityKeys(candidate)) {
    if (reviewIndex.has(key)) return reviewIndex.get(key);
  }

  return null;
}

function isEligibleCandidate(candidate) {
  return candidate?.wikidataId
    && String(candidate.type || "").toLocaleLowerCase("it-IT") !== "morte"
    && ELIGIBLE_TRIAGE.has(candidate.publicationTriage)
    && ["A", "B", "C"].includes(candidate.editorialClass);
}

function reviewedCandidate(candidate, decisionIndex, secondPassReviewIndex) {
  const secondPassReview = secondPassReviewFor(candidate, secondPassReviewIndex);

  return {
    sourceCandidateId: candidate.sourceCandidateId,
    wikidataId: candidate.wikidataId,
    title: candidate.sourceTitle || candidate.title?.it || "",
    year: candidate.year,
    place: candidate.place,
    category: candidate.category,
    score: candidate.score,
    editorialClass: candidate.editorialClass,
    detailPreview: candidate.detailPreview || "",
    discoveryUrl: candidate.wikipediaUrl || "",
    existingDecisions: decisionsFor(candidate, decisionIndex),
    secondPassReview: secondPassReview ? {
      decision: secondPassReview.decision,
      reason: secondPassReview.reason,
    } : null,
  };
}

function countBy(records, keyFn) {
  return records.reduce((result, record) => {
    const key = keyFn(record);
    result[key] = (result[key] || 0) + 1;
    return result;
  }, {});
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const master = readJson(args.master);
  const localMemory = readJson(args.localMemory);
  const reviewPack = readJson(args.reviewPack);
  const expandedReview = readJson(args.expandedReview);
  const secondPassReview = readJson(args.secondPassReview);
  const reviewWaves = readReviewWaves(args.reviewWaveDir);
  const readyPrimaryDates = readyPrimaryDateAnchors(localMemory);
  const missingDateAnchors = calendarDateAnchors()
    .filter((dateAnchor) => !readyPrimaryDates.has(dateAnchor));
  const missingDateSet = new Set(missingDateAnchors);
  const masterDaysByDate = new Map((master.days || [])
    .map((day) => [day.dateAnchor, day]));
  const decisionIndex = new Map();
  const secondPassReviewIndex = indexSecondPassReview(secondPassReview);
  const secondaryMemoriesByDate = readySecondaryMemoriesByDate(
    localMemory,
    missingDateSet,
    secondPassReviewIndex,
  );

  indexReviewSource(decisionIndex, localMemory, path.basename(args.localMemory));
  indexReviewSource(decisionIndex, reviewPack, path.basename(args.reviewPack));
  indexReviewSource(decisionIndex, expandedReview, path.basename(args.expandedReview));
  for (const wave of reviewWaves) indexReviewSource(decisionIndex, wave.source, wave.name);

  const records = missingDateAnchors.map((dateAnchor) => {
    const sourceDay = masterDaysByDate.get(dateAnchor) || { candidates: [] };
    const rawCandidates = sourceDay.candidates || [];
    const eligibleCandidates = rawCandidates.filter(isEligibleCandidate);
    const reviewedCandidates = eligibleCandidates
      .filter((candidate) => candidate.editorialClass === "B")
      .sort((first, second) => Number(second.score || 0) - Number(first.score || 0))
      .map((candidate) => reviewedCandidate(candidate, decisionIndex, secondPassReviewIndex));
    const targetedSourceCandidates = reviewedCandidates.filter((candidate) => (
      candidate.secondPassReview?.decision === "targeted_source_research"
    ));
    const readySecondaryMemories = secondaryMemoriesByDate.get(dateAnchor) || [];
    const researchLane = targetedSourceCandidates.length
      ? "targeted_source_check"
      : "research_new_source";

    return {
      dateIt: sourceDay.dayKey || toItalianDate(dateAnchor),
      dateAnchor,
      researchLane,
      editorialDecision: "pending",
      readyForUi: false,
      sourceInventory: {
        rawCandidates: rawCandidates.length,
        eligibleCandidates: eligibleCandidates.length,
        reviewedClassBCandidates: reviewedCandidates.length,
        readySecondaryMemories: readySecondaryMemories.length,
      },
      reviewedCandidates,
      readySecondaryMemories,
      researchNotes: "",
    };
  });

  const recordsWithTargetedSourceChecks = records
    .filter((record) => record.researchLane === "targeted_source_check");
  const recordsNeedingNewSources = records
    .filter((record) => record.researchLane === "research_new_source");
  const reviewedCandidates = records.flatMap((record) => record.reviewedCandidates);
  const reviewedSecondaryMemories = records.flatMap((record) => record.readySecondaryMemories);
  const unreviewedCandidates = reviewedCandidates
    .filter((candidate) => candidate.secondPassReview === null);
  const completedPromotions = recordsFrom(secondPassReview).filter((record) => (
    record.decision === "promote_existing_memory_to_primary"
    && !missingDateSet.has(record.dateAnchor)
  ));

  const payload = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString().slice(0, 10),
    purpose: "Coda editoriale dei giorni senza Memoria primaria exact-date in Scopri. Non letta dalla UI.",
    datePolicy: {
      dateIt: "DD-MM, formato mostrato e usato nella revisione italiana",
      dateAnchor: "MM-DD, chiave tecnica interna del calendario applicativo",
    },
    policy: {
      noAutomaticPublication: true,
      exactDateRequired: true,
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      doNotLowerEditorialThresholdToFillCalendar: true,
      requireVerifiedSourceAndApprovedItFurBeforePromotion: true,
      classBCandidatesRequireExplicitSecondPassDecision: true,
    },
    summary: {
      dailyTarget: 366,
      readyPrimaryDays: readyPrimaryDates.size,
      missingPrimaryDays: records.length,
      targetedSourceCheckDays: recordsWithTargetedSourceChecks.length,
      targetedSourceCheckCandidates: recordsWithTargetedSourceChecks
        .reduce((total, record) => total + record.reviewedCandidates.filter((candidate) => (
          candidate.secondPassReview?.decision === "targeted_source_research"
        )).length, 0),
      closedSecondPassCandidates: reviewedCandidates.filter((candidate) => (
        candidate.secondPassReview?.decision !== "targeted_source_research"
      )).length,
      completedPromotions: completedPromotions.length,
      reviewedSecondaryMemories: reviewedSecondaryMemories.length,
      secondaryMemoriesKeptSecondary: reviewedSecondaryMemories.filter((record) => (
        record.secondPassReview?.decision === "keep_secondary"
      )).length,
      researchNewSourceDays: recordsNeedingNewSources.length,
      rawButNoEligibleDays: records.filter((record) => (
        record.sourceInventory.rawCandidates > 0
        && record.sourceInventory.eligibleCandidates === 0
      )).length,
      processedEligibleButNoPrimaryDays: records.filter((record) => (
        record.sourceInventory.eligibleCandidates > 0
      )).length,
      byMonth: countBy(records, (record) => record.dateAnchor.slice(0, 2)),
    },
    records,
  };

  if (records.some((record) => !missingDateSet.has(record.dateAnchor))) {
    throw new Error("La coda contiene una data gia coperta.");
  }

  if (unreviewedCandidates.length > 0) {
    throw new Error(`Mancano decisioni di secondo passaggio per ${unreviewedCandidates.length} candidati di classe B.`);
  }

  if (reviewedSecondaryMemories.some((record) => record.secondPassReview === null)) {
    throw new Error("Mancano decisioni di secondo passaggio per memorie secondarie in giorni scoperti.");
  }

  const outputPath = path.resolve(args.output);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");

  console.log(`Discover missing-date queue written: ${outputPath}`);
  console.log(JSON.stringify(payload.summary, null, 2));
}

main();
