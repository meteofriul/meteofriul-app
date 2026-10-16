import curatedLinksArchive from "../../data/ostermann/curatedLinks.json";
import extractsArchive from "../../data/ostermann/extracts.json";
import curatedCulturalArchive from "../../data/ostermannCulturalDiscover.json";
import sourceCatalog from "../../data/ostermann/sourceCatalog.json";

function getRecords(archive) {
  if (Array.isArray(archive)) return archive;
  return Array.isArray(archive?.records) ? archive.records : [];
}

function getDuplicateValues(values) {
  const seen = new Set();
  const duplicates = new Set();

  values.filter(Boolean).forEach((value) => {
    if (seen.has(value)) {
      duplicates.add(value);
      return;
    }

    seen.add(value);
  });

  return Array.from(duplicates);
}

function hasSecondaryUse(record, matcher) {
  return (record.secondaryUse || []).some((use) => matcher(String(use)));
}

function hasExactDateAnchor(record) {
  return (record.dateAnchors || []).some((dateAnchor) => /^\d{2}-\d{2}$/.test(dateAnchor));
}

function hasAnyDateAnchor(record) {
  return Array.isArray(record.dateAnchors) && record.dateAnchors.length > 0;
}

function getDiscoverQueueBucket(record, curatedLinkExtractIds = new Set()) {
  if (record.editorialStatus === "do_not_publish") {
    return "editorially_closed";
  }

  if (
    record.curatedRecordId ||
    curatedLinkExtractIds.has(record.id) ||
    record.editorialStatus === "curated_recovered"
  ) {
    return "already_curated_link";
  }

  if (
    hasExactDateAnchor(record) &&
    hasSecondaryUse(record, (use) => use.includes("almanac_calendar") || use.includes("proverb_candidates"))
  ) {
    return "daily_or_saying_candidate";
  }

  if (record.editorialStatus === "archive_context" || hasSecondaryUse(record, (use) => use.includes("archive"))) {
    return "archive_story_candidate";
  }

  if (
    hasAnyDateAnchor(record) ||
    hasSecondaryUse(record, (use) => use.includes("calendar") || use.includes("season"))
  ) {
    return "seasonal_context_candidate";
  }

  return "discover_topic_candidate";
}

function toDiscoverQueueItem(record, curatedLinkMap = new Map()) {
  const curatedLink = curatedLinkMap.get(record.id);

  return {
    id: record.id,
    sourcePage: record.sourcePage,
    title: record.title?.itDraft || record.title?.it || "",
    dateAnchors: record.dateAnchors || [],
    editorialStatus: record.editorialStatus,
    uiReadiness: record.uiReadiness,
    curatedRecordId: record.curatedRecordId || null,
    curatedRecordIds: curatedLink?.curatedRecordIds || (record.curatedRecordId ? [record.curatedRecordId] : []),
    furState: record.title?.fur || record.translation?.furDraft || "missing",
    nextAction: record.review?.notes || "",
  };
}

export function getOstermannSourceCatalogRecords(catalog = sourceCatalog) {
  return getRecords(catalog);
}

export function getOstermannExtractRecords(archive = extractsArchive) {
  return getRecords(archive);
}

export function getOstermannCuratedRecords(archive = curatedCulturalArchive) {
  return getRecords(archive);
}

export function getOstermannCuratedLinkRecords(archive = curatedLinksArchive) {
  return getRecords(archive);
}

