import { describe, expect, it } from "vitest";
import milestoneSources from "../../data/discover/municipalityMilestoneSources.json";

import { FIXED_FVG_PLACES, FVG_PLACES_SOURCE } from "../../data/fvgPlaces";
import { getLocationDisplayName } from "../geo/locationDisplayName";
import {
  getMunicipalityProfile,
  getMunicipalityProfileRecords,
} from "./municipalityProfiles";

const PILOT_MUNICIPALITIES = [
  ["Pordenone", "093033", "PN"],
  ["Udine", "030129", "UD"],
  ["Gorizia", "031007", "GO"],
  ["Trieste", "032006", "TS"],
];

const REVIEWED_SOURCE_TYPES = [
  "official_municipality",
  "national_institution",
  "regional_institution",
  "cultural_institution",
  "wikipedia_reference",
];

describe("municipalityProfiles", () => {
  it("covers the complete canonical FVG municipality registry", () => {
    const profiles = getMunicipalityProfileRecords();
    const canonicalPlaces = Object.values(FIXED_FVG_PLACES);

    expect(profiles).toHaveLength(FVG_PLACES_SOURCE.count);
    expect(profiles).toHaveLength(canonicalPlaces.length);
    expect(new Set(profiles.map((profile) => profile.id)).size).toBe(profiles.length);
    expect(new Set(profiles.map((profile) => profile.istatCode)).size).toBe(profiles.length);
    expect(new Set(profiles.map((profile) => profile.istatCode))).toEqual(
      new Set(canonicalPlaces.map((place) => place.istatCode)),
    );
  });

  it("publishes all municipalities as reviewed editorial profiles", () => {
    const profiles = getMunicipalityProfileRecords();
    const editorialProfiles = profiles.filter((profile) => profile.profileTier === "editorial");
    const registryProfiles = profiles.filter((profile) => profile.profileTier === "registry");
    const pilotProfiles = profiles.filter((profile) => profile.editorialStatus === "pilot_ready");
    const reviewedProfiles = profiles.filter((profile) => profile.editorialStatus === "reviewed");

    const pilotIdentities = pilotProfiles.map((profile) => [
      profile.municipality,
      profile.istatCode,
      profile.province,
    ]).sort((first, second) => first[1].localeCompare(second[1]));
    const expectedPilotIdentities = [...PILOT_MUNICIPALITIES]
      .sort((first, second) => first[1].localeCompare(second[1]));

    expect(editorialProfiles).toHaveLength(FVG_PLACES_SOURCE.count);
    expect(registryProfiles).toHaveLength(0);
    expect(pilotIdentities).toEqual(expectedPilotIdentities);
    expect(reviewedProfiles).toHaveLength(FVG_PLACES_SOURCE.count - PILOT_MUNICIPALITIES.length);

    for (const profile of pilotProfiles) {
      expect(profile).toMatchObject({
        editorialStatus: "pilot_ready",
        source: { type: "official_municipality" },
      });
      expect(profile.milestones.length).toBeGreaterThanOrEqual(3);
    }

    for (const profile of reviewedProfiles) {
      expect(profile).toMatchObject({
        editorialStatus: "reviewed",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
      });
      expect(REVIEWED_SOURCE_TYPES).toContain(profile.source.type);
      expect(profile.source.url).toMatch(/^https:\/\//);
      expect(profile.title.it).toBeTruthy();
      expect(profile.title.fur).toBeTruthy();
      expect(profile.summary.it).toBeTruthy();
      expect(profile.summary.fur).toBeTruthy();
    }
  });

  it("matches every profile to the canonical name and province", () => {
    const canonicalByIstatCode = new Map(
      Object.values(FIXED_FVG_PLACES).map((place) => [place.istatCode, place]),
    );

    for (const profile of getMunicipalityProfileRecords()) {
      expect(canonicalByIstatCode.get(profile.istatCode)).toMatchObject({
        name: profile.municipality,
        province: profile.province,
      });
    }
  });

  it("serves every municipality in both IT and FUR", () => {
    for (const place of Object.values(FIXED_FVG_PLACES)) {
      for (const language of ["it", "fur"]) {
        const card = getMunicipalityProfile({
          language,
          location: { city: place.name, istatCode: place.istatCode },
        });

        expect(card).toMatchObject({
          istatCode: place.istatCode,
          locationLabel: getLocationDisplayName(place, language),
          seasonLabel: getLocationDisplayName(place, language),
          province: place.province,
          selectionKind: "municipality_profile",
          visualKind: "municipality",
        });
        expect(card.title).toBeTruthy();
        expect(card.text).toBeTruthy();
      }
    }
  });

  it("keeps municipality milestones complete, bilingual and uniquely keyed", () => {
    const milestoneIds = new Set();

    for (const profile of getMunicipalityProfileRecords()) {
      expect(profile.milestones.length).toBeLessThanOrEqual(3);

      for (const milestone of profile.milestones) {
        expect(milestone.id).toBeTruthy();
        expect(milestoneIds.has(milestone.id)).toBe(false);
        expect(milestone.year !== undefined || milestone.century).toBeTruthy();
        expect(milestone.label.it).toBeTruthy();
        expect(milestone.label.fur).toBeTruthy();
        milestoneIds.add(milestone.id);
      }
    }

    expect(milestoneIds.size).toBe(463);
  });

  it("prefers the ISTAT code over a conflicting city label", () => {
    const card = getMunicipalityProfile({
      language: "it",
      location: { city: "Udine", istatCode: "093033" },
    });

    expect(card).toMatchObject({
      id: "municipality-profile-pordenone",
      istatCode: "093033",
      locationLabel: "Pordenone",
      profileTier: "editorial",
    });
  });

  it("serves an enriched editorial profile outside the old pilot", () => {
    const cordenonsSource = {
      label: "Comune di Cordenons - Storia del Comune",
      type: "official_municipality",
      url: "https://www.comune.cordenons.pn.it/it/novita-31910/notizie-31911/storia-del-comune-49452",
    };
    const villaRaetzSource = {
      label: "ERPAC FVG - Parco di Villa Raetz",
      type: "regional_institution",
      url: "https://patrimonioculturale.regione.fvg.it/parchi-e-giardini/?s_id=749704",
      checkedAt: "2026-09-01",
    };
    const italianCard = getMunicipalityProfile({
      language: "it",
      location: { city: "Cordenons", istatCode: "093017" },
    });
    const friulianCard = getMunicipalityProfile({
      language: "fur",
      location: { city: "Cordenons", istatCode: "093017" },
    });

    expect(italianCard).toMatchObject({
      id: "municipality-profile-cordenons",
      profileTier: "editorial",
      sourceType: "official_municipality",
      title: "Cordenons, dalla Curtis Naonis alle risorgive",
      typeLabel: "Il comune",
    });
    expect(italianCard.milestones).toHaveLength(3);
    expect(italianCard.milestones).toEqual([
      {
        id: "cordenons-897",
        label: "Un diploma ricorda la corte regia di Cordenons",
        period: 897,
        source: cordenonsSource,
        supportingSources: [],
      },
      {
        id: "cordenons-1814",
        label: "Cordenons diventa comune autonomo",
        period: 1814,
        source: cordenonsSource,
        supportingSources: [],
      },
      {
        id: "cordenons-1902-giardino-villa-raetz",
        label: "Viene creato il giardino di Villa Raetz",
        period: 1902,
        source: villaRaetzSource,
        supportingSources: [],
      },
    ]);
    expect(friulianCard).toMatchObject({
      profileTier: "editorial",
      title: "Cordenons, de Curtis Naonis aes risultivis",
      typeLabel: "Il comun",
    });
    expect(friulianCard.milestones[0].label).toBe(
      "Un diplome al ricuarde la curt regjie di Cordenons",
    );
    expect(friulianCard.milestones[2].label).toBe("Al ven creât il zardin di Vile Raetz");
  });

  it("preserves each milestone source and uses the profile source only for legacy omissions", () => {
    for (const profile of getMunicipalityProfileRecords()) {
      for (const language of ["it", "fur"]) {
        const card = getMunicipalityProfile({
          language,
          location: { city: profile.municipality, istatCode: profile.istatCode },
        });

        for (const milestone of profile.milestones) {
          const renderedMilestone = card.milestones.find(({ id }) => id === milestone.id);
          expect(renderedMilestone.source).toEqual(milestone.source || milestoneSources[milestone.id] || profile.source);
          expect(renderedMilestone.supportingSources).toEqual(milestone.supportingSources || []);
        }
      }
    }
  });

  it("does not mix museum, refuge, park and city evidence across the enriched PN timelines", () => {
    const expectedSources = [
      ["Andreis", "093001", [
        ["andreis-1949", "https://www.sbhu.it/Archivi/SBUF/Files/131107-tavan.pdf"],
        ["andreis-museo-1981", "https://www.parcodolomitifriulane.it/i-paesi-del-parco/andreis/"],
      ]],
      ["Cimolais", "093014", [
        ["cimolais-1902", "https://www.parcodolomitifriulane.it/i-paesi-del-parco/cimolais/"],
        ["cimolais-rifugio-pordenone-1930", "https://caipordenone.it/chi-siamo/storia/"],
        ["cimolais-stambecco-1985", "https://www.parcodolomitifriulane.it/i-paesi-del-parco/cimolais/"],
      ]],
      ["Sacile", "093037", [
        ["sacile-796", "https://www.visitsacile.it/arte-storia-fede/storia/"],
        ["sacile-liberta-comunali-1190", "https://www.visitsacile.it/arte-storia-fede/storia/"],
        ["sacile-1420", "https://www.visitsacile.it/arte-storia-fede/storia/"],
      ]],
    ];

    for (const language of ["it", "fur"]) {
      for (const [city, istatCode, milestoneSources] of expectedSources) {
        const card = getMunicipalityProfile({ language, location: { city, istatCode } });
        expect(card.milestones.map(({ id, source }) => [id, source.url]))
          .toEqual(milestoneSources);

        for (const milestone of card.milestones) {
          if (milestone.id === "cimolais-rifugio-pordenone-1930") {
            expect(milestone.supportingSources.map(({ url }) => url)).toEqual([
              "https://caipordenone.it/strutture/rifugio-pordenone/",
              "https://www.prenotarifugi.cai.it/en/detail/Rifugio%20Pordenone/?id=6000",
            ]);
          } else {
            expect(milestone.supportingSources).toEqual([]);
          }
        }
      }
    }
  });

  it("renders historical periods with Arabic numerals in both languages", () => {
    const italianCard = getMunicipalityProfile({
      language: "it",
      location: { city: "Trieste", istatCode: "032006" },
    });
    const friulianCard = getMunicipalityProfile({
      language: "fur",
      location: { city: "Trieste", istatCode: "032006" },
    });

    expect(italianCard.milestones.at(-1).period).toBe("18°-19° sec.");
    expect(friulianCard.milestones.at(-1).period).toBe("Secui 18-19");
  });

  it("removes Roman numerals from user-facing municipality copy", () => {
    const italianCard = getMunicipalityProfile({
      language: "it",
      location: { city: "Cervignano del Friuli", istatCode: "030023" },
    });
    const friulianCard = getMunicipalityProfile({
      language: "fur",
      location: { city: "Attimis", istatCode: "030007" },
    });

    expect(italianCard.text).toContain("Giuseppe 2°");
    expect(italianCard.text).not.toContain("Giuseppe II");
    expect(friulianCard.text).toContain("secul 10 e il 15");
    expect(friulianCard.text).not.toContain("secul X e il XV");
  });

  it("does not mistake elided words for Roman numerals", () => {
    const italianCard = getMunicipalityProfile({
      language: "it",
      location: { city: "Fanna", istatCode: "093020" },
    });
    const friulianCard = getMunicipalityProfile({
      language: "fur",
      location: { city: "Fanna", istatCode: "093020" },
    });

    expect(italianCard.milestones[1].label).toBe(
      "L'abitato viene diviso nei paesi di Fanna e Cavasso",
    );
    expect(italianCard.milestones[1].label).not.toContain("50°");
    expect(friulianCard.milestones[1].label).toBe(
      "L'abitât al ven dividût tai paîs di Fane e Cjavàs",
    );
    expect(friulianCard.milestones[1].label).not.toContain("50");
  });

  it("does not rewrite a Roman-looking initial followed by an accented letter", () => {
    const friulianCard = getMunicipalityProfile({
      language: "fur",
      location: { city: "Sauris", istatCode: "030107" },
    });

    expect(friulianCard.milestones[1].label).toBe(
      "Al nas il Lâc di Sauris cu la dighe sul Lumiei",
    );
    expect(friulianCard.milestones[1].label).not.toContain("50âc");

    const sanVitoCard = getMunicipalityProfile({
      language: "fur",
      location: { city: "San Vito al Tagliamento", istatCode: "093041" },
    });
    expect(sanVitoCard.title).toContain("San Vît");
    expect(sanVitoCard.title).not.toContain("San 5ît");
  });

  it("does not rewrite the name I Mistîrs as a Roman numeral", () => {
    const italianCard = getMunicipalityProfile({
      language: "it",
      location: { city: "Paularo", istatCode: "030073" },
    });
    const friulianCard = getMunicipalityProfile({
      language: "fur",
      location: { city: "Paularo", istatCode: "030073" },
    });

    expect(italianCard.text).toContain("L'Ecomuseo I Mistîrs");
    expect(italianCard.text).not.toContain("L'Ecomuseo 1° Mistîrs");
    expect(friulianCard.text).toContain("L'Ecomuseu I Mistîrs");
    expect(friulianCard.text).not.toContain("L'Ecomuseu 1 Mistîrs");
  });

  it("does not mistake historical abbreviations for Roman numerals", () => {
    const italianCard = getMunicipalityProfile({
      language: "it",
      location: { city: "Tramonti di Sotto", istatCode: "093046" },
    });
    const friulianCard = getMunicipalityProfile({
      language: "fur",
      location: { city: "Tramonti di Sotto", istatCode: "093046" },
    });

    expect(italianCard.milestones[0].period).toBe("6°-7° d.C.");
    expect(friulianCard.milestones[0].period).toBe("6-7 d.C.");
    expect(italianCard.milestones[1].period).toBe("fine 15°");
    expect(friulianCard.milestones[1].period).toBe("Ae fin dal secul 15");
    expect(italianCard.milestones[2].period).toBe("inizio 16°");
    expect(friulianCard.milestones[2].period).toBe("Al inizi dal secul 16");
  });

  it("keeps Roman numerals out of every rendered municipality card", () => {
    const romanNumeral = /(?<![\p{L}\p{N}])(?:II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII|XIX|XX)(?![\p{L}\p{N}])/u;

    for (const profile of getMunicipalityProfileRecords()) {
      for (const language of ["it", "fur"]) {
        const card = getMunicipalityProfile({
          language,
          location: {
            city: profile.municipality,
            istatCode: profile.istatCode,
          },
        });
        const visibleCopy = [
          card.title,
          card.text,
          ...card.milestones.flatMap((milestone) => [milestone.period, milestone.label]),
        ].join(" ");

        expect(visibleCopy).not.toMatch(romanNumeral);
      }
    }
  });

  it("respects an explicitly empty profile source used by isolated view-model tests", () => {
    expect(getMunicipalityProfile({
      language: "it",
      location: { city: "Cordenons", istatCode: "093017" },
      source: { profiles: [] },
    })).toBeNull();
  });
});
