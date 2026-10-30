import inventory from "../../data/markets/catalogue2026.json";
import { FIXED_FVG_PLACES } from "../../data/fvgPlaces";
import { isFvgLocation } from "../../domain/scope/productScope";
import { parseEventDateRange, UPCOMING_WINDOW_DAYS } from "../events/eventsViewModel";

export const MARKET_CATALOGUE = inventory;
const municipalities = Object.values(FIXED_FVG_PLACES);
export function marketToken(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}
export function marketDay(now = new Date()) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Rome", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(now);
}
export function addMarketDays(day, count) {
  const date = new Date(day + "T12:00:00Z");
  date.setUTCDate(date.getUTCDate() + count);
  return date.toISOString().slice(0, 10);
}
// Calendar source content stays in Italian in both UI languages.
export function formatMarketDate(day) {
  return new Intl.DateTimeFormat("it-IT", {
    day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  }).format(new Date(day + "T12:00:00Z"));
}
export function safeMarketUrl(value) {
  try { const url = new URL(value); return url.protocol === "https:" ? url.href : ""; }
  catch { return ""; }
}
export function marketDirectionsUrl(market, edition) {
  const venue = edition?.venue || market;
  return venue?.directionsQuery
    ? "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(venue.directionsQuery) : "";
}
function urlKey(value) {
  try {
    const url = new URL(value);
    for (const key of [...url.searchParams.keys()]) {
      if (/^utm_|^(fbclid|gclid)$/i.test(key)) url.searchParams.delete(key);
    }
    url.searchParams.sort();
    return url.hostname.replace(/^www\./, "").toLowerCase() + url.pathname.replace(/\/+$/, "") + url.search;
  } catch { return ""; }
}
export function findMarketMunicipality(location) {
  if (!isFvgLocation(location) || !location) return null;
  const country = String(location.countryCode || location.country_code || "IT").toUpperCase();
  if (country !== "IT") return null;
  const name = marketToken(location.municipality?.name || location.city || location.name);
  const code = location.istatCode || location.istat_code || location.municipality?.istatCode;
  const place = municipalities.find(item => code ? item.istatCode === code : marketToken(item.name) === name);
  if (!place || (name && marketToken(place.name) !== name)) return null;
  return place;
}
function distanceKm(a, b) {
  const radians = value => value * Math.PI / 180;
  const dlat = radians(b.latitude - a.latitude), dlon = radians(b.longitude - a.longitude);
  const value = Math.sin(dlat / 2) ** 2 + Math.cos(radians(a.latitude)) * Math.cos(radians(b.latitude)) * Math.sin(dlon / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
}
export function publicMarkets(catalogue = inventory) {
  if (catalogue.unavailable) return [];
  return catalogue.markets.filter(market => market.quality === "Documentato"
    && (!market.status || market.status === "published")
    && !["suspended", "archived", "withdrawn", "closed"].includes(market.activityStatus)
    && !marketIsWithdrawn(market.id, catalogue));
}
function marketIsWithdrawn(marketId, catalogue) {
  return (catalogue.tombstones || []).some(item => item.marketId === marketId && !item.editionId && !item.date
    && ["archived", "withdrawn", "suspended", "cancelled"].includes(item.status));
}
function editionIsWithdrawn(edition, catalogue) {
  return marketIsWithdrawn(edition.marketId, catalogue) || (catalogue.tombstones || []).some(item =>
    item.marketId === edition.marketId && (item.editionId === edition.id || item.date === edition.date)
      && item.status !== "rescheduled");
}
function marketDayIsWithdrawn(marketId, day, catalogue) {
  return (catalogue.tombstones || []).some(item => item.marketId === marketId && item.date === day
    && (item.status !== "rescheduled" || item.replacementDate !== day))
    || catalogue.dates.some(item => item.marketId === marketId && item.date === day
      && ["cancelled", "postponed"].includes(item.status));
}
export function getMarket(id, catalogue = inventory) {
  return publicMarkets(catalogue).find(market => market.id === id) || null;
}
export function publishedMarketDates(market, now = new Date(), catalogue = inventory) {
  if (!market || market.quality !== "Documentato" || catalogue.unavailable || marketIsWithdrawn(market.id, catalogue)) return [];
  const today = marketDay(now);
  return catalogue.dates.filter(item => item.marketId === market.id && item.date >= today
    && (!market.validFrom || item.date >= market.validFrom)
    && (!market.validThrough || item.date <= market.validThrough)
    && item.date <= catalogue.validThrough && item.status === "published" && !editionIsWithdrawn(item, catalogue))
    .sort((a, b) => a.date.localeCompare(b.date));
}
export function marketDateInEvents(day, now = new Date()) {
  const today = marketDay(now);
  return day >= today && day <= addMarketDays(today, UPCOMING_WINDOW_DAYS);
}
export function weekendMarketDays(now = new Date()) {
  const today = marketDay(now), weekday = new Date(today + "T12:00:00Z").getUTCDay();
  const saturday = addMarketDays(today, weekday === 0 ? -1 : (6 - weekday + 7) % 7);
  return [saturday, addMarketDays(saturday, 1)].filter(day => day >= today);
}
export function selectMarkets({ location, radius = 20, period = "all", now = new Date(), catalogue = inventory } = {}) {
  const origin = findMarketMunicipality(location);
  if (!origin) return { supported: false, items: [], areaCount: 0 };
  const today = marketDay(now);
  const selectedDays = period === "today" ? [today] : weekendMarketDays(now);
  const area = publicMarkets(catalogue).flatMap(market => {
    const place = municipalities.find(item => marketToken(item.name) === marketToken(market.comune));
    if (!place) return [];
    const distance = distanceKm(origin, place);
    if (distance > radius && place.istatCode !== origin.istatCode) return [];
    return [{ ...market, distance, dates: publishedMarketDates(market, now, catalogue) }];
  });
  const items = area.filter(market => period === "all" || selectedDays.some(day =>
    market.group === "regular"
      ? !marketDayIsWithdrawn(market.id, day, catalogue) && (market.dates.some(item => item.date === day)
        || (day >= (market.validFrom || market.checked) && day <= catalogue.validThrough
        && (!market.validThrough || day <= market.validThrough)
        && market.weekdays.includes(new Date(day + "T12:00:00Z").getUTCDay())))
      : market.dates.some(item => item.date === day)))
    .sort((a, b) => a.group !== b.group ? (a.group === "regular" ? -1 : 1)
      : (a.group === "occasional" ? (a.dates[0]?.date || "9999").localeCompare(b.dates[0]?.date || "9999") : 0)
        || a.distance - b.distance || a.name.localeCompare(b.name, "it"));
  return { supported: true, items, areaCount: area.length, origin };
}
export function matchMarket(event, catalogue = inventory, { includeWithdrawn = false } = {}) {
  if (!event) return null;
  const raw = event.raw || event;
  // Do not trust arbitrary IDs or fuzzy names to merge distinct local markets.
  const city = marketToken(raw.event_city || raw.city);
  const identities = includeWithdrawn ? (catalogue.identities || []).map(item => ({
    ...item, id: item.marketId, sourceAliases: item.sourceUrls || [],
  })) : [];
  const recordsById = new Map(identities.map(item => [item.id, item]));
  for (const market of includeWithdrawn ? catalogue.markets : publicMarkets(catalogue)) {
    const identity = recordsById.get(market.id);
    recordsById.set(market.id, { ...market,
      titleAliases: [...(market.titleAliases || []), ...(identity?.titleAliases || []), ...(identity?.name ? [identity.name] : [])],
      sourceAliases: [...(market.sourceAliases || []), ...(identity?.sourceAliases || [])],
      municipalityAliases: [...(market.municipalityAliases || []), ...(identity?.municipalityAliases || [])],
    });
  }
  const matchesCity = market => !city || [market.comune, ...(market.municipalityAliases || [])].some(value => marketToken(value) === city);
  const explicit = recordsById.get(raw.market_id);
  if (explicit) return matchesCity(explicit) ? explicit : null;
  const records = [...recordsById.values()].filter(matchesCity);
  const key = urlKey(raw.url);
  const byUrl = key ? records.filter(market => [market.url, ...(market.sourceAliases || []),
    ...catalogue.dates.filter(item => item.marketId === market.id).map(item => item.source)]
    .some(value => urlKey(value) === key)) : [];
  if (byUrl.length === 1) return byUrl[0];
  const title = marketToken(raw.title || raw.name);
  const byName = city ? records.filter(market => [market.name, ...(market.titleAliases || [])]
    .some(value => marketToken(value) === title)) : [];
  return byName.length === 1 ? byName[0] : null;
}
export function eventMarketDays(event, now = new Date()) {
  const raw = event?.raw || event || {};
  if (Array.isArray(raw.occurrences) && raw.occurrences.length) return raw.occurrences.filter(day => /^\d{4}-\d{2}-\d{2}$/.test(day));
  const start = raw.start_date || raw.date;
  if (/^\d{4}-\d{2}-\d{2}$/.test(start || "")) {
    // A broad range is not proof of daily market editions.
    return raw.end_date && raw.end_date !== start ? [] : [start];
  }
  const range = parseEventDateRange(raw.date || raw.date_label || "", { now });
  if (!range || range.start.getTime() !== range.end.getTime()) return [];
  const date = range.start;
  return [String(date.getFullYear()) + "-" + String(date.getMonth() + 1).padStart(2, "0") + "-" + String(date.getDate()).padStart(2, "0")];
}
function cancelled(event) {
  return event.cancelled === true || /cancel|annull|postpon|rinvi/i.test(event.status || event.event_status || "");
}
export function mergeMarketEvents(events = [], { location, radius = 20, now = new Date(), catalogue = inventory } = {}) {
  if (!findMarketMunicipality(location)) return events;
  if (catalogue.schemaVersion === 2) return mergeManagedMarketEvents(events, { location, radius, now, catalogue });
  const consumed = new Set(), broad = new Set();
  const existing = events.flatMap(event => {
    const market = matchMarket(event, catalogue);
    if (!market) return [event];
    const days = eventMarketDays(event, now);
    days.forEach(day => consumed.add(market.id + ":" + day));
    if (!days.length) broad.add(market.id);
    return cancelled(event) ? [] : [{ ...event, market_id: market.id }];
  });
  const local = selectMarkets({ location, radius, now, catalogue }).items.flatMap(market =>
    market.group !== "occasional" || broad.has(market.id) ? [] : market.dates.flatMap(edition => {
      const key = market.id + ":" + edition.date;
      if (!marketDateInEvents(edition.date, now) || consumed.has(key)) return [];
      consumed.add(key);
      return [{
        id: "market:" + key, market_id: market.id, category: "mercato", title: market.name,
        date: formatMarketDate(edition.date), start_date: edition.date, end_date: edition.date,
        event_city: market.comune, place: market.place, source: market.authority, url: edition.source || market.url,
        description: market.kind + ". " + market.cadence + ". " + (market.scheduleNote || "")
          + " Date pubblicate dalla fonte; verificare eventuali variazioni.",
        market_catalogue: true, description_source_name: market.authority,
        description_source_url: edition.source || market.url,
      }];
    }));
  return [...existing, ...local];
}
export function findRequestedMarketEvent(items, request, now = new Date(), catalogue = inventory) {
  if (!request) return null;
  const requestedEditionId = request.editionId || catalogue.dates.find(item => item.marketId === request.marketId
    && (item.date === request.date || item.legacyDates?.includes(request.date)))?.id;
  if (requestedEditionId) return items.find(event => {
    const raw = event.raw || event;
    return raw.market_id === request.marketId && raw.market_edition_id === requestedEditionId
      && eventMarketDays(event, now).some(day => marketDateInEvents(day, now));
  }) || null;
  if (!marketDateInEvents(request.date, now)) return null;
  return items.find(event => matchMarket(event, catalogue)?.id === request.marketId
    && eventMarketDays(event, now).includes(request.date)) || null;
}

function managedEditionEvent(market, edition, source = {}) {
  const venue = edition.venue || market;
  return {
    image: source.image, id: edition.id, market_id: market.id, market_edition_id: edition.id,
    category: "mercato", title: market.name, start_date: edition.date, end_date: edition.date,
    date: formatMarketDate(edition.date), occurrences: [edition.date],
    event_city: market.comune, place: venue.place || "", venue: venue.place || "", address: "",
    maps_url: marketDirectionsUrl(market, edition), lat: venue.lat ?? null, lon: venue.lon ?? null,
    time: edition.hours || market.hours || "", market_catalogue: true, market_managed: true,
    market_venue: edition.venue || null, source: market.authority || source.source,
    url: edition.source || market.url || source.url,
    description: `${market.kind}. ${market.cadence}. ${market.scheduleNote || ""}`,
    description_source_name: market.authority,
    description_source_url: edition.source || market.url,
  };
}

function mergeManagedMarketEvents(events, { location, radius, now, catalogue }) {
  const area = new Map(selectMarkets({ location, radius, now, catalogue }).items.map(market => [market.id, market]));
  const consumed = new Set();
  const existing = events.flatMap(event => {
    const raw = event.raw || event;
    if (raw.market_id && marketIsWithdrawn(raw.market_id, catalogue)) return [];
    const identity = matchMarket(event, catalogue, { includeWithdrawn: true });
    if (!identity) {
      const retiredEdition = (catalogue.tombstones || []).some(item =>
        item.editionId && item.editionId === raw.market_edition_id);
      return retiredEdition || (catalogue.blockUnknownMarkets && (raw.market_id || raw.market_edition_id || /mercat/i.test(raw.category || ""))) ? [] : [event];
    }
    const market = area.get(identity.id);
    if (!market) return [];
    const days = eventMarketDays(event, now);
    const editions = catalogue.dates.filter(edition => edition.marketId === market.id
      && (edition.id === raw.market_edition_id || days.some(day => edition.date === day || edition.legacyDates?.includes(day))
        || (catalogue.editionAliases || []).some(alias => alias.editionId === edition.id && alias.legacyId === raw.id)));
    if (editions.length) return editions.flatMap(edition => {
      if (consumed.has(edition.id)) return [];
      consumed.add(edition.id);
      if (!market.dates.some(item => item.id === edition.id) || !marketDateInEvents(edition.date, now)) return [];
      // An obsolete cancellation for the old date cannot cancel its replacement.
      if (cancelled(raw) && days.includes(edition.date)) return [];
      return [managedEditionEvent(market, edition, raw)];
    });
    const tombstones = (catalogue.tombstones || []).filter(item => item.marketId === market.id);
    if (cancelled(raw) || tombstones.some(item => item.editionId === raw.market_edition_id
      || (item.date && days.includes(item.date)))) return [];
    // The managed occasional calendar is authoritative. A source range is not
    // an extra edition and must not revive a withdrawn or superseded occurrence.
    if (market.group === "occasional") return [];
    if (!days.length || (market.validThrough && marketDay(now) > market.validThrough)
      || days.some(day => day > catalogue.validThrough || (market.validThrough && day > market.validThrough)
        || (market.validFrom && day < market.validFrom)
        || !market.weekdays.includes(new Date(day + "T12:00:00Z").getUTCDay()))) return [];
    return [{ id: raw.id, image: raw.image, start_date: raw.start_date, end_date: raw.end_date,
      date: days.length === 1 ? formatMarketDate(days[0]) : raw.date, occurrences: days,
      market_id: market.id, title: market.name, category: "mercato", event_city: market.comune,
      place: market.place, venue: market.place, address: "", lat: null, lon: null, time: market.hours || "",
      description: `${market.kind}. ${market.cadence}. ${market.scheduleNote || ""}`,
      description_excerpt: "", url: market.url || raw.url, source: market.authority || raw.source,
      description_source_name: market.authority, description_source_url: market.url,
      maps_url: marketDirectionsUrl(market), market_managed: true, market_catalogue: true }];
  });
  // Explicit, approved editions are events, including extraordinary openings of
  // a weekly market. Habitual weekdays alone never generate events.
  const local = [...area.values()].flatMap(market => market.dates.flatMap(edition => {
    if (consumed.has(edition.id) || !marketDateInEvents(edition.date, now)) return [];
    consumed.add(edition.id);
    return [managedEditionEvent(market, edition)];
  }));
  return [...existing, ...local];
}
