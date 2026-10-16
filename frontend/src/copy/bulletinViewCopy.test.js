import { describe, expect, it } from "vitest";

import { formatBulletinEmission, getBulletinHeading, getBulletinViewCopy } from "./bulletinViewCopy";

describe("bulletinViewCopy", () => {
  it("returns IT copy for bulletin UI labels", () => {
    const copy = getBulletinViewCopy("it");

    expect(copy.title).toBe("Bollettino FVG");
    expect(copy.officialExternalLabel).toBe("Apri il bollettino ufficiale ARPA FVG OSMER");
    expect(copy.translationCredit).toBe("");
    expect(copy.areaLabels.highPlain).toBe("Alta pianura");
  });

  it("returns FUR copy for bulletin UI labels", () => {
    const copy = getBulletinViewCopy("fur");

    expect(copy.title).toBe("Boletin FVG");
    expect(copy.officialExternalLabel).toBe("Vierç il boletin uficiâl ARPA FVG OSMER");
    expect(copy.translationCredit).toBe("Traduzione a cura di Meteo Friul");
    expect(copy.areaLabels.coast).toBe("Cueste");
  });

  it("formats bulletin emission labels without changing source dates", () => {
    expect(formatBulletinEmission("16-06-2026 12:25", "it")).toBe("16/06/2026 alle 12:25");
    expect(formatBulletinEmission("16-06-2026 12:25", "fur")).toBe("16/06/2026 aes 12:25");
    expect(formatBulletinEmission("non disponibile", "fur")).toBe("non disponibile");
  });

  it("formats non-trend headings with localized prefixes", () => {
    expect(getBulletinHeading("sabato 20 giugno", false, "it")).toBe("Previsioni per sabato 20 giugno");
    expect(getBulletinHeading("sabide 20 Jugn", false, "fur")).toBe("Previsions par sabide 20 Jugn");
    expect(getBulletinHeading("Tendenza", true, "it")).toBe("Tendenza");
  });

  it("falls back to IT for unknown languages", () => {
    expect(getBulletinViewCopy("unknown").title).toBe("Bollettino FVG");
  });
});