export function getOstermannArchiveSummary({
  catalog = sourceCatalog,
  extracts = extractsArchive,
  curated = curatedCulturalArchive,
  curatedLinks = curatedLinksArchive,
} = {}) {
  const catalogRecords = getRecords(catalog);
  const extractRecords = getRecords(extracts);
  const curatedRecords = getRecords(curated);
  const curatedLinkRecords = getRecords(curatedLinks);
  const catalogPages = new Set(catalogRecords.map((record) => record.pdfPage).filter(Boolean));
  const extractedPages = new Set(extractRecords.map((record) => record.sourcePage).filter(Boolean));
  const curatedPages = new Set(curatedRecords.map((record) => record.source?.pdfPage).filter(Boolean));
  const recoveredLinkedCatalogRecords = catalogRecords.filter((record) => (
    Array.isArray(record.recoveredRecordIds) && record.recoveredRecordIds.length > 0
  ));
  const curatedRecoveredExtracts = extractRecords.filter((record) => Boolean(record.curatedRecordId));
  const curatedCoverageExtractIds = new Set([
    ...curatedRecoveredExtracts.map((record) => record.id),
    ...curatedLinkRecords.map((record) => record.extractId).filter(Boolean),
  ]);
  const editoriallyClosedExtracts = extractRecords.filter((record) => (
    record.editorialStatus === "do_not_publish"
  ));

  return {
    catalogSourcePages: catalogPages.size,
    highPriorityPages: catalogRecords.filter((record) => String(record.priority).startsWith("P1")).length,
    curatedRecoveredRecords: curatedRecords.length,
    curatedRecoveredPages: curatedPages.size,
    curatedFurApprovedRecords: curatedRecords.filter((record) => record.languageStatus?.fur === "approved").length,
    curatedFurShortReadyRecords: curatedRecords.filter((record) => record.languageStatus?.fur === "short_ready").length,
    curatedReadyItRecords: curatedRecords.filter((record) => record.editorialStatus === "ready_it").length,
    recoveredLinkedCatalogRecords: recoveredLinkedCatalogRecords.length,
    curatedPagesMissingFromCatalog: Array.from(curatedPages).filter((page) => !catalogPages.has(page)).length,
    curatedPagesMissingFromGranular: Array.from(curatedPages).filter((page) => !extractedPages.has(page)).length,
    curatedRecoveredExtracts: curatedRecoveredExtracts.length,
    curatedRecoveredExtractsWithFurReviewRequired: curatedRecoveredExtracts.filter((record) => (
      record.review?.furReviewRequired === true
    )).length,
    curatedLinkRecords: curatedLinkRecords.length,
    curatedLinkedExtracts: new Set(curatedLinkRecords.map((record) => record.extractId).filter(Boolean)).size,
    curatedLinkedRecordRefs: curatedLinkRecords.reduce((total, record) => (
      total + (Array.isArray(record.curatedRecordIds) ? record.curatedRecordIds.length : 0)
    ), 0),
    editoriallyClosedExtracts: editoriallyClosedExtracts.length,
    unresolvedEditorialExtracts: extractRecords.filter((record) => (
      !curatedCoverageExtractIds.has(record.id) && record.editorialStatus !== "do_not_publish"
    )).length,
    granularExtracts: extractRecords.length,
    extractedSourcePages: extractedPages.size,
    discoverPrimaryExtracts: extractRecords.filter((record) => record.primaryUse === "discover").length,
    almanacBridgeExtracts: extractRecords.filter((record) => (
      Array.isArray(record.secondaryUse) &&
      record.secondaryUse.some((use) => use.startsWith("almanac"))
    )).length,
    archiveContextExtracts: extractRecords.filter((record) => record.editorialStatus === "archive_context").length,
    cleanPageCheckedExtracts: extractRecords.filter((record) => (
      String(record.review?.sourceCheck || "").startsWith("clean_page_checked")
    )).length,
    inconclusiveSourceChecks: extractRecords.filter((record) => (
      record.review?.sourceCheck === "clean_page_checked_inconclusive" ||
      record.source?.auditStatus === "clean_page_inconclusive"
    )).length,
    remainingNeedsSourceCheck: extractRecords.filter((record) => record.editorialStatus === "needs_source_check").length,
    pendingFurReviewExtracts: extractRecords.filter((record) => (
      record.title?.fur === "pending_review" ||
      record.translation?.furDraft === "pending_review" ||
      record.review?.furReviewRequired === true
    )).length,
    itDraftTranslations: extractRecords.filter((record) => (
      record.translation?.status === "it_draft" &&
      Boolean(record.translation?.itDraft)
    )).length,
    readyForUiExtracts: extractRecords.filter((record) => record.uiReadiness === "ready_for_ui").length,
  };
}

