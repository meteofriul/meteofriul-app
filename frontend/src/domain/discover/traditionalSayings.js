import archive from "../../data/discover/traditionalSayings.json";
import almanacReuse from "../../data/discover/traditionalSayingAlmanacReuse.json";
import almanacProverbs from "../../data/almanac/proverbs.json";
import {
  getDiscoverDateKey,
  getDiscoverTemporalRank,
  pickDiscoverTemporalRecord,
} from "./discoverTemporalSelection";

function getLanguageKey(language) {
  return language === "fur" ? "fur" : "it";
}

function localizedValue(value, language) {
  if (!value || typeof value !== "object") return "";
  return value[language] || value.it || value.fur || "";
}

function normalizeDateRanges(ranges) {
  if (!Array.isArray(ranges)) return [];
  return ranges
    .map((range) => {
      if (typeof range === "string") return range;
      if (range?.from && range?.to) return `${range.from}..${range.to}`;
      return "";
    })
    .filter(Boolean);
}

function inferReusedRecurrence({
  descriptor,
  dateAnchors,
  dateRanges,
  months,
  seasons,
  movableDates,
}) {
  if (descriptor.recurrence) return descriptor.recurrence;
  if (movableDates.length) return "movable_date";
  if (dateRanges.length) return "date_range";
  if (dateAnchors.length) return "fixed_date";
  if (months.length || seasons.length) return "seasonal";
  return "always";
}

function getReusedSourceReference(proverb) {
  const citation = String(proverb.source || "");
  const primaryCitation = citation.split(";")[0];
  const edition = primaryCitation.match(/^(?:Facsimile\s+)?Ostermann\s+(\d{4})\b/i)?.[1];
  const validPage = (value) => Number.isInteger(value) && value > 0;
  const explicitPdfPage = Number(primaryCitation.match(/\bPDF\s+(\d+)\b/i)?.[1]);
  const pdfPage = validPage(proverb.sourceDetail?.pdfPage)
    ? proverb.sourceDetail.pdfPage : explicitPdfPage;
  const textPage = proverb.sourceDetail?.textPage;
  return {
    label: edition ? `Ostermann ${edition}` : (primaryCitation.trim() || "Ostermann"),
    ...(validPage(pdfPage) ? { pdfPage } : {}),
    ...(validPage(textPage) ? { textPage } : {}),
  };
}

function buildReusedAlmanacRecord(descriptor) {
  const proverb = almanacProverbs.find((record) => record.id === descriptor.proverbId);
  const languagesApproved = proverb?.editorialReview?.it === "approved"
    && proverb?.editorialReview?.fur === "approved";
  if (!proverb || !languagesApproved) return null;

  const dateAnchors = descriptor.dateAnchors || proverb.dateAnchors || [];
  const dateRanges = normalizeDateRanges(
    descriptor.dateRanges || proverb.dateRanges || [],
  );
  const months = descriptor.months || [];
  const seasons = descriptor.seasons || [];
  const movableDates = descriptor.movableDates || [];
  const recurrence = inferReusedRecurrence({
    descriptor,
    dateAnchors,
    dateRanges,
    months,
    seasons,
    movableDates,
  });

  return {
    id: `saying-almanac-${proverb.id}`,
    primaryUse: "discover",
    recommendedSurface: "discover",
    rubric: "si_diceva_che",
    candidateId: proverb.id,
    category: descriptor.category || "detto_popolare",
    dateAnchors,
    dateRanges,
    months,
    seasons,
    movableDates,
    recurrence,
    priority: descriptor.priority,
    title: { it: proverb.it, fur: proverb.fur },
    summary: { it: "", fur: "" },
    dateLabel: descriptor.dateLabel || { it: "", fur: "" },
    original: { it: proverb.it, fur: proverb.fur_original || proverb.fur },
    source: {
      ...getReusedSourceReference(proverb),
      type: "verified_source",
      sourcePath: "frontend/src/data/almanac/proverbs.json",
      verifiedAgainst: proverb.source,
      note: "Testo IT/FUR gia approvato per l'Almanacco e riutilizzato in Scopri come detto popolare.",
    },
    editorialStatus: "ready_for_discover",
    languageStatus: { it: "approved", fur: "approved" },
    editorialReview: {
      reviewedAt: proverb.editorialReview.reviewedAt,
      note: "Riuso editoriale controllato: la fonte testuale resta unica.",
    },
    reusedFromAlmanac: true,
    readyForUi: true,
  };
}

