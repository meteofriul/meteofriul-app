import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(scriptDirectory, "..");
const sourceDirectory = process.argv[2];
const outputPath = resolve(
  process.argv[3] || resolve(repositoryRoot, "frontend/src/data/discover/pilotWhyCatalog.json"),
);

if (!sourceDirectory) {
  throw new Error("Usage: node scripts/import-pilot-why-catalog.mjs <markdown-directory> [output-json]");
}

const sourceFiles = {
  archive: "01_ARCHIVIO_I_PERCHE_DEL_FRIUL.md",
  calendar: "02_CALENDARIO_ANNUALE.md",
};

const sourceText = Object.fromEntries(Object.entries(sourceFiles).map(([key, name]) => [
  key,
  readFileSync(resolve(sourceDirectory, name), "utf8").replace(/\r\n/g, "\n"),
]));

const corrections = [
  { from: "r撹e", occurrences: 1, reason: "Scheda #48: ricostruzione minima della parola friulana 'rave'.", to: "rave" },
  { from: "l识e", occurrences: 1, reason: "Scheda #77: ricostruzione minima del verbo friulano 'lasse'.", to: "lasse" },
  { from: "v顕is", occurrences: 3, reason: "Schede #102 e #363: ricostruzione minima della parola friulana 'vignis'.", to: "vignis" },
];

let correctedArchive = sourceText.archive;
for (const correction of corrections) {
  const found = correctedArchive.split(correction.from).length - 1;
  if (found !== correction.occurrences) {
    throw new Error(`Expected ${correction.occurrences} occurrence(s) of ${correction.from}, found ${found}.`);
  }
  correctedArchive = correctedArchive.split(correction.from).join(correction.to);
}

if (/[\u3400-\u9fff]/u.test(correctedArchive)) {
  throw new Error("The archive still contains an unreviewed CJK character.");
}

function section(block, startHeading, endHeading) {
  const startToken = `**${startHeading}**`;
  const endToken = `**${endHeading}**`;
  const start = block.indexOf(startToken);
  const end = block.indexOf(endToken, start + startToken.length);
  if (start < 0 || end < 0) throw new Error(`Missing section ${startHeading}.`);
  return block.slice(start + startToken.length, end).trim();
}

function nonEmptyLines(value) {
  return value.split("\n").map(line => line.trim()).filter(Boolean);
}

function localized(value, field, archiveId) {
  const result = {};
  for (const line of nonEmptyLines(value)) {
    const match = line.match(/^(IT|FUR):(?:\\\*)?\s*(.+)$/u);
    if (match) result[match[1].toLowerCase()] = match[2].trim();
  }
  if (!result.it || !result.fur) throw new Error(`Incomplete ${field} in ${archiveId}.`);
  return result;
}

function originalArchiveId(number) {
  return `#${number < 100 ? String(number).padStart(2, "0") : number}`;
}

