import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import review from "../../data/discover/weatherContextReview.json";
import originalRecords from "../../data/ostermannCulturalDiscover.json";
import { DiscoverCard } from "./DiscoverView";
import { buildDiscoverEditorialCalendarAudit } from "./discoverEditorialCalendarAudit";
import { buildDiscoverViewModel } from "./discoverViewModel";

const LOCATION = { city: "Pordenone", province: "PN", region: "Friuli Venezia Giulia" };

describe("Scopri historical weather stories", () => {
  it.each(["it", "fur"])("keeps recovered stories out of the generic focus for unknown municipalities in %s", (language) => {
    const recoveredIds = new Set(review.editorialDecision.recordIds);
    const seenInArchive = new Set();
    for (let day = 1; day <= 31; day += 1) {
      const model = buildDiscoverViewModel({
        today: `2028-01-${String(day).padStart(2, "0")}`,
        language,
        location: { city: "Sconosciuta", province: "XX" },
      });
      expect(model.focus).toBeTruthy();
      expect(recoveredIds.has(model.focus.id)).toBe(false);
      const archive = model.sections.find((section) => section.id === "archive");
      expect(archive.cards).toHaveLength(1);
      if (recoveredIds.has(archive.cards[0].id)) seenInArchive.add(archive.cards[0].id);
      const cards = [model.focus, ...model.sections.flatMap((section) => section.cards)];
      const keys = cards.map((card) => card.contentKey || card.id);
      expect(new Set(keys).size).toBe(keys.length);
    }
    expect(seenInArchive.size).toBeGreaterThan(0);
  });

  it.each(["it", "fur"])("renders the eight recovered stories only as archive cards in %s", (language) => {
    const audit = buildDiscoverEditorialCalendarAudit({ year: 2028, language, location: LOCATION });
    const recoveredIds = review.editorialDecision.recordIds;
    expect(audit.summary.archive.usedIds).toEqual(expect.arrayContaining(recoveredIds));
    const excludedIds = review.records.filter((record) => record.disposition === "excluded")
      .map((record) => record.recordId);
    expect(audit.rows.some((row) => excludedIds.includes(row.archive?.id) || excludedIds.includes(row.ritual?.id)))
      .toBe(false);

    recoveredIds.forEach((id) => {
      const original = originalRecords.find((record) => record.id === id);
      const day = audit.rows.find((row) => row.archive?.id === id);
      const model = buildDiscoverViewModel({ today: day.date, language, location: LOCATION });
      const archive = model.sections.find((section) => section.id === "archive");
      const visibleCards = [model.focus, ...model.sections.flatMap((section) => section.cards)].filter(Boolean);
      const keys = visibleCards.map((card) => card.contentKey || card.id);
      expect(new Set(keys).size).toBe(keys.length);
      expect(archive.cards).toHaveLength(1);
      expect(archive.cards[0]).toMatchObject({
        id,
        title: original.title[language],
        text: original.text[language],
        sourceLabel: original.source.label,
        sourceNote: original.source.note,
        selectionKind: original.seasons.includes("all") ? "rotation" : "seasonal",
        isFurPending: false,
      });
      expect(model.sections.filter((section) => section.id !== "archive")
        .flatMap((section) => section.cards).some((card) => card.id === id)).toBe(false);
      expect(visibleCards.filter((card) => card.id === id)).toHaveLength(1);
      const html = renderToStaticMarkup(createElement(DiscoverCard, { card: archive.cards[0] }));
      expect(html).toContain(renderToStaticMarkup(createElement("p", null, original.text[language])));
      expect(html).toContain("Ostermann 1894");
      expect(html).not.toMatch(/pending_review|human_review_needed|source_needed/);
    });
  });
});
