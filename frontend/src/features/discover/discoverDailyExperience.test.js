import { describe, expect, it } from "vitest";

import { getDiscoverSeasonLabel } from "../../copy/discoverCopy";
import culturalDiscoverRecords from "../../domain/discover/discoverCulturalRecords";
import {
  getDiscoverSeasonForRecord,
  getDiscoverTemporalRank,
} from "../../domain/discover/discoverTemporalSelection";
import { getTraditionalSayingRecords } from "../../domain/discover/traditionalSayings";
import { buildDiscoverViewModel } from "./discoverViewModel";

const DAILY_TARGET = 366;
const PORDENONE = {
  city: "Pordenone",
  istatCode: "093033",
  province: "PN",
  region: "Friuli Venezia Giulia",
};
const culturalRecordById = new Map(culturalDiscoverRecords.map((record) => [record.id, record]));
const sayingRecordById = new Map(
  getTraditionalSayingRecords().map((record) => [record.id, record]),
);

function getLeapYearDates() {
  return Array.from({ length: DAILY_TARGET }, (_, index) => (
    new Date(Date.UTC(2024, 0, index + 1, 12))
  ));
}

function getVisibleCards(model) {
  return [
    model.focus,
    ...model.sections.flatMap((section) => section.cards),
  ].filter(Boolean);
}

describe("Discover daily experience", () => {
  for (const language of ["it", "fur"]) {
    it(`keeps all editorial cards temporally coherent on 366 days in ${language}`, () => {
      for (const today of getLeapYearDates()) {
        const dayKey = today.toISOString().slice(5, 10);
        const model = buildDiscoverViewModel({
          language,
          location: PORDENONE,
          today,
        });
        const memorySection = model.sections.find((section) => section.id === "today-memory");
        const sayingSection = model.sections.find((section) => section.id === "traditional-sayings");
        const archiveSection = model.sections.find((section) => section.id === "archive");
        const visibleCards = getVisibleCards(model);
        const visibleContentKeys = visibleCards.map((card) => card.contentKey || card.id);

        expect(model.focus, `${language} ${dayKey}: municipality focus`).toMatchObject({
          id: "municipality-profile-pordenone",
          selectionKind: "municipality_profile",
        });
        expect(memorySection, `${language} ${dayKey}: exact memory`).toMatchObject({
          role: "exact-date-memory",
          cards: [expect.objectContaining({ selectionKind: "exact_date" })],
        });
        if (sayingSection) {
          const sayingCard = sayingSection.cards[0];
          const sayingRecord = sayingRecordById.get(sayingCard.id);

          expect(sayingRecord, `${language} ${dayKey}: known saying`).toBeTruthy();
          expect(
            getDiscoverTemporalRank(sayingRecord, today),
            `${language} ${dayKey}: saying matches date`,
          ).not.toBeNull();
        }
        expect(archiveSection, `${language} ${dayKey}: documented archive`).toMatchObject({
          role: "archive-rotation",
          cards: [expect.objectContaining({ sourceLabel: expect.any(String) })],
        });
        const archiveCard = archiveSection.cards[0];
        const archiveRecord = culturalRecordById.get(archiveCard.id);
        expect(archiveRecord, `${language} ${dayKey}: known archive record`).toBeTruthy();
        expect(archiveCard.sourceLabel, `${language} ${dayKey}: original source credit`).toBe(
          archiveRecord.source.label,
        );
        expect(
          getDiscoverTemporalRank(archiveRecord, today),
          `${language} ${dayKey}: archive matches date`,
        ).not.toBeNull();
        expect(archiveCard.seasonLabel).toBe(getDiscoverSeasonLabel(
          getDiscoverSeasonForRecord(archiveRecord, today),
          language,
        ));
        expect(
          visibleCards.every((card) => (
            card.title && (card.text || sayingRecordById.has(card.id))
          )),
          `${language} ${dayKey}: complete localized copy`,
        ).toBe(true);
        expect(
          new Set(visibleContentKeys).size,
          `${language} ${dayKey}: no duplicated content`,
        ).toBe(visibleContentKeys.length);
      }
    });
  }
});
