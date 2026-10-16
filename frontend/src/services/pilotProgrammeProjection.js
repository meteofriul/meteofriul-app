const PROGRAMMES = [
  {
    editionId: "2026",
    endDate: "2026-09-20",
    id: "pordenonelegge-2026",
    seriesId: "pordenonelegge",
    source: "Pordenonelegge",
    startDate: "2026-09-16",
    title: "Pordenonelegge 2026",
    url: "https://www.pordenonelegge.it/programma?giorno=tutto",
    city: "Pordenone",
    multiPlace: true,
    multiVenue: true,
    place: "Pordenone e territorio",
    venue: "Più sedi",
    reviewedRegionalUrls: new Map([
      ["https://www.turismofvg.it/eventi/pordenonelegge-2026", "umbrella"],
      ["https://www.turismofvg.it/eventi/pordenonelegge-scimmia-sapiens", "session_reference"],
      ["https://www.turismofvg.it/eventi/pordenonelegge-non-e-mai-troppo-tardi-la-salute-e-una-scelta-quotidiana", "session_reference"],
      ["https://www.turismofvg.it/eventi/pordenonelegge-csaba-dalla-zorza-presenta-il-tempo-per-un-altra-vita", "session_reference"],
      ["https://www.turismofvg.it/eventi/pordenonelegge-502757", "session_reference"],
    ]),
  },
  {
    editionId: "2026",
    endDate: "2026-09-07",
    id: "pordenone-pensa-in-giallo-2026",
    seriesId: "pordenone-pensa-in-giallo",
    source: "Pordenone Pensa",
    startDate: "2026-09-05",
    title: "Pordenone Pensa in Giallo 2026",
    url: "https://www.pnpensa.it/pnpensa-giallo-settembre-2026-pordenone/",
    city: "Pordenone",
    multiPlace: false,
    multiVenue: true,
    place: "Pordenone",
    venue: "Più sedi",
    reviewedRegionalUrls: new Map(),
  },
];

const CINEMA_MUTO_TURISMO_2026 = "https://www.turismofvg.it/eventi/45-le-giornate-del-cinema-muto";

function reviewedCinemaMutoRegional(event) {
  if (event?.source !== "TurismoFVG"
    || String(event?.url || "").split("?", 1)[0] !== CINEMA_MUTO_TURISMO_2026
    || event?.start_date !== "2026-10-03"
    || event?.end_date !== "2026-10-10"
    || event?.event_city !== "Pordenone"
    || (event?.programme_id && event.programme_id !== "giornate-del-cinema-muto-2026")) return null;
  return {
    editionId: "2026",
    endDate: "2026-10-11",
    id: "giornate-del-cinema-muto-2026",
    mainStartDate: "2026-10-03",
    mainEndDate: "2026-10-10",
    seriesId: "giornate-del-cinema-muto",
    source: "Le Giornate del Cinema Muto",
    startDate: "2026-10-02",
    title: "Le Giornate del Cinema Muto 2026",
    url: "https://www.giornatedelcinemamuto.it/",
    city: "Pordenone",
    multiPlace: true,
    multiVenue: true,
    place: "Pordenone e territorio",
    venue: "Più sedi",
  };
}

function declaredPordenonelegge(event) {
  if (event?.source !== "Pordenonelegge" || event?.series_id !== "pordenonelegge") return null;
  const year = String(event?.edition_id || "");
  if (!/^20\d{2}$/.test(year)
    || event?.programme_id !== `pordenonelegge-${year}`
    || event?.programme_title !== `Pordenonelegge ${year}`
    || !String(event?.programme_start_date || "").startsWith(`${year}-`)
    || !String(event?.programme_end_date || "").startsWith(`${year}-`)
    || event?.programme_url !== "https://www.pordenonelegge.it/programma?giorno=tutto") return null;
  return {
    editionId: year,
    endDate: event.programme_end_date,
    id: event.programme_id,
    seriesId: "pordenonelegge",
    source: "Pordenonelegge",
    startDate: event.programme_start_date,
    title: event.programme_title,
    url: event.programme_url,
    city: "Pordenone",
    multiPlace: true,
    multiVenue: true,
    place: "Pordenone e territorio",
    venue: "Più sedi",
  };
}

