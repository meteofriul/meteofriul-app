import { describe, expect, it } from "vitest";

import {
  getDailyHistoryMemoryFinalReview,
  getDailyHistoryMemoryFinalReviewIds,
  getDailyHistoryMemoryFinalReviewSummary,
} from "./dailyHistoryMemoryFinalReview";

describe("daily history memory final review", () => {
  it("keeps the first thirty-six reviewed candidates explicit and ordered", () => {
    expect(getDailyHistoryMemoryFinalReviewIds()).toEqual([
      "memory-copy-0818-gaetano-kanizsa",
      "memory-copy-1015-giovanni-da-udine",
      "memory-copy-0121-tito-maniacco",
      "memory-copy-0615-lojze-spacal",
      "memory-copy-0603-giovanni-battista-bassi",
      "memory-copy-0507-gianni-bisiach",
      "memory-copy-0504-lojzka-bratuz",
      "memory-copy-0429-valentin-stanic",
      "memory-copy-0412-gillo-dorfles",
      "memory-copy-1005-giorgio-pressburger",
      "memory-copy-0120-luca-carlevarijs",
      "memory-copy-0411-matteo-pertsch",
      "memory-copy-0616-stanislaus-joyce",
      "memory-copy-0205-napoleone-cozzi",
      "memory-copy-0813-lella-vignelli",
      "memory-copy-0902-adalgiso-fior",
      "memory-copy-1013-marcello-de-stefano",
      "memory-copy-0820-enrico-rava",
      "memory-copy-0316-ernesto-nathan-rogers",
      "memory-copy-0409-stefan-kociancic",
      "memory-copy-0705-flavio-paulin",
      "memory-copy-0318-eugenio-pilutti",
      "memory-copy-0708-lelio-luttazzi",
      "memory-copy-0706-alberto-spaini",
      "memory-copy-0709-aldo-stellita",
      "memory-copy-1111-giorgio-voghera",
      "memory-copy-1122-silvio-benco",
      "memory-copy-0225-eugenio-geiringer",
      "memory-copy-0325-giulio-camagni",
      "memory-copy-0410-claudio-magris",
      "memory-copy-0304-afro-basaldella",
      "memory-copy-1017-carlo-michelstaedter",
      "memory-copy-0629-biagio-marin",
      "memory-copy-0826-novella-cantarutti",
      "memory-copy-1001-pierluigi-cappello",
      "memory-copy-1007-giovanni-battista-brusin",
    ]);
  });

  it("publishes the primary and secondary reviewed memories", () => {
    const summary = getDailyHistoryMemoryFinalReviewSummary();

    expect(summary).toMatchObject({
      totalRecords: 36,
      byDecision: {
        source_ok_for_staging: 36,
      },
      byPublishDecision: {
        not_ready_for_ui: 15,
        ready_for_ui: 21,
      },
      byEditorialRank: {
        A: 10,
        B: 17,
        C: 9,
      },
      byEditorialSurface: {
        archive: 15,
        daily_primary: 10,
        daily_secondary: 11,
      },
      dailyPrimaryCandidateIds: [
        "memory-copy-0818-gaetano-kanizsa",
        "memory-copy-1015-giovanni-da-udine",
        "memory-copy-0121-tito-maniacco",
        "memory-copy-0615-lojze-spacal",
        "memory-copy-0410-claudio-magris",
        "memory-copy-0304-afro-basaldella",
        "memory-copy-1017-carlo-michelstaedter",
        "memory-copy-0629-biagio-marin",
        "memory-copy-0826-novella-cantarutti",
        "memory-copy-1001-pierluigi-cappello",
      ],
      dailySecondaryCandidateIds: [
        "memory-copy-0603-giovanni-battista-bassi",
        "memory-copy-0504-lojzka-bratuz",
        "memory-copy-0429-valentin-stanic",
        "memory-copy-1005-giorgio-pressburger",
        "memory-copy-0120-luca-carlevarijs",
        "memory-copy-0411-matteo-pertsch",
        "memory-copy-0902-adalgiso-fior",
        "memory-copy-0316-ernesto-nathan-rogers",
        "memory-copy-0409-stefan-kociancic",
        "memory-copy-0225-eugenio-geiringer",
        "memory-copy-1007-giovanni-battista-brusin",
      ],
      archiveCandidateIds: [
        "memory-copy-0507-gianni-bisiach",
        "memory-copy-0412-gillo-dorfles",
        "memory-copy-0616-stanislaus-joyce",
        "memory-copy-0205-napoleone-cozzi",
        "memory-copy-0813-lella-vignelli",
        "memory-copy-1013-marcello-de-stefano",
        "memory-copy-0820-enrico-rava",
        "memory-copy-0705-flavio-paulin",
        "memory-copy-0318-eugenio-pilutti",
        "memory-copy-0708-lelio-luttazzi",
        "memory-copy-0706-alberto-spaini",
        "memory-copy-0709-aldo-stellita",
        "memory-copy-1111-giorgio-voghera",
        "memory-copy-1122-silvio-benco",
        "memory-copy-0325-giulio-camagni",
      ],
      recordsWithoutEditorialTriage: [],
      furApproved: 21,
      readyForUi: 21,
      recordsReadyForPublish: [
        "memory-copy-0818-gaetano-kanizsa",
        "memory-copy-1015-giovanni-da-udine",
        "memory-copy-0121-tito-maniacco",
        "memory-copy-0615-lojze-spacal",
        "memory-copy-0603-giovanni-battista-bassi",
        "memory-copy-0504-lojzka-bratuz",
        "memory-copy-0429-valentin-stanic",
        "memory-copy-1005-giorgio-pressburger",
        "memory-copy-0120-luca-carlevarijs",
        "memory-copy-0411-matteo-pertsch",
        "memory-copy-0902-adalgiso-fior",
        "memory-copy-0316-ernesto-nathan-rogers",
        "memory-copy-0409-stefan-kociancic",
        "memory-copy-0225-eugenio-geiringer",
        "memory-copy-0410-claudio-magris",
        "memory-copy-0304-afro-basaldella",
        "memory-copy-1017-carlo-michelstaedter",
        "memory-copy-0629-biagio-marin",
        "memory-copy-0826-novella-cantarutti",
        "memory-copy-1001-pierluigi-cappello",
        "memory-copy-1007-giovanni-battista-brusin",
      ],
      recordsWithoutBlockers: [
        "memory-copy-0818-gaetano-kanizsa",
        "memory-copy-1015-giovanni-da-udine",
        "memory-copy-0121-tito-maniacco",
        "memory-copy-0615-lojze-spacal",
        "memory-copy-0603-giovanni-battista-bassi",
        "memory-copy-0504-lojzka-bratuz",
        "memory-copy-0429-valentin-stanic",
        "memory-copy-1005-giorgio-pressburger",
        "memory-copy-0120-luca-carlevarijs",
        "memory-copy-0411-matteo-pertsch",
        "memory-copy-0902-adalgiso-fior",
        "memory-copy-0316-ernesto-nathan-rogers",
        "memory-copy-0409-stefan-kociancic",
        "memory-copy-0225-eugenio-geiringer",
        "memory-copy-0410-claudio-magris",
        "memory-copy-0304-afro-basaldella",
        "memory-copy-1017-carlo-michelstaedter",
        "memory-copy-0629-biagio-marin",
        "memory-copy-0826-novella-cantarutti",
        "memory-copy-1001-pierluigi-cappello",
        "memory-copy-1007-giovanni-battista-brusin",
      ],
      recordsWithoutSourceReview: [],
    });
  });

  it("keeps FUR review and UI readiness as explicit blockers for unpublished records", () => {
    const records = getDailyHistoryMemoryFinalReview();
    const unpublishedRecords = records.filter((record) => record.publishDecision !== "ready_for_ui");

    expect(unpublishedRecords.every((record) => (
      record.remainingBlockers.includes("fur_human_review") &&
      record.remainingBlockers.includes("ready_for_discover_status") &&
      record.remainingBlockers.includes("ready_for_ui_flag")
    ))).toBe(true);
    expect(unpublishedRecords.every((record) => record.copyReview.fur === "human_review_needed")).toBe(true);
    expect(records.filter((record) => record.publishDecision === "ready_for_ui").every((record) => (
      record.copyReview.fur === "approved" && record.remainingBlockers.length === 0
    ))).toBe(true);
    expect(records.every((record) => record.sourceReview.url.startsWith("https://www.wikidata.org/wiki/"))).toBe(true);
  });

  it("keeps source verification separate from editorial publication value", () => {
    const records = getDailyHistoryMemoryFinalReview();
    const bisiach = records.find((record) => record.id === "memory-copy-0507-gianni-bisiach");
    const dorfles = records.find((record) => record.id === "memory-copy-0412-gillo-dorfles");
    const kanizsa = records.find((record) => record.id === "memory-copy-0818-gaetano-kanizsa");
    const rava = records.find((record) => record.id === "memory-copy-0820-enrico-rava");
    const fior = records.find((record) => record.id === "memory-copy-0902-adalgiso-fior");

    expect(bisiach.editorialTriage).toMatchObject({
      rank: "C",
      surface: "archive",
    });
    expect(dorfles.editorialTriage).toMatchObject({
      rank: "B",
      surface: "archive",
    });
    expect(kanizsa.editorialTriage).toMatchObject({
      rank: "A",
      surface: "daily_primary",
    });
    expect(rava.editorialTriage).toMatchObject({
      rank: "B",
      surface: "archive",
    });
    expect(fior.editorialTriage).toMatchObject({
      rank: "B",
      surface: "daily_secondary",
    });
  });

  it("documents the two review notes that affect final copy choices", () => {
    const records = getDailyHistoryMemoryFinalReview();
    const giovanni = records.find((record) => record.id === "memory-copy-1015-giovanni-da-udine");
    const bassi = records.find((record) => record.id === "memory-copy-0603-giovanni-battista-bassi");
    const dorfles = records.find((record) => record.id === "memory-copy-0412-gillo-dorfles");

    expect(giovanni.sourceReview.note).toContain("Zuan di Udin");
    expect(giovanni.copyReview.note).toContain("Zuan di Udin");
    expect(bassi.sourceReview.note).toContain("Pordenone");
    expect(dorfles.sourceReview.note).toContain("data alternativa");
  });
});
