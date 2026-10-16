import { describe, expect, it } from "vitest";

import {
  getCommunityActiveCount,
  getCommunityActiveSummary,
  getCommunityAvailability,
  getCommunityConfirmationSummary,
  getCommunityContributionLabel,
  getCommunityDenialLabel,
  getCommunityMapWithdrawalLabel,
  getCommunityNearbyMatchSummary,
  getCommunityRecentSummary,
  getCommunityUpdatedLabel,
  getOwnReportExpiryLabel,
} from "./communitySocialPresentation";

const copy = {
  communityActiveSummaryMany: "{count} segnalazioni attive",
  communityActiveSummaryOne: "1 segnalazione attiva",
  communityRecentSummaryMany: "{count} segnalazioni recenti",
  communityRecentSummaryOne: "1 segnalazione recente",
  communityStateAging: "Da aggiornare",
  communityStateMixed: "Segnalazioni discordanti",
  communityStateNew: "Nuova",
  communityUpdatedMinutesAgo: "Aggiornato {minutes} min fa",
  communityUpdatedNow: "Aggiornato adesso",
  communityUpdatedUnknown: "Aggiornamento recente",
  confirmationRecentMany: "{count} conferme recenti",
  confirmationRecentOne: "1 conferma recente",
  denialCountMany: "{count} smentite",
  denialCountOne: "1 smentita",
  denialMapRemoved: "Rimossa dalla mappa",
  communityContributionToday: "Contributi di oggi · {count}",
  communityMatchMany: "Ci sono già {count} riscontri di {phenomenon} qui",
  communityMatchOne: "C’è già 1 riscontro di {phenomenon} qui",
  ownReportExpiresIn: "Scade tra {minutes} min",
};

describe("communitySocialPresentation", () => {
  it("counts active reports inside grouped cards", () => {
    expect(getCommunityActiveCount([{ count: 3 }, { count: 1 }])).toBe(4);
    expect(getCommunityActiveSummary(copy, 1)).toBe("1 segnalazione attiva");
    expect(getCommunityActiveSummary(copy, 4)).toBe("4 segnalazioni attive");
    expect(getCommunityRecentSummary(copy, 0)).toBe("0 segnalazioni recenti");
    expect(getCommunityRecentSummary(copy, 1)).toBe("1 segnalazione recente");
    expect(getCommunityRecentSummary(copy, 4)).toBe("4 segnalazioni recenti");
  });

  it("presents the private daily counter and nearby support without claiming people", () => {
    expect(getCommunityContributionLabel(copy, 2)).toBe("Contributi di oggi · 2");
    expect(getCommunityNearbyMatchSummary(copy, {
      confirmations: { yes: 2 },
      count: 1,
      typeLabel: "Pioggia",
    })).toBe("Ci sono già 3 riscontri di pioggia qui");
    expect(getCommunityNearbyMatchSummary(copy, {
      confirmations: { yes: 0 },
      count: 1,
      typeLabel: "Nebbia",
    })).toBe("C’è già 1 riscontro di nebbia qui");
  });

  it("uses neutral collaboration states instead of verification language", () => {
    expect(getCommunityConfirmationSummary(copy, { no: 0, yes: 0 })).toBe("Nuova");
    expect(getCommunityConfirmationSummary(copy, { no: 0, yes: 2 })).toBe("2 conferme recenti");
    expect(getCommunityConfirmationSummary(copy, { no: 1, yes: 2 }))
      .toBe("2 conferme recenti");
    expect(getCommunityConfirmationSummary(copy, { no: 2, yes: 0 })).toBe("Nuova");
  });

  it.each([
    [0, ""],
    [1, "1 smentita"],
    [2, "2 smentite"],
    [4, "4 smentite"],
  ])("presents the full denial total %s", (count, expected) => {
    expect(getCommunityDenialLabel(copy, { no: count, yes: 7 })).toBe(expected);
  });

  it("marks reports as removed from the map only at the denial threshold", () => {
    expect(getCommunityMapWithdrawalLabel(copy, { confirmations: { no: 2 } })).toBe("");
    expect(getCommunityMapWithdrawalLabel(copy, { confirmations: { no: 3 } }))
      .toBe("Rimossa dalla mappa");
    expect(getCommunityMapWithdrawalLabel(copy, { confirmations: { no: 4 } }))
      .toBe("Rimossa dalla mappa");
  });

  it("formats source freshness and own-report expiry", () => {
    const now = Date.parse("2026-08-28T10:10:00Z");
    const justOverSixtyMinutes = now + (60 * 60_000) + 30_000;

    expect(getCommunityUpdatedLabel(copy, {
      now,
      sourceUpdatedAt: "2026-08-28T10:08:00Z",
    })).toBe("Aggiornato 2 min fa");
    expect(getOwnReportExpiryLabel(copy, now + 61_000, now)).toBe("Scade tra 2 min");
    expect(getOwnReportExpiryLabel(copy, justOverSixtyMinutes, now)).toBe("Scade tra 61 min");
    expect(getOwnReportExpiryLabel(
      copy,
      justOverSixtyMinutes,
      now,
      { maxMinutes: 60 },
    )).toBe("Scade tra 60 min");
  });

  it("keeps loading, errors and true empty states distinct", () => {
    expect(getCommunityAvailability({ items: [], markers: [], status: { id: "loading" } }).kind).toBe("loading");
    expect(getCommunityAvailability({ items: [], markers: [], status: { id: "error" } }).kind).toBe("error");
    expect(getCommunityAvailability({ items: [], markers: [], status: { id: "fresh" } }).kind).toBe("empty");
    expect(getCommunityAvailability({ items: [], markers: [], status: { id: "cache" } }).kind).toBe("empty");
    expect(getCommunityAvailability({ items: [{ id: "one" }], status: { id: "cache" } }).kind).toBe("ready");
    expect(getCommunityAvailability({ items: [{ id: "one" }], status: { id: "stale" } }).kind).toBe("stale");
  });
});
