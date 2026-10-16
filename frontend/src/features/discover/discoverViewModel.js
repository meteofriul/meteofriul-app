import {
  getDiscoverCopy,
  getDiscoverSeasonLabel,
  getDiscoverTitle,
  getDiscoverTypeLabel,
} from "../../copy/discoverCopy";
import {
  getLocalMemoryForDate,
  getLocalMemoryForLocation,
  getLocalMemorySecondaryForDate,
} from "../../domain/discover/localMemory";
import records from "../../domain/discover/discoverCulturalRecords";
import { getMunicipalityProfile } from "../../domain/discover/municipalityProfiles";
import { getTraditionalSayingForDate } from "../../domain/discover/traditionalSayings";
import {
  getDiscoverSeasonForRecord,
  getDiscoverTemporalRank,
  pickDiscoverTemporalRecord,
} from "../../domain/discover/discoverTemporalSelection";
import { isCuratedDiscoverUiReady } from "../../domain/discover/discoverCulturalReadiness";
import { isDiscoverWeatherArchiveStory } from "../../domain/discover/discoverWeatherEditorialPolicy";

function getLanguageKey(language) {
  return language === "fur" ? "fur" : "it";
}

function localizedValue(value, language) {
  if (!value || typeof value !== "object") return "";
  return value[language] || value.it || value.fur || "";
}

function isFurReady(record) {
  return record?.languageStatus?.fur === "approved";
}

function getPrimaryRecords(sourceRecords, languageKey) {
  return sourceRecords
    .filter((record) => (
      isCuratedDiscoverUiReady(record) && (languageKey !== "fur" || isFurReady(record))
    ))
    .sort((first, second) => {
      const priorityDiff = Number(first.priority || 99) - Number(second.priority || 99);
      if (priorityDiff) return priorityDiff;
      return String(first.id).localeCompare(String(second.id));
    });
}

function getContentKey(record) {
  return record?.candidateId || record?.id;
}

function buildCard(record, language, date) {
  const languageKey = getLanguageKey(language);
  const canUseRequestedLanguage = languageKey !== "fur" || isFurReady(record);
  const contentLanguage = canUseRequestedLanguage ? languageKey : "it";

  const temporalRank = getDiscoverTemporalRank(record, date);
  const selectionKinds = ["exact_date", "movable_date", "date_range", "seasonal", "rotation"];

  return {
    id: record.id,
    contentKey: record.candidateId || record.id,
    title: localizedValue(record.title, contentLanguage),
    text: localizedValue(record.text, contentLanguage),
    type: record.type,
    typeLabel: getDiscoverTypeLabel(record.type, languageKey),
    seasonLabel: getDiscoverSeasonLabel(
      getDiscoverSeasonForRecord(record, date),
      languageKey,
    ),
    selectionKind: selectionKinds[temporalRank] || "unavailable",
    temporalRank,
    sourceLabel: record.source?.label || "Ostermann 1894",
    sourceNote: record.source?.note || "",
    isFurPending: languageKey === "fur" && !canUseRequestedLanguage,
  };
}

function getLocalMemorySection(localMemoryCard, copy) {
  if (!localMemoryCard) return null;

  if (localMemoryCard.selectionKind === "exact_date") {
    return {
      id: "today-memory",
      title: copy.exactMemoryTitle || copy.localMemoryTitle,
      cards: [localMemoryCard],
      role: "exact-date-memory",
    };
  }

  return {
    id: "territory-stories",
    title: copy.localMemoryFallbackTitle || copy.localMemoryTitle,
    cards: [localMemoryCard],
    role: "rotation-memory",
  };
}

function uniqueSections(sections, initialCardIds = []) {
  const usedIds = new Set();
  const usedCardIds = new Set(initialCardIds);

  return sections
    .filter((section) => section?.cards.length)
    .map((section) => ({
      ...section,
      cards: section.cards.filter((card) => {
        const contentKey = card?.contentKey || card?.id;
        if (!card?.id || usedCardIds.has(contentKey)) return false;
        usedCardIds.add(contentKey);
        return true;
      }),
    }))
    .filter((section) => {
      if (!section.cards.length || usedIds.has(section.id)) return false;
      usedIds.add(section.id);
      return true;
    });
}

function getPageSourceLine({ copy, focus, sections }) {
  const visibleCards = [
    focus,
    ...sections.flatMap((section) => section.cards),
  ].filter(Boolean);

  if (!visibleCards.length) return copy.editorialSourceLine || copy.sourceLine;

  const allOstermann = visibleCards.every((card) => (
    String(card.sourceLabel || "").toLowerCase().includes("ostermann")
  ));

  return allOstermann ? copy.sourceLine : copy.editorialSourceLine || copy.sourceLine;
}

