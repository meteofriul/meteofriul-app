import { describe, expect, it } from "vitest";

import almanacProverbs from "../../data/almanac/proverbs.json";
import almanacReuse from "../../data/discover/traditionalSayingAlmanacReuse.json";
import { getTraditionalSayingRecords } from "./traditionalSayings";

const WAVE_02_SAYING_IDS = [
  "ost1876-genar-febrar-marc",
  "ost1876-febrar-un-di-ben",
  "ost1876-san-nicolo-fred-cumo",
  "ost1876-nef-prime-nadal-regal",
  "ost1876-prime-ploe-avost-bosc",
  "ost1876-avril-ploe-sutil",
  "ostermann-103-no-mai-ploe",
  "ostermann-105-bon-timp-gnot",
  "ostermann-105-aghe-pais",
  "ostermann-190-marz-avril-mai",
  "ostermann-126-bruntule-tempieste",
  "ostermann-126-tempieste-no-charestie",
  "ostermann-132-prime-nev-plan",
  "ostermann-029-canicule-bagnat-sut",
  "ostermann-062-sis-dis-an-mesais",
  "ostermann-063-otubar-febrar",
  "ostermann-063-sant-egidi-color-mes",
  "ost1876-ploe-stagion-tesaur",
  "ost1876-se-semena-vece-forment",
  "ost1876-ogni-jerbe-semence",
];

describe("discover daily editorial expansion wave 02", () => {
  it("reuses twenty approved bilingual sayings without copying their text", () => {
    const proverbsById = new Map(almanacProverbs.map((record) => [record.id, record]));
    const descriptorsById = new Map(
      almanacReuse.records.map((record) => [record.proverbId, record]),
    );
    const discoverByCandidateId = new Map(
      getTraditionalSayingRecords().map((record) => [record.candidateId, record]),
    );

    expect(WAVE_02_SAYING_IDS).toHaveLength(20);
    expect(new Set(WAVE_02_SAYING_IDS).size).toBe(20);

    WAVE_02_SAYING_IDS.forEach((id) => {
      const proverb = proverbsById.get(id);
      const descriptor = descriptorsById.get(id);
      const discoverRecord = discoverByCandidateId.get(id);

      expect(descriptor).toBeTruthy();
      expect(proverb).toMatchObject({
        almanacEligible: true,
        editorialReview: { it: "approved", fur: "approved" },
      });
      expect(discoverRecord).toMatchObject({
        candidateId: id,
        reusedFromAlmanac: true,
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
      });
      expect(discoverRecord.title).toEqual({ it: proverb.it, fur: proverb.fur });
    });
  });

  it("adds explicit calendar context to the fourteen temporal sayings", () => {
    const descriptors = almanacReuse.records.filter((record) => (
      WAVE_02_SAYING_IDS.includes(record.proverbId)
    ));
    const temporalDescriptors = descriptors.filter((record) => (
      record.dateAnchors?.length
      || record.dateRanges?.length
      || record.months?.length
      || record.seasons?.length
    ));

    expect(temporalDescriptors).toHaveLength(14);
    temporalDescriptors.forEach((record) => {
      expect(record.dateLabel?.it).toBeTruthy();
      expect(record.dateLabel?.fur).toBeTruthy();
    });

    expect(getTraditionalSayingRecords().find((record) => (
      record.candidateId === "ostermann-062-sis-dis-an-mesais"
    ))).toMatchObject({
      dateAnchors: [],
      dateRanges: ["12-26..01-06"],
      recurrence: "date_range",
    });
    expect(getTraditionalSayingRecords().find((record) => (
      record.candidateId === "ost1876-nef-prime-nadal-regal"
    ))).toMatchObject({
      dateRanges: ["12-01..12-24"],
      recurrence: "date_range",
    });
    expect(getTraditionalSayingRecords().find((record) => (
      record.candidateId === "ostermann-029-canicule-bagnat-sut"
    ))).toMatchObject({
      dateRanges: ["07-21..08-23"],
      recurrence: "date_range",
    });
  });
});
