import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const REVIEW_DIR = path.join(ROOT, "scripts", "data", "ostermann-proverbs-1876");
const PROVERBS_PATH = path.join(ROOT, "frontend", "src", "data", "almanac", "proverbs.json");
const SCHEDULE_PATH = path.join(ROOT, "frontend", "src", "data", "almanac", "schedule.json");
const CALENDAR_RESOLUTION_PATH = path.join(REVIEW_DIR, "almanac-calendar-conflict-resolution.json");
const CALENDAR_RULE_NORMALIZATION_PATH = path.join(
  REVIEW_DIR,
  "almanac-calendar-rule-normalization.json",
);

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function getCategory(rule) {
  if (rule.type === "date" || rule.type === "movable_feast") return "almanacco_santi";
  if (rule.type === "months") return "meteo_mensile";
  if (rule.type === "date_range" || rule.type === "seasons") return "meteo_stagionale";
  if (rule.bucket === "agriculture") return "lavoro";
  if (rule.bucket === "nature") return "natura";
  return "saggezza";
}

function getTags(record) {
  const tags = new Set(["ostermann", "tradizione"]);
  const rule = record.calendarRule || {};

  if (rule.bucket) tags.add(rule.bucket === "agriculture" ? "campagna" : rule.bucket);
  if (rule.type === "date" || rule.type === "movable_feast") tags.add("calendario");
  if (rule.type === "months" || rule.type === "date_range" || rule.type === "seasons") {
    tags.add("stagione");
  }

  const searchable = `${record.itFinal} ${record.furNormalized}`.toLowerCase();
  const keywordTags = [
    ["piogg", "pioggia"],
    ["plo", "pioggia"],
    ["neve", "neve"],
    ["nêf", "neve"],
    ["fredd", "freddo"],
    ["frêt", "freddo"],
    ["tempo", "tempo"],
    ["timp", "tempo"],
    ["frumento", "raccolto"],
    ["forment", "raccolto"],
    ["vite", "vigna"],
    ["vît", "vigna"],
  ];

  keywordTags.forEach(([needle, tag]) => {
    if (searchable.includes(needle)) tags.add(tag);
  });

  return [...tags];
}

function applyCalendarRule(target, rule) {
  if (rule.type === "date") {
    const dayKey = `${pad(rule.month)}-${pad(rule.day)}`;
    target.almanacTargetUse = "almanac_dated";
    target.dateAnchors = [dayKey];
    return;
  }

  if (rule.type === "months") {
    target.almanacTargetUse = "almanac_monthly";
    target.months = rule.months.map(pad);
    return;
  }

  if (rule.type === "date_range") {
    target.almanacTargetUse = "almanac_date_range";
    target.dateRanges = [{
      from: `${pad(rule.from.month)}-${pad(rule.from.day)}`,
      to: `${pad(rule.to.month)}-${pad(rule.to.day)}`,
    }];
    return;
  }

  if (rule.type === "seasons") {
    target.almanacTargetUse = "almanac_seasonal";
    target.seasons = [...rule.seasons];
    return;
  }

  if (rule.type === "movable_feast") {
    target.almanacTargetUse = "almanac_movable_feast";
    target.movableFeasts = [{ id: rule.feast, offsetDays: Number(rule.offsetDays || 0) }];
  }
}

const selection = readJson(path.join(REVIEW_DIR, "editorial-selection-it.json"));
const furSelection = readJson(path.join(REVIEW_DIR, "editorial-selection-fur.json"));
const languageRecords = selection.sourceLanguageReviewFiles.flatMap((fileName) => {
  const batch = readJson(path.join(REVIEW_DIR, fileName));
  return batch.records.map((record) => ({
    ...record,
    reviewedAt: batch.reviewedAt,
  }));
});
const languageById = new Map(languageRecords.map((record) => [record.id, record]));
const approvedFurIds = new Set(furSelection.approvedIds || []);
const approvedDecisions = selection.records.filter((record) => record.decision === "approve_almanac");

const promotedRecords = approvedDecisions.map((decision) => {
  const reviewed = languageById.get(decision.id);
  if (!reviewed) throw new Error(`Missing language review for ${decision.id}`);
  if (!approvedFurIds.has(decision.id)) throw new Error(`Missing approved FUR for ${decision.id}`);
  if (!reviewed.itFinal || !reviewed.furNormalized) throw new Error(`Incomplete bilingual copy for ${decision.id}`);

  const primaryEvidence = reviewed.evidence?.find((item) => item.kind === "primary");
  const record = {
    id: decision.id,
    fur_original: reviewed.furNormalized,
    fur: reviewed.furNormalized,
    it: reviewed.itFinal,
    category: getCategory(reviewed.calendarRule || {}),
    tags: getTags(reviewed),
    almanacEligible: true,
    humanReviewRequired: true,
    normalizationStatus: "lab_ready",
    source: primaryEvidence?.label || "Ostermann 1876, facsimile verificato",
    editorialReview: {
      it: "approved",
      fur: "approved",
      reviewedAt: reviewed.reviewedAt || selection.reviewedAt,
    },
  };

  applyCalendarRule(record, reviewed.calendarRule || {});
  return record;
});

const existingProverbs = readJson(PROVERBS_PATH);
const calendarResolutions = readJson(CALENDAR_RESOLUTION_PATH);
const calendarRuleNormalization = readJson(CALENDAR_RULE_NORMALIZATION_PATH);
const calendarDemotions = new Map(
  [
    ...calendarResolutions.records,
    ...(calendarRuleNormalization.demotions || []),
  ].map((record) => [record.id, record]),
);
const calendarRulePatches = new Map(
  (calendarRuleNormalization.rules || []).map((record) => [record.id, record.patch]),
);
const promotedById = new Map(promotedRecords.map((record) => [record.id, record]));
const existingIds = new Set(existingProverbs.map((record) => record.id));
const nextProverbs = existingProverbs.map((record) => {
  const promoted = promotedById.get(record.id) || record;
  const patched = calendarRulePatches.has(record.id)
    ? { ...promoted, ...calendarRulePatches.get(record.id) }
    : promoted;
  const demotion = calendarDemotions.get(record.id);

  if (!demotion) return patched;

  return {
    ...patched,
    almanacEligible: false,
    almanacArchiveUse: demotion.decision,
    calendarExclusionReason: demotion.reason,
  };
});
nextProverbs.push(...promotedRecords.filter((record) => !existingIds.has(record.id)));
writeJson(PROVERBS_PATH, nextProverbs);

const schedule = readJson(SCHEDULE_PATH);
const conflicts = [];
promotedRecords.forEach((record) => {
  const dayKey = record.dateAnchors?.[0];
  if (!dayKey) return;

  const current = schedule.dailyProverbs[dayKey];
  if (current && current !== record.id) {
    conflicts.push({ dayKey, kept: current, secondary: record.id });
    return;
  }
  schedule.dailyProverbs[dayKey] = record.id;
});

schedule.dailyProverbs = Object.fromEntries([
  ...Object.entries(schedule.dailyProverbs)
    .filter(([key]) => key !== "default")
    .sort(([first], [second]) => first.localeCompare(second)),
  ["default", schedule.dailyProverbs.default],
]);
writeJson(SCHEDULE_PATH, schedule);

console.log(JSON.stringify({
  promoted: promotedRecords.length,
  proverbTotal: nextProverbs.length,
  almanacEligible: nextProverbs.filter((record) => record.almanacEligible).length,
  scheduledDates: Object.keys(schedule.dailyProverbs).filter((key) => key !== "default").length,
  conflicts,
}, null, 2));
