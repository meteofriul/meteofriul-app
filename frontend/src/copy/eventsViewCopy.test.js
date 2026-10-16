import { describe, expect, it } from "vitest";
import {
  EVENTS_CATEGORY_FILTERS,
  EVENTS_TIME_TAB_IDS,
  getEventsBadgeCategoryLabel,
  getEventsCategoryFilterLabel,
  getEventsDateChipMonthLabel,
  getEventsDateFallbackLabel,
  getEventsTimeTabLabel,
  getEventsViewCopy,
} from "./eventsViewCopy";

describe("eventsViewCopy", () => {
  it("returns IT copy for the Eventi tab", () => {
    const copy = getEventsViewCopy("it");

    expect(copy.viewTitle).toBe("Eventi");
    expect(copy.locationLabel).toBe("Località");
    expect(copy.eventCountLabel).toBe("eventi");
    expect(copy.emptyBody).toBe("Mostriamo solo eventi con fonte e data affidabili.");
    expect(copy.fvgOnlyTitle).toBe("Eventi disponibili solo in FVG");
    expect(copy.fvgOnlyBody).toContain("{location}");
  });

  it("returns FUR copy for the Evenis tab", () => {
    const copy = getEventsViewCopy("fur");

    expect(copy.viewTitle).toBe("Evenis");
    expect(copy.locationLabel).toBe("Localitât");
    expect(copy.dateFallbackToday).toBe("Vuê");
    expect(copy.loadingTitle).toBe("O sin daûr a cirî evenis");
    expect(copy.fvgOnlyTitle).toBe("Evenis disponibii dome in FVG");
    expect(copy.fvgOnlyBody).toContain("{location}");
  });

  it("falls back to IT for unknown languages", () => {
    expect(getEventsViewCopy("unknown").viewTitle).toBe("Eventi");
    expect(getEventsDateFallbackLabel("unknown")).toBe("Oggi");
  });

  it("keeps Eventi filter ids stable while moving labels into copy", () => {
    expect(EVENTS_TIME_TAB_IDS).toEqual(["today", "weekend", "next"]);
    expect(EVENTS_CATEGORY_FILTERS.map(category => category.id)).toEqual([
      "all",
      "sagra",
      "food_wine",
      "mercato",
      "cultura",
      "convegni",
      "musica",
      "sport",
      "natura",
      "famiglia",
      "other",
    ]);
  });

  it("returns localized labels for Eventi filters and date chips", () => {
    expect(getEventsTimeTabLabel("next", "it", { short: true })).toBe("Prossimi");
    expect(getEventsTimeTabLabel("next", "fur")).toBe("Prossims dîs");
    expect(getEventsCategoryFilterLabel("sagra", "it")).toBe("Feste e sagre");
    expect(getEventsCategoryFilterLabel("sagra", "fur")).toBe("Sagris");
    expect(getEventsDateChipMonthLabel(5, "it")).toBe("GIU");
    expect(getEventsDateChipMonthLabel(5, "fur")).toBe("JUG");
  });

  it("keeps category badge labels localized without forcing unknown categories", () => {
    expect(getEventsBadgeCategoryLabel("sagra", "it")).toBe("Sagra / festa locale");
    expect(getEventsBadgeCategoryLabel("sagra", "fur")).toBe("Sagris / fiestis locâls");
    expect(getEventsBadgeCategoryLabel("musica", "fur")).toBe("Musiche");
    expect(getEventsBadgeCategoryLabel("unknown", "it")).toBe("Evento");
    expect(getEventsBadgeCategoryLabel("unknown", "it", { fallback: false })).toBeUndefined();
  });
});
