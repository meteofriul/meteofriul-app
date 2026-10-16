export const COMMUNITY_RECENT_WINDOW_MS = 48 * 60 * 60 * 1000;

export function getCommunityHistoryTimeLabel(createdAt, now, copy) {
  const minutes = Math.max(0, Math.floor((now - createdAt) / 60_000));
  if (minutes < 1) return copy.reportNow;
  if (minutes < 60) return copy.reportMinutesAgo.replace("{minutes}", String(minutes));
  const hours = Math.floor(minutes / 60);
  return hours === 1 ? copy.reportHourAgo : copy.reportHoursAgo.replace("{hours}", String(hours));
}

export function getCommunityHistoryCountLabel(report, copy) {
  const count = Math.max(1, Number(report.count) || 1);
  return count === 1 ? copy.reportCountOne : copy.reportCountMany.replace("{count}", String(count));
}

// Archived groups come from the server, already counted before pagination.
export function buildCommunityRecentItems(history, activeGroups, now) {
  const current = history.filter((report) => report.createdAt > now - COMMUNITY_RECENT_WINDOW_MS)
    .map((report) => ({ ...report, status: report.status === "active" && report.expiresAt <= now
      ? "expired" : report.status }));
  const byId = new Map(current.map((report) => [report.id, report]));
  const represented = new Set();
  const items = activeGroups.filter((group) => group.expiresAt > now).flatMap((group) => {
    const ids = group.reportIds?.length ? group.reportIds : [group.id];
    const liveIds = ids.filter((id) => !byId.has(id) || byId.get(id).status === "active");
    if (!liveIds.length) return [];
    liveIds.forEach((id) => represented.add(id));
    return [{ ...group, recentKind: "live", recentKey: `live:${group.id}` }];
  });
  for (const report of current) {
    if (report.status === "active" && represented.has(report.id)) continue;
    items.push({ ...report, recentKind: "history", recentKey: `history:${report.id}` });
  }
  return items.sort((a, b) => b.createdAt - a.createdAt || b.recentKey.localeCompare(a.recentKey));
}
