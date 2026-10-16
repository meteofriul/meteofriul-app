import backlog from "../../data/discover/ostermannDiscoverBacklog.json";
import localMemory from "../../data/discover/localMemory.json";
import traditionalSayings from "../../data/discover/traditionalSayings.json";
import culturalDiscover from "../../data/ostermannCulturalDiscover.json";
import curatedLinks from "../../data/ostermann/curatedLinks.json";
import almanacProverbs from "../../data/almanac/proverbs.json";
import { isCuratedDiscoverPublished } from "./discoverCulturalReadiness";

const MEMORY_TYPES = new Set(["santi_e_territorio"]);
const TRADITIONAL_SAYING_TYPES = new Set([
  "calendario_agricolo",
  "credenze_popolari",
  "meteo_popolare",
]);
const ARCHIVE_TYPES = new Set([
  "calendario_popolare",
  "lessico_popolare",
  "meteo_estremo_popolare",
  "proverbi_meteo",
  "vita_popolare",
]);
const ALMANAC_PROVERB_TYPES = new Set([
  "calendario_agricolo",
  "calendario_popolare",
  "proverbi_meteo",
]);

function getRecords(source = backlog) {
  if (Array.isArray(source)) return source;
  return Array.isArray(source?.records) ? source.records : [];
}

function isPublishedDiscoverRecord(record) {
  if (record?.readyForUi === true && record?.editorialStatus === "ready_for_discover") return true;
  return Boolean(record?.candidateId) && isCuratedDiscoverPublished(record);
}

function getPublishedCandidateIds(sources = [traditionalSayings, localMemory]) {
  const sourceList = Array.isArray(sources) ? sources : [sources];
  return new Set(sourceList.flatMap((source) => (
    getRecords(source)
      .filter(isPublishedDiscoverRecord)
      .map((record) => record.candidateId)
      .filter(Boolean)
  )));
}

function getCuratedCoverageBySourcePage(source = curatedLinks) {
  return getRecords(source).reduce((byPage, record) => {
    const sourcePage = record?.sourcePage;
    if (!sourcePage) return byPage;

    const coveredIds = Array.isArray(record.curatedRecordIds)
      ? record.curatedRecordIds.filter(Boolean)
      : [];
    if (!coveredIds.length) return byPage;

    const currentIds = byPage.get(sourcePage) || [];
    byPage.set(sourcePage, [...new Set([...currentIds, ...coveredIds])]);
    return byPage;
  }, new Map());
}

function getAlmanacProverbCoverageBySourcePage(source = almanacProverbs) {
  return getRecords(source).reduce((byPage, record) => {
    const sourcePage = record?.sourceDetail?.pdfPage;
    if (!sourcePage || !record?.id) return byPage;

    const currentIds = byPage.get(sourcePage) || [];
    byPage.set(sourcePage, [...new Set([...currentIds, record.id])]);
    return byPage;
  }, new Map());
}

function hasExactDate(record) {
  return Array.isArray(record?.dateAnchors) && record.dateAnchors.length > 0;
}

function isShortExtract(record) {
  return Array.isArray(record?.sourceLines) && record.sourceLines.length <= 2;
}

function hasSecondaryUse(record, use) {
  return Array.isArray(record?.secondaryUse) && record.secondaryUse.includes(use);
}

