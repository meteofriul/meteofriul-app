import fs from "node:fs";

const REVIEW_PATH = process.argv[2] || "frontend/src/data/discover/discoverDailyFurReviewWave.json";
const LOCAL_MEMORY_PATH = "frontend/src/data/discover/localMemory.json";

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8").replace(/^\uFEFF/, ""));
}

function isAlreadyPromoted(record, review) {
  return record.title?.fur === review.titleFur
    && record.summary?.fur === review.summaryFur
    && record.editorialStatus === "ready_for_discover"
    && record.languageStatus?.fur === "approved"
    && record.readyForUi === true;
}

function replaceOnce(text, before, after, recordId) {
  const index = text.indexOf(before);
  if (index === -1) throw new Error(`Cannot update ${recordId}: missing ${before}`);
  return `${text.slice(0, index)}${after}${text.slice(index + before.length)}`;
}

function replaceOneOf(text, replacements, after, recordId) {
  for (const before of replacements) {
    if (text.includes(before)) return replaceOnce(text, before, after, recordId);
  }
  throw new Error(`Cannot update ${recordId}: missing one of ${replacements.join(" | ")}`);
}

function promoteRecordText(text, item) {
  const idMarker = `      "id": "${item.id}",`;
  const start = text.indexOf(idMarker);
  if (start === -1) throw new Error(`Cannot locate canonical record: ${item.id}`);
  const nextRecord = text.indexOf("\n    },\n    {", start);
  const end = nextRecord === -1 ? text.indexOf("\n    }\n  ]", start) : nextRecord + 7;
  if (end === -1) throw new Error(`Cannot locate canonical record end: ${item.id}`);

  let segment = text.slice(start, end);
  segment = replaceOnce(segment, '"fur": "pending_review"', `"fur": ${JSON.stringify(item.titleFur)}`, item.id);
  segment = replaceOnce(segment, '"fur": "pending_review"', `"fur": ${JSON.stringify(item.summaryFur)}`, item.id);
  segment = replaceOneOf(
    segment,
    [
      "Fonte e copy IT approvati nella seconda ondata Scopri. Pubblicazione bloccata fino alla revisione FUR.",
      "Fonte e copy IT approvati nella revisione Scopri. Pubblicazione bloccata fino alla revisione FUR.",
      "Fonte e copy IT approvate; pubblicazione bloccata finche la denominazione istituzionale storica FUR non supera la revisione umana.",
    ],
    "Fonte, copy IT e FUR approvate per la pubblicazione controllata in Scopri.",
    item.id,
  );
  segment = replaceOnce(segment, '"editorialStatus": "source_verified"', '"editorialStatus": "ready_for_discover"', item.id);
  segment = replaceOnce(segment, '"fur": "human_review_needed"', '"fur": "approved"', item.id);
  segment = replaceOneOf(
    segment,
    [
      "Record canonico IT approvato; FUR e readyForUi restano bloccanti.",
      "Record canonico IT approvato; FUR e readyForUi restano bloccanti. Voce secondaria/archivio.",
      "Fonte e copy IT approvate; la denominazione istituzionale storica FUR richiede ancora revisione umana.",
    ],
    "Fonte, copy IT e FUR approvate; record promosso per Memoria del giorno in Scopri.",
    item.id,
  );
  segment = replaceOnce(segment, '"readyForUi": false', '"readyForUi": true', item.id);
  return `${text.slice(0, start)}${segment}${text.slice(end)}`;
}

const review = readJson(REVIEW_PATH);
const localMemoryText = fs.readFileSync(LOCAL_MEMORY_PATH, "utf8");
const localMemory = JSON.parse(localMemoryText.replace(/^\uFEFF/, ""));
const recordsById = new Map(localMemory.records.map((record) => [record.id, record]));
const approved = review.records.filter((record) => record.status === "approved");
const pending = review.records.filter((record) => record.status === "pending_human_review");
const promotedIds = [];
let nextLocalMemoryText = localMemoryText;

if (review.records.length !== review.summary.totalRecords
  || approved.length !== review.summary.approved
  || pending.length !== review.summary.pendingHumanReview) {
  throw new Error("FUR review summary does not match its records.");
}

for (const item of review.records) {
  const record = recordsById.get(item.id);
  if (!record) throw new Error(`Missing canonical record: ${item.id}`);

  if (item.status === "pending_human_review") {
    if (record.readyForUi !== false || record.languageStatus?.fur !== "human_review_needed") {
      throw new Error(`Pending FUR record is not blocked: ${item.id}`);
    }
    continue;
  }

  if (isAlreadyPromoted(record, item)) continue;
  if (record.editorialStatus !== "source_verified"
    || record.languageStatus?.it !== "approved"
    || record.languageStatus?.fur !== "human_review_needed"
    || record.readyForUi !== false) {
    throw new Error(`Canonical staging state is invalid: ${item.id}`);
  }

  nextLocalMemoryText = promoteRecordText(nextLocalMemoryText, item);
  promotedIds.push(record.id);
}

if (promotedIds.length) {
  fs.writeFileSync(LOCAL_MEMORY_PATH, nextLocalMemoryText, "utf8");
}

console.log(JSON.stringify({
  promoted: promotedIds.length,
  promotedIds,
  approved: approved.length,
  pendingHumanReview: pending.length,
}, null, 2));
