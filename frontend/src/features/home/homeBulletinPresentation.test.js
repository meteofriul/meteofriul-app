import { describe, expect, it } from "vitest";

import { buildHomeBulletinPresentation } from "./homeBulletinPresentation";

const NONE = Object.freeze({ code: 100, id: "none", label: "" });

function buildStructuredDay({ isStale = false } = {}) {
  return {
    areas9: {
      A5: {
        id: "A5",
        source_kind: "structured_xml",
        symbols: {
          cielo: { code: 3, id: "cloudy", label: "nuvoloso" },
          nebbia: NONE,
          neve: NONE,
          pioggia: { code: 7, id: "moderate_rain", label: "moderata" },
          temporale: NONE,
          vento: NONE,
        },
        text: "ALLERTA E TEMPORALI FINO A SERA: testo narrativo da non interpretare.",
        valid_date: "2026-09-17",
      },
    },
    osmer_structured_source: {
      data_emissione: "2026-09-17T08:23:00Z",
      id_emissione: "PW26091710",
      is_stale: isStale,
      raw_hash: "sha256-a5-20260917",
      source_status: "normalized",
    },
    source_kind: "structured_xml",
    valid_date: "2026-09-17",
  };
}

function buildBulletinModel(structuredDay = buildStructuredDay(), overrides = {}) {
  return {
    days: [
      {
        id: "today",
        date: "Giovedì 17 settembre",
        emission: "17-09-2026 09:17 CEST",
        forecastDate: "2026-09-17",
        osmerStructuredDay: structuredDay,
        text: "AGGIORNAMENTO: Cielo in prevalenza nuvoloso. Piogge sparse e temporalesche soprattutto verso la costa.",
      },
    ],
    source: { label: "OSMER ARPA FVG" },
    status: "ready",
    ...overrides,
  };
}

function buildIconWeatherState(slots, overrides = {}) {
  return {
    isStale: false,
    rawCurrent: {
      primary_source: "icon2i_local_pilot",
      hourly_forecast: slots,
    },
    status: "fresh",
    ...overrides,
  };
}

function buildIconSlot(hour, overrides = {}) {
  return {
    condition: "Sereno",
    precipitation: 0,
    temperature: 18,
    time: `2026-09-17T${String(hour).padStart(2, "0")}:00:00Z`,
    wind_gusts: 10,
    wind_speed: 5,
    ...overrides,
  };
}