function getRoute(record) {
  if (MEMORY_TYPES.has(record?.type) && hasExactDate(record)) {
    return {
      target: "local_memory_candidate",
      reason: "Tema territoriale con data esplicita: adatto a Memoria del giorno dopo fonte/copy FUR.",
    };
  }

  if (TRADITIONAL_SAYING_TYPES.has(record?.type) && isShortExtract(record)) {
    return {
      target: "traditional_saying_candidate",
      reason: "Estratto breve e isolabile: candidato per Si diceva che..., non per Almanacco automatico.",
    };
  }

  if (
    hasSecondaryUse(record, "almanac_proverbs") &&
    ALMANAC_PROVERB_TYPES.has(record?.type)
  ) {
    return {
      target: "almanac_proverb_source_candidate",
      reason: "Pagina serbatoio di proverbi: da spezzare e revisionare per Almanacco/Si diceva che, non da pubblicare come scheda Scopri unica.",
    };
  }

  if (ARCHIVE_TYPES.has(record?.type) || record?.type) {
    return {
      target: "discover_archive_candidate",
      reason: "Tema ampio o multi-detto: meglio come scheda spiegata in archivio Scopri.",
    };
  }

  return {
    target: "needs_editorial_triage",
    reason: "Tipo mancante o non riconosciuto: richiede triage manuale.",
  };
}

function summarizeRoutes(routedRecords) {
  return routedRecords.reduce((summary, record) => {
    const target = record.route.target;
    return {
      ...summary,
      [target]: (summary[target] || 0) + 1,
    };
  }, {});
}

export function getOstermannDiscoverRouting(source = backlog, publishedSources = [traditionalSayings, localMemory, culturalDiscover]) {
  const publishedCandidateIds = getPublishedCandidateIds(publishedSources);
  const curatedCoverageBySourcePage = getCuratedCoverageBySourcePage();
  const almanacProverbCoverageBySourcePage = getAlmanacProverbCoverageBySourcePage();

  return getRecords(source)
    .map((record) => {
      const curatedRecordIds = curatedCoverageBySourcePage.get(record.sourcePage) || [];
      const almanacProverbIds = almanacProverbCoverageBySourcePage.get(record.sourcePage) || [];
      const isPublished = publishedCandidateIds.has(record.id);
      const route = getRoute(record);
      const isCoveredByAlmanacProverbs = (
        route.target === "almanac_proverb_source_candidate" &&
        almanacProverbIds.length > 0
      );

      return {
        id: record.id,
        title: record.title?.it || "",
        sourcePage: record.sourcePage,
        type: record.type,
        dateAnchors: record.dateAnchors || [],
        sourceLineCount: Array.isArray(record.sourceLines) ? record.sourceLines.length : 0,
        priority: record.priority || 99,
        curatedRecordIds,
        almanacProverbIds,
        publicationStatus: isPublished
          ? "published_in_scopri"
          : curatedRecordIds.length
            ? "covered_by_curated_archive"
            : isCoveredByAlmanacProverbs
              ? "covered_by_almanac_proverbs"
              : "pending_copy",
        route,
      };
    })
    .sort((first, second) => {
      const priorityDiff = Number(first.priority || 99) - Number(second.priority || 99);
      if (priorityDiff) return priorityDiff;
      return String(first.id).localeCompare(String(second.id));
    });
}

export function getOstermannDiscoverRoutingSummary(source = backlog, publishedSources = [traditionalSayings, localMemory, culturalDiscover]) {
  const routedRecords = getOstermannDiscoverRouting(source, publishedSources);
  const counts = summarizeRoutes(routedRecords);
  const pendingRecords = routedRecords.filter((record) => record.publicationStatus === "pending_copy");

  return {
    totalRecords: routedRecords.length,
    publishedInScopriRecords: routedRecords.filter((record) => (
      record.publicationStatus === "published_in_scopri"
    )).length,
    coveredByCuratedArchiveRecords: routedRecords.filter((record) => (
      record.publicationStatus === "covered_by_curated_archive"
    )).length,
    coveredByAlmanacProverbRecords: routedRecords.filter((record) => (
      record.publicationStatus === "covered_by_almanac_proverbs"
    )).length,
    pendingCopyRecords: pendingRecords.length,
    counts,
    pendingCounts: summarizeRoutes(pendingRecords),
    routedRecords,
    unclassifiedRecords: routedRecords.filter((record) => (
      record.route.target === "needs_editorial_triage"
    )),
  };
}
