import { describe, expect, it } from "vitest";
import almanacProverbs from "../../data/almanac/proverbs.json";

import {
  getTraditionalSayingForDate,
  getTraditionalSayingRecords,
  getTraditionalSayingsSummary,
} from "./traditionalSayings";
import { getDiscoverTemporalRank } from "./discoverTemporalSelection";

const sourceWithPendingFur = {
  categories: {
    detto_meteo: { it: "Detto meteo", fur: "Dit dal timp" },
  },
  records: [
    {
      id: "ready-it-only",
      primaryUse: "discover",
      recommendedSurface: "discover",
      category: "detto_meteo",
      dateAnchors: [],
      priority: 1,
      title: { it: "Detto italiano", fur: "pending_review" },
      summary: { it: "Testo italiano.", fur: "pending_review" },
      dateLabel: { it: "rotazione", fur: "rotazion" },
      source: { label: "Ostermann 1894", type: "verified_source" },
      editorialStatus: "ready_for_discover",
      languageStatus: { it: "approved", fur: "pending_review" },
      readyForUi: true,
    },
  ],
};

describe("traditional sayings discover rubric", () => {
  it("keeps 80 reviewed sayings in Scopri and reuses Almanacco copy from one source", () => {
    const summary = getTraditionalSayingsSummary();
    const records = getTraditionalSayingRecords();

    expect(summary.totalRecords).toBe(80);
    expect(summary.readyForDiscoverRecords).toBe(80);
    expect(summary.approvedItRecords).toBe(80);
    expect(summary.approvedFurRecords).toBe(80);
    expect(summary.exactDateRecords).toBe(8);
    expect(summary.readyForUiRecords).toBe(80);
    expect(summary.almanacScheduleRecords).toBe(0);
    expect(records.map((record) => record.candidateId)).toEqual(expect.arrayContaining([
      "ostermann-062-san-macari-setembar",
      "ostermann-062-san-ruperto-lui",
      "ost-discover-130-neve-pane-pioggia-fame",
      "ost-discover-140-arcobaleno-annata",
      "ost-discover-141-arcobaleno-tempo",
      "ost-discover-193-pasqua-fieno",
      "ost1876-sante-catarine-fred-caretine",
      "ost1876-ombrene-avost-panze-genar",
      "ost1876-epifanie-fiestis-vie",
      "ost1876-san-valantin-svinte",
      "ost1876-cuc-dafa-par-dut",
      "ost1876-sant-antoni-ore-lus",
      "ost1876-union-fas-fuarce",
      "ost1876-nol-baste-scomenca-seguita",
      "ostermann-mulinars",
      "ostermann-barbe-mus",
      "ost1876-cjase-braide-prat",
      "ost1876-ogni-vit-so-pal",
      "ost1876-troi-batit-no-jerbe",
      "ost1876-rive-prin-mulin",
      "ost1876-roste-denant-aghe",
      "ost1876-no-comede-picule-buse",
      "ost1876-cjar-cence-tamon-fossal",
      "ost1876-ogni-pais-so-usance",
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
      "ostermann-mus-vene",
      "ost1876-cjacaris-lungjis-gnot-curte",
      "ost1876-nissun-nas-mestri",
    ]));
    expect(records.filter((record) => record.reusedFromAlmanac)).toHaveLength(69);
  });

  it("reuses the three new everyday sayings verbatim with their original approval and no invented calendar", () => {
    const records = getTraditionalSayingRecords();
    ["ostermann-mus-vene", "ost1876-cjacaris-lungjis-gnot-curte", "ost1876-nissun-nas-mestri"]
      .forEach((id) => {
        const proverb = almanacProverbs.find((record) => record.id === id);
        const matches = records.filter((record) => record.candidateId === id);
        expect(matches).toHaveLength(1);
        expect(proverb.editorialReview).toMatchObject({ it: "approved", fur: "approved" });
        expect(matches[0]).toMatchObject({
          id: `saying-almanac-${id}`,
          title: { it: proverb.it, fur: proverb.fur },
          summary: { it: "", fur: "" },
          recurrence: "always",
          dateAnchors: [], dateRanges: [], movableDates: [], months: [], seasons: [],
          source: { verifiedAgainst: proverb.source, sourcePath: "frontend/src/data/almanac/proverbs.json" },
          editorialReview: { reviewedAt: proverb.editorialReview.reviewedAt },
          reusedFromAlmanac: true,
        });
        expect(getDiscoverTemporalRank(matches[0], "2028-01-01")).toBe(4);
        expect(getDiscoverTemporalRank(matches[0], "2028-07-01")).toBe(4);
      });
  });

  it("keeps the three new calendar sayings on their exact dates", () => {
    expect(getTraditionalSayingForDate({ date: "2026-01-06" })).toMatchObject({
      id: "saying-ost1876-epifanie-fiestis-vie",
      typeLabel: "Calendario popolare",
      selectionKind: "exact_date",
    });
    expect(getTraditionalSayingForDate({ date: "2026-02-14", language: "fur" })).toMatchObject({
      id: "saying-ost1876-san-valantin-svinte",
      title: "Il vint di Sant Valantin",
      selectionKind: "exact_date",
    });
    expect(getTraditionalSayingForDate({ date: "2026-11-25" })).toMatchObject({
      id: "saying-ost1876-sante-catarine-fred-caretine",
      selectionKind: "exact_date",
    });
  });

  it("keeps dated Almanacco sayings outside the general rotation pool", () => {
    const recordsByCandidate = new Map(
      getTraditionalSayingRecords().map((record) => [record.candidateId, record]),
    );
    const sanNicolo = recordsByCandidate.get("ost1876-san-nicolo-fred-cumo");
    const beforeChristmas = recordsByCandidate.get("ost1876-nef-prime-nadal-regal");
    const canicola = recordsByCandidate.get("ostermann-029-canicule-bagnat-sut");
    const twelveDays = recordsByCandidate.get("ostermann-062-sis-dis-an-mesais");
    const santEgidi = recordsByCandidate.get("ostermann-063-sant-egidi-color-mes");

    expect(sanNicolo).toMatchObject({ recurrence: "fixed_date", dateAnchors: ["12-06"] });
    expect(getDiscoverTemporalRank(sanNicolo, "2026-12-06")).toBe(0);
    expect(getDiscoverTemporalRank(sanNicolo, "2026-12-07")).toBeNull();

    expect(beforeChristmas).toMatchObject({
      recurrence: "date_range",
      dateRanges: ["12-01..12-24"],
    });
    expect(getDiscoverTemporalRank(beforeChristmas, "2026-12-01")).toBe(2);
    expect(getDiscoverTemporalRank(beforeChristmas, "2026-12-24")).toBe(2);
    expect(getDiscoverTemporalRank(beforeChristmas, "2026-12-25")).toBeNull();

    expect(canicola).toMatchObject({
      recurrence: "date_range",
      dateRanges: ["07-21..08-23"],
    });
    expect(getDiscoverTemporalRank(canicola, "2026-07-20")).toBeNull();
    expect(getDiscoverTemporalRank(canicola, "2026-07-21")).toBe(2);
    expect(getDiscoverTemporalRank(canicola, "2026-08-24")).toBeNull();

    expect(twelveDays).toMatchObject({
      recurrence: "date_range",
      dateRanges: ["12-26..01-06"],
    });
    expect(getDiscoverTemporalRank(twelveDays, "2026-01-06")).toBe(2);
    expect(getDiscoverTemporalRank(twelveDays, "2026-01-07")).toBeNull();

    expect(santEgidi).toMatchObject({ recurrence: "fixed_date", dateAnchors: ["09-01"] });
    expect(getDiscoverTemporalRank(santEgidi, "2026-09-01")).toBe(0);
    expect(getDiscoverTemporalRank(santEgidi, "2026-09-02")).toBeNull();
  });

  it("normalizes inherited Almanacco date ranges to the runtime format", () => {
    const reused = getTraditionalSayingRecords().filter((record) => record.reusedFromAlmanac);

    expect(reused.flatMap((record) => record.dateRanges).every((range) => (
      typeof range === "string" && /^\d{2}-\d{2}\.\.\d{2}-\d{2}$/.test(range)
    ))).toBe(true);
  });

  it("rotates the August and cuckoo sayings only inside their declared periods", () => {
    const auditYears = [2026, 2027, 2028];
    const augustCards = auditYears.flatMap((year) => (
      Array.from({ length: 31 }, (_, index) => (
        getTraditionalSayingForDate({
          date: `${year}-08-${String(index + 1).padStart(2, "0")}`,
        })
      ))
    ));
    const springSummerCards = auditYears.flatMap((year) => (
      Array.from({ length: 184 }, (_, index) => {
        const date = new Date(year, 2, 1 + index);
        return getTraditionalSayingForDate({ date });
      })
    ));

    expect(augustCards.some((card) => card?.id === "saying-ost1876-ombrene-avost-panze-genar")).toBe(true);
    expect(springSummerCards.some((card) => card?.id === "saying-ost1876-cuc-dafa-par-dut")).toBe(true);
    expect(getTraditionalSayingForDate({ date: "2026-09-15" })?.id)
      .not.toBe("saying-ost1876-ombrene-avost-panze-genar");
    expect(getTraditionalSayingForDate({ date: "2026-12-15" })?.id)
      .not.toBe("saying-ost1876-cuc-dafa-par-dut");
  });

  it("selects San Macari on its exact anchor date", () => {
    expect(getTraditionalSayingForDate({ date: "2026-01-02" })).toMatchObject({
      id: "saying-ostermann-san-macari-setembar",
      title: "San Macario e settembre",
      typeLabel: "Detto meteo",
      seasonLabel: "2 gennaio / settembre",
      selectionKind: "exact_date",
    });
  });

  it("selects San Ruperto on its exact anchor date", () => {
    expect(getTraditionalSayingForDate({ date: "2026-03-27", language: "fur" })).toMatchObject({
      id: "saying-ostermann-san-ruperto-lui",
      title: "San Ruperto e Lui",
      typeLabel: "Dit dal timp",
      seasonLabel: "27 di Març / Lui",
      selectionKind: "exact_date",
    });
  });

  it("rotates only sayings compatible with the current month", () => {
    const date = "2026-07-05";
    const card = getTraditionalSayingForDate({ date });
    const sourceRecord = getTraditionalSayingRecords()
      .find((record) => record.id === card?.id);

    expect(card).toBeTruthy();
    expect(sourceRecord).toBeTruthy();
    expect(getDiscoverTemporalRank(sourceRecord, date)).not.toBeNull();
    expect(card.title).not.toContain("Pasqua");
  });

  it("publishes the snow and bread saying as a winter Scopri note", () => {
    const winterCards = Array.from({ length: 365 }, (_, index) => {
      const date = new Date(2026, 0, 1 + index);
      return [0, 1, 11].includes(date.getMonth())
        ? getTraditionalSayingForDate({ date })
        : null;
    });
    const card = winterCards.find((candidate) => (
      candidate?.id === "saying-ostermann-neve-pane-pioggia"
    ));

    expect(card).toMatchObject({
      id: "saying-ostermann-neve-pane-pioggia",
      title: "Neve, pane e pioggia",
      seasonLabel: "inverno",
      sourceLabel: "Ostermann 1894",
    });
  });

  it("does not merge the Easter saying with the July Sant'Anacleto reference", () => {
    const card = getTraditionalSayingForDate({ date: "2026-07-15" });
    const furCard = getTraditionalSayingForDate({ date: "2026-07-15", language: "fur" });

    expect(card?.id).not.toBe("saying-ostermann-pasqua-fieno");
    expect(card?.title).not.toContain("Pasqua");
    expect(card?.seasonLabel).not.toContain("15 luglio");
    expect(furCard?.id).not.toBe("saying-ostermann-pasqua-fieno");
    expect(furCard?.title).not.toContain("Pasche");
    expect(furCard?.seasonLabel).not.toContain("15 di Lui");
  });

  it("selects the Easter saying on Easter instead of rotating it all year", () => {
    expect(getTraditionalSayingForDate({ date: "2026-04-05" })).toMatchObject({
      id: "saying-ostermann-pasqua-fieno",
      title: "Pasqua, pioggia e fieno",
      seasonLabel: "Pasqua",
      selectionKind: "movable_date",
    });
    expect(getTraditionalSayingForDate({ date: "2026-04-05", language: "fur" })).toMatchObject({
      id: "saying-ostermann-pasqua-fieno",
      title: "Pasche, ploie e fen",
      seasonLabel: "Pasche",
      selectionKind: "movable_date",
    });
  });

  it("uses the approved general pool when no dated or seasonal saying fits", () => {
    const card = getTraditionalSayingForDate({ date: "2026-11-12" });
    const sourceRecord = getTraditionalSayingRecords().find((record) => record.id === card?.id);

    expect(card).toMatchObject({
      selectionKind: "rotation",
      sourceLabel: sourceRecord.source.label,
    });
    expect(sourceRecord).toMatchObject({ recurrence: "always" });
    expect(sourceRecord.dateAnchors).toEqual([]);
    expect(sourceRecord.dateRanges).toEqual([]);
  });

  it("hides the rubric in FUR when FUR is not approved", () => {
    expect(getTraditionalSayingForDate({
      date: "2026-07-05",
      language: "fur",
      source: sourceWithPendingFur,
    })).toBeNull();
  });
});
