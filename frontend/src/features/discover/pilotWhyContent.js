import catalogData from "../../data/discover/pilotWhyCatalog.json";
import firstQuestion from "../../data/discover/pilotWhyPalmanova.json";
import { getDiscoverCardAnchor } from "./discoverCardAnchor";
import { getDiscoverDateKey } from "../../domain/discover/discoverTemporalSelection";

const COPY = {
  it: { rubric: "I perché del Friûl", cta: "Scopri", action: "Scopri la risposta", sourcesLabel: "Fonti" },
  fur: { rubric: "I parcè dal Friûl", cta: "Scuvierç", action: "Scuvierç la rispueste", sourcesLabel: "Fonts" },
};

const records = catalogData.records.map(record => (
  record.id === "why-001"
    ? { ...record, ...firstQuestion, catalogId: record.id }
    : { ...record, catalogId: record.id }
));
const recordsByCatalogId = new Map(records.map(record => [record.catalogId, record]));
const recordsByPublicId = new Map(records.map(record => [record.id, record]));

export function getPilotWhyRecordForDate(date = new Date()) {
  const catalogId = catalogData.schedule[getDiscoverDateKey(date)];
  return recordsByCatalogId.get(catalogId) || null;
}

export function getPilotWhyRecordById(id) {
  return recordsByPublicId.get(String(id || "")) || null;
}

export function getPilotWhyContent(language = "it", record = firstQuestion) {
  const key = language === "fur" ? "fur" : "it";
  const question = record?.question?.[key];
  const lead = record?.lead?.[key] || "";
  const answerValue = record?.answer?.[key];
  const answer = Array.isArray(answerValue)
    ? answerValue
    : (typeof answerValue === "string" ? [answerValue] : []);
  const sources = record?.sources;
  if (!record?.id || typeof question !== "string" || !question.trim()
    || !Array.isArray(answer) || !answer.length || answer.some(text => typeof text !== "string" || !text.trim())
    || !Array.isArray(sources) || !sources.length
    || sources.some(source => !source?.label || (source.url && !/^https:\/\//u.test(source.url)))) return null;
  return {
    id: record.id,
    archiveId: record.archiveId || "",
    anchor: getDiscoverCardAnchor(record.id),
    rubric: COPY[key].rubric,
    cta: COPY[key].cta,
    actionLabel: `${COPY[key].action}: ${question}`,
    category: record?.category?.[key] || "",
    dateKeys: Array.isArray(record.dateKeys) ? [...record.dateKeys] : [],
    question,
    lead,
    answer: [...answer],
    sourcesLabel: COPY[key].sourcesLabel,
    sources: sources.map(source => ({ ...source })),
  };
}

export function getPilotWhyContentForDate(language = "it", date = new Date()) {
  return getPilotWhyContent(language, getPilotWhyRecordForDate(date));
}

export function getPilotWhyContentById(language = "it", id = "") {
  return getPilotWhyContent(language, getPilotWhyRecordById(id));
}
