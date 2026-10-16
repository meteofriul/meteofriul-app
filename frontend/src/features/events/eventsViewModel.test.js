import { describe, expect, it } from "vitest";

import {
  buildEventRecord,
  buildEventsViewModel,
  classifyEventTime,
  formatEventDateChip,
  getEventFilterCategory,
  rankEventsForLocation,
  sortEventsForTimeTab,
} from "./eventsViewModel";

const now = new Date("2026-06-28T12:00:00");

describe("events view model", () => {
  it.each(["2026-03-29", "2026-10-25", "2026-12-31"])("preserves civil event dates across timezone and DST boundaries: %s", (iso) => {
    const date = new Date(`${iso}T12:00:00`);
    const label = new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "long", year: "numeric" }).format(date);
    const expectedSchedule = new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "short" }).format(date);
    for (const language of ["it", "fur"]) {
      const record = buildEventRecord({ title: "Calendario", date: label, occurrences: [iso] }, { language, now: date });
      expect(record.timeCategory).toBe("today");
      expect(record.dateChip.start.day).toBe(String(date.getDate()));
      expect(record.scheduleLabel).toBe(`${language === "fur" ? "Zornadis" : "Giornate"}: ${expectedSchedule}`);
      if (language === "it") expect(record.dateChip.accessibleLabel).toBe(label);
    }
  });

  it("uses explicit opening days instead of the encompassing period", () => {
    const event = { title: "Sant'Angelo", date: "4 settembre 2026 - 13 settembre 2026",
      occurrences: [4, 5, 6, 11, 12, 13].map(day => `2026-09-${String(day).padStart(2, "0")}`) };
    expect(buildEventRecord(event, { now: new Date("2026-09-07T12:00:00") }).timeCategory).toBe("weekend");
    expect(buildEventRecord(event, { now: new Date("2026-09-11T12:00:00") }).timeCategory).toBe("today");
    expect(buildEventRecord(event, { now: new Date("2026-09-14T12:00:00") }).timeCategory).toBe("outside");
    expect(buildEventRecord(event).scheduleLabel).toContain("11 set");
  });
  it("classifies events into today, weekend and next windows", () => {
    expect(classifyEventTime("Oggi", { now })).toBe("today");
    expect(classifyEventTime("4 luglio", { now })).toBe("weekend");
    expect(classifyEventTime("1 luglio", { now })).toBe("next");
    expect(classifyEventTime("12 luglio", { now })).toBe("next");
    expect(classifyEventTime("25 luglio", { now })).toBe("outside");
  });

  it("keeps an end-only exhibition as a deadline, without claiming an opening day", () => {
    const record = buildEventRecord({
      title: "Memorie riflesse", date_label: "Fino al 7 gennaio 2027",
      schedule_kind: "end_only", start_date: null, end_date: "2027-01-07",
    }, { now: new Date("2026-10-05T12:00:00") });
    expect(record.date).toBe("Fino al 7 gennaio 2027");
    expect(record.dateChip.accessibleLabel).toBe("Fino al 7 gennaio 2027");
    expect(record.dateChip.start).toBeUndefined();
    expect(record.timeCategory).toBe("next");
    expect(buildEventRecord(record.raw, {
      now: new Date("2027-01-08T12:00:00"),
    }).timeCategory).toBe("outside");
  });

  it("keeps a month-precision exhibition visible without claiming it opens today", () => {
    const source = {
      title: "Radici nella pietra", date: "maggio–dicembre 2026",
      schedule_kind: "month_range", start_date: "2026-05-01",
      end_date: "2026-12-31", sort_date: "2026-10-06",
    };
    const record = buildEventRecord(source, {
      now: new Date("2026-10-06T12:00:00"),
    });
    expect(record.dateChip.label).toBe("maggio–dicembre 2026");
    expect(record.dateChip.start).toBeUndefined();
    expect(record.timeCategory).toBe("next");
    expect(buildEventRecord(source, {
      now: new Date("2027-01-01T12:00:00"),
    }).timeCategory).toBe("outside");
  });

  it("normalizes event date chips from single dates and ranges", () => {
    expect(formatEventDateChip("28 giugno", "it", { now })).toMatchObject({
      isRange: false,
      start: { day: "28", month: "GIU" },
    });
    expect(formatEventDateChip("dal 28 giugno al 4 luglio", "it", { now })).toMatchObject({
      accessibleLabel: "dal 28 giugno al 4 luglio",
      isRange: true,
      end: { day: "4", month: "LUG" },
      start: { day: "28", month: "GIU" },
    });
    expect(formatEventDateChip("dal 17 dicembre 2025 al 31 dicembre 2026", "it", { now })).toMatchObject({
      accessibleLabel: "dal 17 dicembre 2025 al 31 dicembre 2026",
      isRange: true,
      end: { day: "31", month: "DIC" },
      start: { day: "17", month: "DIC" },
    });
  });

  it("keeps sagra review sources in the sagra category", () => {
    expect(getEventFilterCategory({ category: "food_wine", source: "Pro Loco FVG" })).toBe("sagra");
    expect(getEventFilterCategory({ category: "food_wine", source: "TurismoFVG" })).toBe("food_wine");
  });

  it("builds display records without exposing backend noise", () => {
    const record = buildEventRecord({
      category: "musica",
      date: "Oggi",
      distance_km: 4.2,
      event_city: "Udine",
      id: "event-1",
      image: "/api/events/image.jpg",
      source: "EventiFVG",
      title: "Notte di musica",
      url: "https://example.com",
    }, { language: "it", now });

    expect(record).toMatchObject({
      category: "musica",
      categoryLabel: "Musica",
      id: "event-1",
      image: "/api/events/image.jpg",
      location: "Udine · 4,2 km",
      source: "EventiFVG",
      timeCategory: "today",
      title: "Notte di musica",
    });
  });

  it.each([
    {
      expected: "Pordenone · 1,2 km",
      input: { distance_km: 1.2 },
      label: "formats an exact distance with the Italian decimal comma",
    },
    {
      expected: "Pordenone · ~1,2 km",
      input: { distance_is_approximate: true, distance_km: 1.2 },
      label: "marks an approximate distance explicitly",
    },
    {
      expected: "Pordenone · 800 m",
      input: { distance_is_approximate: false, distance_km: 0.8 },
      label: "uses rounded metres below one kilometre",
    },
    {
      expected: "Pordenone · ~800 m",
      input: { distance_is_approximate: true, distance_km: 0.8 },
      label: "marks approximate distances expressed in metres",
    },
    {
      expected: "Pordenone",
      input: {},
      label: "keeps only the municipality when distance is missing",
    },
    {
      expected: "Pordenone",
      input: { distance_km: "not-a-distance" },
      label: "keeps only the municipality when distance is invalid",
    },
    {
      expected: "Pordenone",
      input: { distance_km: 0 },
      label: "keeps only the municipality for a zero distance",
    },
    {
      expected: "Pordenone",
      input: { distance_km: -1.2 },
      label: "keeps only the municipality for a negative distance",
    },
    {
      expected: "Pordenone · 1 km",
      input: { distance_km: 0.95 },
      label: "avoids displaying one thousand metres at the unit boundary",
    },
    {
      expected: "Pordenone · <100 m",
      input: { distance_km: 0.04 },
      label: "avoids claiming zero kilometres for a short positive distance",
    },
  ])("$label", ({ expected, input }) => {
    const record = buildEventRecord({
      category: "cultura",
      date: "Oggi",
      event_city: "Pordenone",
      id: "event-distance",
      title: "Evento con distanza",
      ...input,
    }, { language: "it", now });

    expect(record.location).toBe(expected);
  });

  it("uses the editorial territory label for an umbrella programme", () => {
    const record = buildEventRecord({
      date: "dal 16 settembre 2026 al 20 settembre 2026",
      display_mode: "umbrella",
      event_city: "Pordenone",
      location_label: "Pordenone e territorio · Più sedi",
      nearest_session_distance_km: 0.8,
      title: "Pordenonelegge 2026",
    }, { language: "it", now: new Date("2026-09-17T12:00:00") });

    expect(record.location).toBe("Pordenone e territorio · Più sedi");
    expect(record.timeCategory).toBe("today");
  });

  it("keeps a guarded future record visible only in the local preview", () => {
    const record = buildEventRecord({
      category: "food_wine",
      date: "5 settembre 2026",
      event_city: "Codroipo",
      preview_outside_window: true,
      source: "Villa Manin",
      title: "Cena in bianco",
    }, { language: "it", now });

    expect(record.timeCategory).toBe("next");
    expect(record.date).toBe("5 settembre 2026");
  });

  it("removes dangling trailing quotes from event titles", () => {
    const record = buildEventRecord({
      category: "musica",
      date: "3 luglio 2026",
      event_city: "Gorizia",
      id: "seghizzi",
      source: "TurismoFVG",
      title: "23\u00b0 Concorso vocale di musica da camera per voce e pianoforte Seghizzi\"",
    }, { language: "it", now });

    expect(record.title).toBe("23\u00b0 Concorso vocale di musica da camera per voce e pianoforte Seghizzi");
  });

  it("keeps balanced quotes inside event titles", () => {
    const record = buildEventRecord({
      category: "convegni",
      date: "1 luglio 2026",
      event_city: "Trieste",
      id: "iris-viola",
      source: "TurismoFVG",
      title: "Presentazione del libro \"Mi chiamo Iris Viola\"",
    }, { language: "it", now });

    expect(record.title).toBe("Presentazione del libro \"Mi chiamo Iris Viola\"");
  });

  it("compresses multi-location labels when they include the active city", () => {
    const record = buildEventRecord({
      category: "musica",
      date: "3 luglio 2026",
      event_city: "Trieste, Capriva del Friuli, Cormons, Gorizia, Mossa",
      id: "multi-city",
      source: "TurismoFVG",
      title: "Piccolo Opera Festival",
    }, {
      language: "it",
      location: { city: "Gorizia" },
      now,
    });

    expect(record.location).toBe("Gorizia e altre localit\u00e0");
  });

  it("keeps the original multi-location label when the active city is not listed", () => {
    const record = buildEventRecord({
      category: "musica",
      date: "3 luglio 2026",
      event_city: "Trieste, Capriva del Friuli, Cormons",
      id: "multi-city-away",
      source: "TurismoFVG",
      title: "Piccolo Opera Festival",
    }, {
      language: "it",
      location: { city: "Gorizia" },
      now,
    });

    expect(record.location).toBe("Trieste, Capriva del Friuli, Cormons");
  });

  it("builds the page model with copy, tabs and status", () => {
    const model = buildEventsViewModel({
      isPartial: true,
      items: [{ id: "e1", title: "Evento", date: "1 luglio", category: "cultura" }],
      shouldRetry: true,
      total: 12,
    }, {
      language: "it",
      location: { city: "Pordenone" },
      now,
    });

    expect(model.countLabel).toBe("12 eventi");
    expect(model.locationLabel).toBe("Pordenone");
    expect(model.message).toBe("Resto in attesa delle fonti verificate.");
    expect(model.tabs.map((tab) => tab.id)).toEqual(["today", "weekend", "next"]);
    expect(model.items[0]).toMatchObject({
      category: "cultura",
      timeCategory: "next",
    });
  });

  it("uses the approved FUR name for the active municipality", () => {
    const model = buildEventsViewModel({ items: [], total: 0 }, {
      language: "fur",
      location: { city: "Pordenone", istatCode: "093033" },
      now,
    });

    expect(model.locationLabel).toBe("Pordenon");
  });

  it("uses approved FUR municipality names inside event cards", () => {
    const record = buildEventRecord({
      category: "cultura",
      date: "Oggi",
      distance_km: 2.5,
      event_city: "Udine",
      id: "event-udin",
      title: "Event culturâl",
    }, {
      language: "fur",
      location: { city: "Udine", istatCode: "030129" },
      now,
    });

    expect(record.location).toBe("Udin · 2,5 km");
  });

  it("ranks punctual local events before long ongoing exhibitions", () => {
    const records = [
      buildEventRecord({
        category: "cultura",
        date: "dal 28 aprile al 4 luglio",
        event_city: "Pordenone",
        id: "long-exhibition",
        image: "exhibition.jpg",
        source: "TurismoFVG",
        title: "Mostra lunga",
      }, { language: "it", location: { city: "Pordenone" }, now }),
      buildEventRecord({
        category: "musica",
        date: "28 giugno",
        event_city: "Pordenone",
        id: "today-concert",
        source: "TurismoFVG",
        title: "Concerto stasera",
      }, { language: "it", location: { city: "Pordenone" }, now }),
    ];

    expect(rankEventsForLocation(records, { location: { city: "Pordenone" }, now }).map((event) => event.id))
      .toEqual(["today-concert", "long-exhibition"]);
  });

  it("keeps nearer events ahead when timing and type are comparable", () => {
    const records = [
      buildEventRecord({
        category: "sagra",
        date: "4 luglio",
        distance_km: 18,
        event_city: "Sacile",
        id: "far-sagra",
        source: "SagreFVG",
        title: "Sagra lontana",
      }, { language: "it", location: { city: "Pordenone" }, now }),
      buildEventRecord({
        category: "sagra",
        date: "4 luglio",
        distance_km: 3,
        event_city: "Porcia",
        id: "near-sagra",
        source: "SagreFVG",
        title: "Sagra vicina",
      }, { language: "it", location: { city: "Pordenone" }, now }),
    ];

    expect(rankEventsForLocation(records, { location: { city: "Pordenone" }, now })[0].id).toBe("near-sagra");
  });

  it("promotes multi-location events that include the active city", () => {
    const records = [
      buildEventRecord({
        category: "musica",
        date: "3 luglio",
        event_city: "Udine, Cividale del Friuli",
        id: "other-multi",
        source: "TurismoFVG",
        title: "Festival altrove",
      }, { language: "it", location: { city: "Gorizia" }, now }),
      buildEventRecord({
        category: "musica",
        date: "3 luglio",
        event_city: "Trieste, Gorizia, Cormons",
        id: "active-multi",
        source: "TurismoFVG",
        title: "Festival diffuso",
      }, { language: "it", location: { city: "Gorizia" }, now }),
    ];

    expect(rankEventsForLocation(records, { location: { city: "Gorizia" }, now })[0].id).toBe("active-multi");
  });

  it("deduplicates repeated events and keeps the richer record", () => {
    const records = [
      buildEventRecord({
        category: "cultura",
        date: "3 luglio",
        event_city: "Gorizia",
        id: "duplicate-basic",
        source: "EventiFVG",
        title: "Mostra Seghizzi",
      }, { language: "it", location: { city: "Gorizia" }, now }),
      buildEventRecord({
        category: "cultura",
        date: "3 luglio",
        event_city: "Gorizia",
        id: "duplicate-rich",
        image: "poster.jpg",
        source: "TurismoFVG",
        title: "Mostra Seghizzi",
        url: "https://example.com/seghizzi",
      }, { language: "it", location: { city: "Gorizia" }, now }),
    ];

    const ranked = rankEventsForLocation(records, { location: { city: "Gorizia" }, now });

    expect(ranked).toHaveLength(1);
    expect(ranked[0]).toMatchObject({
      id: "duplicate-rich",
      image: "poster.jpg",
      source: "TurismoFVG",
    });
  });

  it("sorts future tabs chronologically while preserving rank within the same day", () => {
    const records = [
      buildEventRecord({
        category: "musica",
        date: "5 luglio",
        event_city: "Gorizia",
        id: "weekend-music",
        source: "TurismoFVG",
        title: "Musica del weekend",
      }, { language: "it", location: { city: "Gorizia" }, now }),
      buildEventRecord({
        category: "cultura",
        date: "3 luglio",
        event_city: "Gorizia",
        id: "friday-culture",
        source: "TurismoFVG",
        title: "Cultura del venerdi",
      }, { language: "it", location: { city: "Gorizia" }, now }),
      buildEventRecord({
        category: "sagra",
        date: "4 luglio",
        event_city: "Gorizia",
        id: "saturday-sagra",
        source: "SagreFVG",
        title: "Sagra di sabato",
      }, { language: "it", location: { city: "Gorizia" }, now }),
    ];

    const ranked = rankEventsForLocation(records, { location: { city: "Gorizia" }, now });

    expect(ranked[0].id).toBe("saturday-sagra");
    expect(sortEventsForTimeTab(ranked, "next", { now }).map((event) => event.id))
      .toEqual(["friday-culture", "saturday-sagra", "weekend-music"]);
  });

  it("puts a local festival programme first only in its own city", () => {
    const scenarioNow = new Date(2026, 8, 15, 12);
    const makeRecords = (city) => [
      buildEventRecord({
        title: "Concerto", id: "concert", start_date: "2026-09-16",
        event_city: city, category: "musica",
      }, { location: { city }, now: scenarioNow }),
      buildEventRecord({
        title: "Pordenonelegge 2026", id: "programme",
        start_date: "2026-09-16", end_date: "2026-09-20",
        display_mode: "umbrella", programme_city: "Pordenone",
        active_session_count: 2, event_city: "Pordenone e territorio",
      }, { location: { city }, now: scenarioNow }),
    ];
    const inPordenone = rankEventsForLocation(makeRecords("Pordenone"),
      { location: { city: "Pordenone" }, now: scenarioNow });
    expect(sortEventsForTimeTab(inPordenone, "next", { now: scenarioNow })[0].id).toBe("programme");

    const elsewhere = rankEventsForLocation(makeRecords("Sacile"),
      { location: { city: "Sacile" }, now: scenarioNow });
    expect(sortEventsForTimeTab(elsewhere, "next", { now: scenarioNow })[0].id).toBe("concert");
  });

  it("keeps Barcis events ahead of nearby towns on the same day in weekend and next tabs", () => {
    const scenarioNow = new Date("2026-08-19T12:00:00");
    const records = [
      buildEventRecord({
        category: "cultura",
        date: "23 agosto",
        distance_km: 20,
        event_city: "Claut",
        id: "claut-23",
        source: "TurismoFVG",
        title: "Evento a Claut",
      }, { language: "it", location: { city: "Barcis" }, now: scenarioNow }),
      buildEventRecord({
        category: "cultura",
        date: "21 agosto",
        distance_km: 15,
        event_city: "Montereale Valcellina",
        id: "montereale-21",
        source: "TurismoFVG",
        title: "Evento a Montereale",
      }, { language: "it", location: { city: "Barcis" }, now: scenarioNow }),
      buildEventRecord({
        category: "cultura",
        date: "23 agosto",
        distance_km: 0,
        event_city: "Barcis",
        id: "barcis-23",
        source: "TurismoFVG",
        title: "Evento del weekend a Barcis",
      }, { language: "it", location: { city: "Barcis" }, now: scenarioNow }),
      buildEventRecord({
        category: "cultura",
        date: "21 agosto",
        distance_km: 0,
        event_city: "Barcis",
        id: "barcis-21",
        source: "TurismoFVG",
        title: "Evento a Barcis",
      }, { language: "it", location: { city: "Barcis" }, now: scenarioNow }),
    ];

    const ranked = rankEventsForLocation(records, {
      location: { city: "Barcis" },
      now: scenarioNow,
    });
    const weekendEvents = ranked.filter((event) => event.timeCategory === "weekend");
    const nextEvents = ranked.filter((event) => event.timeCategory === "weekend" || event.timeCategory === "next");

    expect(sortEventsForTimeTab(weekendEvents, "weekend", { now: scenarioNow }).map((event) => event.id))
      .toEqual(["barcis-23", "claut-23"]);
    expect(sortEventsForTimeTab(nextEvents, "next", { now: scenarioNow }).map((event) => event.id))
      .toEqual(["barcis-21", "montereale-21", "barcis-23", "claut-23"]);
  });
});
