import { describe, expect, it } from "vitest";

import culturalRecords from "../../domain/discover/discoverCulturalRecords";
import { buildDiscoverViewModel } from "./discoverViewModel";

const LOCATIONS = [
  { city: "Gorizia", province: "GO", region: "Friuli Venezia Giulia" },
  { city: "Pordenone", province: "PN", region: "Friuli Venezia Giulia" },
  { city: "Trieste", province: "TS", region: "Friuli Venezia Giulia" },
  { city: "Udine", province: "UD", region: "Friuli Venezia Giulia" },
];

function getLeapYearDates() {
  return Array.from({ length: 366 }, (_, index) => {
    const date = new Date(Date.UTC(2024, 0, index + 1));
    return date.toISOString().slice(0, 10);
  });
}

describe("discover daily composer matrix", () => {
  it("keeps every province, day and language deterministic and fail-closed", () => {
    const archiveContextIds = new Set(
      culturalRecords
        .filter((record) => record.editorialStatus === "archive_context")
        .map((record) => record.id),
    );

    for (const today of getLeapYearDates()) {
      for (const location of LOCATIONS) {
        for (const language of ["it", "fur"]) {
          const model = buildDiscoverViewModel({ language, location, today });
          const visibleCards = [
            model.focus,
            ...model.sections.flatMap((section) => section.cards),
          ].filter(Boolean);
          const contentKeys = visibleCards.map((card) => card.contentKey || card.id);

          expect(new Set(contentKeys).size).toBe(contentKeys.length);
          expect(model.sections.every((section) => (
            section.cards.length <= (section.id === "local-memory-secondary" ? 3 : 1)
          ))).toBe(true);
          expect(model.focus && archiveContextIds.has(model.focus.id)).toBe(false);
          if (language === "fur") {
            expect(visibleCards.some((card) => card.isFurPending)).toBe(false);
          }
        }
      }
    }
  }, 30_000);
});
