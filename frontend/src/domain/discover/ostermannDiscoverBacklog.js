import backlog from "../../data/discover/ostermannDiscoverBacklog.json";

function getRecords(source = backlog) {
  return Array.isArray(source?.records) ? source.records : [];
}

export function getOstermannDiscoverBacklogSummary(source = backlog) {
  const records = getRecords(source);
  const pages = new Set(records.map((record) => record.sourcePage).filter(Boolean));
  const discoverRecords = records.filter((record) => record.primaryUse === "discover");
  const almanacBridgeRecords = records.filter((record) => (
    Array.isArray(record.secondaryUse) &&
    record.secondaryUse.some((use) => use.startsWith("almanac"))
  ));
  const pendingFurRecords = records.filter((record) => (
    record.title?.fur === "pending_review" ||
    record.summary?.fur === "pending_review"
  ));

  return {
    totalRecords: records.length,
    sourcePages: pages.size,
    discoverRecords: discoverRecords.length,
    almanacBridgeRecords: almanacBridgeRecords.length,
    pendingFurRecords: pendingFurRecords.length,
    readyForUiRecords: records.filter((record) => record.editorialStatus === "ready_for_discover").length,
  };
}

export function getOstermannDiscoverBacklogRecords(source = backlog) {
  return getRecords(source);
}
