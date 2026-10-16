import { describe, expect, it } from "vitest";
import {
  getDiscoverCopy,
  getDiscoverSeasonLabel,
  getDiscoverTitle,
  getDiscoverTypeLabel,
} from "./discoverCopy";

describe("discoverCopy", () => {
  it("returns IT and FUR titles", () => {
    expect(getDiscoverTitle("it")).toBe("Scopri");
    expect(getDiscoverTitle("fur")).toBe("Scuvierç");
  });

  it("returns FUR microcopy used by the Scuvierç tab", () => {
    const copy = getDiscoverCopy("fur");

    expect(copy.focus).toBe("In evidencie");
    expect(copy.municipalitySectionTitle).toBe("Comun dal dì");
    expect(copy.municipalityKicker).toBe("Storie e teritori");
    expect(copy.municipalityMilestonesTitle).toBe("Tapis storichis");
    expect(copy.exactMemoryTitle).toBe("Memorie dal dì");
    expect(copy.localMemoryFallbackTitle).toBe("Storiis dal teritori");
    expect(copy.traditionalSayingsTitle).toBe("Si diseve che...");
    expect(copy.relatedTitle).toBe("In risonance vuê");
    expect(copy.editorialSourceLine).toBe("Selezion editoriâl Meteo Friul.");
    expect(copy.furPending).toBe("Test in talian - FUR in revision");
  });

  it("falls back to IT copy for unknown languages", () => {
    expect(getDiscoverCopy("unknown").exactMemoryTitle).toBe("Memoria del giorno");
    expect(getDiscoverCopy("unknown").relatedTitle).toBe("In risonanza oggi");
  });

  it("returns localized season labels with safe fallback", () => {
    expect(getDiscoverSeasonLabel("estate", "fur")).toBe("Istât");
    expect(getDiscoverSeasonLabel("unknown", "fur")).toBe("Dut l'an");
    expect(getDiscoverSeasonLabel("autunno", "unknown")).toBe("Autunno");
  });

  it("returns localized type labels with safe fallback", () => {
    expect(getDiscoverTypeLabel("astronomia", "fur")).toBe("Lune e stelis");
    expect(getDiscoverTypeLabel("archivio", "it")).toBe("Archivio");
    expect(getDiscoverTypeLabel("storia_locale", "fur")).toBe("Storie locâl");
    expect(getDiscoverTypeLabel("vita_quotidiana", "fur")).toBe("Vite di ogni dì");
    expect(getDiscoverTypeLabel("unknown", "fur")).toBe("Almanac");
    expect(getDiscoverTypeLabel("meteo_popolare", "unknown")).toBe("Meteo popolare");
  });
});