function declaredCinemaMuto(event) {
  if (event?.source !== "Le Giornate del Cinema Muto"
    || event?.series_id !== "giornate-del-cinema-muto") return null;
  const year = String(event?.edition_id || "");
  const dates = [event?.programme_start_date, event?.programme_main_start_date,
    event?.programme_main_end_date, event?.programme_end_date];
  if (!/^20\d{2}$/.test(year)
    || event?.programme_id !== `giornate-del-cinema-muto-${year}`
    || event?.programme_title !== `Le Giornate del Cinema Muto ${year}`
    || event?.programme_url !== "https://www.giornatedelcinemamuto.it/"
    || dates.some((day) => !new RegExp(`^${year}-\\d{2}-\\d{2}$`).test(day || ""))
    || dates.some((day, index) => index && day < dates[index - 1])) return null;
  return {
    editionId: year,
    endDate: dates[3],
    id: event.programme_id,
    mainStartDate: dates[1],
    mainEndDate: dates[2],
    seriesId: "giornate-del-cinema-muto",
    source: "Le Giornate del Cinema Muto",
    startDate: dates[0],
    title: event.programme_title,
    url: event.programme_url,
    city: "Pordenone",
    multiPlace: true,
    multiVenue: true,
    place: "Pordenone e territorio",
    venue: "Più sedi",
  };
}

function getProgrammeMembership(event) {
  const dynamic = declaredPordenonelegge(event) || declaredCinemaMuto(event);
  if (dynamic) return { programme: dynamic, role: event?.programme_role || "session" };
  const regionalCinema = reviewedCinemaMutoRegional(event);
  if (regionalCinema) return { programme: regionalCinema, role: "umbrella" };
  if (["Pordenonelegge", "Le Giornate del Cinema Muto"].includes(event?.source)
    && event?.programme_id
    && !PROGRAMMES.some((programme) => programme.id === event.programme_id)) return null;
  const declared = PROGRAMMES.find((programme) => programme.id === event?.programme_id);
  if (declared) return { programme: declared, role: event?.programme_role || "session" };

  const direct = PROGRAMMES.find((programme) => programme.source === event?.source);
  if (direct) return { programme: direct, role: "session" };

  if (event?.source !== "TurismoFVG") return null;
  const regional = PROGRAMMES.find((programme) => programme.reviewedRegionalUrls.has(event?.url));
  return regional
    ? { programme: regional, role: regional.reviewedRegionalUrls.get(event.url) }
    : null;
}

function unique(values) {
  return [...new Set(values.filter(Boolean).map((value) => String(value).trim()).filter(Boolean))].sort();
}

