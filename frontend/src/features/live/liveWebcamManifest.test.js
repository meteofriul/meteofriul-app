import { describe, expect, it } from "vitest";

import activeManifest from "../../../../backend/app/data/webcams_active.json";
import candidateManifest from "../../../../backend/app/data/webcams_candidates.json";
import suspendedManifest from "../../../../backend/app/data/webcams_suspended.json";
import { FIXED_FVG_PLACES } from "../../data/fvgPlaces";
import { buildLiveViewModel } from "./liveViewModel";

function buildManifestModel({
  language = "it",
  location = { city: "Pordenone" },
  manifest = activeManifest,
} = {}) {
  return buildLiveViewModel({
    webcams: { status: "fresh", payload: manifest },
  }, { language, location, now: new Date("2026-08-30T14:30:00Z") });
}

function getRegionalCameras(model) {
  return model.webcams.groups
    .filter((group) => group.id !== "nearby")
    .flatMap((group) => group.cameras);
}

describe("active webcam manifest integration", () => {
  it("keeps all 35 active cameras and the reviewed new identities in the frontend", () => {
    const cameras = getRegionalCameras(buildManifestModel());
    const ids = cameras.map((camera) => camera.id);

    expect(activeManifest.webcams).toHaveLength(35);
    expect(cameras).toHaveLength(35);
    expect(new Set(ids).size).toBe(35);
    expect([...ids].sort()).toEqual(activeManifest.webcams.map((camera) => camera.id).sort());
    expect(ids).toEqual(expect.arrayContaining([
      "sacile",
      "grado-al-bosco",
      "monfalcone-marina",
      "monfalcone-marina-julia-1",
      "monfalcone-marina-julia-2",
      "forni-varmost",
      "piancavallo-panorama",
      "piancavallo-nevelandia",
      "moruzzo-panorama",
      "spilimbergo-duomo",
      "zoncolan-panorama",
      "cividale-campanile-ex-monastero",
      "cividale-piazza-duomo",
      "cividale-piazza-paolo-diacono",
      "sappada-panorama",
      "sella-nevea-canin",
      "lignano-spiaggia-centrale",
      "lignano-piazza-fontana",
      "lignano-pineta-pontile",
      "lignano-riviera",
      "cisar-monte-grisa-sud-est",
      "cisar-monte-grisa-sud-ovest",
      "cisar-lanterna-nord",
      "udine-panorama-castello",
      "trieste-san-giusto",
      "barcis-paese",
      "claut-pradut",
    ]));
    expect(ids).not.toEqual(expect.arrayContaining(["monfalcone-marina-julia"]));
    expect(ids).not.toEqual(expect.arrayContaining(["grado-spiaggia"]));
    expect(ids).not.toEqual(expect.arrayContaining(["forni-chianeit"]));
    expect(ids).not.toEqual(expect.arrayContaining(["piancavallo-sauc"]));
    expect(ids).not.toEqual(expect.arrayContaining(["zoncolan-baita-goles"]));
    expect(ids).not.toEqual(expect.arrayContaining(["val-saisera"]));
    expect(ids).not.toEqual(expect.arrayContaining(["cividale-natisone"]));
    expect(cameras.filter((camera) => ![
      "sacile", "grado-al-bosco",
      "cividale-campanile-ex-monastero", "cividale-piazza-duomo",
      "cividale-piazza-paolo-diacono",
      "lignano-punta-faro", "lignano-spiaggia-centrale",
      "lignano-piazza-fontana", "lignano-pineta-pontile", "lignano-riviera",
      "cisar-monte-grisa-sud-est", "cisar-monte-grisa-sud-ovest",
      "cisar-lanterna-nord",
      "forni-varmost",
      "piancavallo-panorama",
      "piancavallo-nevelandia",
      "moruzzo-panorama",
      "spilimbergo-duomo",
      "monfalcone-marina-julia-1",
      "monfalcone-marina-julia-2",
      "sappada-panorama",
      "sella-nevea-canin",
      "san-daniele-centro",
      "trieste-san-giusto",
      "zoncolan-panorama",
      "udine-panorama-castello",
      "gemona-centro",
      "trieste-miramare",
      "barcis-paese",
      "claut-pradut",
    ].includes(camera.id))
      .every((camera) => camera.sourceUrl && !camera.imageUrl && !camera.playerUrl)).toBe(true);
    expect(cameras.find((camera) => camera.id === "sacile")).toMatchObject({
      imageUrl: "https://sacilemeteo.altervista.org/hik/webcam_r.jpg",
      mediaType: "snapshot",
      attribution: "© Luigi Carbonera",
      attributionUrl: "https://sacilemeteo.altervista.org/hik/webcam_hik.html",
      sourceUrl: "https://sacilemeteo.altervista.org/hik/webcam_hik.html",
      fallbackImageUrl: "/municipalities/photos/093037-photo.webp",
      playerUrl: "",
    });
    expect(cameras.find((camera) => camera.id === "grado-al-bosco")).toMatchObject({
      name: "Grado Pineta - Isolotto Sacca dei Moreri",
      locationLabel: "Grado Pineta",
      imageUrl: "https://cam.kitelifefvg.it/webcam_grado.php",
      mediaType: "snapshot",
      provider: "Grado.it",
      attribution: "Residence Hotel Al Bosco · Kite Life FVG",
      attributionUrl: "https://www.kitelifefvg.it/webcam/",
      sourceUrl: "https://grado.it/it/scoprire-grado/webcam",
      fallbackImageUrl: "/municipalities/photos/031009-photo.webp",
      playerUrl: "",
    });
    const cividale = cameras.filter(
      (camera) => camera.mapClusterId === "cividale-del-friuli",
    );
    expect(cividale).toHaveLength(3);
    expect(cividale.map((camera) => camera.id)).toEqual([
      "cividale-campanile-ex-monastero",
      "cividale-piazza-duomo",
      "cividale-piazza-paolo-diacono",
    ]);
    expect(cividale.every((camera) => (
      camera.mediaType === "snapshot"
      && camera.provider === "ARPA FVG - OSMER e GRN"
      && camera.attribution === "ARPA FVG - OSMER e GRN"
      && camera.attributionUrl === "https://www.meteo.fvg.it/"
      && camera.sourceUrl === "https://www.meteo.fvg.it/webcam_img.php?ln=it"
      && camera.fallbackImageUrl === "/municipalities/photos/030026-photo.webp"
      && camera.mapClusterLabel === "Cividale del Friuli"
      && camera.playerUrl === ""
    ))).toBe(true);
    expect(cividale.map((camera) => camera.imageUrl)).toEqual([
      "https://www.meteo.fvg.it/ext/webcams/webcams/CividaleVedutadalcampanile-cividale_campanileexmonastero.jpg",
      "https://www.meteo.fvg.it/ext/webcams/webcams/CividalePiazzaDuomo-cividale_piazzaduomo.jpg",
      "https://www.meteo.fvg.it/ext/webcams/webcams/CividalePiazzaDiacono-cividale_piazzadiacono.jpg",
    ]);
    expect(cameras.find((camera) => camera.id === "cividale-piazza-duomo")).toMatchObject({
      name: "Cividale del Friuli - Piazza Duomo",
      area: "Piazza Duomo",
    });
    const marinaJulia = cameras.filter(
      (camera) => camera.mapClusterId === "monfalcone-marina-julia",
    );
    expect(marinaJulia).toHaveLength(2);
    expect(marinaJulia.map((camera) => camera.id)).toEqual([
      "monfalcone-marina-julia-1",
      "monfalcone-marina-julia-2",
    ]);
    expect(marinaJulia.every((camera) => (
      camera.mediaType === "snapshot"
      && camera.provider === "Comune di Monfalcone"
      && camera.attribution === "CC BY 4.0 predefinita"
      && camera.attributionUrl
        === "https://www.comune.monfalcone.go.it/it/note-legali-30726"
      && camera.sourceUrl
        === "https://www.comune.monfalcone.go.it/it/novita-220905/notizie-220906/condizioni-del-vento-marina-julia-21786"
      && camera.fallbackImageUrl === "/municipalities/photos/031012-photo.webp"
      && camera.mapClusterLabel === "Monfalcone · Marina Julia"
      && camera.playerUrl === ""
    ))).toBe(true);
    expect(marinaJulia.map((camera) => camera.imageUrl)).toEqual([
      "https://anemometro.comune.monfalcone.go.it/monfalcone-cam-marinaJulia1.php",
      "https://anemometro.comune.monfalcone.go.it/monfalcone-cam-marinaJulia2.php",
    ]);
    expect(marinaJulia.map((camera) => [camera.lat, camera.lon])).toEqual([
      [45.77413, 13.52914],
      [45.77274, 13.52759],
    ]);
    expect(cameras.find((camera) => camera.id === "monfalcone-marina")).toMatchObject({
      imageUrl: "",
      playerUrl: "",
      sourceUrl: "https://marinamonfalcone.com/it/webcam/",
    });
    expect(cameras.find((camera) => camera.id === "lignano-punta-faro")).toMatchObject({
      imageUrl: "https://www.lignanosabbiadoro.com/images/webcam6.jpg",
      mediaType: "snapshot",
      attribution: "LignanoSabbiadoro.com",
      attributionUrl: "https://www.lignanosabbiadoro.com/webcam/webcam-spiaggia-punta-faro",
      sourceUrl: "https://www.lignanosabbiadoro.com/webcam/webcam-spiaggia-punta-faro",
      fallbackImageUrl: "/municipalities/photos/030049-photo.webp",
      playerUrl: "",
    });
    const lignano = cameras.filter((camera) => camera.mapClusterId === "lignano-sabbiadoro");
    expect(lignano).toHaveLength(5);
    expect(lignano.every((camera) => camera.mapClusterLabel === "Lignano Sabbiadoro"))
      .toBe(true);
    const monteGrisa = cameras.filter(
      (camera) => camera.mapClusterId === "trieste-monte-grisa",
    );
    expect(monteGrisa).toHaveLength(2);
    expect(monteGrisa.every((camera) => camera.mapClusterLabel === "Monte Grisa"))
      .toBe(true);
    expect(monteGrisa.map((camera) => [camera.lat, camera.lon]))
      .toEqual([[45.69307, 13.749281], [45.69307, 13.749281]]);
    expect(cameras.find((camera) => camera.id === "cisar-lanterna-nord")).toMatchObject({
      imageUrl: "https://www.cisartrieste.it/meteo/lanterna/cam3.jpg",
      mediaType: "snapshot",
      provider: "CISAR Trieste APS",
      sourceUrl: "https://www.cisartrieste.it/meteo-lanterna/",
      mapClusterId: "",
    });
    expect(cameras.find((camera) => camera.id === "gemona-centro")).toMatchObject({
      name: "Gemona del Friuli - Duomo",
      locationLabel: "Gemona del Friuli · Centro storico · Duomo",
      imageUrl: "https://www.meteoproject.it/ftp/webcam/gemonadelfriuli/gemona.jpg",
      mediaType: "snapshot",
      playerUrl: "",
      provider: "WeatherCam · Meteo System",
      attribution: "WeatherCam · Meteo System",
      attributionUrl: "https://www.weathercam.it/webcam/gemona",
      sourceUrl: "https://www.weathercam.it/webcam/gemona",
      fallbackImageUrl: "/municipalities/photos/030043-photo.webp",
    });
    expect(cameras.find((camera) => camera.id === "trieste-miramare")).toMatchObject({
      name: "Trieste - Parco di Miramare",
      locationLabel: "Trieste - Parco di Miramare",
      imageUrl: "https://www.meteosystem.com/webcam/miramare/parco_miramare.jpg",
      mediaType: "snapshot",
      playerUrl: "",
      provider: "Meteo System",
      attribution: "Meteo System",
      attributionUrl: "https://www.meteosystem.com/stazione/trieste-miramare/webcam.php",
      sourceUrl: "https://www.meteosystem.com/stazione/trieste-miramare/webcam.php",
      fallbackImageUrl: "/municipalities/photos/032006-photo.webp",
    });
  });

  it("uses the official Udine panorama as a direct snapshot with one source credit", () => {
    const source = activeManifest.webcams.find(
      (camera) => camera.id === "udine-panorama-castello",
    );

    expect(source).toMatchObject({
      name: "Udine - Panorama dal Castello",
      area: "Specola del Castello",
      imageUrl: "https://panodata.panomax.com/cams/2859/preview_og.jpg",
      mediaType: "snapshot",
      provider: "Comune di Udine · PromoTurismoFVG · Panomax",
      attribution: "Comune di Udine · PromoTurismoFVG · Panomax",
      attributionUrl: "https://udine.panomax.com/",
      sourcePage: "https://udine.panomax.com/",
      fallbackImageUrl: "/municipalities/photos/030129-photo.webp",
    });

    for (const language of ["it", "fur"]) {
      const model = buildManifestModel({ language });
      expect(getRegionalCameras(model).find((camera) => camera.id === source.id)).toMatchObject({
        imageUrl: source.imageUrl,
        mediaType: "snapshot",
        provider: source.provider,
        attribution: source.attribution,
        attributionUrl: source.attributionUrl,
        sourceUrl: source.sourcePage,
        fallbackImageUrl: source.fallbackImageUrl,
        playerUrl: "",
      });
    }
  });

  it("uses the reviewed Zoncolan panorama as a direct snapshot with one source credit", () => {
    const source = activeManifest.webcams.find(
      (camera) => camera.id === "zoncolan-panorama",
    );

    expect(source).toMatchObject({
      name: "Monte Zoncolan - Panorama",
      area: "Monte Zoncolan · quota 1.750 m",
      imageUrl: "https://panodata.panomax.com/cams/1988/preview_og.jpg",
      mediaType: "snapshot",
      provider: "Panomax / PromoTurismoFVG",
      attribution: "Panomax / PromoTurismoFVG",
      attributionUrl: "https://zoncolan.panomax.com/",
      sourcePage: "https://zoncolan.panomax.com/",
      fallbackImageUrl: "/municipalities/photos/030112-photo.webp",
    });

    for (const language of ["it", "fur"]) {
      const model = buildManifestModel({ language });
      expect(getRegionalCameras(model).find((camera) => camera.id === source.id)).toMatchObject({
        imageUrl: source.imageUrl,
        mediaType: "snapshot",
        provider: source.provider,
        attribution: source.attribution,
        attributionUrl: source.attributionUrl,
        sourceUrl: source.sourcePage,
        fallbackImageUrl: source.fallbackImageUrl,
        playerUrl: "",
      });
    }
  });

  it("uses the reviewed Forni di Sopra panorama as a direct snapshot with one source credit", () => {
    const source = activeManifest.webcams.find(
      (camera) => camera.id === "forni-varmost",
    );

    expect(source).toMatchObject({
      name: "Forni di Sopra - Malga Varmost",
      area: "Malga Varmost",
      imageUrl: "https://panodata.panomax.com/cams/1987/preview_og.jpg",
      mediaType: "snapshot",
      provider: "Panomax / PromoTurismoFVG",
      attribution: "Panomax / PromoTurismoFVG",
      attributionUrl: "https://fornidisopra.panomax.com/",
      sourcePage: "https://fornidisopra.panomax.com/",
      fallbackImageUrl: "/municipalities/photos/030041-photo.webp",
    });

    for (const language of ["it", "fur"]) {
      const model = buildManifestModel({ language });
      expect(getRegionalCameras(model).find((camera) => camera.id === source.id)).toMatchObject({
        imageUrl: source.imageUrl,
        mediaType: "snapshot",
        provider: source.provider,
        attribution: source.attribution,
        attributionUrl: source.attributionUrl,
        sourceUrl: source.sourcePage,
        fallbackImageUrl: source.fallbackImageUrl,
        playerUrl: "",
      });
    }
  });

  it("uses the reviewed Piancavallo panorama as a direct snapshot with one source credit", () => {
    const source = activeManifest.webcams.find(
      (camera) => camera.id === "piancavallo-panorama",
    );

    expect(source).toMatchObject({
      name: "Piancavallo - Panorama",
      area: "Piancavallo · quota 1.625 m",
      imageUrl: "https://panodata.panomax.com/cams/1981/preview_og.jpg",
      mediaType: "snapshot",
      provider: "Panomax / PromoTurismoFVG",
      attribution: "Panomax / PromoTurismoFVG",
      attributionUrl: "https://piancavallo.panomax.com/",
      sourcePage: "https://piancavallo.panomax.com/",
      fallbackImageUrl: "/municipalities/photos/093004-photo.webp",
    });

    for (const language of ["it", "fur"]) {
      const model = buildManifestModel({ language });
      expect(getRegionalCameras(model).find((camera) => camera.id === source.id)).toMatchObject({
        imageUrl: source.imageUrl,
        mediaType: "snapshot",
        provider: source.provider,
        attribution: source.attribution,
        attributionUrl: source.attributionUrl,
        sourceUrl: source.sourcePage,
        fallbackImageUrl: source.fallbackImageUrl,
        playerUrl: "",
      });
    }
  });

  it("uses the reviewed Piancavallo Nevelandia OSMER mirror with owner and collector credits", () => {
    const source = activeManifest.webcams.find(
      (camera) => camera.id === "piancavallo-nevelandia",
    );

    expect(source).toMatchObject({
      name: "Piancavallo - Nevelandia",
      area: "Piancavallo · Nevelandia",
      lat: 46.112847,
      lon: 12.52325,
      imageUrl: "https://www.meteo.fvg.it/ext/webcams/webcams/Piancavallo-Nevelandia-image.cgi.jpg",
      mediaType: "snapshot",
      provider: "Nevelandia / Piancavallo 1265",
      attribution: "PromoTurismoFVG · ARPA FVG - OSMER e GRN",
      attributionUrl: "https://www.meteo.fvg.it/webcam_img.php?ln=it",
      sourcePage: "https://www.nevelandia.com/webcam-piancavallo/",
      fallbackImageUrl: "/municipalities/photos/093004-photo.webp",
    });

    for (const language of ["it", "fur"]) {
      const model = buildManifestModel({ language });
      const camera = getRegionalCameras(model).find((item) => item.id === source.id);

      expect(camera).toMatchObject({
        imageUrl: source.imageUrl,
        mediaType: "snapshot",
        provider: source.provider,
        attribution: source.attribution,
        attributionUrl: source.attributionUrl,
        sourceUrl: source.sourcePage,
        fallbackImageUrl: source.fallbackImageUrl,
        playerUrl: "",
        lat: source.lat,
        lon: source.lon,
        positionIsApproximate: false,
        positionPrecision: "declared",
      });
    }
  });

  it("uses the reviewed Moruzzo OSMER mirror with owner and collector credits", () => {
    const source = activeManifest.webcams.find(
      (camera) => camera.id === "moruzzo-panorama",
    );

    expect(source).toMatchObject({
      name: "Moruzzo - Panorama verso ovest",
      area: "Panorama verso ovest",
      lat: 46.1196936077918,
      lon: 13.1235643188482,
      imageUrl: "https://www.meteo.fvg.it/ext/webcams/webcams/Moruzzo-moruzzo.jpg.jpg",
      mediaType: "snapshot",
      provider: "Comune di Moruzzo / Meteo-Project",
      attribution: "WeatherCam / Meteo-Project · ARPA FVG - OSMER e GRN",
      attributionUrl: "https://www.meteo.fvg.it/webcam_img.php?ln=it",
      sourcePage: "https://www.weathercam.it/webcam/moruzzo",
      fallbackImageUrl: "/municipalities/photos/030063-photo.webp",
    });

    for (const language of ["it", "fur"]) {
      const model = buildManifestModel({ language });
      const camera = getRegionalCameras(model).find((item) => item.id === source.id);

      expect(camera).toMatchObject({
        imageUrl: source.imageUrl,
        mediaType: "snapshot",
        provider: source.provider,
        attribution: source.attribution,
        attributionUrl: source.attributionUrl,
        sourceUrl: source.sourcePage,
        fallbackImageUrl: source.fallbackImageUrl,
        playerUrl: "",
        lat: source.lat,
        lon: source.lon,
        positionIsApproximate: false,
        positionPrecision: "declared",
      });
    }
  });

  it("uses only the reviewed Spilimbergo Duomo OSMER view", () => {
    const source = activeManifest.webcams.find(
      (camera) => camera.id === "spilimbergo-duomo",
    );

    expect(source).toMatchObject({
      name: "Spilimbergo - Duomo",
      area: "Piazza Duomo",
      lat: 46.110679,
      lon: 12.904467,
      imageUrl: "https://www.meteo.fvg.it/ext/webcams/webcams/Spilimbergo-Duomo-spilimbergo_piazzaduomo.jpg.jpg",
      mediaType: "snapshot",
      provider: "PromoTurismoFVG",
      attribution: "PromoTurismoFVG · ARPA FVG - OSMER e GRN",
      attributionUrl: "https://www.meteo.fvg.it/webcam_img.php?ln=it",
      sourcePage: "https://www.meteo.fvg.it/webcam_img.php?ln=it",
      fallbackImageUrl: "/municipalities/photos/093044-photo.webp",
    });
    expect(activeManifest.webcams.some(
      (camera) => camera.id === "spilimbergo-municipio",
    )).toBe(false);

    for (const language of ["it", "fur"]) {
      const model = buildManifestModel({ language });
      const camera = getRegionalCameras(model).find((item) => item.id === source.id);

      expect(camera).toMatchObject({
        imageUrl: source.imageUrl,
        mediaType: "snapshot",
        provider: source.provider,
        attribution: source.attribution,
        attributionUrl: source.attributionUrl,
        sourceUrl: source.sourcePage,
        fallbackImageUrl: source.fallbackImageUrl,
        playerUrl: "",
        lat: source.lat,
        lon: source.lon,
        positionIsApproximate: false,
        positionPrecision: "declared",
      });
    }
  });

  it("uses the reviewed Sappada panorama as a direct snapshot with one source credit", () => {
    const source = activeManifest.webcams.find(
      (camera) => camera.id === "sappada-panorama",
    );

    expect(source).toMatchObject({
      name: "Sappada - Panorama",
      area: "Panorama del paese",
      imageUrl: "https://panodata.panomax.com/cams/1894/preview_og.jpg",
      mediaType: "snapshot",
      provider: "Panomax / PromoTurismoFVG",
      attribution: "Panomax / PromoTurismoFVG",
      attributionUrl: "https://sappada.panomax.com/",
      sourcePage: "https://sappada.panomax.com/",
      fallbackImageUrl: "/municipalities/photos/030189-photo.webp",
    });

    for (const language of ["it", "fur"]) {
      const model = buildManifestModel({ language });
      expect(getRegionalCameras(model).find((camera) => camera.id === source.id)).toMatchObject({
        imageUrl: source.imageUrl,
        mediaType: "snapshot",
        provider: source.provider,
        attribution: source.attribution,
        attributionUrl: source.attributionUrl,
        sourceUrl: source.sourcePage,
        fallbackImageUrl: source.fallbackImageUrl,
        playerUrl: "",
      });
    }
  });

  it("uses the reviewed Sella Nevea panorama as a direct snapshot with one source credit", () => {
    const source = activeManifest.webcams.find(
      (camera) => camera.id === "sella-nevea-canin",
    );

    expect(source).toMatchObject({
      name: "Sella Nevea - Monte Canin",
      area: "Sella Nevea · Monte Canin",
      imageUrl: "https://panodata.panomax.com/cams/1984/preview_og.jpg",
      mediaType: "snapshot",
      provider: "Panomax / PromoTurismoFVG",
      attribution: "Panomax / PromoTurismoFVG",
      attributionUrl: "https://sellanevea.panomax.com/",
      sourcePage: "https://sellanevea.panomax.com/",
      fallbackImageUrl: "/municipalities/photos/030025-photo.webp",
    });

    for (const language of ["it", "fur"]) {
      const model = buildManifestModel({ language });
      expect(getRegionalCameras(model).find((camera) => camera.id === source.id)).toMatchObject({
        imageUrl: source.imageUrl,
        mediaType: "snapshot",
        provider: source.provider,
        attribution: source.attribution,
        attributionUrl: source.attributionUrl,
        sourceUrl: source.sourcePage,
        fallbackImageUrl: source.fallbackImageUrl,
        playerUrl: "",
      });
    }
  });

  it("uses the reviewed San Daniele panorama as a direct snapshot with one source credit", () => {
    const source = activeManifest.webcams.find(
      (camera) => camera.id === "san-daniele-centro",
    );

    expect(source).toMatchObject({
      name: "San Daniele del Friuli - Centro",
      area: "Centro",
      imageUrl: "https://panodata.panomax.com/cams/9495/preview_og.jpg",
      mediaType: "snapshot",
      provider: "Panomax / PromoTurismoFVG",
      attribution: "Panomax / PromoTurismoFVG",
      attributionUrl: "https://sandanieledelfriuli.panomax.com/",
      sourcePage: "https://sandanieledelfriuli.panomax.com/",
      fallbackImageUrl: "/municipalities/photos/030099-photo.webp",
    });

    for (const language of ["it", "fur"]) {
      const model = buildManifestModel({ language });
      expect(getRegionalCameras(model).find((camera) => camera.id === source.id)).toMatchObject({
        imageUrl: source.imageUrl,
        mediaType: "snapshot",
        provider: source.provider,
        attribution: source.attribution,
        attributionUrl: source.attributionUrl,
        sourceUrl: source.sourcePage,
        fallbackImageUrl: source.fallbackImageUrl,
        playerUrl: "",
      });
    }
  });

  it("uses the reviewed Trieste San Giusto panorama as a direct snapshot with one source credit", () => {
    const source = activeManifest.webcams.find(
      (camera) => camera.id === "trieste-san-giusto",
    );

    expect(source).toMatchObject({
      name: "Trieste - Colle di San Giusto",
      area: "Colle di San Giusto",
      imageUrl: "https://panodata.panomax.com/cams/6949/preview_og.jpg",
      mediaType: "snapshot",
      provider: "Panomax / PromoTurismoFVG",
      attribution: "Panomax / PromoTurismoFVG",
      attributionUrl: "https://trieste.panomax.com/",
      sourcePage: "https://trieste.panomax.com/",
      fallbackImageUrl: "/municipalities/photos/032006-photo.webp",
    });

    for (const language of ["it", "fur"]) {
      const model = buildManifestModel({ language });
      expect(getRegionalCameras(model).find((camera) => camera.id === source.id)).toMatchObject({
        imageUrl: source.imageUrl,
        mediaType: "snapshot",
        provider: source.provider,
        attribution: source.attribution,
        attributionUrl: source.attributionUrl,
        sourceUrl: source.sourcePage,
        fallbackImageUrl: source.fallbackImageUrl,
        playerUrl: "",
      });
    }
  });

  it("keeps candidate and suspended sources out of every frontend group", () => {
    const model = buildManifestModel();
    const visibleIds = new Set(model.webcams.groups.flatMap((group) => group.cameras.map((camera) => camera.id)));
    const excluded = [...candidateManifest.candidates, ...suspendedManifest.candidates];

    expect(candidateManifest.publish).toBe(false);
    expect(suspendedManifest.publish).toBe(false);
    expect(excluded.length).toBeGreaterThan(0);
    excluded.forEach((camera) => expect(visibleIds.has(camera.id), camera.id).toBe(false));
    expect(visibleIds.has("aquileia-basilica")).toBe(false);
    expect(visibleIds.has("claut-val-settimana")).toBe(false);
  });

  it("shows Barcis and Pradut as direct snapshots with source links and map candidates", () => {
    const model = buildManifestModel();
    const cameras = getRegionalCameras(model);
    const barcis = cameras.find((camera) => camera.id === "barcis-paese");
    const pradut = cameras.find((camera) => camera.id === "claut-pradut");

    expect(barcis).toMatchObject({
      imageUrl: "https://www.meteo.fvg.it/ext/webcams/webcams/Barcis2-barcis.jpg.jpg",
      mediaType: "snapshot",
      fallbackImageUrl: "/municipalities/photos/093006-photo.webp",
      sourceUrl: "https://www.meteo.fvg.it/webcam_img.php?ln=it",
      provider: "PromoTurismoFVG",
      positionPrecision: "municipality",
      positionIsApproximate: true,
      distanceKm: null,
      distanceLabel: "",
    });
    expect(pradut).toMatchObject({
      imageUrl: "https://www.parcodolomitifriulane.it/webcam/PN01/cam000M.jpg",
      mediaType: "snapshot",
      fallbackImageUrl: "/municipalities/photos/093015-photo.webp",
      sourceUrl: "https://www.parcodolomitifriulane.it/vivere-il-parco/webcam-meteo/",
      provider: "Parco Naturale Dolomiti Friulane",
      lat: 46.25613,
      lon: 12.56501,
      positionPrecision: "declared",
      positionIsApproximate: false,
    });
    expect(model.webcams.mapCandidates).toEqual(expect.arrayContaining([barcis, pradut]));
  });

  it.each([
    ["sacile", "sacile"],
    ["monfalcone-marina", "monfalcone"],
    ["forni-varmost", "forni-di-sopra"],
    ["piancavallo-panorama", "aviano"],
    ["cividale-campanile-ex-monastero", "cividale-del-friuli"],
    ["cividale-piazza-duomo", "cividale-del-friuli"],
    ["cividale-piazza-paolo-diacono", "cividale-del-friuli"],
    ["udine-panorama-castello", "udine"],
    ["gemona-centro", "gemona-del-friuli"],
  ])("uses the %s municipal fallback and marks its distance as approximate", (id, placeKey) => {
    const source = activeManifest.webcams.find((camera) => camera.id === id);
    const place = FIXED_FVG_PLACES[placeKey];

    expect(source.municipality).toBe(place.name);
    expect(source).not.toHaveProperty("lat");
    expect(source).not.toHaveProperty("lon");
    expect(source).not.toHaveProperty("coordinates");

    ["it", "fur"].forEach((language) => {
      const model = buildManifestModel({
        language,
        location: { city: place.name, lat: place.latitude, lon: place.longitude },
      });
      const camera = getRegionalCameras(model).find((item) => item.id === id);

      expect(camera).toMatchObject({
        place: place.name,
        fallbackImageUrl: `/municipalities/photos/${place.istatCode}-photo.webp`,
        sourceUrl: source.sourcePage,
        distanceKm: 0,
        distanceLabel: "~0 km",
        lat: place.latitude,
        lon: place.longitude,
        positionIsApproximate: true,
        positionPrecision: "municipality",
      });
      expect(model.webcams.mapCandidates.find((item) => item.id === id)).toBe(camera);
      expect(model.webcams.groups.find((group) => group.id === "nearby").cameras
        .some((camera) => camera.id === id)).toBe(true);
    });
  });

  it("keeps each active webcam as a map candidate with honest coordinate precision", () => {
    const model = buildManifestModel();
    const declaredIds = new Set(activeManifest.webcams
      .filter((camera) => Number.isFinite(camera.lat) && Number.isFinite(camera.lon))
      .map((camera) => camera.id));

    expect(model.webcams.mapItems).toEqual([]);
    expect(model.webcams.mapCandidates).toHaveLength(activeManifest.webcams.length);
    expect(new Set(model.webcams.mapCandidates.map((camera) => camera.id)).size)
      .toBe(activeManifest.webcams.length);
    model.webcams.mapCandidates.forEach((camera) => {
      expect(Number.isFinite(camera.lat), camera.id).toBe(true);
      expect(Number.isFinite(camera.lon), camera.id).toBe(true);
      expect(camera.positionPrecision).toBe(declaredIds.has(camera.id) ? "declared" : "municipality");
      expect(camera.positionIsApproximate).toBe(!declaredIds.has(camera.id));
      expect(camera.mapEnabled).toBe(false);
      expect(camera.checkedAt).toBeTruthy();
      expect(camera.capturedAt).toBe("");
    });
  });

  it("publishes only a webcam explicitly approved for the map", () => {
    const approvedId = "grado-al-bosco";
    const model = buildManifestModel({
      manifest: {
        ...activeManifest,
        webcams: activeManifest.webcams.map((camera) => camera.id === approvedId
          ? { ...camera, mapEnabled: true }
          : camera),
      },
    });

    expect(model.webcams.mapItems.map((camera) => camera.id)).toEqual([approvedId]);
    expect(model.webcams.mapItems[0]).toMatchObject({
      mapEnabled: true,
      mapStatus: "map_ready",
      positionPrecision: "declared",
    });
  });
});
