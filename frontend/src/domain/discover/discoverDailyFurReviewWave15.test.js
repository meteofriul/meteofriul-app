import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave15.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave15.json";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-0804-luigi-scrosoppi-educazione-e-cura-sociale",
  "memory-it-ready-0418-giovanni-battista-de-gasperi-geografia-e-grotte",
  "memory-it-ready-0920-ruggero-berlam-e-l-architettura-di-trieste",
  "memory-it-ready-0927-vittorio-vidali-antifascismo-e-conflitti-del-novecen",
  "memory-it-ready-0612-daniele-antonio-bertoli-alla-corte-imperiale",
  "memory-it-ready-1220-paolo-rumiz-viaggi-e-frontiere",
  "memory-it-ready-1119-giorgio-celiberti-arte-da-udine-all-europa",
  "memory-it-ready-0217-franco-vegliani-e-la-letteratura-di-frontiera",
  "memory-it-ready-0910-il-litorale-adriatico-sotto-occupazione-tedesca",
  "memory-it-ready-0918-viktor-dankl-da-udine-ai-fronti-della-grande-guerra",
];

const pendingId = "memory-it-ready-0910-il-litorale-adriatico-sotto-occupazione-tedesca";
const approvedIds = reviewedIds.filter((id) => id !== pendingId);

describe("Discover daily FUR review wave 15", () => {
  it("reviews exactly the ten Italian-selected records and excludes holds", () => {
    expect(reviewWave.summary).toEqual({
      totalRecords: 10,
      approved: 9,
      pendingHumanReview: 1,
    });
    expect(reviewWave.records.map((record) => record.id)).toEqual(reviewedIds);
    expect(reviewWave.records.filter((record) => record.status === "approved").map((record) => record.id)).toEqual(approvedIds);
    expect(reviewWave.records.find((record) => record.id === pendingId)?.status).toBe("pending_human_review");

    const canonicalIdsByCandidate = new Map(
      localMemory.records
        .filter((record) => record.candidateId)
        .map((record) => [record.candidateId, record.id]),
    );
    expect(italianWave.keepDaily.map((record) => canonicalIdsByCandidate.get(record.id))).toEqual(reviewedIds);
    expect(italianWave.hold.every((record) => !reviewedIds.includes(canonicalIdsByCandidate.get(record.id)))).toBe(true);
  });

  it("publishes wave 15 approved records and keeps the later wave 17 promotion visible", () => {
    const canonicalRecords = localMemory.records.filter((record) => approvedIds.includes(record.id));

    expect(canonicalRecords).toHaveLength(approvedIds.length);
    expect(canonicalRecords.every((record) => (
      record.editorialStatus === "ready_for_discover"
      && record.languageStatus.it === "approved"
      && record.languageStatus.fur === "approved"
      && record.readyForUi === true
      && record.source?.type === "verified_source"
    ))).toBe(true);

    expect(localMemory.records.find((record) => record.id === pendingId)).toMatchObject({
      editorialStatus: "ready_for_discover",
      languageStatus: {
        it: "approved",
        fur: "approved",
      },
      readyForUi: true,
    });
  });

  it("serves the five new primary dates in FUR", () => {
    expect(getLocalMemoryForDate({ date: "2026-09-27", language: "fur" })).toMatchObject({
      id: reviewedIds[3],
      title: "Vittorio Vidali, antifassisim e conflits dal Nûfcent",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-06-12", language: "fur" })).toMatchObject({
      id: reviewedIds[4],
      title: "Daniele Antonio Bertoli ae cort imperiâl",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-11-19", language: "fur" })).toMatchObject({
      id: reviewedIds[6],
      title: "Giorgio Celiberti, art di Udin ae Europe",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-02-17", language: "fur" })).toMatchObject({
      id: reviewedIds[7],
      title: "Franco Vegliani e la leterature di frontiere",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-09-18", language: "fur" })).toMatchObject({
      id: reviewedIds[9],
      title: "Viktor Dankl, di Udin ai fronts de Grande Vuere",
      selectionKind: "exact_date",
    });
  });

  it("keeps localized secondary memories secondary", () => {
    expect(getLocalMemorySecondaryForDate({
      date: "2026-04-18",
      language: "fur",
      location: { city: "Udine", province: "UD", region: "Friuli Venezia Giulia" },
    })).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: reviewedIds[1],
        title: "Giovanni Battista De Gasperi, gjeografie e grotis",
        dailyRole: "secondary",
        selectionKind: "exact_date_secondary",
      }),
    ]));

    const regionalRecord = localMemory.records.find((record) => record.id === reviewedIds[8]);
    expect(regionalRecord).toMatchObject({
      dailyRole: "secondary",
      areas: expect.arrayContaining(["friuli_venezia_giulia", "fvg"]),
      languageStatus: { fur: "approved" },
      readyForUi: true,
    });
    expect(regionalRecord.areas).not.toContain("udine");
  });

  it("orders multiple secondary memories on the same date by editorial priority", () => {
    const cards = getLocalMemorySecondaryForDate({
      date: "2026-09-20",
      language: "fur",
      location: { city: "Trieste", province: "TS", region: "Friuli Venezia Giulia" },
    });

    expect(cards.map((card) => card.id)).toEqual([
      "memory-it-ready-0920-marij-kogoj-musica-di-confine",
      "memory-it-ready-0920-ruggero-berlam-e-l-architettura-di-trieste",
    ]);
  });
});