function getRecords(source = archive) {
  const sourceRecords = Array.isArray(source?.records) ? source.records : [];
  if (source !== archive) return sourceRecords;

  return [
    ...sourceRecords,
    ...almanacReuse.records.map(buildReusedAlmanacRecord).filter(Boolean),
  ];
}

function isUiReady(record) {
  if (!record || record.readyForUi !== true) return false;
  if (record.primaryUse !== "discover") return false;
  if (record.editorialStatus !== "ready_for_discover") return false;
  return record.source?.type === "verified_source";
}

function isFurReady(record) {
  return record?.languageStatus?.fur === "approved";
}

function compareRecords(first, second) {
  const priorityDiff = Number(first.priority || 99) - Number(second.priority || 99);
  if (priorityDiff) return priorityDiff;
  return String(first.id).localeCompare(String(second.id));
}

function getCategoryLabel(record, source, language) {
  const category = record?.category || "detto_meteo";
  return localizedValue(source?.categories?.[category], language) || category;
}

function buildTraditionalSayingCard(record, source, language, selectionKind) {
  const languageKey = getLanguageKey(language);
  const canUseRequestedLanguage = languageKey !== "fur" || isFurReady(record);
  const contentLanguage = canUseRequestedLanguage ? languageKey : "it";

  return {
    id: record.id,
    contentKey: record.candidateId || record.id,
    title: localizedValue(record.title, contentLanguage),
    text: localizedValue(record.summary, contentLanguage),
    type: record.category,
    typeLabel: getCategoryLabel(record, source, languageKey),
    seasonLabel: localizedValue(record.dateLabel, contentLanguage),
    selectionKind,
    sourceLabel: record.source?.label || "Ostermann 1894",
    sourceNote: record.source?.note || "",
    isFurPending: languageKey === "fur" && !canUseRequestedLanguage,
  };
}

export function getTraditionalSayingsSummary(source = archive) {
  const records = getRecords(source);
  const readyRecords = records.filter(isUiReady);

  return {
    totalRecords: records.length,
    readyForDiscoverRecords: readyRecords.length,
    approvedItRecords: records.filter((record) => record.languageStatus?.it === "approved").length,
    approvedFurRecords: records.filter((record) => isFurReady(record)).length,
    exactDateRecords: records.filter((record) => Array.isArray(record.dateAnchors) && record.dateAnchors.length > 0).length,
    readyForUiRecords: records.filter((record) => record.readyForUi === true).length,
    almanacScheduleRecords: records.filter((record) => record.recommendedSurface === "almanac").length,
  };
}

export function getTraditionalSayingForDate({
  date = new Date(),
  language = "it",
  source = archive,
} = {}) {
  const languageKey = getLanguageKey(language);
  const dateKey = getDiscoverDateKey(date);
  if (!dateKey) return null;

  const readyRecords = getRecords(source)
    .filter((record) => isUiReady(record) && (languageKey !== "fur" || isFurReady(record)))
    .sort(compareRecords);
  const selectedRecord = pickDiscoverTemporalRecord(readyRecords, date, { blendBroader: true });
  if (!selectedRecord) return null;

  const selectedRank = getDiscoverTemporalRank(selectedRecord, date);
  const selectionKinds = ["exact_date", "movable_date", "date_range", "seasonal", "rotation"];
  return buildTraditionalSayingCard(
    selectedRecord,
    source,
    language,
    selectionKinds[selectedRank] || "rotation",
  );
}

export function getTraditionalSayingRecords(source = archive) {
  return getRecords(source);
}
