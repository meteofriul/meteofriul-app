const CURATED_DISCOVER_STATUSES = new Set(["ready_it", "archive_context"]);

export function isCuratedDiscoverUiReady(record) {
  if (!record || record.readyForUi === false) return false;
  return CURATED_DISCOVER_STATUSES.has(record.editorialStatus);
}

export function isCuratedDiscoverPublished(record) {
  return isCuratedDiscoverUiReady(record)
    && record?.languageStatus?.fur === "approved";
}
