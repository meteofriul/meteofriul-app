import municipalityVisuals from "../../data/discover/municipalityVisuals.json";
import municipalityPhotos from "../../data/discover/municipalityPhotos.json";

const MUNICIPALITY_PHOTOS_BY_ISTAT = Object.freeze(Object.fromEntries(
  municipalityPhotos.photos.map(({ istatCode, localUrl, objectPosition }) => [
    istatCode,
    Object.freeze({ localUrl, objectPosition }),
  ]),
));

const MUNICIPALITY_VISUALS_BY_ISTAT = Object.freeze(Object.fromEntries(
  municipalityVisuals.visuals.map(({ istatCode, localUrl }) => [
    istatCode,
    Object.freeze({
      coatOfArmsUrl: localUrl,
      photoAlt: "",
      photoPosition: MUNICIPALITY_PHOTOS_BY_ISTAT[istatCode]?.objectPosition || "50% 50%",
      photoUrl: MUNICIPALITY_PHOTOS_BY_ISTAT[istatCode]?.localUrl || "",
    }),
  ]),
));

export function getMunicipalityVisual(card) {
  return MUNICIPALITY_VISUALS_BY_ISTAT[String(card?.istatCode || "")] || null;
}
