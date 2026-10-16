// The additive policy does not change any legacy manifest or payload.
export const CAMS_CONTINUITY_POLICY = "cams_continuity_36h_v1";
export const CAMS_CONTINUITY_HOURS = 36;
const HOUR = 3_600_000;
const same = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  return value;
}
export function validateCamsContinuity(document, { runId, releaseSha256, releaseJsonBytes, issuedAt, catalog }) {
  if (!/^\d{8}T000000Z$/.test(runId) || !/^[a-f0-9]{64}$/.test(releaseSha256)
    || !Number.isSafeInteger(releaseJsonBytes) || releaseJsonBytes <= 0 || releaseJsonBytes > 128 * 1024) {
    throw new TypeError("Invalid CAMS continuity binding");
  }
  const runAt = `${runId.slice(0,4)}-${runId.slice(4,6)}-${runId.slice(6,8)}T00:00:00Z`;
  const run = Date.parse(runAt);
  const iso = time => new Date(time).toISOString().replace(".000Z", "Z");
  if (!Number.isFinite(run) || iso(run) !== runAt) throw new TypeError("Invalid continuity date");
  const expected = {
    schema_version: 1, kind: "meteofriul.weather.cams_continuity", policy_id: CAMS_CONTINUITY_POLICY,
    source_run_id: runId, catalog, release_sha256: releaseSha256, release_json_bytes: releaseJsonBytes,
    issued_at: issuedAt, run_at: runAt, fresh_until: iso(run + 24 * HOUR),
    usable_until: iso(run + CAMS_CONTINUITY_HOURS * HOUR), current_sample_max_lag_minutes: 60,
  };
  if (!same(document, expected)) throw new TypeError("CAMS continuity policy or release binding mismatch");
  return document;
}

// Persisted evidence must bind the extension to this exact family and to all
// three verified read stages. A cache timestamp alone never grants more time.
export function camsContinuityFromEvidence(value) {
  const evidence = value?.source?.cams?.evidence;
  const stages = evidence?.stages;
  const latest = stages?.latest;
  const document = latest?.freshness?.continuity;
  if (!document) return null;
  try {
    const release = latest.family_release;
    validateCamsContinuity(document, {
      runId: evidence.family.active_run_id, releaseSha256: release.release_sha256,
      releaseJsonBytes: release.release_json_bytes, issuedAt: latest.family_release_published_at,
      catalog: value.source.cams.catalog || value.source.catalog,
    });
    if (document.run_at !== value.data_quality.cams_run_utc
      || release.source_run_id !== document.source_run_id
      || release.release_path !== `runs/${document.source_run_id}/release.json`
      || evidence.family.disabled_run_ids.includes(document.source_run_id)) return null;
    for (const stage of [stages.latest, stages.manifest, stages.municipality]) {
      if (!same(stage?.freshness?.continuity, document)
        || stage.freshness.freshUntil !== document.fresh_until
        || stage.freshness.usableUntil !== document.usable_until) return null;
    }
    return document;
  } catch { return null; }
}
