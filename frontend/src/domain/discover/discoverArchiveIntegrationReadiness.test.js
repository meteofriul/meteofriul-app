import { describe, expect, it } from "vitest";

import archiveResearchWave01 from "../../data/discover/archiveResearchWave01.json";
import archiveResearchWave02 from "../../data/discover/archiveResearchWave02.json";
import culturalRecords from "./discoverCulturalRecords";
import { isCuratedDiscoverPublished, isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";
import { getDiscoverSeasonForRecord, getDiscoverTemporalRank } from "./discoverTemporalSelection";

const EXPECTED_TYPES = {
  "bacio-croci-zuglio": "rito",
  "maj-lucinico": "rito",
  "cramars-carnia": "storia_locale",
  "osmiza-frasco": "vita_quotidiana",
  "toco-marano": "vita_quotidiana",
  "mulini-risorgive": "vita_quotidiana",
  "animali-nomi-campanacci": "vita_quotidiana",
  "pettini-osso-andreis": "vita_quotidiana",
  "bucato-ranno": "vita_quotidiana",
  "ago-osso-prosciutto": "vita_quotidiana",
};
const records = [...archiveResearchWave01.records, ...archiveResearchWave02.records];
const batch = records.filter((record) => (
  record.integrationReview?.batchId === "archive-integration-2026-08-30-04"
));
const bySuffix = new Map(batch.map((record) => [record.id.replace("archive-research-", ""), record]));
const temporal = (suffix) => bySuffix.get(suffix).promotionReview.runtimeTemporal;

function shiftDate(isoDate, days) {
  const date = new Date(`${isoDate}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

describe("discover archive integration preparation", () => {
  it("integrates exactly ten traceable batch targets while preserving the preparatory audit", () => {
    expect([...bySuffix.keys()]).toEqual(Object.keys(EXPECTED_TYPES));
    const activeIdentities = new Set(culturalRecords.flatMap((record) => [
      record.id, record.sourceId, record.candidateId, record.canonicalKey,
    ]).filter(Boolean));
    const allTargets = records.map((record) => record.promotionReview.targetRecordId);
    expect(new Set(allTargets).size).toBe(20);
    expect(new Set(records.map((record) => record.canonicalKey)).size).toBe(20);

    batch.forEach((record) => {
      const suffix = record.id.replace("archive-research-", "");
      expect(record.promotionReview).toMatchObject({
        decision: "promoted",
        promotedAt: "2026-08-31",
        targetRecordId: `institutional-archive-${suffix}`,
        targetSection: "archivio_tradizioni",
        targetType: EXPECTED_TYPES[suffix],
        remainingBlockers: [],
      });
      expect(record.integrationReview).toMatchObject({
        reviewedAt: "2026-08-30",
        method: "shadow_runtime_projection",
        reviewDocument: "docs/operations/SCOPRI_ARCHIVE_INTEGRATION_2026-08-30.md",
        calendarAuditYears: [2026, 2027, 2028, 2029, 2030, 2031],
        calendarAuditLanguages: ["it", "fur"],
      });
      expect(record.integrationReview.references.length).toBeGreaterThan(0);
      record.integrationReview.references.forEach((reference) => {
        expect(new URL(reference.url).protocol).toBe("https:");
        expect(reference.note.length).toBeGreaterThan(5);
      });
      expect(record.languageStatus).toEqual({ it: "approved", fur: "approved" });
      expect(record.languageReview.fur).toMatchObject({
        approvalBasis: "user_explicit_assisted_review_approval",
        approvedAt: "2026-08-31",
      });
      expect(record.readyForUi).toBe(false);
      expect(isCuratedDiscoverUiReady(record)).toBe(false);
      expect(isCuratedDiscoverPublished(record)).toBe(false);
      [record.id, record.canonicalKey, record.promotionReview.targetRecordId].forEach((id) => {
        expect(activeIdentities.has(id)).toBe(true);
      });
      expect(record.promotionReview.runtimeTemporal.months || []).toEqual([]);
    });
  });

  it.each([
    [1818, "04-30", "05-03"],
    [1973, "05-31", "06-03"],
    [2026, "05-14", "05-17"],
    [2027, "05-06", "05-09"],
    [2028, "05-25", "05-28"],
    [2029, "05-10", "05-13"],
    [2030, "05-30", "06-02"],
    [2031, "05-22", "05-25"],
    [2038, "06-03", "06-06"],
  ])("limits the Bacio archive window to Ascension Thursday–Sunday in %i", (year, start, end) => {
    const rule = temporal("bacio-croci-zuglio");
    expect(rule.movableDateRanges).toEqual([{ anchor: "easter", startOffsetDays: 39, endOffsetDays: 42 }]);
    expect(rule.dateAnchors).toEqual([]);
    expect(rule.movableDates).toEqual([]);
    const firstDay = `${year}-${start}`;
    const lastDay = `${year}-${end}`;
    [0, 1, 2, 3].forEach((offset) => {
      expect(getDiscoverTemporalRank(rule, shiftDate(firstDay, offset))).toBe(2);
    });
    expect(shiftDate(firstDay, 3)).toBe(lastDay);
    expect(getDiscoverTemporalRank(rule, shiftDate(firstDay, -1))).toBeNull();
    expect(getDiscoverTemporalRank(rule, shiftDate(lastDay, 1))).toBeNull();
  });

  it("treats seasonal windows as editorial context, not announcements of current rites", () => {
    ["bacio-croci-zuglio", "maj-lucinico"].forEach((suffix) => {
      const record = bySuffix.get(suffix);
      expect(record.promotionReview.temporalInterpretation).toBe("editorial_context_window");
      expect(record.promotionReview.temporalNote).toContain("1973");
      expect(record.draftCopy.it).toContain("1973");
      expect(record.draftCopy.fur).toContain("1973");
      // The original research snapshot is not rewritten to pretend it had a runtime rule.
      expect(record.temporalRule.status).toBe("requires_runtime_rule");
    });
    expect(getDiscoverSeasonForRecord(temporal("bacio-croci-zuglio"), "2038-06-03")).toBe("estate");
    expect(temporal("maj-lucinico").dateRanges).toEqual(["04-30..05-07"]);
    [2022, 2023, 2026, 2027, 2028, 2029, 2030, 2031].forEach((year) => {
      const mayFirst = `${year}-05-01`;
      const weekday = new Date(`${mayFirst}T12:00:00Z`).getUTCDay();
      const firstSunday = shiftDate(mayFirst, (7 - weekday) % 7);
      [firstSunday, shiftDate(firstSunday, -1), `${year}-04-30`, `${year}-05-07`].forEach((date) => {
        expect(getDiscoverTemporalRank(temporal("maj-lucinico"), date)).toBe(2);
      });
      [`${year}-04-29`, `${year}-05-08`, `${year}-05-31`].forEach((date) => {
        expect(getDiscoverTemporalRank(temporal("maj-lucinico"), date)).toBeNull();
      });
    });
  });

  it("keeps cramars seasonal and seven material-culture narratives free of invented dates", () => {
    const cramars = temporal("cramars-carnia");
    ["2028-09-01", "2028-01-15", "2028-05-31"].forEach((date) => {
      expect(getDiscoverTemporalRank(cramars, date)).toBe(3);
    });
    ["2028-06-01", "2028-08-31"].forEach((date) => {
      expect(getDiscoverTemporalRank(cramars, date)).toBeNull();
    });
    const evergreen = batch.filter((record) => record.promotionReview.runtimeTemporal.recurrence === "always");
    expect(evergreen).toHaveLength(7);
    evergreen.forEach((record) => {
      expect(record.promotionReview.temporalInterpretation).toBe("evergreen_archive_rotation");
      expect(record.promotionReview.runtimeTemporal).toEqual({
        recurrence: "always", dateAnchors: [], dateRanges: [], movableDates: [],
        movableDateRanges: [], seasons: ["all"], weatherTags: [],
      });
      for (let month = 1; month <= 12; month += 1) {
        expect(getDiscoverTemporalRank(record.promotionReview.runtimeTemporal,
          `2028-${String(month).padStart(2, "0")}-15`)).toBe(4);
      }
    });
    ["osmiza-frasco", "toco-marano"].forEach((suffix) => {
      expect(bySuffix.get(suffix).temporalRule.status).toBe("no_fixed_date");
    });
  });

  it("contains each batch member exactly once in the real catalog without synthetic projections", () => {
    expect(batch).toHaveLength(10);
    batch.forEach((record) => {
      const matches = culturalRecords.filter((active) => active.sourceId === record.id);
      expect(matches).toHaveLength(1);
      expect(matches[0]).toMatchObject({
        id: record.promotionReview.targetRecordId,
        canonicalKey: record.canonicalKey,
        ...record.promotionReview.runtimeTemporal,
      });
      expect(isCuratedDiscoverPublished(matches[0])).toBe(true);
    });
  });
});