function programmeSessions(entries) {
  const seen = new Set();
  return entries
    .map(({ event }) => Object.fromEntries(
      ["title", "start_date", "time", "place", "event_city", "url", "access_notes"]
        .filter((key) => event?.[key])
        .map((key) => [key, event[key]]),
    ))
    .filter((session) => {
      const key = JSON.stringify([session.url, session.title, session.start_date, session.time, session.place]);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((first, second) => (
      `${first.start_date || ""}|${first.time || ""}|${first.title || ""}|${first.place || ""}`
        .localeCompare(`${second.start_date || ""}|${second.time || ""}|${second.title || ""}|${second.place || ""}`, "it")
    ));
}

function buildProgrammeCard(entries, programme) {
  const authoritative = entries.find(({ event }) => (
    event?.programme_role === "umbrella" || event?.display_mode === "umbrella"
  ))?.event;
  const sessions = entries.filter(({ role }) => role === "session");
  const references = entries.filter(({ role }) => role === "session_reference");
  if (authoritative && !sessions.length && !references.length) {
    const {
      distance_is_approximate: _distanceIsApproximate,
      distance_km: distanceKm,
      lat: _lat,
      lon: _lon,
      ...card
    } = authoritative;
    return {
      ...card,
      event_city: programme.place,
      is_multi_place: programme.multiPlace,
      is_multi_venue: programme.multiVenue,
      location_label: `${programme.place} · ${programme.venue || card.venue || "Più sedi"}`,
      location_confidence: "programme_area",
      nearest_session_distance_km: card.nearest_session_distance_km ?? distanceKm,
      place: programme.place,
      programme_is_multi_place: programme.multiPlace,
      programme_is_multi_venue: programme.multiVenue,
      programme_place_label: programme.place,
      venue: programme.venue || card.venue,
    };
  }
  const scheduleEntries = sessions.length ? sessions : references.length ? references : entries;
  const listedSessions = programmeSessions(sessions.length ? sessions : references);
  const nearest = [...scheduleEntries].sort((first, second) => (
    Number(first.event?.distance_km ?? Number.POSITIVE_INFINITY)
    - Number(second.event?.distance_km ?? Number.POSITIVE_INFINITY)
  ))[0]?.event || entries[0].event;
  const rich = entries.find(({ event, role }) => role === "umbrella"
    && (event?.image || event?.description || event?.description_excerpt))?.event || {};
  const cities = unique(scheduleEntries.map(({ event }) => event?.event_city || event?.city));
  const venues = unique(scheduleEntries.map(({ event }) => event?.venue || event?.place));
  const occurrences = unique(scheduleEntries.flatMap(({ event }) => [
    event?.start_date,
    ...(Array.isArray(event?.occurrences) ? event.occurrences : []),
  ]));
  const sources = unique(entries.map(({ event }) => event?.source));
  const place = programme.place;
  const venue = programme.venue || venues[0] || place;
  const optional = Object.fromEntries(
    ["image", "category", "categories", "provider_categories", "provider_category_list", "audience",
      "description", "description_excerpt", "description_source_name", "description_source_url"]
      .filter((key) => rich[key])
      .map((key) => [key, rich[key]]),
  );
  if (programme.seriesId === "giornate-del-cinema-muto") {
    const officialImage = sessions.find(({ event }) => (
      event?.source === "Le Giornate del Cinema Muto" && event?.image
    ))?.event.image;
    if (officialImage) optional.image = officialImage;
  }

  return {
    ...optional,
    active_session_count: listedSessions.length,
    display_mode: "umbrella",
    edition_id: programme.editionId,
    end_date: programme.endDate,
    event_city: programme.place,
    is_multi_place: programme.multiPlace,
    is_multi_venue: programme.multiVenue,
    location_confidence: "programme_area",
    location_label: venue === "Più sedi" ? `${place} · Più sedi` : place,
    municipality_count: cities.length,
    nearest_session_distance_km: nearest?.distance_km,
    occurrences,
    place,
    programme_display_mode: "umbrella",
    programme_sessions: listedSessions,
    programme_end_date: programme.endDate,
    ...(programme.mainStartDate ? { programme_main_start_date: programme.mainStartDate } : {}),
    ...(programme.mainEndDate ? { programme_main_end_date: programme.mainEndDate } : {}),
    programme_id: programme.id,
    programme_is_multi_place: programme.multiPlace,
    programme_is_multi_venue: programme.multiVenue,
    programme_place_label: programme.place,
    programme_role: "umbrella",
    programme_source: programme.source,
    programme_start_date: programme.startDate,
    programme_title: programme.title,
    programme_url: programme.url,
    series_id: programme.seriesId,
    source: programme.source,
    source_id: programme.id,
    sources,
    start_date: programme.startDate,
    title: programme.title,
    url: programme.url,
    venue,
    venue_count: venues.length,
  };
}

// Compatibility for the already-deployed pilot API. Membership is limited to
// explicit adapter sources and reviewed URLs; unrelated theatres and festivals
// are never inferred from title similarity.
export function projectPilotProgrammeCards(events = []) {
  const regular = [];
  const groups = new Map();

  for (const event of events) {
    const membership = getProgrammeMembership(event);
    if (!membership) {
      regular.push(event);
      continue;
    }
    const entries = groups.get(membership.programme.id) || [];
    entries.push({ event, programme: membership.programme, role: membership.role });
    groups.set(membership.programme.id, entries);
  }

  for (const entries of groups.values()) {
    regular.push(buildProgrammeCard(entries, entries[0].programme));
  }

  return regular;
}
