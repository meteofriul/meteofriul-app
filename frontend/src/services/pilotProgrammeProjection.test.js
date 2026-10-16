import { describe, expect, it } from "vitest";

import { projectPilotProgrammeCards } from "./pilotProgrammeProjection";

describe("pilot programme compatibility projection", () => {
  it("collapses only the explicit Pordenonelegge edition and its reviewed regional card", () => {
    const events = [
      {
        source: "Pordenonelegge",
        title: "Incontro uno",
        url: "https://www.pordenonelegge.it/eventi/uno",
        start_date: "2026-09-17",
        event_city: "Pordenone",
        image: "https://example.test/child.jpg",
        venue: "Sala A",
        lat: 45.9567,
        lon: 12.6605,
        distance_km: 1,
      },
      {
        source: "Pordenonelegge",
        title: "Incontro due",
        url: "https://www.pordenonelegge.it/eventi/due",
        start_date: "2026-09-18",
        event_city: "Cordenons",
        venue: "Sala B",
        lat: 45.9836,
        lon: 12.7004,
        distance_km: 3,
      },
      {
        source: "TurismoFVG",
        title: "Pordenonelegge 2026",
        url: "https://www.turismofvg.it/eventi/pordenonelegge-2026",
        image: "https://example.test/poster.jpg",
        start_date: "2026-09-16",
        end_date: "2026-09-20",
        event_city: "Pordenone",
        distance_km: 1.2,
      },
      {
        source: "TurismoFVG",
        title: "Titolo simile ma non revisionato",
        url: "https://www.turismofvg.it/eventi/pordenonelegge-non-revisionato",
      },
    ];

    const projected = projectPilotProgrammeCards(events);

    expect(projected).toHaveLength(2);
    expect(projected[0].title).toBe("Titolo simile ma non revisionato");
    expect(projected[1]).toMatchObject({
      display_mode: "umbrella",
      event_city: "Pordenone e territorio",
      image: "https://example.test/poster.jpg",
      is_multi_place: true,
      is_multi_venue: true,
      location_confidence: "programme_area",
      nearest_session_distance_km: 1,
      place: "Pordenone e territorio",
      programme_id: "pordenonelegge-2026",
      active_session_count: 2,
      title: "Pordenonelegge 2026",
      venue: "Più sedi",
    });
    expect(projected[1]).not.toHaveProperty("session_count");
    expect(projected[1].sources).toEqual(["Pordenonelegge", "TurismoFVG"]);
    expect(projected[1].programme_sessions.map((session) => session.title))
      .toEqual(["Incontro uno", "Incontro due"]);
    expect(projected[1]).not.toHaveProperty("distance_km");
    expect(projected[1]).not.toHaveProperty("lat");
    expect(projected[1]).not.toHaveProperty("lon");
  });

  it("does not collapse unrelated theatre performances", () => {
    const events = ["17", "18"].map((day) => ({
      source: "Teatro Verdi Pordenone",
      title: "Lo stesso spettacolo",
      url: "https://example.test/spettacolo",
      start_date: `2026-09-${day}`,
    }));

    expect(projectPilotProgrammeCards(events)).toEqual(events);
  });

  it("uses explicit programme metadata from the new backend contract", () => {
    const projected = projectPilotProgrammeCards([{
      programme_id: "pordenone-pensa-in-giallo-2026",
      programme_role: "session",
      source: "Pordenone Pensa",
      image: "https://example.test/session-only.jpg",
      title: "Un incontro",
      start_date: "2026-09-06",
      event_city: "Pordenone",
    }]);

    expect(projected).toHaveLength(1);
    expect(projected[0]).toMatchObject({
      display_mode: "umbrella",
      active_session_count: 1,
      programme_id: "pordenone-pensa-in-giallo-2026",
      title: "Pordenone Pensa in Giallo 2026",
      venue: "Più sedi",
    });
    expect(projected[0]).not.toHaveProperty("session_count");
    expect(projected[0]).not.toHaveProperty("image");
  });

  it("preserves an authoritative backend umbrella without counting it as one session", () => {
    const projected = projectPilotProgrammeCards([{
      active_session_count: 1,
      event_city: "Pordenone e territorio",
      display_mode: "umbrella",
      distance_km: 0.8,
      lat: 45.9567,
      lon: 12.6605,
      programme_id: "pordenonelegge-2026",
      programme_role: "umbrella",
      session_count: 386,
      source: "Pordenonelegge",
      programme_sessions: [{ title: "Incontro", start_date: "2026-09-17", time: "09:00" }],
      title: "Pordenonelegge 2026",
      url: "https://www.pordenonelegge.it/programma?giorno=tutto",
    }]);

    expect(projected).toHaveLength(1);
    expect(projected[0]).toMatchObject({
      active_session_count: 1,
      event_city: "Pordenone e territorio",
      is_multi_place: true,
      is_multi_venue: true,
      location_confidence: "programme_area",
      location_label: "Pordenone e territorio · Più sedi",
      nearest_session_distance_km: 0.8,
      place: "Pordenone e territorio",
      session_count: 386,
      venue: "Più sedi",
    });
    expect(projected[0]).not.toHaveProperty("distance_km");
    expect(projected[0]).not.toHaveProperty("lat");
    expect(projected[0]).not.toHaveProperty("lon");
    expect(projected[0].programme_sessions).toHaveLength(1);
  });

  it("keeps two same-day appointments distinct and orders them by time", () => {
    const events = ["11:00", "09:00"].map((time) => ({
      source: "Pordenonelegge", title: `Incontro ${time}`,
      url: `https://www.pordenonelegge.it/eventi/${time}`,
      start_date: "2026-09-17", time, place: "Pordenone, Sala A",
    }));
    const [card] = projectPilotProgrammeCards(events);
    expect(card.active_session_count).toBe(2);
    expect(card.programme_sessions.map((session) => session.time)).toEqual(["09:00", "11:00"]);
  });

  it("keeps the officially declared next edition instead of relabeling it 2026", () => {
    const edition = {
      source: "Pordenonelegge", series_id: "pordenonelegge",
      programme_id: "pordenonelegge-2027", edition_id: "2027",
      programme_title: "Pordenonelegge 2027",
      programme_start_date: "2027-09-15", programme_end_date: "2027-09-19",
      programme_url: "https://www.pordenonelegge.it/programma?giorno=tutto",
    };
    const projected = projectPilotProgrammeCards([
      { ...edition, programme_role: "session", title: "Primo incontro",
        start_date: "2027-09-15", time: "09:00",
        url: "https://www.pordenonelegge.it/eventi/primo" },
      { ...edition, programme_role: "session", title: "Secondo incontro",
        start_date: "2027-09-16", time: "11:00",
        url: "https://www.pordenonelegge.it/eventi/secondo" },
    ]);
    expect(projected).toHaveLength(1);
    expect(projected[0]).toMatchObject({
      title: "Pordenonelegge 2027", programme_id: "pordenonelegge-2027",
      active_session_count: 2, start_date: "2027-09-15", end_date: "2027-09-19",
    });
    expect(projected[0].programme_sessions).toHaveLength(2);
    const [unverified] = projectPilotProgrammeCards([{
      source: "Pordenonelegge", programme_id: "pordenonelegge-2028",
      title: "Edizione da verificare",
    }]);
    expect(unverified.title).toBe("Edizione da verificare");
  });

  it("shows Cinema Muto as one card with dated programme slots and the announced main period", () => {
    const edition = {
      source: "Le Giornate del Cinema Muto",
      series_id: "giornate-del-cinema-muto",
      programme_id: "giornate-del-cinema-muto-2027",
      edition_id: "2027",
      programme_title: "Le Giornate del Cinema Muto 2027",
      programme_start_date: "2027-10-02",
      programme_main_start_date: "2027-10-03",
      programme_main_end_date: "2027-10-10",
      programme_end_date: "2027-10-11",
      programme_url: "https://www.giornatedelcinemamuto.it/",
    };
    const card = projectPilotProgrammeCards([
      { ...edition, programme_role: "session", title: "Preapertura",
        start_date: "2027-10-02", time: "20:45", event_city: "Sacile",
        image: "https://www.giornatedelcinemamuto.it/wp-content/uploads/2027/08/COVER-GCM2027.jpg",
        url: "https://www.giornatedelcinemamuto.it/calendario-021027/" },
      { ...edition, programme_role: "session", title: "Proiezione",
        start_date: "2027-10-03", time: "09:00", event_city: "Pordenone",
        url: "https://www.giornatedelcinemamuto.it/calendario-031027/" },
    ])[0];
    expect(card).toMatchObject({
      title: "Le Giornate del Cinema Muto 2027",
      display_mode: "umbrella",
      active_session_count: 2,
      start_date: "2027-10-02",
      end_date: "2027-10-11",
      programme_main_start_date: "2027-10-03",
      programme_main_end_date: "2027-10-10",
      place: "Pordenone e territorio",
      image: "https://www.giornatedelcinemamuto.it/wp-content/uploads/2027/08/COVER-GCM2027.jpg",
    });
    expect(card.programme_sessions.map(({ title }) => title))
      .toEqual(["Preapertura", "Proiezione"]);
    expect(projectPilotProgrammeCards([{
      ...edition, programme_id: "giornate-del-cinema-muto-2028",
      title: "Calendario incoerente",
    }])[0].title).toBe("Calendario incoerente");
  });

  it("prefers the official Cinema Muto edition cover and uses the exact regional card as fallback", () => {
    const official = {
      source: "Le Giornate del Cinema Muto", series_id: "giornate-del-cinema-muto",
      programme_id: "giornate-del-cinema-muto-2026", edition_id: "2026",
      programme_title: "Le Giornate del Cinema Muto 2026",
      programme_start_date: "2026-10-02", programme_main_start_date: "2026-10-03",
      programme_main_end_date: "2026-10-10", programme_end_date: "2026-10-11",
      programme_url: "https://www.giornatedelcinemamuto.it/",
      programme_role: "session", start_date: "2026-10-06", time: "09:00",
      title: "Proiezione", url: "https://www.giornatedelcinemamuto.it/calendario-061026/",
      image: "https://www.giornatedelcinemamuto.it/wp-content/uploads/2026/08/COVER-GCM2026.jpg",
    };
    const regional = {
      source: "TurismoFVG", url: "https://www.turismofvg.it/eventi/45-le-giornate-del-cinema-muto",
      start_date: "2026-10-03", end_date: "2026-10-10", event_city: "Pordenone",
      image: "https://www.turismofvg.it/proxyvfs.axd/ext,full/r301069?v=464509&ext=.jpg",
      description_excerpt: "Il festival del cinema muto.",
    };
    const [card] = projectPilotProgrammeCards([official, regional]);
    expect(card.image).toBe(official.image);
    expect(card.description_excerpt).toBe(regional.description_excerpt);
    expect(card.sources).toEqual(["Le Giornate del Cinema Muto", "TurismoFVG"]);
    const [fallback] = projectPilotProgrammeCards([{ ...official, image: null }, regional]);
    expect(fallback.image).toBe(regional.image);
    expect(projectPilotProgrammeCards([{ ...regional, end_date: "2026-10-09" }])[0])
      .toEqual({ ...regional, end_date: "2026-10-09" });
  });
});