describe("buildHomeBulletinPresentation", () => {
  it("keeps the OSMER headline but derives the public advice only from ICON", () => {
    const presentation = buildHomeBulletinPresentation(buildBulletinModel(), {
      language: "it",
      location: { city: "Pordenone" },
      now: "2026-09-17T09:00:00Z",
      weatherState: buildIconWeatherState([
        buildIconSlot(10, { condition: "Temporale", precipitation: 2 }),
      ]),
    });

    expect(presentation).toMatchObject({
      advice: {
        group: "storm",
        label: "Se il cielo brontola, niente attese: cerca subito riparo.",
        source: "icon2i",
        title: "Consigliato",
      },
      adviceStatus: "ready",
      dateLabel: "Oggi · OSMER 10:23",
      headline: "Nuvoloso con piogge",
      icon: { type: "Rain" },
      kind: "local_structured",
      snapshotKey: "osmer:PW26091710:2026-09-17T08:23:00Z:sha256-a5-20260917:2026-09-17:A5",
      sourceLabel: "OSMER ARPA FVG",
    });
    expect(presentation.body).toBeUndefined();
    expect(JSON.stringify(presentation)).not.toMatch(/allerta|fino a sera/iu);
  });

  it("uses the local ICON forecast as branded advice without reinterpreting OSMER prose", () => {
    const structuredDay = buildStructuredDay({ isStale: true });
    const weatherState = buildIconWeatherState([
      buildIconSlot(10, { temperature: 19 }),
      buildIconSlot(11, { temperature: 18 }),
      buildIconSlot(12, { temperature: 17 }),
    ]);

    const presentation = buildHomeBulletinPresentation(buildBulletinModel(structuredDay), {
      language: "it",
      location: { city: "Pordenone" },
      now: "2026-09-17T09:00:00Z",
      weatherState,
    });

    expect(presentation).toMatchObject({
      advice: {
        group: "stable",
        label: "Il tempo tiene: una buona occasione per stare all’aperto.",
        source: "icon2i",
        title: "Consigliato",
      },
      adviceStatus: "ready",
      body: "",
      headline: "Cielo in prevalenza nuvoloso",
      kind: "official_text",
    });
    expect(JSON.stringify(presentation.advice)).not.toMatch(/costa|temporalesche|OSMER/iu);
  });

  it("keeps the source-faithful OSMER detail when ICON is stale", () => {
    const presentation = buildHomeBulletinPresentation(
      buildBulletinModel(buildStructuredDay({ isStale: true })),
      {
        language: "it",
        location: "Pordenone",
        now: "2026-09-17T09:00:00Z",
        weatherState: buildIconWeatherState([buildIconSlot(10)], { isStale: true }),
      },
    );

    expect(presentation).toMatchObject({
      advice: null,
      adviceStatus: "unavailable",
      body: "Piogge sparse e temporalesche soprattutto verso la costa.",
    });
  });

  it("suppresses the OSMER detail and reserves the advice callout while ICON is pending", () => {
    const presentation = buildHomeBulletinPresentation(
      buildBulletinModel(buildStructuredDay({ isStale: true })),
      {
        advicePending: true,
        language: "it",
        location: "Pordenone",
        now: "2026-09-17T09:00:00Z",
        weatherState: null,
      },
    );

    expect(presentation).toMatchObject({
      advice: null,
      adviceStatus: "pending",
      body: "",
    });
  });

  it.each([
    ["stale", (day) => { day.osmer_structured_source.is_stale = true; }],
    ["incomplete", (day) => { delete day.osmer_structured_source.id_emissione; }],
  ])("fails closed for %s local provenance and shows only the official bulletin", (_case, mutate) => {
    const structuredDay = buildStructuredDay();
    mutate(structuredDay);

    const presentation = buildHomeBulletinPresentation(buildBulletinModel(structuredDay), {
      language: "it",
      location: { city: "Pordenone" },
    });

    expect(presentation).toMatchObject({
      advice: null,
      adviceStatus: "unavailable",
      body: "Piogge sparse e temporalesche soprattutto verso la costa.",
      dateLabel: "Oggi · OSMER 09:17",
      headline: "Cielo in prevalenza nuvoloso",
      icon: { type: "Cloud" },
      kind: "official_text",
      snapshotKey: "official:17-09-2026 09:17 CEST:2026-09-17",
    });
    expect(JSON.stringify(presentation)).not.toMatch(/Ombrello consigliato|Prudenza durante i temporali/iu);
  });

  it("marks the official fallback as not updated without inventing local advice", () => {
    const presentation = buildHomeBulletinPresentation(
      buildBulletinModel(buildStructuredDay({ isStale: true }), { status: "stale_visible" }),
      { language: "it", location: "Pordenone" },
    );

    expect(presentation).toMatchObject({
      advice: null,
      body: "Piogge sparse e temporalesche soprattutto verso la costa.",
      dateLabel: "Oggi · OSMER 09:17 · non aggiornato",
      headline: "Cielo in prevalenza nuvoloso",
      icon: { type: "Cloud" },
      kind: "official_text",
    });
  });

  it("promotes the official lead and keeps the following sentence as source-faithful detail", () => {
    const model = buildBulletinModel(null);
    model.days[0].text = "Cielo da variabile a nuvoloso. Tempo più instabile verso la costa, dove sarà possibile qualche rovescio o temporale sparso.";

    const presentation = buildHomeBulletinPresentation(model, {
      language: "it",
      location: "Pordenone",
    });

    expect(presentation).toMatchObject({
      advice: null,
      body: "Tempo più instabile verso la costa, dove sarà possibile qualche rovescio o temporale sparso.",
      dateLabel: "Oggi · OSMER 09:17",
      headline: "Cielo da variabile a nuvoloso",
      kind: "official_text",
    });
    expect(presentation.headline).not.toContain("OSMER");
  });

  it("does not repeat a one-sentence official forecast below its headline", () => {
    const model = buildBulletinModel(null);
    model.days[0].text = "Cielo da variabile a nuvoloso.";

    const presentation = buildHomeBulletinPresentation(model, {
      language: "it",
      location: "Pordenone",
    });

    expect(presentation.headline).toBe("Cielo da variabile a nuvoloso");
    expect(presentation.body).toBe("");
  });

  it.each([
    ["it", "Previsione non disponibile"],
    ["fur", "Prevision no disponibile"],
  ])("uses a neutral %s fallback without duplicating the source", (language, headline) => {
    const model = buildBulletinModel(null);
    model.days[0].text = "";

    const presentation = buildHomeBulletinPresentation(model, {
      language,
      location: "Pordenone",
    });

    expect(presentation.headline).toBe(headline);
    expect(presentation.headline).not.toContain("OSMER");
  });
});
