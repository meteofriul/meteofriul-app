import { describe, expect, it } from "vitest";

import osmerFixture from "../../tests/fixtures/PW20260606.normalized.json";
import { OSMER_SOURCE_KINDS, OSMER_STRUCTURED_STATES } from "../../domain/weather/osmerStructuredContract";
import {
  buildBulletinViewModel,
  buildOfficialAlertPresentation,
} from "./bulletinViewModel";

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

describe("bulletin view model", () => {
  it("builds bulletin days from official OSMER text and structured A1-A9 data", () => {
    const model = buildBulletinViewModel({
      forecast: {
        official: {
          it: {
            forecasts: [
              {
                date: "2026-06-07",
                date_label: "domenica 7 giugno",
                emission: "06-06-2026 12:19",
                text: "Al mattino cielo poco nuvoloso. Nel pomeriggio rovesci locali sui monti.",
              },
            ],
          },
        },
        osmer_structured: osmerFixture,
      },
      officialAlerts: { active: false, alerts: [] },
    });

    expect(model.status).toBe("ready");
    expect(model.hasOfficialText).toBe(true);
    expect(model.hasStructuredMap).toBe(true);
    expect(model.source).toMatchObject({
      label: "OSMER ARPA FVG",
      updatedLabel: "Aggiornato 06/06 - 12:19",
      url: "https://www.meteo.fvg.it/",
    });
    expect(model.days[0]).toMatchObject({
      date: "domenica 7 giugno",
      forecastDate: "2026-06-07",
      hasOfficialText: true,
      hasStructuredMap: true,
      source: "osmer_structured",
      text: "Al mattino cielo poco nuvoloso. Nel pomeriggio rovesci locali sui monti.",
    });
    expect(model.days[0].mapPoints).toHaveLength(9);
  });

  it("localizes the bulletin source updated label in Friulian", () => {
    const model = buildBulletinViewModel({
      forecast: {
        official: {
          it: {
            updated_at: "06-06-2026 12:19",
            forecasts: [
              {
                date: "2026-06-07",
                text: "Bollettino testuale.",
              },
            ],
          },
        },
      },
    }, { fallbackDays: [], language: "fur" });

    expect(model.source.updatedLabel).toBe("Inzornat 06/06 - 12:19");
  });

  it("derives visible tab labels from forecast dates instead of fixture weekdays", () => {
    const forecasts = [
      "2026-06-27",
      "2026-06-28",
      "2026-06-29",
      "2026-06-30",
      "2026-07-01",
    ].map((date) => ({
      date,
      text: `Bollettino test ${date}.`,
    }));

    const model = buildBulletinViewModel({
      forecast: {
        official: {
          it: {
            forecasts,
          },
        },
      },
    }, { now: new Date("2026-06-27T10:00:00+02:00") });

    expect(model.days.map((day) => day.tabLabel)).toEqual([
      "Oggi",
      "Domenica",
      "Luned\u00ec",
      "Marted\u00ec",
      "Mercoled\u00ec",
    ]);
    expect(model.days[1]).toMatchObject({
      date: "domenica 28 giugno",
      tabLabel: "Domenica",
    });
  });

  it("keeps Oggi tied to the current local date when days advance", () => {
    const model = buildBulletinViewModel({
      forecast: {
        official: {
          it: {
            forecasts: [
              {
                date: "2026-06-28",
                text: "Bollettino di domenica.",
              },
            ],
          },
        },
      },
    }, { now: new Date("2026-06-28T09:00:00+02:00") });

    expect(model.days[0]).toMatchObject({
      date: "domenica 28 giugno",
      tabLabel: "Oggi",
    });
  });

  it("does not label an old first forecast as Oggi after midnight", () => {
    const model = buildBulletinViewModel({
      forecast: {
        official: {
          it: {
            forecasts: [
              {
                date: "2026-06-27",
                text: "Bollettino del giorno precedente.",
              },
            ],
          },
        },
      },
    }, { now: new Date("2026-06-28T09:00:00+02:00") });

    expect(model.days[0]).toMatchObject({
      date: "sabato 27 giugno",
      tabLabel: "Sabato",
    });
  });

  it("derives Friulian tab labels from forecast dates without using stale fixture weekdays", () => {
    const forecasts = [
      "2026-06-27",
      "2026-06-28",
      "2026-06-29",
      "2026-06-30",
      "2026-07-01",
    ].map((date) => ({
      date,
      text: `Bollettino test ${date}.`,
    }));

    const model = buildBulletinViewModel({
      forecast: {
        official: {
          it: {
            forecasts,
          },
        },
      },
    }, { language: "fur", now: new Date("2026-06-27T10:00:00+02:00") });

    expect(model.days.slice(1).map((day) => day.tabLabel)).toEqual([
      "Domenie",
      "Lunis",
      "Martars",
      "Miercus",
    ]);
  });

  it("does not let a shifted model forecast override the official OSMER summary", () => {
    const model = buildBulletinViewModel({
      forecast: {
        forecast: [
          {
            condition: "Coperto",
            date: "2026-06-08",
          },
        ],
        official: {
          it: {
            forecasts: [
              {
                date: "2026-06-07",
                text: "Temporali diffusi su tutta la regione nel corso della giornata.",
              },
            ],
          },
        },
      },
    }, { fallbackDays: [] });

    expect(model.days[0]).toMatchObject({
      forecastDate: "2026-06-07",
      source: "official_text",
      summary: "Temporali possibili",
    });
  });

  it("keeps a not-yet-emitted fifth bulletin as pending on the correct calendar day", () => {
    const forecasts = [
      "2026-06-28",
      "2026-06-29",
      "2026-06-30",
      "2026-07-01",
    ].map((date) => ({
      date,
      text: `Bollettino ufficiale ${date}.`,
    }));

    const model = buildBulletinViewModel({
      forecast: {
        forecast: [
          { condition: "Poco nuvoloso", date: "2026-06-29" },
          { condition: "Poco nuvoloso", date: "2026-06-30" },
          { condition: "Temporale", date: "2026-07-01" },
          { condition: "Coperto", date: "2026-07-02" },
          { condition: "Rovesci", date: "2026-07-03" },
        ],
        official: {
          it: {
            forecasts,
          },
        },
      },
    }, { now: new Date("2026-06-28T09:00:00+02:00") });

    expect(model.days).toHaveLength(5);
    expect(model.days[4]).toMatchObject({
      forecastDate: "2026-07-02",
      hasOfficialText: false,
      hasStructuredMap: false,
      source: "pending_official",
      summary: "Non ancora emesso",
      tabLabel: "Giovedì",
      text: "Bollettino non ancora emesso.",
    });
    expect(model.days[4].mapPoints).toEqual([]);
  });

  it("keeps the Friulian bulletin calendar aligned when translated forecasts are stale", () => {
    const italianForecasts = [
      "2026-06-28",
      "2026-06-29",
      "2026-06-30",
      "2026-07-01",
    ].map((date) => ({
      date,
      text: `Bollettino italiano ${date}.`,
    }));
    const friulianForecasts = [
      { date: "2026-06-27", date_label: "domenie 28 Jugn", text: "Boletin furlan 28." },
      { date: "2026-06-28", date_label: "lunis 29 Jugn", text: "Boletin furlan 29." },
      { date: "2026-06-29", date_label: "martars 30 Jugn", text: "Boletin furlan 30." },
      { date: "2026-06-30", date_label: "tindince par miercus 01 Lui", text: "Boletin furlan 01." },
    ];

    const model = buildBulletinViewModel({
      forecast: {
        official: {
          fur: {
            forecasts: friulianForecasts,
          },
          it: {
            forecasts: italianForecasts,
          },
        },
      },
    }, { language: "fur", now: new Date("2026-06-28T09:00:00+02:00") });

    expect(model.days.map((day) => day.tabLabel)).toEqual([
      "Vuê",
      "Lunis",
      "Martars",
      "Miercus",
      "Joibe",
    ]);
    expect(model.days[0]).toMatchObject({
      forecastDate: "2026-06-28",
      date: "domenie 28 Jugn",
      text: "Boletin furlan 28.",
    });
    expect(model.days[3]).toMatchObject({
      forecastDate: "2026-07-01",
      date: "tindince par miercus 01 Lui",
      text: "Boletin furlan 01.",
    });
    expect(model.days[4]).toMatchObject({
      forecastDate: "2026-07-02",
      source: "pending_official",
      summary: "No ancjemò publicât",
      tabLabel: "Joibe",
      text: "Boletin no ancjemò publicât.",
    });
  });

  it("matches structured OSMER maps by forecast date instead of model array index", () => {
    const shiftedModelDay = {
      condition: "Coperto",
      date: "2026-06-08",
      osmer_structured_day: osmerFixture.days[1],
    };

    const model = buildBulletinViewModel({
      forecast: {
        forecast: [shiftedModelDay],
        official: {
          it: {
            forecasts: [
              {
                date: "2026-06-07",
                text: "Testo ufficiale del giorno corretto.",
              },
            ],
          },
        },
        osmer_structured: osmerFixture,
      },
    }, { fallbackDays: [] });

    expect(model.days[0]).toMatchObject({
      forecastDate: "2026-06-07",
      hasStructuredMap: true,
      source: "osmer_structured",
    });
    expect(model.days[0].osmerStructuredDay.valid_date).toBe("2026-06-07");
  });

  it("keeps the map unavailable when A1-A9 data are missing instead of inventing markers", () => {
    const model = buildBulletinViewModel({
      forecast: {
        official: {
          it: {
            forecasts: [
              {
                date: "2026-06-07",
                text: "Bollettino testuale senza mappa strutturata.",
              },
            ],
          },
        },
      },
    }, { fallbackDays: [] });

    expect(model.status).toBe("ready");
    expect(model.hasStructuredMap).toBe(false);
    expect(model.days[0]).toMatchObject({
      hasOfficialText: true,
      hasStructuredMap: false,
      source: "official_text",
    });
    expect(model.days[0].mapPoints).toEqual([]);
  });

  it("does not render stale OSMER structured data as a current native map", () => {
    const staleFixture = clone(osmerFixture);
    staleFixture.is_stale = true;
    staleFixture.source_status = "source_unavailable";

    const model = buildBulletinViewModel({
      forecast: {
        official: {
          it: {
            forecasts: [
              {
                date: "2026-06-07",
                text: "Testo ufficiale disponibile, mappa strutturata non fresca.",
              },
            ],
          },
        },
        osmer_structured: staleFixture,
      },
    }, { fallbackDays: [] });

    expect(model.hasStructuredMap).toBe(false);
    expect(model.days[0]).toMatchObject({
      hasOfficialText: true,
      hasStructuredMap: false,
      reliability: "",
      source: "official_text",
    });
    expect(model.days[0].mapPoints).toEqual([]);
    expect(model.days[0].mapBadges).toEqual([]);
    expect(model.days[0].osmerStructuredContract).toMatchObject({
      canRenderNativeMap: false,
      state: OSMER_STRUCTURED_STATES.STALE,
    });
  });

  it("exposes per-day provenance without changing the bulletin map availability contract", () => {
    const mergedFixture = clone(osmerFixture);
    mergedFixture.id_emissione = "NW20260609";
    mergedFixture.data_emissione = "2026-06-06T16:30:00Z";
    mergedFixture.is_stale = false;
    mergedFixture.days[0].osmer_structured_source = {
      id_emissione: "PW20260605",
      data_emissione: "2026-06-05T10:15:00Z",
      published_at: "2026-06-05T10:15:00Z",
      updated_at: "2026-06-05T10:17:00Z",
      raw_hash: "day-specific-hash",
      source_date: "2026-06-05",
      source_status: "reachable_xml",
      is_stale: true,
    };

    const model = buildBulletinViewModel({
      forecast: {
        official: {
          it: {
            forecasts: [
              {
                date: "2026-06-07",
                emission: "06-06-2026 12:19",
                text: "Testo ufficiale della stessa emissione HTML.",
              },
            ],
          },
        },
        osmer_structured: mergedFixture,
      },
    }, { fallbackDays: [] });

    expect(model.source.updatedLabel).toBe("Aggiornato 06/06 - 12:19");
    expect(model.days[0]).toMatchObject({
      emission: "06-06-2026 12:19",
      hasStructuredMap: true,
      source: "osmer_structured",
      osmerStructuredSource: {
        dataEmission: "2026-06-05T10:15:00Z",
        id: "PW20260605",
        isStale: true,
        rawHash: "day-specific-hash",
        updatedAt: "2026-06-05T10:17:00Z",
      },
    });
    expect(model.days[0].osmerStructuredContract).toMatchObject({
      canRenderNativeMap: true,
      state: OSMER_STRUCTURED_STATES.READY,
    });
  });

  it("keeps official projected OSMER days distinct from native XML maps", () => {
    const projectedFixture = clone(osmerFixture);
    projectedFixture.fonte = OSMER_SOURCE_KINDS.OFFICIAL_PROJECTED;
    projectedFixture.days = [projectedFixture.days[0]];

    for (const area of Object.values(projectedFixture.days[0].areas9)) {
      area.source_kind = OSMER_SOURCE_KINDS.OFFICIAL_PROJECTED;
      area.projected_condition = "poco nuvoloso";
    }

    const model = buildBulletinViewModel({
      forecast: {
        official: {
          it: {
            forecasts: [
              {
                date: "2026-06-07",
                text: "Testo ufficiale proiettato.",
              },
            ],
          },
        },
        osmer_structured: projectedFixture,
      },
    }, { fallbackDays: [] });

    expect(model.hasStructuredMap).toBe(false);
    expect(model.days[0]).toMatchObject({
      hasOfficialText: true,
      hasStructuredMap: false,
      reliability: "",
      source: "official_text",
    });
    expect(model.days[0].mapBadges).toEqual([]);
    expect(model.days[0].mapPoints).toEqual([]);
    expect(model.days[0].osmerStructuredContract).toMatchObject({
      canRenderNativeMap: false,
      canRenderProjectedMap: true,
      sourceKind: OSMER_SOURCE_KINDS.OFFICIAL_PROJECTED,
    });
  });

  it("keeps reliability hidden when structured A1-A9 data are partial", () => {
    const partialFixture = clone(osmerFixture);
    partialFixture.days = [partialFixture.days[0]];
    delete partialFixture.days[0].areas9.A9;

    const model = buildBulletinViewModel({
      forecast: {
        official: {
          it: {
            forecasts: [
              {
                date: "2026-06-07",
                text: "Testo ufficiale disponibile, mappa incompleta.",
              },
            ],
          },
        },
        osmer_structured: partialFixture,
      },
    }, { fallbackDays: [] });

    expect(model.days[0]).toMatchObject({
      hasOfficialText: true,
      hasStructuredMap: false,
      reliability: "",
      source: "official_text",
    });
    expect(model.days[0].mapPoints).toEqual([]);
  });

  it("exposes only actionable official alerts to the bulletin UI", () => {
    const model = buildBulletinViewModel({
      forecast: {},
      officialAlerts: {
        alerts: [
          { id: "green", level: "verde", title: "Nessuna allerta" },
          {
            id: "yellow",
            level: "gialla",
            official_text: "ALLERTA GIALLA PER TEMPORALI",
            valid_to: "2026-08-03T12:00:00+02:00",
          },
        ],
      },
    }, {
      fallbackDays: [],
      now: new Date("2026-08-03T09:00:00+02:00"),
    });

    expect(model.alert).toMatchObject({
      count: 1,
      label: "Allerta gialla in FVG",
      level: "yellow",
      meta: "Protezione Civile FVG",
      tone: "yellow",
      validityLabel: "Valida fino alle 12:00 del 3 agosto",
    });
    expect(model.alert.text).toBe("Allerta gialla per temporali.");
    expect(model).not.toHaveProperty("alertStatus");
  });

  it("exports the localized official-alert presentation independently from the bulletin", () => {
    const alert = buildOfficialAlertPresentation({
      active: true,
      alerts: [{
        id: "regional-orange",
        level: "arancione",
        official_text: "ALLERTA ARANCIONE PER TEMPORALI",
        valid_to: "2026-08-03T14:00:00+02:00",
      }],
      source_mode: "official_widget",
    }, {
      language: "fur",
      now: new Date("2026-08-03T09:00:00+02:00"),
    });

    expect(alert).toMatchObject({
      action: { anchor: "official-alerts", tab: "bulletin" },
      label: "Alerte narançon in FVG",
      languageNotice: "Test uficiâl in talian - FUR in revision",
      meta: "Protezion Civîl FVG",
      tone: "orange",
      validityLabel: "Valide fin aes 14:00 dai 03 di Avost",
    });
  });

  it("preserves the official area, risks, validity, and source for the pilot alert detail", () => {
    const alert = buildOfficialAlertPresentation({
      active: true,
      alerts: [{
        area: "Friuli Venezia Giulia - pianura e costa",
        id: "regional-orange-rich",
        level: "arancione",
        official_text: "ALLERTA ARANCIONE PER TEMPORALI FORTI",
        risks: ["Temporali forti", "Rischio idrogeologico"],
        source: { name: "Protezione Civile FVG" },
        valid_from: "2026-08-03T14:00:00+02:00",
        valid_to: "2026-08-03T20:00:00+02:00",
        zones: ["FVG-C", "FVG-D"],
      }],
    }, {
      language: "it",
      now: new Date("2026-08-03T15:00:00+02:00"),
    });

    expect(alert).toMatchObject({
      area: "Friuli Venezia Giulia - pianura e costa",
      risks: ["Temporali forti", "Rischio idrogeologico"],
      sourceLabel: "Protezione Civile FVG",
      validFrom: "2026-08-03T14:00:00+02:00",
      validTo: "2026-08-03T20:00:00+02:00",
      zones: ["FVG-C", "FVG-D"],
    });
  });

  it("keeps an explicit compact validity label when the official narrative already includes it", () => {
    const alert = buildOfficialAlertPresentation({
      active: true,
      alerts: [{
        id: "regional-orange",
        level: "arancione",
        official_text: "#AllertameteoFVG - ALLERTA REGIONALE 24 DEL 2026 DALLE ORE 18:00 DI GIOVEDI' 20/08/26 ALLE ORE 24:00 DI VENERDI' 21/08/26 ALLERTA ARANCIONE PER TEMPORALI FORTI SU TUTTA LA REGIONE.",
        valid_to: "2026-08-21T23:59:00+02:00",
      }],
      source_mode: "official_widget",
    }, {
      language: "it",
      now: new Date("2026-08-20T18:00:00+02:00"),
    });

    expect(alert).toMatchObject({
      validityIncludedInText: true,
      validityLabel: "Valida fino alle 23:59 del 21 agosto",
    });
  });

  it("uses the highest-severity alert for label, text, and validity", () => {
    const model = buildBulletinViewModel({
      forecast: {},
      officialAlerts: {
        active: true,
        alerts: [
          {
            id: "yellow-first",
            level: "gialla",
            official_text: "ALLERTA GIALLA PER PIOGGIA",
            valid_to: "2026-08-03T13:00:00+02:00",
          },
          {
            id: "red-second",
            level: "rossa",
            official_text: "ALLERTA ROSSA PER TEMPORALI",
            valid_to: "2026-08-03T14:00:00+02:00",
          },
        ],
      },
    }, {
      fallbackDays: [],
      now: new Date("2026-08-03T09:00:00+02:00"),
    });

    expect(model.alert).toMatchObject({
      label: "Allerta rossa in FVG",
      level: "red",
      text: "Allerta rossa per temporali.",
      validityLabel: "Valida fino alle 14:00 del 3 agosto",
    });
  });

  it("recomputes the presentation at each exact valid-to boundary", () => {
    const payload = {
      active: true,
      alerts: [
        {
          id: "red-first",
          level: "rossa",
          official_text: "ALLERTA ROSSA PER TEMPORALI",
          valid_to: "2026-08-03T10:00:00+02:00",
        },
        {
          id: "yellow-second",
          level: "gialla",
          official_text: "ALLERTA GIALLA PER PIOGGIA",
          valid_to: "2026-08-03T12:00:00+02:00",
        },
      ],
      expires_at: "2026-08-03T12:00:00+02:00",
      source_mode: "official_widget",
    };

    expect(buildOfficialAlertPresentation(payload, {
      now: new Date("2026-08-03T09:59:59.999+02:00"),
    })).toMatchObject({ label: "Allerta rossa in FVG", validityLabel: "Valida fino alle 10:00 del 3 agosto" });
    expect(buildOfficialAlertPresentation(payload, {
      now: new Date("2026-08-03T10:00:00+02:00"),
    })).toMatchObject({ label: "Allerta gialla in FVG", validityLabel: "Valida fino alle 12:00 del 3 agosto" });
    expect(buildOfficialAlertPresentation(payload, {
      now: new Date("2026-08-03T12:00:00+02:00"),
    })).toBeNull();
  });

  it("does not keep showing an expired severe alert while a lower one remains valid", () => {
    const model = buildBulletinViewModel({
      forecast: {},
      officialAlerts: {
        active: true,
        alerts: [
          {
            id: "expired-red",
            level: "rossa",
            official_text: "ALLERTA ROSSA SCADUTA",
            valid_to: "2026-08-03T08:59:00+02:00",
          },
          {
            id: "active-yellow",
            level: "gialla",
            official_text: "ALLERTA GIALLA PER PIOGGIA",
            valid_to: "2026-08-03T14:00:00+02:00",
          },
        ],
        expires_at: "2026-08-03T14:00:00+02:00",
      },
    }, {
      fallbackDays: [],
      now: new Date("2026-08-03T09:00:00+02:00"),
    });

    expect(model.alert).toMatchObject({
      label: "Allerta gialla in FVG",
      level: "yellow",
      text: "Allerta gialla per PIOGGIA.",
      validityLabel: "Valida fino alle 14:00 del 3 agosto",
    });
  });

  it("does not expose unavailable or stale official alerts as active bulletin alerts", () => {
    const unavailableModel = buildBulletinViewModel({
      forecast: {},
      officialAlerts: {
        active: false,
        alerts: [],
        cache: { status: "unavailable" },
        error: "official_alerts_unavailable",
        source_mode: "official_alerts_unavailable_fast_fallback",
      },
    }, { fallbackDays: [] });

    expect(unavailableModel.alert).toBeNull();
    expect(unavailableModel).not.toHaveProperty("alertStatus");

    const staleModel = buildBulletinViewModel({
      forecast: {},
      officialAlerts: {
        active: true,
        alerts: [{ id: "old-yellow", level: "gialla" }],
        cache: { status: "stale" },
        source_mode: "github_actions_official_page",
      },
    }, { fallbackDays: [] });

    expect(staleModel.alert).toBeNull();
    expect(staleModel).not.toHaveProperty("alertStatus");
  });

  it("does not expose the availability notice after a confirmed regional no-alert state", () => {
    const model = buildBulletinViewModel({
      forecast: {},
      officialAlerts: {
        active: false,
        alerts: [{ id: "green", level: "verde", title: "Nessuna allerta" }],
        source_mode: "official_widget",
      },
    }, { fallbackDays: [] });

    expect(model.alert).toBeNull();
    expect(model).not.toHaveProperty("alertStatus");
  });

  it("does not prompt a manual alert check in Furlan", () => {
    const model = buildBulletinViewModel({
      forecast: {},
      officialAlerts: {
        active: false,
        alerts: [],
        error: "official_alerts_unavailable",
      },
    }, { fallbackDays: [], language: "fur" });

    expect(model.alert).toBeNull();
    expect(model).not.toHaveProperty("alertStatus");
  });

  it("does not use fixture forecasts when official text and structured data are unavailable", () => {
    const model = buildBulletinViewModel({});

    expect(model).not.toHaveProperty("alertStatus");
    expect(model.status).toBe("unavailable");
    expect(model.hasOfficialText).toBe(false);
    expect(model.hasStructuredMap).toBe(false);
    expect(model.days[0]).toMatchObject({
      focus: [],
      hasOfficialText: false,
      hasStructuredMap: false,
      source: "unavailable",
      summary: "Dati OSMER non disponibili",
      text: "Il bollettino non e' disponibile in questo momento. Consulta la fonte ARPA FVG - OSMER dal link sotto.",
    });
    expect(model.days[0].mapPoints).toEqual([]);
  });

  it("keeps recently cached official bulletin visible after refresh failure", () => {
    const model = buildBulletinViewModel({
      error: "Risposta bollettino non valida",
      isStale: true,
      forecast: {
        official: {
          it: {
            forecasts: [
              {
                date: "2026-06-17",
                text: "Vecchio bollettino da non mostrare.",
                title: "Vecchio titolo",
              },
            ],
          },
        },
        osmer_structured: osmerFixture,
      },
    }, { fallbackDays: [] });

    expect(model.status).toBe("stale_visible");
    expect(model.hasOfficialText).toBe(true);
    expect(model.hasStructuredMap).toBe(true);
    expect(model.days[0]).toMatchObject({
      hasOfficialText: true,
      hasStructuredMap: false,
      source: "official_text",
      summary: expect.any(String),
      text: "Vecchio bollettino da non mostrare.",
    });
    expect(model.days[0].mapPoints).toEqual([]);
  });

  it("shows source unreachable only when no usable bulletin cache remains", () => {
    const model = buildBulletinViewModel({
      error: "Risposta bollettino non valida",
      isStale: true,
      forecast: null,
    }, { fallbackDays: [] });

    expect(model.status).toBe("source_unreachable");
    expect(model.hasOfficialText).toBe(false);
    expect(model.hasStructuredMap).toBe(false);
    expect(model.days[0]).toMatchObject({
      source: "source_unreachable",
      summary: "Dati non raggiungibili",
      text: "Non riusciamo a raggiungere la fonte ARPA FVG - OSMER. Riprova piu tardi.",
    });
  });

  it("can still enable fixture forecasts explicitly for lab previews", () => {
    const model = buildBulletinViewModel({}, { allowFixtureFallback: true });

    expect(model.status).toBe("fixture_fallback");
    expect(model.days[0].text).toContain("Giornata calda");
    expect(model.days[0].mapPoints).toHaveLength(9);
  });
});


it("localizes an unreachable bulletin source in Friulian without using fixture weather", () => {
  const model = buildBulletinViewModel({ error: "offline", forecast: null }, { language: "fur", fallbackDays: [] });
  expect(model.days[0]).toMatchObject({
    summary: "Dâts no acessibii",
    text: "No rivin a contatâ la font ARPA FVG - OSMER. Torne a provâ plui tart.",
    hasStructuredMap: false,
    source: "source_unreachable",
  });
});
