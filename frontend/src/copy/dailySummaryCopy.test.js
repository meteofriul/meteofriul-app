import { describe, expect, it } from "vitest";

import { getDailySummaryCopy } from "./dailySummaryCopy";

describe("dailySummaryCopy", () => {
  it("returns IT copy for the Home daily summary card", () => {
    const copy = getDailySummaryCopy("it");

    expect(copy.bulletinCtaLabel).toBe("Apri bollettino OSMER");
    expect(copy.currentSummaryFallback).toBe("Sintesi meteo in aggiornamento.");
    expect(copy.locationLabel).toBe("Località");
    expect(copy.regionalBulletinAvailable).toBe("Bollettino regionale OSMER disponibile.");
    expect(copy.officialTextPendingLabel).toBe("");
  });

  it("returns FUR copy for the Home daily summary card", () => {
    const copy = getDailySummaryCopy("fur");

    expect(copy.bulletinCtaLabel).toBe("Vierç boletin OSMER");
    expect(copy.currentSummaryFallback).toBe("Sintesi meteo in inzornament.");
    expect(copy.locationLabel).toBe("Localitât");
    expect(copy.regionalBulletinAvailable).toBe("Boletin regjonâl OSMER disponibil.");
    expect(copy.officialTextPendingLabel).toBe("Test uficiâl in talian - FUR in revision");
  });

  it("falls back to IT for unknown languages", () => {
    expect(getDailySummaryCopy("unknown").bulletinCtaLabel).toBe("Apri bollettino OSMER");
  });
});
