import { describe, expect, it } from "vitest";

import { normalizeWeatherData } from "../../domain/weather/normalizedWeather";
import { getLocalMemoryForDate } from "../../domain/discover/localMemory";

import {
  buildHomeAlmanacStateFromModel,
  buildHomeAlmanacViewModel,
  buildHomeBulletinViewModel,
  buildHomeEventsViewModel,
  buildHomeViewModel,
  buildHomeWeatherViewModel,
} from "./homeViewModel";

describe("home view model", () => {
  it("carries ICON source dates and localized semantic condition without touching official alerts", () => {
    const officialAlerts = { active: false, alerts: [] };
    const current = normalizeWeatherData({
      primary_source: "icon2i_local_pilot", temperature: 24, feels_like: 23,
      weathercode: null, condition: "Temporale", precipitation: null,
      data_quality: { run_utc: "2026-09-03T00:00:00Z", native_condition_status: "valid", native_condition_label: "Temporale debole o moderato" },
    });
    const weather = buildHomeWeatherViewModel({ current, officialAlerts });
    expect(weather.conditionLabel).toBe("Temporale");
    expect(buildHomeWeatherViewModel({ current }, { language: "fur" }).conditionLabel).toBe("Temporâl");
    expect(weather.icon.type).toBe("Storm");
    expect(weather.localPilot.run_utc).toBe("2026-09-03T00:00:00Z");
    expect(weather.details.some((detail) => detail.id === "precipitation")).toBe(false);
    expect(weather.officialAlerts).toBe(officialAlerts);
    expect(buildHomeWeatherViewModel({ current: normalizeWeatherData({ primary_source: "open_meteo" }) }).localPilot).toBeNull();
  });

  it.each(["it", "fur"])("keeps Open-Meteo hero values separate from OSMER and alerts in %s", (language) => {
    const official = { it: { forecasts: [{ text: "Temporali forti secondo OSMER." }] } };
    const officialAlerts = { active: true, alerts: [{ id: "official-yellow", level: "gialla" }] };
    const current = normalizeWeatherData({
      temperature: 24,
      feels_like: 25,
      weathercode: 0,
      condition: "Soleggiato",
      is_day: 1,
      primary_source: "open_meteo",
      source: { active: "open_meteo" },
      station: { temperature: 30, condition: "temporale" },
      official,
    });
    const weather = buildHomeWeatherViewModel({ current, officialAlerts }, { language });

    expect(weather.temperature.value).toBe("24");
    expect(weather.feelsLike.value).toBe("25°C");
    expect(weather.icon).toMatchObject({ type: "Sun", code: 0, semanticKey: "clear" });
    expect(weather.conditionLabel).toBeTruthy();
    expect(weather.conditionLabel).not.toMatch(/temporal|OSMER/iu);
    expect(weather.officialAlerts).toBe(officialAlerts);
    expect(weather.alertCount).toBe(1);
    expect(current.official).toBe(official);
    expect(current.station.temperature).toBe(30);
  });

  it("omits the perceived-temperature detail when the model does not provide it", () => {
    const current = normalizeWeatherData({ temperature: 24, feels_like: null });
    const weather = buildHomeWeatherViewModel({ current });

    expect(weather.temperature.value).toBe("24");
    expect(weather.feelsLike).toBeNull();
  });

  it("does not turn a missing model temperature into zero degrees", () => {
    const weather = buildHomeWeatherViewModel({ current: normalizeWeatherData({ temperature: null }) });

    expect(weather.temperature.value).toBeNull();
    expect(weather.temperature.label).toBe("Dato non disponibile");
  });

  it("labels the backend model-cache fallback as not updated", () => {
    const current = normalizeWeatherData({ temperature: 24, data_quality: { status: "stale" } });
    const weather = buildHomeWeatherViewModel({ current, updatedAt: new Date().toISOString() });

    expect(weather.showStatus).toBe(true);
    expect(weather.updatedLabel).toBe("Dati non aggiornati");
  });

  it("adapts the shared local model without adding metrics to the main weather scene", () => {
    const model = buildHomeViewModel({
      localWeather: {
        metrics: [{ id: "wind", label: "Vento", value: "3 km/h" }],
        pollen: { available: true, tone: "medium", level: "Livello medio" },
      },
    }, { language: "it" });

    expect(model.localMetrics.items.map((item) => item.id)).toEqual([
      "wind", "humidity", "pressure", "precipitation", "pollen",
    ]);
    expect(model.localMetrics.items[0]).toMatchObject({ value: "3", unit: "km/h" });
    expect(model.localMetrics.items[4].value).toBe("Medio");
    expect(model.weather.details).toEqual([]);
    expect(buildHomeViewModel({}).localMetrics).toBeNull();
  });

  it("adapts the current Almanac model for the Home teaser in IT and FUR", () => {
    const almanacModel = {
      dayLabel: "Venerdi 17 luglio",
      moon: { cycleProgress: 31, phase: "Luna crescente" },
      proverb: { body: "Un proverbio completo resta nell'Almanacco." },
      saint: { label: "Sant'Alessio" },
      tradition: { label: "Tradizione del giorno" },
    };

    expect(buildHomeAlmanacStateFromModel(almanacModel, { language: "it" })).toEqual({
      dateLabel: "Venerdi 17 luglio",
      saintLabel: "Sant'Alessio",
      body: "Sant'Alessio",
      moonLabel: "Luna",
      moon: { cycleProgress: 31, phase: "Luna crescente" },
    });
    expect(buildHomeAlmanacStateFromModel(almanacModel, { language: "fur" })).toEqual({
      dateLabel: "Venerdi 17 luglio",
      saintLabel: "Sant'Alessio",
      body: "Sant'Alessio",
      moonLabel: "Lune",
      moon: { cycleProgress: 31, phase: "Luna crescente" },
    });
  });

  it("formats weather into presentation-ready values without secondary hero metrics", () => {
    const weather = buildHomeWeatherViewModel(
      {
        status: "fresh",
        city: "Udine",
        current: {
          condition: "Sereno",
          weathercode: 0,
          isDay: true,
          temperature: 23.4,
          feelsLike: 24.1,
          windSpeed: 74,
          windDirection: "NE",
          humidity: 68,
          precipitationAmount: 0,
          visibilityKm: 18,
          pressure: 1012,
          cloudCover: 12,
          semantic: {
            key: "clear",
            family: "clear",
            labelKey: "conditionSun",
            overlays: {
              wind: { key: "wind_overlay", intensity: "strong" },
            },
          },
          type: "Wind",
          code: 0,
        },
        updatedAt: "2026-06-21T10:00:00.000Z",
      },
      { language: "it", now: "2026-06-21T10:05:00.000Z" },
    );

    expect(weather.conditionLabel).toBe("Soleggiato");
    expect(weather.temperature.value).toBe("23");
    expect(weather.temperature.unit).toMatch(/C$/);
    expect(weather.icon).toMatchObject({
      type: "Sun",
      semanticKey: "clear",
      overlays: {
        wind: { key: "wind_overlay" },
      },
    });
    expect(weather.details.map((detail) => detail.id)).toEqual([
      "feels-like",
      "wind",
      "humidity",
      "precipitation",
      "visibility",
      "pressure",
      "cloud-cover",
    ]);
    expect(weather).not.toHaveProperty("heroMetrics");
    expect(weather).not.toHaveProperty("heroMetricsLabel");
    expect(weather.updatedLabel).toBe("Aggiornato 5 minuti fa");
  });

  it("marks stale weather without dropping the displayable data", () => {
    const weather = buildHomeWeatherViewModel({
      status: "stale",
      city: "Pordenone",
      current: { condition: "Pioggia debole", weathercode: 61, temperature: 11, type: "LightRain" },
      forecast: { daily: [] },
      fromCache: true,
      isStale: true,
      error: "Risposta meteo non valida",
    });

    expect(weather.statusLabel).toBe("Dati non aggiornati");
    expect(weather.showStatus).toBe(false);
    expect(weather.statusTone).toBe("fresh");
    expect(weather.error).toBe("Risposta meteo non valida");
    expect(weather.conditionLabel).toBe("Pioggia debole");
    expect(weather.temperature.label).toMatch(/^11/);
  });

  it("keeps fresh cached weather ready without showing the saved-data pill", () => {
    const weather = buildHomeWeatherViewModel(
      {
        status: "cache",
        city: "Pordenone",
        current: {
          condition: "Prevalentemente soleggiato",
          weathercode: 1,
          isDay: true,
          temperature: 34,
          type: "MostlySunny",
        },
        updatedAt: "2026-06-28T18:00:00.000Z",
        fromCache: true,
      },
      { language: "it", now: "2026-06-28T20:00:00.000Z" },
    );

    expect(weather.fromCache).toBe(true);
    expect(weather.showStatus).toBe(false);
    expect(weather.statusLabel).toBe("Meteo aggiornato");
    expect(weather.temperature.label).toMatch(/^34/);
    expect(weather.updatedLabel).toBe("Aggiornato 2 ore fa");
  });

  it("builds an empty weather model for missing data", () => {
    const weather = buildHomeWeatherViewModel({ status: "empty", error: "Dati meteo mancanti" });

    expect(weather.conditionLabel).toBe("Meteo non disponibile");
    expect(weather.temperature.label).toBe("Dato non disponibile");
    expect(weather.details).toEqual([]);
    expect(weather.error).toBe("Dati meteo mancanti");
  });

  it("distinguishes planned national ICON-2I coverage from an unsupported territory", () => {
    expect(buildHomeWeatherViewModel({
      status: "planned",
      unavailableReason: "national_icon2i_planned",
    }).conditionLabel).toBe("Previsioni nazionali in preparazione");

    expect(buildHomeWeatherViewModel({
      status: "unsupported",
      unavailableReason: "weather_territory_unsupported",
    }).conditionLabel).toBe("Località fuori copertura");
  });

  it("formats official alert labels for the compact Home hero", () => {
    const singleAlertWeather = buildHomeWeatherViewModel({
      officialAlerts: [{ id: "alert-1" }],
    });

    expect(singleAlertWeather.alertsLabel).toBe("Allerta ufficiale");
    expect(singleAlertWeather.alertSummary).toMatchObject({
      action: {
        anchor: "official-alerts",
        tab: "bulletin",
        type: "tab-anchor",
      },
      isOfficial: true,
      label: "Allerta ufficiale",
      level: null,
      tone: "neutral",
    });

    expect(
      buildHomeWeatherViewModel({
      officialAlerts: [{ id: "alert-1" }, { id: "alert-2" }],
      }).alertsLabel,
    ).toBe("2 allerte ufficiali");
  });

  it("accepts the backend official_alerts object shape", () => {
    const weather = buildHomeWeatherViewModel({
      officialAlerts: {
        active: true,
        alerts: [{ id: "backend-yellow", level: "gialla" }],
        count: 1,
      },
    });

    expect(weather.alertCount).toBe(1);
    expect(weather.alertsLabel).toBe("Allerta gialla in FVG");
    expect(weather.alertSummary).toMatchObject({ level: "yellow", tone: "yellow" });
  });

  it("does not show green official alert states as active Home alerts", () => {
    const weather = buildHomeWeatherViewModel({
      officialAlerts: {
        active: false,
        alerts: [{ id: "green", level: "verde", title: "Nessuna allerta" }],
        count: 0,
      },
    });

    expect(weather.alertCount).toBe(0);
    expect(weather.alertsLabel).toBe("");
    expect(weather.alertSummary).toBeNull();
  });

  it("does not show unavailable or stale official alert states in the Home hero", () => {
    const unavailableWeather = buildHomeWeatherViewModel({
      officialAlerts: {
        active: false,
        alerts: [],
        cache: { status: "unavailable" },
        error: "official_alerts_unavailable",
        source_mode: "official_alerts_unavailable_fast_fallback",
      },
    });

    expect(unavailableWeather.alertCount).toBe(0);
    expect(unavailableWeather.alertsLabel).toBe("");
    expect(unavailableWeather.alertSummary).toBeNull();

    const staleWeather = buildHomeWeatherViewModel({
      officialAlerts: {
        active: true,
        alerts: [{ id: "old-yellow", level: "gialla" }],
        cache: { status: "stale" },
        source_mode: "github_actions_official_page",
      },
    });

    expect(staleWeather.alertCount).toBe(0);
    expect(staleWeather.alertsLabel).toBe("");
    expect(staleWeather.alertSummary).toBeNull();
  });

  it.each([
    ["it", "Allerta gialla in FVG", "Allerta arancione in FVG", "Allerta rossa in FVG"],
    ["fur", "Alerte zale in FVG", "Alerte narançon in FVG", "Alerte rosse in FVG"],
  ])("uses the regional color label in %s", (language, yellowLabel, orangeLabel, redLabel) => {
    const yellowWeather = buildHomeWeatherViewModel({
      officialAlerts: [{ id: "yellow-alert", level: "yellow" }],
    }, { language });

    expect(yellowWeather.alertsLabel).toBe(yellowLabel);
    expect(yellowWeather.alertSummary).toMatchObject({ level: "yellow", tone: "yellow" });

    const orangeWeather = buildHomeWeatherViewModel({
      officialAlerts: [{ id: "orange-alert", level: "arancione" }],
    }, { language });

    expect(orangeWeather.alertsLabel).toBe(orangeLabel);
    expect(orangeWeather.alertSummary).toMatchObject({ level: "orange", tone: "orange" });

    const redWeather = buildHomeWeatherViewModel({
      officialAlerts: [{ id: "red-alert", severity: "rossa" }],
    }, { language });

    expect(redWeather.alertsLabel).toBe(redLabel);
    expect(redWeather.alertSummary).toMatchObject({ level: "red", tone: "red" });
  });

  it.each([
    ["it", "Allerta arancione in FVG"],
    ["fur", "Alerte narançon in FVG"],
  ])("keeps the highest regional level and bulletin action in %s", (language, label) => {
    const weather = buildHomeWeatherViewModel({
      officialAlerts: [
        { id: "yellow-alert", level: "yellow" },
        { id: "orange-alert", level: "orange" },
      ],
    }, { language });

    expect(weather.alertsLabel).toBe(label);
    expect(weather.alertSummary).toMatchObject({
      action: { anchor: "official-alerts", tab: "bulletin", type: "tab-anchor" },
      level: "orange",
      tone: "orange",
    });
  });

  it("uses a short phenomenon label instead of verbose official alert text", () => {
    const weather = buildHomeWeatherViewModel({
      officialAlerts: [
        {
          id: "storm",
          headline: "Allerta ufficiale: temporali forti sulla pianura e sulla costa",
        },
      ],
    });

    expect(weather.alertsLabel).toBe("Allerta temporali");
    expect(weather.alertSummary).toMatchObject({ level: null, tone: "neutral" });
  });

  it("keeps concise fallback labels only when no color or known phenomenon is present", () => {
    const weather = buildHomeWeatherViewModel({
      officialAlerts: [{ id: "custom", shortLabel: "Avviso locale" }],
    });

    expect(weather.alertsLabel).toBe("Avviso locale");
  });

  it("maps weather semantics into compact Home hero variants", () => {
    expect(
      buildHomeWeatherViewModel({
        current: { condition: "Sereno", semantic: { sceneVariant: "clear" }, temperature: 22, type: "Sun" },
      }).weatherVariant,
    ).toBe("clear");

    expect(
      buildHomeWeatherViewModel({
        current: { condition: "Variabile", semantic: { sceneVariant: "partly" }, temperature: 18, type: "PartlyCloudy" },
      }).weatherVariant,
    ).toBe("partly");

    expect(
      buildHomeWeatherViewModel({
        current: { condition: "Coperto", semantic: { sceneVariant: "cloud" }, temperature: 14, type: "Overcast" },
      }).weatherVariant,
    ).toBe("cloud");

    expect(
      buildHomeWeatherViewModel({
        current: { condition: "Pioggia", semantic: { sceneVariant: "rain" }, temperature: 11, type: "Rain" },
      }).weatherVariant,
    ).toBe("rain");

    expect(
      buildHomeWeatherViewModel({
        current: { condition: "Temporale", semantic: { sceneVariant: "storm" }, temperature: 16, type: "Storm" },
      }).weatherVariant,
    ).toBe("storm");

    expect(
      buildHomeWeatherViewModel({
        current: { condition: "Neve", semantic: { sceneVariant: "snow" }, temperature: -1, type: "Snow" },
      }).weatherVariant,
    ).toBe("snow");

    expect(
      buildHomeWeatherViewModel({
        current: { condition: "Nebbia", semantic: { sceneVariant: "fog" }, temperature: 7, type: "Fog" },
      }).weatherVariant,
    ).toBe("fog");
  });

  it("uses the night Home hero variant as a transversal weather state", () => {
    const weather = buildHomeWeatherViewModel({
      current: { condition: "Sereno", isNight: true, temperature: 10, type: "ClearNight" },
    });

    expect(weather.weatherVariant).toBe("night");
  });

  it("keeps meteo-specific Home hero variants for night rain, storm and snow", () => {
    expect(
      buildHomeWeatherViewModel({
        current: {
          condition: "Pioggia",
          isNight: true,
          semantic: { sceneVariant: "rain" },
          temperature: 9,
          type: "Rain",
        },
      }).weatherVariant,
    ).toBe("rain-night");

    expect(
      buildHomeWeatherViewModel({
        current: {
          condition: "Temporale",
          isNight: true,
          semantic: { sceneVariant: "storm" },
          temperature: 12,
          type: "Storm",
        },
      }).weatherVariant,
    ).toBe("storm-night");

    expect(
      buildHomeWeatherViewModel({
        current: {
          condition: "Neve",
          isNight: true,
          semantic: { sceneVariant: "snow" },
          temperature: -2,
          type: "Snow",
        },
      }).weatherVariant,
    ).toBe("snow-night");
  });

  it("uses explicit update age when present for static previews", () => {
    const weather = buildHomeWeatherViewModel({
      updatedAgoMinutes: 5,
      updatedAt: "2026-06-21T10:00:00.000Z",
    });

    expect(weather.updatedLabel).toBe("Aggiornato 5 minuti fa");
  });

  it("prepares event teaser items and refresh state for the Home", () => {
    const events = buildHomeEventsViewModel({
      status: "fresh",
      items: [
        { id: "1", title: "Festa in piazza", city: "Udine", date_label: "Oggi" },
        { id: "2", title: "Mercato", city: "Pordenone", date_label: "Domani" },
        { id: "3", title: "Concerto", city: "Gorizia", date_label: "Sabato" },
        { id: "4", title: "Mostra", city: "Trieste", date_label: "Domenica" },
      ],
      total: 4,
      loadedLimit: 100,
      isPartial: true,
      shouldRetry: true,
    });

    expect(events.items).toHaveLength(3);
    expect(events.items[0]).toMatchObject({
      id: "1",
      title: "Festa in piazza",
      location: "Udine",
      dateLabel: "Oggi",
    });
    expect(events.countValue).toBe("1");
    expect(events.countCaption).toBe("evento oggi");
    expect(events.countLabel).toBe("1 evento oggi");
    expect(events.metaLabel).toBe("1 evento oggi vicino a te");
    expect(events.actionLabel).toBe("Eventi");
    expect(events.tagsLabel).toBe("Dettagli evento");
    expect(events.message).toBe("Eventi in aggiornamento");
    expect(events.shouldRetry).toBe(true);
  });

  it.each([
    ["it", "Eventi vicino a te", "evento oggi"],
    ["fur", "Evenis dongje di te", "eveniment vuê"],
  ])("exposes the contextual today count while retaining the raw catalog total in %s", (language, title, countLabel) => {
    const events = buildHomeEventsViewModel({
      status: "fresh",
      items: [{ id: "one", title: "Sagra", city: "Codroipo", date_label: "Oggi" }],
      total: 100,
      loadedLimit: 200,
    }, { language });

    expect(events.title).toBe(title);
    expect(events.items).toHaveLength(1);
    expect(events.countValue).toBe("1");
    expect(events.countLabel).toBe(`1 ${countLabel}`);
    expect(events.total).toBe(100);
  });

  it("replaces the editorial event catalogue with the FVG boundary outside the region", () => {
    const model = buildHomeViewModel({
      location: { city: "Roma", region: "Lazio", countryCode: "IT" },
      editorialLocation: { city: "Pordenone", region: "Friuli Venezia Giulia" },
      events: { status: "fresh", items: [], total: 0 },
      sourceAvailability: {
        events: { status: "unsupported" },
        osmer: { status: "unsupported" },
      },
    }, { language: "it" });

    expect(model.locationTitle).toBe("Roma");
    expect(model.events.available).toBe(false);
    expect(model.events.title).toBe("Eventi disponibili solo in FVG");
    expect(model.events.message).toContain("La località attiva è Roma");
    expect(model.events.items).toEqual([]);
    expect(model.events.metaLabel).toBe("");
    expect(model.bulletin).toBeNull();
  });

  it("does not surface cached FVG editorial events under a national location", () => {
    const model = buildHomeViewModel({
      location: { city: "Roma", region: "Lazio", countryCode: "IT" },
      editorialLocation: { city: "Pordenone", region: "Friuli Venezia Giulia" },
      sourceAvailability: { events: { status: "unsupported" } },
      weather: {
        current: { condition: "Temporale", weathercode: 95, temperature: 20 },
      },
      events: {
        status: "fresh",
        items: [
          {
            category: "sagra",
            date: "domenica 28 giugno 2026",
            id: "outdoor-sagra",
            place: "Pordenone",
            title: "Sagra in piazza",
          },
          {
            category: "cultura",
            date: "domenica 28 giugno 2026",
            id: "indoor-museum",
            place: "Pordenone",
            title: "Mostra al museo",
          },
        ],
        total: 2,
      },
    }, {
      language: "it",
      now: new Date(2026, 5, 28),
    });

    expect(model.events.available).toBe(false);
    expect(model.events.items).toEqual([]);
  });

  it.each([
    ["it", "eventi nei prossimi 15 giorni"],
    ["fur", "evenis tai prossims 15 dîs"],
  ])("counts all loaded upcoming cards before limiting teasers in %s", (language, countLabel) => {
    const events = buildHomeEventsViewModel({
      status: "fresh",
      items: Array.from({ length: 4 }, (_, index) => ({
        date_label: "Domani",
        id: String(index),
        title: `Sagra ${index}`,
      })),
      loadedLimit: 100,
    }, { language, maxItems: 1 });

    expect(events.items).toHaveLength(1);
    expect(events.countValue).toBe("4");
    expect(events.countLabel).toBe(`4 ${countLabel}`);
    expect(events.total).toBe(4);
  });

  it.each([
    ["it", "eventi nei prossimi 15 giorni"],
    ["fur", "evenis tai prossims 15 dîs"],
  ])("keeps a successful empty event count as zero in %s", (language, countLabel) => {
    const events = buildHomeEventsViewModel({ status: "fresh", items: [], total: 0 }, { language });

    expect(events.countValue).toBe("0");
    expect(events.countLabel).toBe(`0 ${countLabel}`);
    expect(events.total).toBe(0);
    expect(events.items).toEqual([]);
    expect(events.message).toBe(events.emptyBody);
  });

  it.each([
    ["it", "evento oggi", "Mostro gli eventi salvati"],
    ["fur", "eveniment vuê", "O mostri i evenis salvats"],
  ])("preserves a cached total through refresh errors in %s", (language, countLabel, message) => {
    const events = buildHomeEventsViewModel({
      status: "stale",
      items: [{ id: "cached", title: "Sagra", city: "Codroipo", date_label: "Oggi" }],
      total: 42,
      fromCache: true,
      isRefreshing: true,
      error: "Risposta eventi non valida",
    }, { language });

    expect(events.countValue).toBe("1");
    expect(events.countLabel).toBe(`1 ${countLabel}`);
    expect(events.total).toBe(42);
    expect(events.message).toBe(message);
  });

  it("uses the Events normalization for Home teaser place and compact dates", () => {
    const events = buildHomeEventsViewModel({
      status: "fresh",
      items: [{
        id: "gorizia-1",
        title: "Mostra “Italico Brass. Paesaggi isontini”",
        place: "Gorizia",
        date: "martedì 28 aprile 2026 - sabato 4 luglio 2026",
      }],
      total: 1,
    });

    expect(events.items[0]).toMatchObject({
      dateLabel: "28 APR - 4 LUG",
      location: "Gorizia",
      title: "Mostra “Italico Brass. Paesaggi isontini”",
    });
  });

  it("prioritizes punctual Home events over long-running exhibitions", () => {
    const events = buildHomeEventsViewModel(
      {
        status: "fresh",
        items: [
          {
            id: "long-exhibition",
            title: "Mostra lunga",
            place: "Gorizia",
            date: "martedì 28 aprile 2026 - sabato 4 luglio 2026",
          },
          {
            id: "today-music",
            title: "Concerto di oggi",
            place: "Gorizia",
            date: "domenica 28 giugno 2026",
          },
          {
            id: "tomorrow-market",
            title: "Mercato di domani",
            place: "Cormons",
            date: "lunedì 29 giugno 2026",
          },
        ],
        total: 3,
      },
      { now: new Date(2026, 5, 28) },
    );

    expect(events.items.map((event) => event.id)).toEqual([
      "today-music",
      "tomorrow-market",
      "long-exhibition",
    ]);
  });

  it("automatically features an active local umbrella programme with a reliable source and poster", () => {
    const state = {
      status: "fresh",
      items: [
        {
          id: "local-programme",
          title: "Festival locale 2026",
          date: "venerdì 2 ottobre 2026 - domenica 11 ottobre 2026",
          place: "Pordenone",
          display_mode: "umbrella",
          programme_city: "Pordenone",
          programme_id: "festival-locale-2026",
          programme_start_date: "2026-10-02",
          programme_end_date: "2026-10-11",
          programme_url: "https://example.org/festival",
          source: "Organizzatore ufficiale",
          image: "https://example.org/poster.jpg",
          is_real: true,
          active_session_count: 21,
        },
        {
          id: "today-concert",
          title: "Concerto di oggi",
          date: "venerdì 9 ottobre 2026",
          place: "Pordenone",
        },
      ],
    };
    const options = { location: { city: "Pordenone" }, now: new Date(2026, 9, 9) };
    const home = buildHomeEventsViewModel(state, options);
    const elsewhere = buildHomeEventsViewModel(state, {
      ...options,
      location: { city: "Udine" },
    });
    const upcoming = buildHomeEventsViewModel(state, {
      ...options,
      now: new Date(2026, 9, 1),
    });
    const expired = buildHomeEventsViewModel(state, {
      ...options,
      now: new Date(2026, 9, 12),
    });

    expect(home.items[0]).toMatchObject({ id: "local-programme", featured: true });
    expect(home.items[1]).toMatchObject({ id: "today-concert", featured: false });
    expect(elsewhere.items.every((event) => !event.featured)).toBe(true);
    expect(upcoming.items.every((event) => !event.featured)).toBe(true);
    expect(expired.items.every((event) => !event.featured)).toBe(true);
  });

  it.each([
    ["no poster", { image: "" }],
    ["invalid poster URL", { image: "javascript:invalid" }],
    ["no source", { source: "" }],
    ["no source link", { programme_url: "" }],
    ["not real", { is_real: false }],
    ["invalid programme date", { programme_start_date: "2026-02-31" }],
    ["no active sessions", { active_session_count: 0 }],
  ])("does not feature a local programme with %s", (_reason, changes) => {
    const programme = {
      id: "local-programme",
      title: "Festival locale",
      date: "2-11 ottobre 2026",
      display_mode: "umbrella",
      programme_city: "Pordenone",
      programme_start_date: "2026-10-02",
      programme_end_date: "2026-10-11",
      programme_url: "https://example.org/festival",
      source: "Organizzatore ufficiale",
      image: "https://example.org/poster.jpg",
      active_session_count: 12,
      ...changes,
    };
    const home = buildHomeEventsViewModel(
      { status: "fresh", items: [programme] },
      { location: { city: "Pordenone" }, now: new Date(2026, 9, 9) },
    );

    expect(home.items).toHaveLength(1);
    expect(home.items[0].featured).toBe(false);
  });

  it("prioritizes exact-location Home events over nearby same-day events", () => {
    const events = buildHomeEventsViewModel(
      {
        status: "fresh",
        items: [
          {
            date: "mercoledÃ¬ 1 luglio 2026",
            distance_km: "4,4",
            event_city: "Palse",
            id: "nearby-sagra",
            place: "Palse di Porcia",
            title: "Luglio Palsese",
          },
          {
            date: "mercoledÃ¬ 1 luglio 2026",
            event_city: "Pordenone",
            id: "local-concert",
            place: "Pordenone",
            title: "New Etno Jazz",
          },
        ],
        total: 2,
      },
      {
        location: { city: "Pordenone" },
        now: new Date(2026, 6, 1),
      },
    );

    expect(events.items.map((event) => event.id)).toEqual(["local-concert", "nearby-sagra"]);
  });

  it("exposes the selected event image to the Home teaser", () => {
    const events = buildHomeEventsViewModel(
      {
        status: "fresh",
        items: [
          {
            category: "musica",
            date: "mercoledì 1 luglio 2026",
            event_city: "Pordenone",
            id: "local-event-with-image",
            image: "https://example.com/event-preview.jpg",
            place: "Pordenone",
            title: "Evento con anteprima",
          },
        ],
        total: 1,
      },
      {
        location: { city: "Pordenone" },
        now: new Date(2026, 6, 1),
      },
    );

    expect(events.items[0]).toMatchObject({
      category: "musica",
      id: "local-event-with-image",
      image: "https://example.com/event-preview.jpg",
    });
  });

  it("does not let a remote today event hide a local upcoming event in Home", () => {
    const events = buildHomeEventsViewModel(
      {
        status: "fresh",
        items: [
          {
            date: "mercoledÃ¬ 1 luglio 2026",
            distance_km: 64,
            event_city: "Udine",
            id: "remote-today",
            place: "Udine",
            title: "Evento lontano oggi",
          },
          {
            date: "giovedÃ¬ 2 luglio 2026",
            event_city: "Pordenone",
            id: "local-tomorrow",
            place: "Pordenone",
            title: "Evento locale domani",
          },
        ],
        total: 2,
      },
      {
        location: { city: "Pordenone" },
        now: new Date(2026, 6, 1),
      },
    );

    expect(events.items.map((event) => event.id)).toEqual(["local-tomorrow", "remote-today"]);
  });

  it("uses compact multi-location labels in the Home event teaser", () => {
    const events = buildHomeEventsViewModel(
      {
        status: "fresh",
        items: [
          {
            date: "venerdÃ¬ 3 luglio 2026",
            event_city: "Trieste, Capriva del Friuli, Cormons, Gorizia, Mossa",
            id: "multi-city",
            place: "Trieste, Capriva del Friuli, Cormons, Gorizia, Mossa",
            title: "Piccolo Opera Festival",
          },
        ],
        total: 1,
      },
      {
        location: { city: "Gorizia" },
        now: new Date(2026, 6, 1),
      },
    );

    expect(events.items[0]).toMatchObject({
      id: "multi-city",
      location: "Gorizia e altre localit\u00e0",
    });
  });

  it("uses weather fit only as hidden Home teaser ranking", () => {
    const events = buildHomeEventsViewModel(
      {
        status: "fresh",
        items: [
          {
            category: "sagra",
            date: "domenica 28 giugno 2026",
            id: "outdoor-sagra",
            place: "Gorizia",
            title: "Sagra in piazza",
          },
          {
            category: "cultura",
            date: "domenica 28 giugno 2026",
            id: "indoor-museum",
            place: "Gorizia",
            title: "Mostra al museo",
          },
        ],
        total: 2,
      },
      {
        now: new Date(2026, 5, 28),
        weather: { condition: "Temporale", weathercode: 95, temperature: 20 },
      },
    );

    expect(events.items.map((event) => event.id)).toEqual(["indoor-museum", "outdoor-sagra"]);
    expect(events.items[0]).not.toHaveProperty("weatherFit");
    expect(JSON.stringify(events.items)).not.toContain("protected_activity");
  });

  it("still shows a long-running event when it is the only Home candidate", () => {
    const events = buildHomeEventsViewModel(
      {
        status: "fresh",
        items: [{
          id: "only-exhibition",
          title: "Mostra visitabile",
          place: "Gorizia",
          date: "martedì 28 aprile 2026 - sabato 4 luglio 2026",
        }],
        total: 1,
      },
      { now: new Date(2026, 5, 28), maxItems: 1 },
    );

    expect(events.items[0]).toMatchObject({
      id: "only-exhibition",
      dateLabel: "28 APR - 4 LUG",
      location: "Gorizia",
    });
  });

  it("prepares bulletin and almanac sections from explicit Home data", () => {
    const bulletin = buildHomeBulletinViewModel({
      sourceLabel: "OSMER ARPA FVG",
      dateLabel: "domenica 28 giugno",
      headline: "Tempo stabile sulla pianura",
      body: "Cielo sereno o poco nuvoloso, con nubi alte sui monti.",
    });
    const almanac = buildHomeAlmanacViewModel({
      eyebrow: "Oggi in Friuli",
      dateLabel: "domenica 28 giugno",
      cardTitle: "L'almanacco del giorno",
      headline: "Luna e tradizione",
      body: "Santi, luna e proverbi della giornata.",
      moonLabel: "Luna",
      moon: { cycleProgress: 31, phase: "Luna crescente" },
    });

    expect(bulletin).toMatchObject({
      title: "Sintesi",
      sourceLabel: "OSMER ARPA FVG",
      dateLabel: "Domenica 28 giugno",
      headline: "Tempo stabile sulla pianura",
    });
    expect(almanac).toMatchObject({
      title: "Almanacco",
      eyebrow: "Oggi in Friuli",
      dateLabel: "Domenica 28 giugno",
      cardTitle: "L'almanacco del giorno",
      headline: "Luna e tradizione",
      moonLabel: "Luna",
      moon: { cycleProgress: 31, phase: "Luna crescente" },
    });
  });

  it("keeps the bulletin detail empty while local advice is pending", () => {
    const bulletin = buildHomeBulletinViewModel({
      advice: null,
      adviceStatus: "pending",
      body: "",
      headline: "Cielo variabile",
    });

    expect(bulletin).toMatchObject({
      advice: null,
      adviceStatus: "pending",
      body: "",
    });
  });

  it.each([
    ["it", "domenica 30 agosto", "Domenica 30 agosto"],
    ["fur", "domenie 30 Avost", "Domenie 30 Avost"],
    ["it", "  Lunedì 31 agosto  ", "Lunedì 31 agosto"],
    ["fur", "Lunis 31 Avost", "Lunis 31 Avost"],
    ["it", "", ""],
    ["fur", "   ", ""],
    ["it", null, ""],
    ["fur", undefined, ""],
  ])("aligns the first letter of Home card dates in %s (%s)", (language, dateLabel, expected) => {
    const source = { dateLabel };

    expect(buildHomeBulletinViewModel(source, { language }).dateLabel).toBe(expected);
    expect(buildHomeAlmanacViewModel(source, { language }).dateLabel).toBe(expected);
    expect(source.dateLabel).toBe(dateLabel);
  });

  it("keeps cached events visible when the event state carries an error", () => {
    const events = buildHomeEventsViewModel({
      status: "error",
      items: [{ id: "cached", title: "Sagra", city: "Codroipo" }],
      total: 1,
      fromCache: true,
      error: "Risposta eventi non valida",
    });

    expect(events.items).toEqual([
      expect.objectContaining({
        id: "cached",
        title: "Sagra",
      }),
    ]);
    expect(events.message).toBe("Mostro gli eventi salvati");
  });

  it("builds the full Home contract with localized shell text", () => {
    const model = buildHomeViewModel(
      {
        location: {
          city: "Pordenone",
          istatCode: "093033",
          lat: 45.9567,
          lon: 12.6605,
        },
        weather: {
          status: "fresh",
          city: "Pordenone",
          current: {
            condition: "Sereno",
            sunrise: "2026-08-12T06:02",
            sunset: "2026-08-12T20:21",
            temperature: 21,
            type: "Sun",
            weathercode: 0,
          },
          forecast: { daily: [] },
        },
        events: {
          status: "fresh",
          items: [],
          total: 0,
        },
        hourly: {
          title: "Prossimis 48 oris",
          items: Array.from({ length: 60 }, (_, index) => ({
            ariaLabel: `${index}:00`,
            precipitationProbability: index,
            temperature: `${20 + index}°`,
            time: `${index}:00`,
          })),
        },
      },
      { language: "fur" },
    );

    expect(model.locationTitle).toBe("Pordenon");
    expect(model.locationLabel).toBe("Localitât");
    expect(model.weather.conditionLabel).toBe("Soreli");
    expect(model.weather.solarContext).toEqual({
      sunrise: "2026-08-12T06:02",
      sunset: "2026-08-12T20:21",
      latitude: 45.9567,
      longitude: 12.6605,
      timeZone: "Europe/Rome",
    });
    expect(model.bulletin.title).toBe("Sintesi");
    expect(model.almanac.title).toBe("Almanac");
    expect(model.events.countValue).toBe("0");
    expect(model.events.countLabel).toBe("0 evenis tai prossims 15 dîs");
    expect(model.hourly.title).toBe("Prossimis 48 oris");
    expect(model.hourly.items).toHaveLength(48);
    expect(model.hourly.scrollLabel).toContain("Previsions orariis");
    expect(model.status).toBe("ready");
  });

  it.each([
    ["it", "Evoluzione oraria"],
    ["fur", "Evoluzion orarie"],
  ])("does not advertise 48 hours for a partial %s fixture", (language, title) => {
    const model = buildHomeViewModel({ hourly: { items: [{ time: "10:00", temperature: "20°" }] } }, { language });

    expect(model.hourly.title).toBe(title);
    expect(model.hourly.items).toHaveLength(1);
  });

  it("shows the verified locality before the municipality returned by weather", () => {
    const model = buildHomeViewModel({
      location: {
        city: "Fontanafredda",
        displayName: "Vigonovo",
        locality: { id: "irdat:vigonovo", name: "Vigonovo" },
        municipality: { istatCode: "093022", name: "Fontanafredda" },
        lat: 45.9892,
        lon: 12.5473,
      },
      weather: {
        status: "fresh",
        city: "Fontanafredda",
        current: { condition: "Sereno", temperature: 21, type: "Sun", weathercode: 0 },
        forecast: { daily: [] },
      },
      events: { status: "fresh", items: [], total: 0 },
    });

    expect(model.locationTitle).toBe("Vigonovo");
  });

  it("selects the neutral Home treatment for an automatically resolved external place", () => {
    const model = buildHomeViewModel({
      location: {
        city: "Bologna",
        displayName: "Bologna",
        region: "Emilia-Romagna",
        dataPoint: {
          lat: 44.4938203,
          lon: 11.3426327,
          source: "nominatim_place",
        },
      },
      weather: {
        status: "fresh",
        city: "Bologna",
        current: { condition: "Sereno", temperature: 29, type: "Sun", weathercode: 0 },
        forecast: { daily: [] },
      },
      events: { status: "fresh", items: [], total: 0 },
    });

    expect(model.locationTitle).toBe("Bologna");
    expect(model.sceneMode).toBe("neutral");
  });

  it("maps the daily Scopri memory to a stable Home target", () => {
    const model = buildHomeViewModel({
      territory: {
        heading: "Memoria del giorno",
        id: "memory-0906",
        seasonLabel: "6 settembre",
        text: "Una storia friulana legata alla data di oggi.",
        title: "Francesco Maria Franceschinis, matematica e insegnamento",
        typeLabel: "Scienza e territorio",
      },
    });

    expect(model.territory).toEqual({
      anchor: "discover-card-memory-0906",
      heading: "Memoria del giorno",
      id: "memory-0906",
      type: "",
      typeLabel: "Scienza e territorio",
      seasonLabel: "6 settembre",
      metaLabel: "Scienza e territorio · 6 settembre",
      text: "Una storia friulana legata alla data di oggi.",
      title: "Francesco Maria Franceschinis, matematica e insegnamento",
    });
  });

  it.each(["it", "fur"])("preserves the real Glauco memory metadata and legacy %s label", language => {
    const memory = getLocalMemoryForDate({ date: new Date("2026-09-08T12:00:00Z"), language });
    expect(memory.id).toBe("memory-it-ready-0908-glauco-venier-dal-friuli-al-jazz-internazionale");
    expect(memory.type).toBe("musica");
    const territory = Object.freeze({
      ...memory,
      heading: language === "fur" ? "Memorie dal dì" : "Memoria del giorno",
    });
    const model = buildHomeViewModel({ territory }, { language });

    expect(model.territory).toMatchObject({
      id: territory.id,
      anchor: `discover-card-${territory.id}`,
      heading: territory.heading,
      title: territory.title,
      text: territory.text,
      type: "musica",
      typeLabel: territory.typeLabel,
      seasonLabel: territory.seasonLabel,
      metaLabel: `${territory.typeLabel} · ${territory.seasonLabel}`,
    });
  });

  it("does not infer missing memory metadata from its title or text", () => {
    const model = buildHomeViewModel({ territory: {
      id: "music-without-metadata",
      title: "Glauco Venier e la musica",
      text: "Una memoria musicale dell'8 settembre.",
    } });

    expect(model.territory).toMatchObject({ type: "", typeLabel: "", seasonLabel: "", metaLabel: "" });
  });

  it("passes the detailed official-alert presentation through without mixing it into OSMER", () => {
    const officialAlert = {
      label: "Allerta arancione in FVG",
      meta: "Protezione Civile FVG",
      text: "Temporali forti sulla regione.",
      validityLabel: "Valida fino alle 18:00",
    };
    const model = buildHomeViewModel({
      bulletin: { headline: "Sintesi OSMER" },
      officialAlert,
    });

    expect(model.officialAlert).toBe(officialAlert);
    expect(model.bulletin.headline).toBe("Sintesi OSMER");
  });
});
