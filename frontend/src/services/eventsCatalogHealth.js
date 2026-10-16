function stringMap(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(Object.entries(value)
    .filter(([, item]) => typeof item === "string" && item.length)
    .sort(([first], [second]) => first.localeCompare(second)));
}

// Catalog health describes a completed scheduled collection. It is distinct
// from the legacy on-demand API's partial/refreshing (retryable) responses.
export function readEventsCatalogHealth(payload) {
  const sourceStatus = stringMap(payload?.source_status);
  const sourceFailureTags = stringMap(payload?.source_failure_tags);
  const degraded = payload?.catalog_status === "degraded"
    || Object.values(sourceStatus).some((status) => status !== "fresh")
    || Object.keys(sourceFailureTags).length > 0;
  if (!degraded && payload?.catalog_status !== "complete"
      && !Object.keys(sourceStatus).length) return null;
  return {
    status: degraded ? "degraded" : "complete",
    snapshot: typeof payload?.snapshot === "string" ? payload.snapshot : null,
    sourceStatus,
    sourceFailureTags,
    sourceUpdatedAt: stringMap(payload?.source_updated_at),
  };
}
