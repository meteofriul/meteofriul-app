import { describe, expect, it } from "vitest";

import municipalityPhotos from "../../data/discover/municipalityPhotos.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import municipalityVisuals from "../../data/discover/municipalityVisuals.json";
import { getMunicipalityVisual } from "./municipalityVisuals";

describe("getMunicipalityVisual", () => {
  it("returns a reviewed local photograph and crop for a municipality", () => {
    const visual = getMunicipalityVisual({ istatCode: "093033" });

    expect(visual).toMatchObject({
      coatOfArmsUrl: "/municipalities/coats/093033-coat.png",
      photoAlt: "",
      photoPosition: "50% 45%",
      photoUrl: "/municipalities/photos/093033-photo.webp",
    });
  });

  it("returns a reviewed local photograph outside the original pilot", () => {
    expect(getMunicipalityVisual({ istatCode: "030002" })).toMatchObject({
      photoAlt: "",
      photoPosition: "50% 50%",
      photoUrl: "/municipalities/photos/030002-photo.webp",
    });
  });

  it("covers every known municipality profile with one reviewed local photograph", () => {
    const photoCodes = municipalityPhotos.photos.map((photo) => photo.istatCode);
    const profileCodes = new Set(
      municipalityProfiles.profiles.map((profile) => profile.istatCode),
    );

    expect(new Set(photoCodes).size).toBe(215);
    expect([...photoCodes].sort()).toEqual([...profileCodes].sort());
    expect(municipalityPhotos.coverage).toEqual({
      profiles: 215,
      resolved: 215,
      unresolved: 0,
    });
    for (const istatCode of photoCodes) {
      expect(profileCodes.has(istatCode)).toBe(true);
      expect(getMunicipalityVisual({ istatCode }).photoUrl).toBe(
        `/municipalities/photos/${istatCode}-photo.webp`,
      );
    }
  });

  it("covers every reviewed municipality profile exactly once", () => {
    const visualCodes = municipalityVisuals.visuals.map((visual) => visual.istatCode);
    const profileCodes = municipalityProfiles.profiles.map((profile) => profile.istatCode);

    expect(new Set(visualCodes).size).toBe(215);
    expect([...visualCodes].sort()).toEqual([...profileCodes].sort());
    for (const istatCode of profileCodes) {
      expect(getMunicipalityVisual({ istatCode })?.coatOfArmsUrl).toMatch(
        new RegExp(`/municipalities/coats/${istatCode}-coat\\.(?:png|jpg)$`),
      );
    }
  });

  it("returns no visual for an unknown municipality code", () => {
    expect(getMunicipalityVisual({ istatCode: "000000" })).toBeNull();
  });
});
