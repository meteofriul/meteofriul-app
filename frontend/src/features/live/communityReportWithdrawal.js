// Report-specific acknowledgements protect the pilot UI from older feed/cache
// responses. They never suppress an entire municipality, author or group.

function text(value) {
  return String(value || "").trim();
}

function unique(values) {
  return [...new Set(values.map(text).filter(Boolean))];
}

function sourceKeys(entry) {
  return unique([...(entry?.sourceKeys || []), entry?.sourceKey]);
}

function countLabel(count, copy) {
  return count === 1
    ? copy.reportCountOne || "1"
    : String(copy.reportCountMany || "{count}").replace("{count}", String(count));
}

function collectIdentities(entries, allowedSourceKeys, fallbacks = []) {
  const allowed = new Set(allowedSourceKeys);
  const identities = new Map();
  for (const entry of [...fallbacks, ...entries.flatMap((value) => [
    ...(value?.identities || []),
    ...(value?.sourceKey && value?.identity ? [{ sourceKey: value.sourceKey, identity: value.identity }] : []),
  ])]) {
    const key = text(entry?.sourceKey);
    if (allowed.has(key) && entry?.identity) identities.set(key, { sourceKey: key, identity: entry.identity });
  }
  return [...identities.values()];
}

function latestEntry(entries) {
  return entries.reduce((latest, entry) => (
    !latest || Number(entry.createdAt || 0) > Number(latest.createdAt || 0) ? entry : latest
  ), null);
}

function filterEntry(entry, withdrawn, copy) {
  const contributions = Array.isArray(entry?.contributions) ? entry.contributions : [];
  const declaredReportIds = Array.isArray(entry?.reportIds) ? entry.reportIds : [];
  const knownIds = unique([
    ...declaredReportIds,
    ...contributions.map((contribution) => contribution?.id),
    // Support a single raw-report item without mistaking a group for a report.
    ...(!contributions.length && !declaredReportIds.length && entry?.id !== entry?.groupId ? [entry?.id] : []),
  ]);
  const removedIds = knownIds.filter((id) => withdrawn.has(id));
  if (!removedIds.length) return entry;

  const visibleContributions = contributions.filter((contribution) => !withdrawn.has(text(contribution?.id)));
  const reportIds = knownIds.filter((id) => !withdrawn.has(id));
  const declaredCount = Math.max(knownIds.length, contributions.length, Number(entry.count) || 0);
  const count = Math.max(reportIds.length, visibleContributions.length, declaredCount - removedIds.length);
  if (!count) return null;

  // In partial feeds the unidentified contributors still belong to the group.
  // Keep their aggregate attribution until a fresh authoritative response.
  const completeContributions = visibleContributions.length === count;
  const keys = completeContributions
    ? unique(visibleContributions.flatMap(sourceKeys))
    : sourceKeys(entry);
  const identities = collectIdentities(visibleContributions, keys, entry.identities || []);
  const latest = completeContributions ? latestEntry(visibleContributions) : null;
  return {
    ...entry,
    contributions: visibleContributions,
    count,
    countLabel: countLabel(count, copy),
    identities,
    identity: latest?.identity || (identities.length === 1 ? identities[0].identity : null),
    reportIds,
    sourceKey: keys.length === 1 ? keys[0] : "",
    sourceKeys: keys,
    ...(latest ? {
      createdAt: latest.createdAt,
      expiresAt: Math.max(...visibleContributions.map((contribution) => Number(contribution.expiresAt) || 0)),
      timeLabel: latest.timeLabel,
    } : {}),
  };
}

function filterMarker(marker, withdrawn, copy) {
  if (!Array.isArray(marker.phenomena) || !marker.phenomena.length) return filterEntry(marker, withdrawn, copy);
  const filtered = marker.phenomena.map((phenomenon) => filterEntry(phenomenon, withdrawn, copy));
  if (filtered.every((phenomenon, index) => phenomenon === marker.phenomena[index])) return marker;
  const phenomena = filtered.filter(Boolean).sort((a, b) => Number(b.createdAt || 0) - Number(a.createdAt || 0));
  if (!phenomena.length) return null;
  const latest = latestEntry(phenomena);
  const count = phenomena.reduce((total, phenomenon) => total + Math.max(1, Number(phenomenon.count) || 1), 0);
  const keys = unique(phenomena.flatMap(sourceKeys));
  return {
    ...marker,
    confirmations: phenomena.reduce((totals, phenomenon) => ({
      no: totals.no + Math.max(0, Number(phenomenon.confirmations?.no) || 0),
      yes: totals.yes + Math.max(0, Number(phenomenon.confirmations?.yes) || 0),
    }), { no: 0, yes: 0 }),
    contributions: phenomena.flatMap((phenomenon) => phenomenon.contributions || []),
    count,
    countLabel: countLabel(count, copy),
    createdAt: latest.createdAt,
    expiresAt: Math.max(...phenomena.map((phenomenon) => Number(phenomenon.expiresAt) || 0)),
    groupId: latest.groupId,
    identities: collectIdentities(phenomena, keys),
    identity: latest.identity,
    phenomena,
    reportIds: unique(phenomena.flatMap((phenomenon) => phenomenon.reportIds || [])),
    sourceKey: keys.length === 1 ? keys[0] : "",
    sourceKeys: keys,
    timeLabel: latest.timeLabel,
    typeId: phenomena.length > 1 ? "multiple" : latest.typeId,
    typeLabel: phenomena.length > 1 ? copy.reportMultiplePhenomena : latest.typeLabel,
  };
}

export function filterCommunityWithdrawnReportsModel(model, state, { now = Date.now() } = {}) {
  const withdrawals = Array.isArray(state?.reportWithdrawals) ? state.reportWithdrawals : [];
  const withdrawn = new Set(withdrawals
    .filter((item) => Number.isFinite(Number(item.expiresAt)) && Number(item.expiresAt) > now)
    .map((item) => text(item.reportId)).filter(Boolean));
  if (!model || !withdrawn.size) return model;
  const copy = model.copy || {};
  const items = (model.items || []).map((item) => filterEntry(item, withdrawn, copy));
  const markers = (model.markers || []).map((marker) => filterMarker(marker, withdrawn, copy));
  const changed = items.some((item, index) => item !== model.items[index])
    || markers.some((marker, index) => marker !== model.markers[index]);
  if (!changed) return model;
  const byRecency = (first, second) => Number(second.createdAt || 0) - Number(first.createdAt || 0);
  return { ...model, items: items.filter(Boolean).sort(byRecency), markers: markers.filter(Boolean).sort(byRecency) };
}

// Server-confirmed expiries are map-only reconciliation guards. Recent items
// keep their existing retention rules and never become updateable from here.
export function filterCommunityExpiredReportsFromMap(model, state, { now = Date.now() } = {}) {
  const expired = new Set((Array.isArray(state?.reportExpirations) ? state.reportExpirations : [])
    .filter((item) => Number.isFinite(Number(item.expiresAt)) && Number(item.expiresAt) > now)
    .map((item) => text(item.reportId)).filter(Boolean));
  if (!model || !expired.size) return model;
  const copy = model.copy || {};
  const markers = (model.markers || []).map((marker) => filterMarker(marker, expired, copy));
  if (markers.every((marker, index) => marker === model.markers[index])) return model;
  const byRecency = (first, second) => Number(second.createdAt || 0) - Number(first.createdAt || 0);
  return { ...model, markers: markers.filter(Boolean).sort(byRecency) };
}
