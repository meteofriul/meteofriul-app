import culturalRecords from "../../domain/discover/discoverCulturalRecords";
import { isCuratedDiscoverUiReady } from "../../domain/discover/discoverCulturalReadiness";
import { getDiscoverTemporalRank } from "../../domain/discover/discoverTemporalSelection";
import { getTraditionalSayingRecords } from "../../domain/discover/traditionalSayings";
import { buildDiscoverViewModel } from "./discoverViewModel";

const DEFAULT_LOCATION = {
  city: "Pordenone",
  province: "Pordenone",
  region: "Friuli Venezia Giulia",
};

const SECTION_IDS = {
  archive: "archive",
  memory: "today-memory",
  ritual: "rituals",
  saying: "traditional-sayings",
};

function getYearDates(year) {
  const start = Date.UTC(year, 0, 1);
  const end = Date.UTC(year + 1, 0, 1);
  const dates = [];

  for (let cursor = start; cursor < end; cursor += 24 * 60 * 60 * 1000) {
    dates.push(new Date(cursor).toISOString().slice(0, 10));
  }

  return dates;
}

function isCulturalRecordReady(record, language) {
  return isCuratedDiscoverUiReady(record)
    && (language !== "fur" || record?.languageStatus?.fur === "approved");
}

function isSayingReady(record, language) {
  return record?.readyForUi === true
    && record?.primaryUse === "discover"
    && record?.editorialStatus === "ready_for_discover"
    && record?.source?.type === "verified_source"
    && (language !== "fur" || record?.languageStatus?.fur === "approved");
}

function getCard(model, sectionId) {
  return model.sections.find((section) => section.id === sectionId)?.cards[0] || null;
}

function getSecondaryMemoryCards(model) {
  return model.sections.find((section) => section.id === "local-memory-secondary")?.cards || [];
}

function toSelection(card) {
  if (!card) return null;
  return {
    id: card.id,
    contentKey: card.contentKey || card.id,
    selectionKind: card.selectionKind,
    temporalRank: card.temporalRank ?? null,
    title: card.title,
  };
}

function summarizeRubric(rows, key, eligibleIds) {
  const selectedIds = rows.map((row) => row[key]?.id || null);
  const usedIds = [...new Set(selectedIds.filter(Boolean))];
  let currentId = null;
  let currentLength = 0;
  let longest = { id: null, days: 0 };

  selectedIds.forEach((id) => {
    if (!id) {
      currentId = null;
      currentLength = 0;
      return;
    }
    if (id === currentId) {
      currentLength += 1;
    } else {
      currentId = id;
      currentLength = 1;
    }
    if (currentLength > longest.days) longest = { id, days: currentLength };
  });

  return {
    daysShown: selectedIds.filter(Boolean).length,
    daysAbsent: selectedIds.filter((id) => !id).length,
    uniqueUsed: usedIds.length,
    usedIds,
    eligibleIds,
    unusedEligibleIds: eligibleIds.filter((id) => !usedIds.includes(id)),
    longestConsecutiveRepeat: longest,
  };
}

function getEligibleIds(records, dates, allowedRanks = [0, 1, 2, 3, 4]) {
  return records
    .filter((record) => dates.some((date) => allowedRanks.includes(getDiscoverTemporalRank(record, date))))
    .map((record) => record.id)
    .sort();
}

function findVisibleCollisions(row) {
  const selections = [
    ["memory", row.memory],
    ["ritual", row.ritual],
    ["saying", row.saying],
    ["archive", row.archive],
  ].filter(([, selection]) => selection);
  const grouped = new Map();

  selections.forEach(([rubric, selection]) => {
    const matches = grouped.get(selection.contentKey) || [];
    matches.push({ rubric, id: selection.id });
    grouped.set(selection.contentKey, matches);
  });

  return [...grouped.entries()]
    .filter(([, matches]) => matches.length > 1)
    .map(([contentKey, matches]) => ({ contentKey, matches }));
}

function findCatalogCrossRubricDuplicates(cultural, sayings) {
  const entries = [
    ...cultural.map((record) => ({
      rubric: record.section === "riti_credenze_popolari" ? "ritual" : "archive",
      id: record.id,
      contentKey: record.candidateId || record.id,
    })),
    ...sayings.map((record) => ({
      rubric: "saying",
      id: record.id,
      contentKey: record.candidateId || record.id,
    })),
  ];
  const grouped = new Map();

  entries.forEach((entry) => {
    const matches = grouped.get(entry.contentKey) || [];
    matches.push(entry);
    grouped.set(entry.contentKey, matches);
  });

  return [...grouped.entries()]
    .filter(([, matches]) => new Set(matches.map((match) => match.rubric)).size > 1)
    .map(([contentKey, matches]) => ({ contentKey, matches }));
}