const cardHeaders = [...correctedArchive.matchAll(/^### Scheda #(\d{2,3})$/gmu)];
const records = cardHeaders.map((header, index) => {
  const number = Number.parseInt(header[1], 10);
  const archiveId = originalArchiveId(number);
  const blockStart = header.index + header[0].length;
  const blockEnd = cardHeaders[index + 1]?.index ?? correctedArchive.length;
  const block = correctedArchive.slice(blockStart, blockEnd);
  const categories = nonEmptyLines(section(block, "Categoria", "Domanda (IT / FUR)"));
  const sourceLines = nonEmptyLines(block.slice(block.indexOf("**Fonte**") + "**Fonte**".length));

  if (categories.length < 2 || !sourceLines[0]) throw new Error(`Incomplete category or source in ${archiveId}.`);

  return {
    id: `why-${String(number).padStart(3, "0")}`,
    archiveId,
    category: { it: categories[0], fur: categories[1] },
    question: localized(section(block, "Domanda (IT / FUR)", "Risposta (IT / FUR)"), "question", archiveId),
    answer: localized(section(block, "Risposta (IT / FUR)", "Fonte"), "answer", archiveId),
    sources: [{ label: sourceLines[0] }],
  };
});

const expectedIds = Array.from({ length: 366 }, (_, index) => `why-${String(index + 1).padStart(3, "0")}`);
const actualIds = records.map(record => record.id);
if (records.length !== 366 || new Set(actualIds).size !== 366 || expectedIds.some((id, index) => actualIds[index] !== id)) {
  throw new Error("Archive IDs must be the complete ordered range #01-#366.");
}

const schedule = {};
const calendarMatches = [...sourceText.calendar.matchAll(/^- (\d{2}-\d{2}) → #(\d{1,3}) \(.+\)$/gmu)];
for (const match of calendarMatches) {
  const [, dateKey, numberText] = match;
  if (schedule[dateKey]) throw new Error(`Duplicate calendar date ${dateKey}.`);
  schedule[dateKey] = `why-${String(Number.parseInt(numberText, 10)).padStart(3, "0")}`;
}
schedule["02-29"] = "why-366";

if (calendarMatches.length !== 365 || Object.keys(schedule).length !== 366) {
  throw new Error(`Expected 365 ordinary dates plus leap day, found ${calendarMatches.length} plus leap day.`);
}

for (const [dateKey, id] of Object.entries(schedule)) {
  const [month, day] = dateKey.split("-").map(Number);
  const parsed = new Date(Date.UTC(2000, month - 1, day));
  if (parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day) throw new Error(`Invalid date ${dateKey}.`);
  if (!actualIds.includes(id)) throw new Error(`Calendar date ${dateKey} refers to missing ${id}.`);
}

for (const record of records) {
  record.dateKeys = Object.entries(schedule)
    .filter(([, id]) => id === record.id)
    .map(([dateKey]) => dateKey);
}

const ordinaryCounts = new Map();
for (const [dateKey, id] of Object.entries(schedule)) {
  if (dateKey === "02-29") continue;
  ordinaryCounts.set(id, (ordinaryCounts.get(id) || 0) + 1);
}
const duplicateScheduleIds = [...ordinaryCounts]
  .filter(([, count]) => count > 1)
  .map(([id]) => records.find(record => record.id === id).archiveId)
  .sort((first, second) => Number(first.slice(1)) - Number(second.slice(1)));
const unassignedArchiveIds = records
  .filter(record => record.id !== "why-366" && !ordinaryCounts.has(record.id))
  .map(record => record.archiveId);
const expectedDuplicateIds = ["#80", "#110", "#186", "#290", "#303", "#340"];
const expectedUnassignedIds = ["#167", "#250", "#266", "#272", "#286", "#298"];
if (JSON.stringify(duplicateScheduleIds) !== JSON.stringify(expectedDuplicateIds)
  || JSON.stringify(unassignedArchiveIds) !== JSON.stringify(expectedUnassignedIds)) {
  throw new Error("The documented calendar anomalies changed; review the source before importing.");
}

const sha256 = value => createHash("sha256").update(value, "utf8").digest("hex");
const escapeCjk = value => value.replace(/[\u3400-\u9fff]/gu, character => (
  `<U+${character.codePointAt(0).toString(16).toUpperCase().padStart(4, "0")}>`
));
const payload = {
  metadata: {
    recordCount: records.length,
    scheduledDateCount: Object.keys(schedule).length,
    sourceHashes: Object.fromEntries(Object.entries(sourceFiles).map(([key, name]) => [
      name,
      sha256(sourceText[key]),
    ])),
    editorialStatus: "converted_source_not_independently_fact_checked",
    friulianReviewStatus: "provided_source_not_human_certified",
    textCorrections: corrections.map(({ from, occurrences, reason, to }) => ({
      from: escapeCjk(from), occurrences, reason, to,
    })),
    scheduleWarnings: { duplicateScheduleIds, unassignedArchiveIds },
  },
  schedule,
  records,
};

writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
console.log(`Wrote ${records.length} records and ${Object.keys(schedule).length} date mappings to ${outputPath}.`);