export function buildDiscoverViewModel({
  language = "it",
  location,
  localMemorySource,
  municipalityLocation = location,
  municipalityProfileSource,
  sourceRecords = records,
  today = new Date(),
  traditionalSayingsSource,
} = {}) {
  const languageKey = getLanguageKey(language);
  const copy = getDiscoverCopy(languageKey);
  const primaryRecords = getPrimaryRecords(sourceRecords, languageKey);
  const municipalityProfile = getMunicipalityProfile({
    language: languageKey,
    location: municipalityLocation,
    source: municipalityProfileSource,
  });
  const localMemoryCard = getLocalMemoryForDate({
    date: today,
    language: languageKey,
    source: localMemorySource,
  });
  const secondaryMemoryCards = getLocalMemorySecondaryForDate({
    date: today,
    language: languageKey,
    location,
    source: localMemorySource,
  });
  const traditionalSayingCard = getTraditionalSayingForDate({
    date: today,
    language: languageKey,
    source: traditionalSayingsSource,
  });
  const locationFocus = getLocalMemoryForLocation({
    date: today,
    excludeIds: [
      localMemoryCard?.id,
      localMemoryCard?.contentKey,
      ...secondaryMemoryCards.map((card) => card.id),
      ...secondaryMemoryCards.map((card) => card.contentKey),
    ].filter(Boolean),
    language: languageKey,
    location,
    source: localMemorySource,
  });
  const reservedDailyContentKeys = new Set([
    localMemoryCard?.contentKey,
    ...secondaryMemoryCards.map((card) => card.contentKey),
    traditionalSayingCard?.contentKey,
  ].filter(Boolean));
  if (locationFocus) reservedDailyContentKeys.add(locationFocus.contentKey || locationFocus.id);
  const focusEligibleRecords = primaryRecords.filter((record) => (
    record.editorialStatus === "ready_it"
      && !isDiscoverWeatherArchiveStory(record)
      && getDiscoverTemporalRank(record, today) === 4
  ));
  const genericFocusRecord = municipalityProfile || locationFocus
    ? null
    : pickDiscoverTemporalRecord(focusEligibleRecords, today, {
      excludedContentKeys: reservedDailyContentKeys,
    });
  if (genericFocusRecord) reservedDailyContentKeys.add(getContentKey(genericFocusRecord));
  const sectionRecords = genericFocusRecord
    ? primaryRecords.filter((record) => record.id !== genericFocusRecord.id)
    : primaryRecords;
  const ritualRecords = sectionRecords.filter((record) => (
    record.section === "riti_credenze_popolari" &&
    [0, 1, 2].includes(getDiscoverTemporalRank(record, today))
  ));
  const archiveRecords = sectionRecords.filter((record) => record.section !== "riti_credenze_popolari");
  const dailyRitualRecord = pickDiscoverTemporalRecord(ritualRecords, today, {
    excludedContentKeys: reservedDailyContentKeys,
  });
  if (dailyRitualRecord) reservedDailyContentKeys.add(getContentKey(dailyRitualRecord));
  const dailyArchiveRecord = pickDiscoverTemporalRecord(archiveRecords, today, {
    blendBroader: true,
    excludedContentKeys: reservedDailyContentKeys,
    offset: 1,
  });
  const focus = municipalityProfile
    || locationFocus
    || (genericFocusRecord ? buildCard(genericFocusRecord, languageKey, today) : null);
  const sections = uniqueSections([
    getLocalMemorySection(localMemoryCard, copy),
    dailyRitualRecord ? {
      id: "rituals",
      title: copy.ritualsTitle,
      cards: [buildCard(dailyRitualRecord, languageKey, today)],
      role: "daily-ritual",
    } : null,
    traditionalSayingCard ? {
      id: "traditional-sayings",
      title: copy.traditionalSayingsTitle,
      cards: [traditionalSayingCard],
      role: traditionalSayingCard.selectionKind === "exact_date" ? "exact-date-saying" : "rotation-saying",
    } : null,
    dailyArchiveRecord ? {
      id: "archive",
      title: languageKey === "fur" ? "Archivis e tradizions" : "Archivio e tradizioni",
      cards: [buildCard(dailyArchiveRecord, languageKey, today)],
      role: "archive-rotation",
    } : null,
    secondaryMemoryCards.length ? {
      id: "local-memory-secondary",
      title: copy.secondaryMemoryTitle,
      cards: secondaryMemoryCards,
      role: "exact-date-secondary-memory",
    } : null,
  ], focus ? [focus.contentKey || focus.id] : []);

  return {
    title: getDiscoverTitle(languageKey),
    copy,
    location: location || null,
    count: primaryRecords.length,
    focus,
    focusTitle: municipalityProfile
      ? copy.municipalitySectionTitle
      : locationFocus
        ? copy.locationFocusTitle
        : copy.focus,
    sections,
    sourceLine: getPageSourceLine({ copy, focus, sections }),
  };
}