function getExactCandidates(records, date) {
  return records.filter((record) => getDiscoverTemporalRank(record, date) === 0);
}

export function buildDiscoverEditorialCalendarAudit({
  year = 2028,
  language = "it",
  location = DEFAULT_LOCATION,
  localMemorySource,
  municipalityProfileSource,
  sourceRecords = culturalRecords,
  traditionalSayingsSource,
} = {}) {
  const dates = getYearDates(year);
  const readyCultural = sourceRecords.filter((record) => isCulturalRecordReady(record, language));
  const readyRituals = readyCultural.filter((record) => record.section === "riti_credenze_popolari");
  const readyArchive = readyCultural.filter((record) => record.section !== "riti_credenze_popolari");
  const readySayings = getTraditionalSayingRecords(traditionalSayingsSource)
    .filter((record) => isSayingReady(record, language));

  const rows = dates.map((date) => {
    const model = buildDiscoverViewModel({
      language,
      location,
      localMemorySource,
      municipalityProfileSource,
      sourceRecords,
      today: date,
      traditionalSayingsSource,
    });
    const row = {
      date,
      memory: toSelection(getCard(model, SECTION_IDS.memory)),
      secondaryMemories: getSecondaryMemoryCards(model).map(toSelection),
      ritual: toSelection(getCard(model, SECTION_IDS.ritual)),
      saying: toSelection(getCard(model, SECTION_IDS.saying)),
      archive: toSelection(getCard(model, SECTION_IDS.archive)),
    };

    return {
      ...row,
      visibleCollisions: findVisibleCollisions(row),
    };
  });

  const exactDateConflicts = [];
  const exactDateCoveredByHigherRubric = [];
  const exactDatePrecedenceViolations = [];
  rows.forEach((row) => {
    const visibleSelections = [row.memory, ...row.secondaryMemories, row.ritual, row.saying, row.archive]
      .filter(Boolean);
    [
      ["ritual", readyRituals, row.ritual],
      ["saying", readySayings, row.saying],
      ["archive", readyArchive, row.archive],
    ].forEach(([rubric, records, selected]) => {
      const candidates = getExactCandidates(records, row.date);
      if (!candidates.length) return;
      const candidateIds = candidates.map((record) => record.id);
      if (candidates.length > 1) {
        exactDateConflicts.push({
          date: row.date,
          rubric,
          candidateIds,
          selectedId: selected?.id || null,
        });
      }
      const selectedExact = selected && candidateIds.includes(selected.id);
      const coveringSelections = visibleSelections.filter((selection) => (
        candidates.some((candidate) => (
          (candidate.candidateId || candidate.id) === selection.contentKey
        ))
      ));
      if (!selectedExact && coveringSelections.length) {
        exactDateCoveredByHigherRubric.push({
          date: row.date,
          rubric,
          candidateIds,
          coveringSelections: coveringSelections.map((selection) => ({
            id: selection.id,
            contentKey: selection.contentKey,
          })),
        });
      } else if (!selectedExact) {
        exactDatePrecedenceViolations.push({
          date: row.date,
          rubric,
          candidateIds,
          selectedId: selected?.id || null,
        });
      }
    });
  });

  const eligibleRitualIds = getEligibleIds(readyRituals, dates, [0, 1, 2]);
  const eligibleSayingIds = getEligibleIds(readySayings, dates);
  const eligibleArchiveIds = getEligibleIds(readyArchive, dates);
  const visibleCollisions = rows.flatMap((row) => (
    row.visibleCollisions.map((collision) => ({ date: row.date, ...collision }))
  ));

  return {
    year,
    days: rows.length,
    location,
    rows,
    summary: {
      memory: summarizeRubric(rows, "memory", []),
      ritual: summarizeRubric(rows, "ritual", eligibleRitualIds),
      saying: summarizeRubric(rows, "saying", eligibleSayingIds),
      archive: summarizeRubric(rows, "archive", eligibleArchiveIds),
      secondaryMemoryDays: rows.filter((row) => row.secondaryMemories.length > 0).length,
      visibleCollisions,
      catalogCrossRubricDuplicates: findCatalogCrossRubricDuplicates(readyCultural, readySayings),
      exactDateConflicts,
      exactDateCoveredByHigherRubric,
      exactDatePrecedenceViolations,
    },
  };
}