export function getOstermannDiscoverQueue({
  extracts = extractsArchive,
  curatedLinks = curatedLinksArchive,
} = {}) {
  const extractRecords = getRecords(extracts);
  const curatedLinkMap = new Map(
    getRecords(curatedLinks).map((record) => [record.extractId, record]),
  );
  const curatedLinkExtractIds = new Set(curatedLinkMap.keys());
  const buckets = {
    already_curated_link: [],
    editorially_closed: [],
    daily_or_saying_candidate: [],
    seasonal_context_candidate: [],
    discover_topic_candidate: [],
    archive_story_candidate: [],
  };

  extractRecords.forEach((record) => {
    const bucket = getDiscoverQueueBucket(record, curatedLinkExtractIds);
    buckets[bucket].push(toDiscoverQueueItem(record, curatedLinkMap));
  });

  return {
    total: extractRecords.length,
    counts: Object.fromEntries(
      Object.entries(buckets).map(([bucket, records]) => [bucket, records.length]),
    ),
    buckets,
  };
}

export function getOstermannArchiveIssues({
  catalog = sourceCatalog,
  extracts = extractsArchive,
  curated = curatedCulturalArchive,
  curatedLinks = curatedLinksArchive,
} = {}) {
  const catalogRecords = getRecords(catalog);
  const extractRecords = getRecords(extracts);
  const curatedRecords = getRecords(curated);
  const curatedLinkRecords = getRecords(curatedLinks);
  const catalogPages = new Set(catalogRecords.map((record) => record.pdfPage).filter(Boolean));
  const curatedPages = new Set(curatedRecords.map((record) => record.source?.pdfPage).filter(Boolean));
  const extractIds = new Set(extractRecords.map((record) => record.id).filter(Boolean));
  const curatedIds = new Set(curatedRecords.map((record) => record.id).filter(Boolean));

  return {
    duplicateCatalogPages: getDuplicateValues(catalogRecords.map((record) => record.pdfPage)),
    duplicateExtractIds: getDuplicateValues(extractRecords.map((record) => record.id)),
    duplicateCuratedLinkExtractIds: getDuplicateValues(curatedLinkRecords.map((record) => record.extractId)),
    unknownSourcePageReferences: extractRecords
      .filter((record) => !catalogPages.has(record.sourcePage))
      .map((record) => ({ id: record.id, sourcePage: record.sourcePage })),
    missingSourcePath: extractRecords
      .filter((record) => !record.source?.sourcePath || !record.source?.verifiedAgainst)
      .map((record) => record.id),
    missingItDraft: extractRecords
      .filter((record) => !record.translation?.itDraft)
      .map((record) => record.id),
    unresolvedSourceChecks: extractRecords
      .filter((record) => (
        record.editorialStatus === "needs_source_check" &&
        record.source?.auditStatus !== "clean_page_inconclusive"
      ))
      .map((record) => record.id),
    recoveredPagesMissingFromCatalog: Array.from(curatedPages)
      .filter((page) => !catalogPages.has(page))
      .sort((first, second) => first - second),
    catalogExtractIdsMissing: catalogRecords.flatMap((record) => (
      (record.extractIds || [])
        .filter((extractId) => !extractIds.has(extractId))
        .map((extractId) => ({ pdfPage: record.pdfPage, extractId }))
    )),
    recoveredExtractsMissingCuratedRecord: extractRecords
      .filter((record) => record.curatedRecordId && !curatedIds.has(record.curatedRecordId))
      .map((record) => ({ id: record.id, curatedRecordId: record.curatedRecordId })),
    curatedLinksMissingExtract: curatedLinkRecords
      .filter((record) => !extractIds.has(record.extractId))
      .map((record) => record.extractId),
    curatedLinksMissingCuratedRecord: curatedLinkRecords.flatMap((record) => (
      (record.curatedRecordIds || [])
        .filter((curatedRecordId) => !curatedIds.has(curatedRecordId))
        .map((curatedRecordId) => ({ extractId: record.extractId, curatedRecordId }))
    )),
    readyWithoutFurReview: extractRecords
      .filter((record) => (
        record.uiReadiness === "ready_for_ui" &&
        record.review?.furReviewRequired !== false
      ))
      .map((record) => record.id),
  };
}
