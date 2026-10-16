import fs from "node:fs";

const BATCH_PATH = "frontend/src/data/discover/dailyHistoryLightEditorialBatch.json";
const LOCAL_MEMORY_PATH = "frontend/src/data/discover/localMemory.json";

const SELECTED_WIKIDATA_IDS = [
  "Q1491020",
  "Q326243",
  "Q17284902",
  "Q983350",
  "Q6520921",
  "Q3991880",
  "Q922154",
  "Q133876935",
  "Q15921979",
  "Q661716",
  "Q12795100",
  "Q2508496",
  "Q2273489",
  "Q1008988",
  "Q3746508",
  "Q3845573",
  "Q104176849",
  "Q2704669",
  "Q1339427",
  "Q3830078",
  "Q544750",
  "Q3608590",
  "Q18646312",
  "Q3609332",
  "Q325885",
  "Q2161101",
  "Q3960835",
  "Q3059608",
  "Q3769521",
];

const TITLE_OVERRIDES = {
  Q1491020: "Gaetano Kanizsa e la percezione",
  Q326243: "Stanislaus Joyce, Trieste letteraria",
  Q17284902: "Napoleone Cozzi, arte e montagna",
  Q983350: "Giovanni da Udine, botteghe e Rinascimento",
  Q6520921: "Lella Vignelli e il design",
  Q3991880: "Tito Maniacco, cultura friulana",
  Q922154: "Lojze Spacal e il Carso",
  Q133876935: "Adalgiso Fior, voce friulana",
  Q15921979: "Giovanni Battista Bassi a Pordenone",
  Q661716: "Gianni Bisiach, racconto e divulgazione",
  Q12795100: "Lojzka Bratuz, memoria di confine",
  Q2508496: "Valentin Stanic, montagna e cultura",
  Q2273489: "Gillo Dorfles, arte europea",
  Q1008988: "Giorgio Pressburger, teatro e memoria",
  Q3746508: "Flavio Paulin, una nota pop",
  Q3845573: "Marcello De Stefano, cinema e pittura",
  Q104176849: "Eugenio Pilutti, voce da archivio",
  Q2704669: "Luca Carlevarijs, dal Friuli alle vedute",
  Q1339427: "Enrico Rava, jazz e territorio",
  Q3830078: "Lelio Luttazzi, musica e radio",
  Q544750: "Ernesto Nathan Rogers e il Novecento",
  Q3608590: "Alberto Spaini, Trieste e i libri",
  Q18646312: "Stefan Kociancic, lingue e confine",
  Q3609332: "Aldo Stellita, memoria pop friulana",
  Q325885: "Matteo Pertsch e la Trieste urbana",
  Q2161101: "Giorgio Voghera, Trieste discreta",
  Q3960835: "Silvio Benco, giornalismo e letteratura",
  Q3059608: "Eugenio Geiringer, tecnica e citta",
  Q3769521: "Giulio Camagni, disegno contemporaneo",
};

const CATEGORY_OVERRIDES = {
  Q15921979: "storia",
};

function readJson(path) {
  return JSON.parse(fs.readFileSync(path, "utf8"));
}

function formatRecordForLocalMemory(record) {
  return JSON.stringify(record, null, 2)
    .split("\n")
    .map((line) => `    ${line}`)
    .join("\n");
}

function appendRecordsPreservingFile(path, newRecords) {
  if (!newRecords.length) return;

  const text = fs.readFileSync(path, "utf8");
  const marker = "\n  ]\n}\n";
  const index = text.lastIndexOf(marker);
  if (index === -1) {
    throw new Error(`Cannot find localMemory records array closing marker in ${path}`);
  }

  const block = newRecords.map(formatRecordForLocalMemory).join(",\n");
  fs.writeFileSync(path, `${text.slice(0, index)},\n${block}${text.slice(index)}`, "utf8");
}

function slugify(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
}

function normalizeArea(value) {
  return slugify(value || "friuli").replace(/-/g, "_");
}

function buildRecord(batchRecord) {
  const wikidataId = batchRecord.wikidataId;
  const dayKey = batchRecord.dateAnchor;
  const compactDay = dayKey.replace("-", "");
  const place = batchRecord.place || batchRecord.province || "Friuli Venezia Giulia";
  const area = normalizeArea(place);

  return {
    id: `memory-copy-${compactDay}-${slugify(batchRecord.title)}`,
    primaryUse: "discover",
    recommendedSurface: "discover",
    category: CATEGORY_OVERRIDES[wikidataId] || "cultura",
    dateAnchors: [dayKey],
    rotationTags: ["memoria", area],
    areas: [area, "friuli_venezia_giulia"],
    priority: 60,
    title: {
      it: TITLE_OVERRIDES[wikidataId] || batchRecord.title,
      fur: "pending_review",
    },
    summary: {
      it: batchRecord.copyDraft?.it || "",
      fur: "pending_review",
    },
    source: {
      label: "Master Accadde oggi FVG esteso",
      type: "daily_history_master_candidate",
      wikidataId,
      url: `https://www.wikidata.org/wiki/${wikidataId}`,
      confidence: "candidate_reviewed",
      note: "Bozza promossa dal light editorial batch. Non pubblicare senza review editoriale finale e FUR approvato.",
    },
    editorialStatus: "copy_candidate",
    languageStatus: {
      it: "copy_draft",
      fur: "human_review_needed",
    },
    editorialReview: {
      reviewedAt: "2026-07-08",
      note: "Primo blocco copy candidate per Memoria del giorno; pronto per revisione FUR/IT, non per UI.",
    },
    readyForUi: false,
  };
}

const batch = readJson(BATCH_PATH);
const localMemory = readJson(LOCAL_MEMORY_PATH);

const batchRecords = Array.isArray(batch.records) ? batch.records : batch;
const records = Array.isArray(localMemory.records) ? localMemory.records : [];
const byWikidataId = new Map(batchRecords.map((record) => [record.wikidataId, record]));
const knownWikidataIds = new Set(records.map((record) => record.source?.wikidataId).filter(Boolean));

const promoted = [];
const promotedRecords = [];

for (const wikidataId of SELECTED_WIKIDATA_IDS) {
  const batchRecord = byWikidataId.get(wikidataId);
  if (!batchRecord) {
    throw new Error(`Missing batch record: ${wikidataId}`);
  }

  if (batchRecord.batchDecision !== "copy_candidate") {
    throw new Error(`Selected record is not a copy_candidate: ${wikidataId}`);
  }

  if (knownWikidataIds.has(wikidataId)) {
    continue;
  }

  const record = buildRecord(batchRecord);
  promotedRecords.push(record);
  promoted.push(record.id);
}

appendRecordsPreservingFile(LOCAL_MEMORY_PATH, promotedRecords);

const updatedLocalMemory = readJson(LOCAL_MEMORY_PATH);
const updatedRecords = Array.isArray(updatedLocalMemory.records) ? updatedLocalMemory.records : [];

console.log(JSON.stringify({
  promotedCount: promoted.length,
  promoted,
  totalRecords: updatedRecords.length,
}, null, 2));
