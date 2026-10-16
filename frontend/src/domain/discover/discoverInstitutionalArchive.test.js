import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import archiveResearchWave01 from "../../data/discover/archiveResearchWave01.json";
import archiveResearchWave02 from "../../data/discover/archiveResearchWave02.json";
import { buildDiscoverEditorialCalendarAudit } from "../../features/discover/discoverEditorialCalendarAudit";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import {
  getDiscoverCulturalRecords,
  getInstitutionalArchiveRecords,
} from "./discoverCulturalRecords";
import { isCuratedDiscoverPublished, isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";
import { getDiscoverTemporalRank } from "./discoverTemporalSelection";

const FIRST_PROMOTIONS = {
  "archive-research-cesti-vimini": "institutional-archive-cesti-vimini",
  "archive-research-latteria-sociale": "institutional-archive-latteria-sociale",
  "archive-research-cartoline-lignano": "institutional-archive-cartoline-lignano",
};

const researchRecords = [...archiveResearchWave01.records, ...archiveResearchWave02.records];
const researchById = new Map(researchRecords.map((record) => [record.id, record]));
const PROMOTIONS = {
  ...FIRST_PROMOTIONS,
  ...Object.fromEntries(researchRecords.filter((record) => !FIRST_PROMOTIONS[record.id])
    .map((record) => [record.id, record.id.replace("archive-research-", "institutional-archive-")])),
};

function getHistoricalArchiveRecords() {
  return getInstitutionalArchiveRecords().filter((record) => researchById.has(record.sourceId));
}

describe("institutional archive approved batches", () => {
  it("promotes exactly twenty reviewed records with their source and temporal scope intact", () => {
    const archive = getHistoricalArchiveRecords();
    const active = getDiscoverCulturalRecords();

    expect(archive.map((record) => record.id)).toEqual(Object.values(PROMOTIONS));
    expect(new Set(active.map((record) => record.id)).size).toBe(active.length);
    expect(archive).toHaveLength(20);
    expect(new Set(archive.map((record) => record.canonicalKey)).size).toBe(20);

    archive.forEach((record) => {
      const research = researchById.get(record.sourceId);

      expect(research).toBeTruthy();
      expect(record).toMatchObject({
        id: PROMOTIONS[research.id],
        sourceId: research.id,
        candidateId: research.id,
        canonicalKey: research.canonicalKey,
        section: research.promotionReview.targetSection,
        type: research.promotionReview.targetType,
        priority: 8,
        editorialStatus: "ready_it",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
        ...research.promotionReview.runtimeTemporal,
      });
      expect(record.title).toEqual(research.title);
      expect(record.text).toEqual(research.draftCopy);
      expect(record.appShort).toEqual(research.draftAppShort);
      expect(record.source).toEqual(research.source);
      expect(record.areas).toEqual(research.geographicScope);
      expect(record.languageReview).toEqual(research.languageReview);
      expect(isCuratedDiscoverPublished(record)).toBe(true);
      expect(active.filter((entry) => entry.sourceId === research.id)).toHaveLength(1);

      expect(research).toMatchObject({
        reviewStatus: "promoted",
        editorialStatus: "promoted_to_catalog",
        readyForUi: false,
        promotionReview: {
          decision: "promoted",
          promotedAt: FIRST_PROMOTIONS[research.id] ? "2026-08-30" : "2026-08-31",
          remainingBlockers: [],
        },
      });
      expect(isCuratedDiscoverUiReady(research)).toBe(false);
    });
  });

  it("distinguishes initial conditional approval from subsequent explicit approval with references", () => {
    getHistoricalArchiveRecords().forEach((record) => {
      const review = record.languageReview.fur;

      expect(review).toMatchObject({
        approvalBasis: FIRST_PROMOTIONS[record.sourceId]
          ? "user_conditional_standard_reference_review" : "user_explicit_assisted_review_approval",
        reviewMethod: "assisted_standard_reference_review",
        approvedAt: FIRST_PROMOTIONS[record.sourceId] ? "2026-08-30" : "2026-08-31",
        approvalNote: expect.any(String),
        references: expect.any(Array),
      });
      expect(review.approvalNote).toMatch(/non.*certificazion/i);
      expect(review.references.length).toBeGreaterThan(0);
      review.references.forEach((reference) => {
        const url = typeof reference === "string" ? reference : reference.url;
        expect(new URL(url).protocol).toBe("https:");
      });
      [record.title, record.text, record.appShort].forEach((copy) => {
        expect(copy.it).toBeTruthy();
        expect(copy.fur).toBeTruthy();
        expect(copy.fur).not.toBe(copy.it);
      });
    });
  });

  it("keeps research snapshots out of the UI while publishing each approved target once", () => {
    const active = getDiscoverCulturalRecords();
    expect(researchRecords).toHaveLength(20);
    researchRecords.forEach((record) => {
      expect(record.languageStatus).toEqual({ it: "approved", fur: "approved" });
      expect(record.readyForUi).toBe(false);
      expect(isCuratedDiscoverUiReady(record)).toBe(false);
      expect(active.filter((entry) => entry.sourceId === record.id)).toHaveLength(1);
      expect(active.some((entry) => entry.id === record.id)).toBe(false);
      expect(record.promotionReview.decision).toBe("promoted");
      expect(record.promotionReview.remainingBlockers).toEqual([]);
    });
  });

  it("restricts Lignano to summer while keeping everyday material available year-round", () => {
    getInstitutionalArchiveRecords().filter((record) => FIRST_PROMOTIONS[record.sourceId]).forEach((record) => {
      if (record.id === PROMOTIONS["archive-research-cartoline-lignano"]) {
        expect(record.recurrence).toBe("seasonal");
        expect(getDiscoverTemporalRank(record, "2028-05-31")).toBeNull();
        expect(getDiscoverTemporalRank(record, "2028-06-01")).toBe(3);
        expect(getDiscoverTemporalRank(record, "2028-08-31")).toBe(3);
        expect(getDiscoverTemporalRank(record, "2028-09-01")).toBeNull();
      } else {
        expect(record.recurrence).toBe("always");
        expect(getDiscoverTemporalRank(record, "2028-01-01")).toBe(4);
        expect(getDiscoverTemporalRank(record, "2028-07-01")).toBe(4);
      }
    });
  });

  it.each(["it", "fur"])("renders historical and later approved records in the actual 2028 %s rotation without collisions", (language) => {
    const audit = buildDiscoverEditorialCalendarAudit({ year: 2028, language });

    expect(audit.summary.archive.usedIds).toEqual(expect.arrayContaining(Object.values(PROMOTIONS)));
    expect(audit.summary.archive.daysShown).toBe(366);
    expect(audit.summary.archive.longestConsecutiveRepeat.days).toBeLessThanOrEqual(2);
    expect(audit.summary.visibleCollisions).toEqual([]);
    expect(audit.summary.exactDatePrecedenceViolations).toEqual([]);
    const lignanoRows = audit.rows.filter((row) => (
      row.archive?.id === PROMOTIONS["archive-research-cartoline-lignano"]
    ));
    expect(lignanoRows.length).toBeGreaterThan(0);
    expect(lignanoRows.every((row) => ["06", "07", "08"].includes(row.date.slice(5, 7)))).toBe(true);

    getInstitutionalArchiveRecords().forEach((record) => {
      const selectedDay = audit.rows.find((row) => row.archive?.id === record.id);
      expect(selectedDay).toBeTruthy();
      const model = buildDiscoverViewModel({
        language,
        location: { city: "Pordenone", province: "Pordenone", region: "Friuli Venezia Giulia" },
        today: selectedDay.date,
      });
      const card = model.sections.find((section) => section.id === "archive").cards[0];
      const pendingLabel = "FUR_IN_REVISION_TEST_SENTINEL";
      const html = renderToStaticMarkup(createElement(DiscoverCard, {
        card,
        furPendingLabel: pendingLabel,
      }));

      expect(card).toMatchObject({
        id: record.id,
        title: record.title[language],
        text: record.text[language],
        sourceLabel: record.source.label,
        isFurPending: false,
      });
      expect(html).toContain(renderToStaticMarkup(createElement("h2", null, record.title[language])));
      expect(html).toContain(renderToStaticMarkup(createElement("p", null, record.text[language])));
      expect(html).toContain(renderToStaticMarkup(createElement("small", null, record.source.label)));
      expect(html).not.toContain(pendingLabel);
    });
  });
});
