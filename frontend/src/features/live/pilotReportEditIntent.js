// Presentation only: the server remains authoritative for expiry and all quotas.
export function getPilotReportEditIntent(report, typeId, now = Date.now()) {
  if (!report || !typeId) return "";
  if (typeId === report.typeId) return "update";
  if (Number(report.correctionUntil) > now) return "correct";
  return report.replacementAvailable === true ? "replace" : "unavailable";
}

export function reviewPilotReportEditIntent(report, typeId, now = Date.now()) {
  return { intent: getPilotReportEditIntent(report, typeId, now), reviewedAt: now };
}
