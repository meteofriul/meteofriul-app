import { describe, expect, it } from "vitest";

import {
  getCandidateReviewById,
  getCandidateReviewSummary,
  isCandidateRecommendedForPromotion,
} from "./proverbCandidateReview";

describe("proverb candidate editorial review", () => {
  it("summarizes Ostermann candidate review passes", () => {
    const summary = getCandidateReviewSummary();

    expect(summary.totalReviewed).toBe(122);
    expect(summary.byRecommendation.promote_after_fur_review).toBe(65);
    expect(summary.byRecommendation.promoted_after_fur_review).toBe(17);
    expect(summary.byRecommendation.archive_only).toBe(29);
    expect(summary.byRecommendation.variant_not_selected).toBe(10);
    expect(summary.byRecommendation.hold ?? 0).toBe(0);
    expect(summary.byRecommendation.needs_context ?? 0).toBe(0);
    expect(summary.byPriority.P1).toBeGreaterThan(summary.byPriority.P3);
    expect(summary.promotionCandidateCount).toBe(66);
  });

  it("keeps closed candidates out of the pending promotion shortlist", () => {
    expect(isCandidateRecommendedForPromotion("ostermann-105-aghe-pais")).toBe(false);
    expect(isCandidateRecommendedForPromotion("ostermann-105-lune-cercli")).toBe(true);
  });

  it("keeps review decisions separate from raw candidate data", () => {
    const review = getCandidateReviewById("ostermann-103-umiditat-glazze");

    expect(review).toMatchObject({
      recommendation: "replace_existing_after_review",
      replaces: "ostermann-umiltat-glace",
    });
  });

  it("tracks the page 54 winter review with recommended copy", () => {
    const review = getCandidateReviewById("ostermann-054-san-blas-fred");

    expect(review).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_dated",
      reviewedAt: "2026-07-03",
      recommendedFur: "San Blâs, il frêt al taie il nâs, o al fâs la pâs.",
      recommendedIt: "A San Biagio il freddo taglia il naso, oppure fa pace.",
      sourceCheck: {
        pdfPage: 54,
        textPage: 29,
      },
    });
  });

  it("tracks the page 60 summer saints review with recommended copy", () => {
    const review = getCandidateReviewById("ostermann-060-san-bortolomio-bon-timp");

    expect(review).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_dated",
      reviewedAt: "2026-07-03",
      recommendedFur: "Se a San Bortolomio al è bon timp, al è bon timp dutis lis vendemis.",
      recommendedIt: "Se a San Bartolomeo fa bel tempo, sarà bel tempo per tutta la vendemmia.",
      dateAnchors: ["08-24"],
      sourceCheck: {
        pdfPage: 60,
        textPage: 35,
      },
    });
  });

  it("tracks the page 61 autumn review and separates dated from seasonal use", () => {
    const sanSimon = getCandidateReviewById("ostermann-061-san-simon-unviar");
    const lateLeaves = getCandidateReviewById("ostermann-061-fueis-tardis");

    expect(sanSimon).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_dated",
      reviewedAt: "2026-07-03",
      recommendedFur: "San Simon passât, l'unviâr entrât.",
      recommendedIt: "Passato San Simone, l'inverno è entrato.",
      dateAnchors: ["10-28"],
      sourceCheck: {
        pdfPage: 61,
        textPage: 36,
      },
    });
    expect(lateLeaves).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_seasonal",
      reviewedAt: "2026-07-03",
      dateAnchors: [],
      seasons: ["autumn"],
      sourceCheck: {
        pdfPage: 61,
        textPage: 36,
      },
    });
  });

  it("tracks the page 192 vineyard calendar review with recommended copy", () => {
    const sanBarnaba = getCandidateReviewById("ostermann-192-san-barnaba-vin");
    const assunta = getCandidateReviewById("ostermann-192-assunte-vin");

    expect(sanBarnaba).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_dated",
      reviewedAt: "2026-07-03",
      recommendedFur: "Ploe a San Barnaba, il vin al va.",
      recommendedIt: "Pioggia a San Barnaba, il vino se ne va.",
      dateAnchors: ["06-11"],
      sourceCheck: {
        pdfPage: 192,
        textPage: 167,
      },
    });
    expect(assunta).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_dated",
      reviewedAt: "2026-07-03",
      recommendedFur: "Biel soreli a l'Assunte, bondance di vin.",
      recommendedIt: "Bel sole all'Assunta, abbondanza di vino.",
      dateAnchors: ["08-15"],
      sourceCheck: {
        pdfPage: 192,
        textPage: 167,
      },
    });
  });

  it("tracks the page 126 thunderstorm review without dating it as a calendar slot", () => {
    const thunder = getCandidateReviewById("ostermann-126-tone-ploe-tempieste");
    const mayHail = getCandidateReviewById("ostermann-126-mai-tempieste");

    expect(thunder).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_weather_sign",
      reviewedAt: "2026-07-03",
      recommendedFur: "Cuant che al tone, o ploe o tempieste.",
      recommendedIt: "Quando tuona, arriva pioggia o grandine.",
      dateAnchors: [],
      seasons: ["spring", "summer"],
      sourceCheck: {
        pdfPage: 126,
        textPage: 101,
      },
    });
    expect(mayHail).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_monthly",
      reviewedAt: "2026-07-03",
      recommendedFur: "Se in Mai e tempieste, nuie nus reste.",
      recommendedIt: "Se in maggio grandina, non resta nulla.",
      dateAnchors: [],
      months: ["05"],
      seasons: ["spring"],
      sourceCheck: {
        pdfPage: 126,
        textPage: 101,
      },
    });
  });

  it("tracks the page 130 snow review as winter content", () => {
    const snow = getCandidateReviewById("ostermann-130-sot-nev-pan");

    expect(snow).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_seasonal",
      reviewedAt: "2026-07-03",
      recommendedFur: "Sot nef pan, sot ploe fan.",
      recommendedIt: "Sotto la neve pane, sotto la pioggia fame.",
      dateAnchors: [],
      seasons: ["winter"],
      sourceCheck: {
        pdfPage: 130,
        textPage: 105,
      },
    });
  });

  it("tracks the page 104 visual weather signs without dating them", () => {
    const mountainHat = getCandidateReviewById("ostermann-104-monts-chapiel");
    const woolSky = getCandidateReviewById("ostermann-104-cil-lane");

    expect(mountainHat).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_weather_sign",
      reviewedAt: "2026-07-03",
      recommendedFur: "Cuant che lis monts a àn il cjapiel, met jù la falç, cjol sù il rischjel.",
      recommendedIt: "Quando i monti hanno il cappello, posa la falce e prendi il rastrello.",
      dateAnchors: [],
      seasons: ["spring", "summer", "autumn"],
      sourceCheck: {
        pdfPage: 104,
        textPage: 79,
      },
    });
    expect(woolSky).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_weather_sign",
      reviewedAt: "2026-07-03",
      recommendedFur: "Il cîl al è dut a lane, la ploe no è lontane.",
      recommendedIt: "Il cielo è tutto a lana: la pioggia non è lontana.",
      dateAnchors: [],
      seasons: ["all"],
      sourceCheck: {
        pdfPage: 104,
        textPage: 79,
      },
    });
  });

  it("tracks the page 49 lunar review without dating it as a calendar slot", () => {
    const firstTuesday = getCandidateReviewById("ostermann-049-prin-martars-lune-pluv");
    const novemberMoon = getCandidateReviewById("ostermann-049-lune-brume");

    expect(firstTuesday).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_lunar_cycle",
      reviewedAt: "2026-07-03",
      recommendedFur: "Cuant che al plûf il prin martars di lune, no vin sec plui par chê lune.",
      recommendedIt: "Quando piove il primo martedì della luna, per quella lunazione non avremo più secco.",
      dateAnchors: [],
      seasons: ["all"],
      sourceCheck: {
        pdfPage: 49,
        textPage: 24,
      },
    });
    expect(novemberMoon).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_monthly",
      reviewedAt: "2026-07-03",
      recommendedFur: "Lune di Brume, mieze sute e mieze bagnade.",
      recommendedIt: "Luna di novembre, mezza asciutta e mezza bagnata.",
      dateAnchors: [],
      months: ["11"],
      seasons: ["autumn"],
      sourceCheck: {
        pdfPage: 49,
        textPage: 24,
      },
    });
  });

  it("tracks the last Almanac review queue records without publishing them", () => {
    const garbin = getCandidateReviewById("ostermann-096-garbin-timp");
    const dew = getCandidateReviewById("ostermann-097-rosadis-marz-bueris-avril");
    const fog = getCandidateReviewById("ostermann-099-tre-fumatis-ploe");
    const cuckoo = getCandidateReviewById("ostermann-102-cuch-ploe-sut");

    expect(garbin).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_weather_sign",
      reviewedAt: "2026-07-04",
      dateAnchors: [],
      seasons: ["all"],
      sourceCheck: { pdfPage: 96, textPage: 71 },
    });
    expect(dew).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_monthly",
      reviewedAt: "2026-07-04",
      months: ["03", "04"],
      seasons: ["spring"],
      sourceCheck: { pdfPage: 97, textPage: 72 },
    });
    expect(fog).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_weather_sign",
      reviewedAt: "2026-07-04",
      seasons: ["autumn", "winter"],
      sourceCheck: { pdfPage: 99, textPage: 74 },
    });
    expect(cuckoo).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_seasonal",
      reviewedAt: "2026-07-04",
      seasons: ["spring"],
      sourceCheck: { pdfPage: 102, textPage: 77 },
    });
  });

  it("tracks the closure of the first remaining-candidate review batch", () => {
    const saintAnthony = getCandidateReviewById("ostermann-054-sant-antoni-fred");
    const sanVincenzoLorenzo = getCandidateReviewById("ostermann-054-san-vizenz-san-lorenz");
    const goodFriday = getCandidateReviewById("ostermann-059-vinars-sant-arsure");
    const moonColor = getCandidateReviewById("ostermann-102-lune-tinte");

    expect(saintAnthony).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_dated",
      reviewedAt: "2026-07-04",
      dateAnchors: ["01-17"],
      sourceCheck: { pdfPage: 54, textPage: 29 },
    });
    expect(sanVincenzoLorenzo).toMatchObject({
      recommendation: "variant_not_selected",
      variantGroup: "san_lorenzo_caldo_agosto",
      reviewedAt: "2026-07-04",
    });
    expect(goodFriday).toMatchObject({
      recommendation: "promoted_after_fur_review",
      targetUse: "almanac_movable_feast",
      reviewedAt: "2026-07-23",
      promotedAt: "2026-07-23",
    });
    expect(moonColor).toMatchObject({
      recommendation: "archive_only",
      targetUse: "scopri",
      reviewedAt: "2026-07-04",
    });
  });

  it("records the final choice for every previously unresolved variant group", () => {
    const selected = [
      getCandidateReviewById("ostermann-103-nadal-chase-pasche-plazze"),
      getCandidateReviewById("ostermann-103-no-mai-ploe"),
    ];
    const rejected = [
      "ostermann-103-nadal-pasche-fuch",
      "ostermann-103-dopo-ploe-bon-timp",
      "ostermann-190-san-josef-seren",
      "ostermann-054-san-vizenz-san-lorenz",
      "ostermann-099-fumate-no-sbasse",
      "ostermann-189-pulvin-zenar-granar",
      "ostermann-192-san-barnabe-ue",
    ].map((id) => getCandidateReviewById(id));

    expect(selected.every((record) => (
      record.recommendation === "promoted_after_fur_review" &&
      record.promotedAt === "2026-07-23" &&
      record.recommendedFur
    ))).toBe(true);
    expect(rejected.every((record) => record.recommendation === "variant_not_selected")).toBe(true);
  });

  it("tracks the final remaining-candidate review batch and promoted dated follow-ups", () => {
    const sanPauli = getCandidateReviewById("ostermann-058-san-pauli-scur");
    const sanZuan = getCandidateReviewById("ostermann-063-san-zuan-timp");
    const sanMarco = getCandidateReviewById("ostermann-141-arch-san-march-doman");
    const midili = getCandidateReviewById("ostermann-068-fum-traviers-bez");
    const sanGorgon = getCandidateReviewById("ostermann-061-san-gorgon-ploe");
    const muarz = getCandidateReviewById("ostermann-103-muarz-novembre");

    expect(sanPauli).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_dated",
      dateAnchors: ["01-10"],
      sourceCheck: { pdfPage: 58, textPage: 33 },
    });
    expect(sanZuan).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_dated",
      dateAnchors: ["06-24"],
      sourceCheck: { pdfPage: 63, textPage: 38 },
    });
    expect(sanMarco).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_dated",
      dateAnchors: ["04-25"],
    });
    expect(midili).toMatchObject({
      recommendation: "archive_only",
      targetUse: "scopri",
      dateAnchors: ["01-06"],
    });
    expect(sanGorgon).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_dated",
      dateAnchors: ["09-09"],
      sourceCheck: { pdfPage: 61, textPage: 36 },
    });
    expect(muarz).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_dated",
      dateAnchors: ["11-02"],
      sourceCheck: { pdfPage: 103, textPage: 78 },
    });
  });

  it("tracks page 57 dated daylight proverbs and publishes only the selected Christmas variant", () => {
    const sanTomas = getCandidateReviewById("ostermann-057-san-tomas-zornade-curte");
    const sanTomasNadal = getCandidateReviewById("ostermann-057-san-tomas-nadal-di-gial");
    const sanLucio = getCandidateReviewById("ostermann-057-san-lucio-nadal-gial");
    const nadalPascute = getCandidateReviewById("ostermann-057-nadal-pascute-orute");
    const sanLuigi = getCandidateReviewById("ostermann-057-san-luigi-zornade-lunge");

    expect(sanTomas).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_dated",
      reviewedAt: "2026-07-05",
      dateAnchors: ["12-21"],
      sourceCheck: { pdfPage: 57, textPage: 32 },
    });
    expect(sanTomasNadal).toMatchObject({
      recommendation: "archive_only",
      targetUse: "scopri",
      variantGroup: "giornate_san_tomas_nadal",
      reviewedAt: "2026-07-05",
    });
    expect(sanLucio).toMatchObject({
      recommendation: "variant_not_selected",
      priority: "P3",
      targetUse: "scopri",
      variantGroup: "giornate_san_tomas_nadal",
      reviewedAt: "2026-07-23",
    });
    expect(nadalPascute).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_dated",
      variantGroup: "giornate_nadal_epifanie",
      dateAnchors: ["12-25"],
      reviewedAt: "2026-07-05",
    });
    expect(sanLuigi).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_dated",
      dateAnchors: ["06-21"],
      sourceCheck: { pdfPage: 57, textPage: 32 },
    });
  });

  it("tracks page 62 monthly and dated candidates without publishing uncertain saints", () => {
    const januaryApril = getCandidateReviewById("ostermann-062-zenar-ploe-avril");
    const shortFebruary = getCandidateReviewById("ostermann-062-febrar-curt-amar");
    const greenMarch = getCandidateReviewById("ostermann-062-febrar-senze-criure");
    const sanMacari = getCandidateReviewById("ostermann-062-san-macari-setembar");
    const sanRuperto = getCandidateReviewById("ostermann-062-san-ruperto-lui");

    expect(januaryApril).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_monthly",
      months: ["01", "04"],
      sourceCheck: { pdfPage: 62, textPage: 37 },
    });
    expect(shortFebruary).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_monthly",
      months: ["02"],
    });
    expect(greenMarch).toMatchObject({
      recommendation: "promote_after_fur_review",
      targetUse: "almanac_monthly",
      months: ["02", "03"],
    });
    expect(sanMacari).toMatchObject({
      recommendation: "archive_only",
      targetUse: "almanac_dated",
      dateAnchors: ["01-02"],
      reviewedAt: "2026-07-23",
    });
    expect(sanRuperto).toMatchObject({
      recommendation: "promoted_after_fur_review",
      targetUse: "almanac_dated",
      dateAnchors: ["03-27"],
      reviewedAt: "2026-07-23",
      promotedAt: "2026-07-23",
    });
  });
});
