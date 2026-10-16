const VERIFIED_REVIEW_STATUSES = new Set([
  "source_verified_for_copy",
  "ready_for_copy",
]);

const HOLD_STATUSES = new Set([
  "hold",
  "hold_duplicate_theme",
  "do_not_publish",
  "discarded",
]);

const SOURCE_LEAD_STATUSES = new Set([
  "source_lead_found",
  "source_candidate",
  "needs_review",
]);

const SENSITIVE_TERMS = [
  "assassinio",
  "assedio",
  "battaglia",
  "conflitto",
  "disastro",
  "eccidio",
  "foibe",
  "guerra",
  "incidente",
  "morte",
  "morti",
  "occupazione",
  "repressione",
  "rivolta",
  "strage",
  "tragedia",
];

function normalize(value) {
  return String(value || "")
    .trim()
    .toLocaleLowerCase("it-IT");
}

export function isValidItalianDayMonth(value) {
  const match = String(value || "").match(/^(\d{2})-(\d{2})$/);
  if (!match) return false;

  const day = Number(match[1]);
  const month = Number(match[2]);
  const parsed = new Date(Date.UTC(2000, month - 1, day));

  return parsed.getUTCDate() === day && parsed.getUTCMonth() === month - 1;
}

function getStatus(record) {
  return (
    record?.reviewStatus ||
    record?.sourceReview?.status ||
    record?.batchStatus ||
    record?.editorialStatus ||
    ""
  );
}

function getSearchableText(record) {
  return [
    record?.title?.it,
    record?.title,
    record?.sourceTitle,
    record?.category,
    record?.place,
    record?.editorialNote,
    record?.reason,
  ].map(normalize).join(" ");
}

export function isSensitiveDailyHistoryCandidate(record) {
  const text = getSearchableText(record);
  if (SENSITIVE_TERMS.some((term) => text.includes(term))) return true;
  if (Number(record?.year) >= 1900 && text.includes("storia")) return true;
  return false;
}

export function getDiscoverEditorialReadiness(record) {
  const status = getStatus(record);

  if (record?.readyForUi === true && record?.editorialStatus === "ready_for_discover") {
    return {
      status: "published",
      canPublishLight: false,
      needsStrongSource: false,
      reason: "Il record e' gia pubblicato in Scopri.",
    };
  }

  if (HOLD_STATUSES.has(status)) {
    return {
      status: "hold",
      canPublishLight: false,
      needsStrongSource: false,
      reason: "Il record e' sospeso o scartato.",
    };
  }

  if (VERIFIED_REVIEW_STATUSES.has(status)) {
    return {
      status: "strong_ready_for_copy",
      canPublishLight: false,
      needsStrongSource: false,
      reason: "Fonte abbastanza solida: serve copy IT/FUR e review prima della UI.",
    };
  }

  const sensitive = isSensitiveDailyHistoryCandidate(record);
  if (sensitive) {
    return {
      status: "needs_strong_source",
      canPublishLight: false,
      needsStrongSource: true,
      reason: "Tema sensibile: non basta una rubrica leggera senza fonte forte.",
    };
  }

  if (SOURCE_LEAD_STATUSES.has(status)) {
    return {
      status: "light_candidate",
      canPublishLight: true,
      needsStrongSource: false,
      reason: "Tema leggero: pubblicabile solo con copy prudente e review umana.",
    };
  }

  return {
    status: "needs_editorial_triage",
    canPublishLight: false,
    needsStrongSource: false,
    reason: "Serve una decisione editoriale prima di classificarlo.",
  };
}

export function getDiscoverEditorialPolicyAudit(records = []) {
  const items = records.map((record) => ({
    id: record.id || record.sourceCandidateId,
    readiness: getDiscoverEditorialReadiness(record),
  }));

  const byReadiness = items.reduce((acc, item) => {
    const key = item.readiness.status;
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});

  return {
    totalRecords: items.length,
    byReadiness,
    lightCandidateRecordIds: items
      .filter((item) => item.readiness.canPublishLight)
      .map((item) => item.id),
    strongSourceRequiredRecordIds: items
      .filter((item) => item.readiness.needsStrongSource)
      .map((item) => item.id),
    strongReadyForCopyRecordIds: items
      .filter((item) => item.readiness.status === "strong_ready_for_copy")
      .map((item) => item.id),
  };
}
