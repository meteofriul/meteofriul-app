import { describe, expect, it } from "vitest";
import sources from "../../data/discover/municipalityMilestoneSources.json";
import research from "../../data/discover/municipalitySourceReview.ud-quality-10.json";
import { getMunicipalityProfile } from "./municipalityProfiles";

describe("verified milestone citations", () => {
  for (const language of ["it", "fur"]) {
    it(`exposes the verified sources in ${language}`, () => {
      const card = getMunicipalityProfile({ language, location: { istatCode: "030124", city: "Trasaghis" } });
      for (const item of research.reviews) {
        expect(sources[item.recordId]).toEqual(item.source);
        expect(card.milestones.find(m => m.id === item.recordId).source).toEqual(item.source);
      }
    });
  }
});
