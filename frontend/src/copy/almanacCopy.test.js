import { describe, expect, it } from "vitest";

import {
  getAlmanacCopy,
  getAlmanacCulturalSourceLabel,
  getAlmanacHiddenOtherSaintsLabel,
  getAlmanacLunarAgeLabel,
  getAlmanacSourceLabel,
  getMoonNextHint,
} from "./almanacCopy";

describe("almanacCopy", () => {
  it("returns IT copy for the Almanacco UI", () => {
    const copy = getAlmanacCopy("it");

    expect(copy.title).toBe("L'Almanacco del giorno");
    expect(copy.farmingTitle).toBe("Consiglio della terra");
    expect(copy.nameDayPrefix).toBe("Onomastico");
    expect(copy.otherSaintsCollapseLabel).toBe("Mostra meno");
    expect(copy.otherSaintsLabel).toBe("Altri santi del giorno");
    expect(copy.openCta).toBe("Apri almanacco");
    expect(copy.textPendingReview).toBe("Testo in italiano - FUR in revisione");
  });

  it("returns FUR copy for the Almanac UI", () => {
    const copy = getAlmanacCopy("fur");

    expect(copy.title).toBe("L'Almanac dal dì");
    expect(copy.farmingTitle).toBe("Il consei de tiere");
    expect(copy.nameDayPrefix).toBe("Nons dal dì");
    expect(copy.otherSaintsCollapseLabel).toBe("Mostre mancul");
    expect(copy.otherSaintsLabel).toBe("Altris sants dal dì");
    expect(copy.openCta).toBe("Vierç Almanac");
    expect(copy.textPendingReview).toBe("Test in talian - FUR in revision");
  });

  it("falls back to IT for unknown languages", () => {
    expect(getAlmanacCopy("unknown").title).toBe("L'Almanacco del giorno");
    expect(getAlmanacLunarAgeLabel(3.25, "unknown")).toBe("Età lunare: 3.3 giorni");
  });

  it("keeps source labels explicit and localized", () => {
    expect(getAlmanacSourceLabel("Ostermann 1894, p. 60", "it")).toBe(
      "Da Ostermann 1894, con selezione editoriale Meteo Friul."
    );
    expect(getAlmanacCulturalSourceLabel("Ostermann 1894, p. 60", "fur")).toBe(
      "Di Ostermann 1894, cun selezion editoriâl Meteo Friul."
    );
    expect(getAlmanacSourceLabel("Archivio locale", "fur")).toBe("Selezion editoriâl Meteo Friul.");
  });

  it("formats moon copy without touching moon logic", () => {
    expect(getMoonNextHint({ id: "new", age: 1.2 }, "fur")).toBe(
      "Prossime: lune cressint · mancul di un dì"
    );
    expect(getAlmanacHiddenOtherSaintsLabel(3, "fur")).toBe("e altris 3");
  });
});
