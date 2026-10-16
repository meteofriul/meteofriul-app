import { getDiscoverSeasonLabel, getDiscoverTypeLabel } from "../../copy/discoverCopy";
import {
  getDiscoverSeasonForRecord,
  getDiscoverTemporalRank,
} from "../../domain/discover/discoverTemporalSelection";

const SELECTION_KINDS = ["exact_date", "movable_date", "date_range", "seasonal", "rotation"];

function text(value) {
  return typeof value === "string" ? value.trim() : "";
}

function normalized(value) {
  return text(value).normalize("NFKC").toLocaleLowerCase("it-IT")
    .replace(/[\s\p{P}]+/gu, " ").trim();
}

function significant(value) {
  return value.length >= 32 && value.split(" ").length >= 5;
}

function fingerprints(card) {
  const body = normalized(card?.text);
  const title = normalized(card?.title);
  // A title-only saying contains the actual quotation. A short/shared heading
  // is never evidence that two otherwise different stories are duplicates.
  const candidates = body ? [body, `${title} ${body}`.trim()] : [title];
  return candidates.filter(significant);
}

function identity(card) {
  return text(card?.contentKey) || text(card?.id);
}

function identityAliases(card) {
  return [text(card?.contentKey), text(card?.id)].filter(Boolean);
}

function sourceLabel(value) {
  return text(typeof value === "string" ? value : value?.label);
}

function cardIndex(excludedCards) {
  const identities = new Set();
  const bodies = new Set();
  const remember = card => {
    identityAliases(card).forEach(key => identities.add(key));
    fingerprints(card).forEach(value => bodies.add(value));
  };
  excludedCards.forEach(remember);
  return {
    take(card) {
      if (!card || !identity(card) || (!text(card.title) && !text(card.text))) return null;
      if (identityAliases(card).some(key => identities.has(key))
        || fingerprints(card).some(value => bodies.has(value))) return null;
      remember(card);
      return { ...card, id: text(card.id) || identity(card) };
    },
  };
}

function almanacProverb(calendar) {
  if (!text(calendar.proverb?.body)) return null;
  const raw = calendar.raw?.proverb || {};
  const key = text(raw.candidateId) || text(raw.id) || "almanac-proverb";
  return {
    id: text(raw.id) || "almanac-proverb",
    contentKey: key,
    title: calendar.proverb.title,
    text: calendar.proverb.body,
    type: raw.category || "proverb",
    sourceLabel: sourceLabel(raw.source),
    sourceNote: text(raw.source?.note),
  };
}

function almanacTradition(calendar, language) {
  if (!text(calendar.tradition?.body)) return null;
  const raw = calendar.raw?.tradition || {};
  const key = text(raw.candidateId) || text(raw.id) || "almanac-tradition";
  const date = calendar.raw?.date;
  const rank = date ? getDiscoverTemporalRank(raw, date) : null;
  return {
    id: text(raw.id) || "almanac-tradition",
    contentKey: key,
    title: calendar.tradition.label,
    text: calendar.tradition.body,
    type: raw.type,
    typeLabel: raw.type ? getDiscoverTypeLabel(raw.type, language) : "",
    seasonLabel: date ? getDiscoverSeasonLabel(getDiscoverSeasonForRecord(raw, date), language) : "",
    recurrence: raw.recurrence,
    selectionKind: rank === null ? null : SELECTION_KINDS[rank],
    sourceLabel: text(calendar.tradition.source) || sourceLabel(raw.source),
    sourceNote: text(raw.source?.note),
  };
}

/** Presentation-only grouping of records already selected by the two models.
 * The caller opts in for the pilot; no selectors, catalogues or inputs change.
 */
export function buildPilotDiscoverCulture({
  calendar = {}, sections = [], language = "it", copy = {}, excludedCards = [],
} = {}) {
  const languageKey = language === "fur" ? "fur" : "it";
  const index = cardIndex(excludedCards);
  const cardsFor = id => sections.filter(section => section?.id === id)
    .flatMap(section => Array.isArray(section.cards) ? section.cards : []);
  // Exactly one daily saying. Preserve the curated Discover selection; only
  // fall back to the already-selected almanac proverb when none is available.
  let saying = null;
  for (const card of cardsFor("traditional-sayings")) {
    saying = index.take(card);
    if (saying) break;
  }
  if (!saying) saying = index.take(almanacProverb(calendar));
  const traditions = [
    ...cardsFor("rituals"),
    ...cardsFor("archive"),
    almanacTradition(calendar, languageKey),
  ].map(card => index.take(card)).filter(Boolean);
  const tipKeys = new Set();
  const earthItems = (Array.isArray(calendar.earth?.items) ? calendar.earth.items : [])
    .filter(item => {
      const key = normalized(item);
      if (!key || tipKeys.has(key)) return false;
      tipKeys.add(key);
      return true;
    });
  return {
    sayings: {
      id: "traditional-sayings",
      title: copy.traditionalSayingsTitle || (languageKey === "fur" ? "Si diseve che..." : "Si diceva che..."),
      cards: saying ? [saying] : [],
    },
    traditions: {
      id: "traditions",
      title: languageKey === "fur" ? "Tradizions dal Friûl" : "Tradizioni del Friûl",
      cards: traditions,
    },
    // Tips are editorial advice, not a proverb or an archival attribution.
    earth: { title: text(calendar.earth?.title), items: earthItems },
  };
}
