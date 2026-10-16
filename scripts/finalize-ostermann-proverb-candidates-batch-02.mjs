import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ALMANAC_DIR = path.join(ROOT, "frontend", "src", "data", "almanac");
const AUDIT_DIR = path.join(ROOT, "scripts", "data", "ostermann-proverbs-1876");
const REVIEWED_AT = "2026-07-23";

const readJson = (filePath) => JSON.parse(fs.readFileSync(filePath, "utf8"));
const writeJson = (filePath, value) =>
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");

const candidatesPath = path.join(ALMANAC_DIR, "proverbCandidates.json");
const reviewsPath = path.join(ALMANAC_DIR, "proverbCandidateReview.json");
const proverbsPath = path.join(ALMANAC_DIR, "proverbs.json");
const schedulePath = path.join(ALMANAC_DIR, "schedule.json");

const candidateArchive = readJson(candidatesPath);
const reviewArchive = readJson(reviewsPath);
const proverbs = readJson(proverbsPath);
const schedule = readJson(schedulePath);

const candidatesById = new Map(candidateArchive.records.map((record) => [record.id, record]));

const promotions = [
  {
    id: "ostermann-105-bon-timp-gnot",
    fur: "Bon timp fat di gnot, se al dure un'ore al dure trop.",
    it: "Bel tempo fatto di notte: se dura un'ora, dura troppo.",
    reason:
      "Testo breve, comprensibile e valido tutto l'anno; revisione IT/FUR completata.",
  },
  {
    id: "ostermann-105-aghe-pais",
    fur: "L'aghe e torne ai siei paîs.",
    it: "L'acqua torna ai suoi luoghi.",
    reason:
      "Immagine popolare autonoma e comprensibile senza spiegazione obbligatoria; revisione IT/FUR completata.",
  },
  {
    id: "ostermann-190-marz-avril-mai",
    almanacTargetUse: "almanac_monthly",
    months: ["03", "04", "05"],
    reason:
      "Sequenza esplicitamente riferita a marzo, aprile e maggio; ruota soltanto nei tre mesi citati.",
  },
  {
    id: "ostermann-126-bruntule-tempieste",
    it: "Prima brontola, poi grandina.",
    almanacTargetUse: "almanac_weather_sign",
    weatherTags: ["temporale", "grandine"],
    reason:
      "Segno meteorologico breve, verificato e limitato alla stagione dei temporali.",
  },
  {
    id: "ostermann-126-tempieste-no-charestie",
    fur: "La tempieste no puarte mai cjarestie, ma puar chel che i tocje.",
    almanacTargetUse: "almanac_weather_sign",
    weatherTags: ["grandine", "temporale"],
    reason:
      "Detto verificato sulla grandine, pubblicabile soltanto nel contesto meteorologico pertinente.",
  },
  {
    id: "ostermann-132-prime-nev-plan",
    almanacTargetUse: "almanac_seasonal",
    reason:
      "Detto invernale chiaro e verificato; escluso dalla rotazione delle altre stagioni.",
  },
  {
    id: "ostermann-029-canicule-bagnat-sut",
    it: "La Canicola, se comincia bagnata, finisce bagnata; se comincia asciutta, finisce asciutta.",
    almanacTargetUse: "almanac_date_range",
    dateRanges: [{ from: "07-21", to: "08-23" }],
    reason:
      "Detto legato alla Canicola e quindi vincolato al suo periodo tradizionale.",
  },
  {
    id: "ostermann-062-sis-dis-an-mesais",
    fur: "I sîs ultins dîs dal an e i sîs prins a indichin lis mesais.",
    almanacTargetUse: "almanac_date_range",
    dateRanges: [{ from: "12-26", to: "01-06" }],
    reason:
      "Regola delle mesais pubblicabile soltanto nei dodici giorni tra fine anno ed Epifania.",
  },
  {
    id: "ostermann-063-otubar-febrar",
    almanacTargetUse: "almanac_monthly",
    months: ["10"],
    reason:
      "Detto imperniato su ottobre; ammesso soltanto nel mese citato.",
  },
  {
    id: "ostermann-059-vinars-sant-arsure",
    almanacTargetUse: "almanac_movable_feast",
    movableFeasts: [{ id: "easter", offsetDays: -2 }],
    reason:
      "Detto sul Venerdì Santo, vincolato al venerdì che precede la Pasqua.",
  },
  {
    id: "ostermann-059-vinars-sant-ploe",
    almanacTargetUse: "almanac_movable_feast",
    movableFeasts: [{ id: "easter", offsetDays: -2 }],
    reason:
      "Seconda voce documentata sul Venerdì Santo, mantenuta nella stessa giornata e non nella rotazione generica.",
  },
  {
    id: "ostermann-059-ascense-ploe",
    fur: "Se al plûf il dì de Sense, par cuarante dîs no si sta cence.",
    almanacTargetUse: "almanac_movable_feast",
    movableFeasts: [{ id: "easter", offsetDays: 39 }],
    reason:
      "Detto dell'Ascensione, vincolato alla ricorrenza mobile corretta.",
  },
  {
    id: "ostermann-193-pasche-fen",
    almanacTargetUse: "almanac_movable_feast",
    movableFeasts: [{ id: "easter", offsetDays: 0 }],
    reason:
      "Detto pasquale verificato sul facsimile e limitato al giorno di Pasqua.",
  },
  {
    id: "ostermann-063-sant-egidi-color-mes",
    almanacTargetUse: "almanac_dated",
    reason:
      "Detto esplicitamente datato al primo settembre; revisione IT/FUR completata.",
    scheduleDate: "09-01",
  },
  {
    id: "ostermann-062-san-ruperto-lui",
    fur: "Se San Ruperto nol à nûis, no ju varà nancje il mês di Lui.",
    almanacTargetUse: "almanac_dated",
    reason:
      "Detto esplicitamente datato al 27 marzo; revisione IT/FUR completata.",
    scheduleDate: "03-27",
  },
];

const archiveOnly = new Map([
  [
    "ostermann-103-montane-san-michel",
    "La data di San Michele riportata nel blocco sorgente è incoerente con il calendario corrente: resta materiale d'archivio.",
  ],
  [
    "ostermann-103-cuatri-timporis",
    "Richiede una spiegazione estesa delle Quattro Tempora e non funziona come proverbio quotidiano autonomo.",
  ],
  [
    "ostermann-103-joibe-vinars",
    "Formula legata a una sequenza settimanale poco immediata: utile soltanto in una scheda di approfondimento.",
  ],
  [
    "ostermann-049-lune-sabadine",
    "Detto lunare che richiede contesto e confronto con le varianti: destinato all'archivio tematico.",
  ],
  [
    "ostermann-049-sabadine-camisine",
    "Variante lunare non adatta a una card giornaliera senza spiegazione: destinata all'archivio tematico.",
  ],
  [
    "ostermann-104-ambruset-chapiel",
    "Lessico e riferimento locale richiedono una nota editoriale estesa: non entra nel repertorio quotidiano.",
  ],
  [
    "ostermann-131-sante-catarine-nev",
    "La data indicata dalla fonte non coincide con la ricorrenza adottata dall'app: resta fuori dal calendario giornaliero.",
  ],
  [
    "ostermann-031-macis-zenar",
    "Testo oscuro senza una spiegazione culturale sufficiente: destinato all'archivio, non all'Almanacco.",
  ],
  [
    "ostermann-062-san-macari-setembar",
    "Data e interpretazione non sono abbastanza solide per un aggancio giornaliero.",
  ],
  [
    "ostermann-190-albe-anunziade",
    "Il riferimento cronologico della fonte non coincide con la ricorrenza corrente: resta materiale di studio.",
  ],
  [
    "ostermann-102-quart-dopo-pleniluni",
    "La regola lunare non dispone ancora di una forma FUR e di un'interpretazione abbastanza sicure.",
  ],
  [
    "ostermann-131-nev-decembrine",
    "Il significato meteorologico resta ambiguo e non va presentato come proverbio autonomo.",
  ],
]);

const variantsNotSelected = new Map([
  [
    "ostermann-132-verd-nadal",
    "Variante ridondante del gruppo Natale/Pasqua: non selezionata per evitare duplicazioni.",
  ],
  [
    "ostermann-141-cercli-san-march",
    "Variante ambigua e sovrapposta alla voce di San Marco già calendarizzata.",
  ],
  [
    "ostermann-057-san-lucio-nadal-gial",
    "Variante meno chiara del gruppo Santa Lucia/Natale: non selezionata.",
  ],
]);

const makeSourceDetail = (candidate) => ({
  label: `${candidate.source.label}, p. ${candidate.source.pdfPage}`,
  pdfPage: candidate.source.pdfPage,
  textPage: candidate.source.textPage,
  sourcePath: path.posix.join(
    "documentazione ed installer/ostermann-text",
    candidate.source.sourcePath,
  ),
  verifiedAgainst: path.posix.join(
    "documentazione ed installer/ostermann-text",
    candidate.source.verifiedAgainst,
  ),
});

const promotedIds = new Set(promotions.map((entry) => entry.id));
const existingIds = new Set(proverbs.map((record) => record.id));

for (const promotion of promotions) {
  const candidate = candidatesById.get(promotion.id);
  if (!candidate) {
    throw new Error(`Candidato mancante: ${promotion.id}`);
  }

  const sourceDetail = makeSourceDetail(candidate);
  const record = {
    id: candidate.id,
    fur_original: candidate.furOriginal,
    fur: promotion.fur ?? candidate.fur,
    it: promotion.it ?? candidate.it,
    category: candidate.category,
    tags: candidate.tags,
    almanacEligible: true,
    humanReviewRequired: true,
    normalizationStatus: "lab_ready",
    source: `${sourceDetail.label} / pagina testo ${sourceDetail.textPage}; fonte controllata su pagina clean`,
    sourceDetail,
    editorialReview: {
      it: "approved",
      fur: "approved",
      reviewedAt: REVIEWED_AT,
    },
  };

  for (const key of [
    "almanacTargetUse",
    "months",
    "seasons",
    "weatherTags",
    "dateAnchors",
    "movableFeasts",
    "dateRanges",
  ]) {
    const value = promotion[key] ?? candidate[key];
    if (value?.length || (value && !Array.isArray(value))) {
      record[key] = value;
    }
  }

  const existingIndex = proverbs.findIndex((item) => item.id === record.id);
  if (existingIndex >= 0) {
    proverbs[existingIndex] = record;
  } else {
    proverbs.push(record);
    existingIds.add(record.id);
  }

  if (promotion.scheduleDate) {
    const occupied = schedule.dailyProverbs[promotion.scheduleDate];
    if (occupied && occupied !== promotion.id) {
      throw new Error(
        `Data ${promotion.scheduleDate} già occupata da ${occupied}; impossibile assegnare ${promotion.id}.`,
      );
    }
    schedule.dailyProverbs[promotion.scheduleDate] = promotion.id;
  }
}

for (const review of reviewArchive.records) {
  const promotion = promotions.find((entry) => entry.id === review.id);
  if (promotion) {
    const candidate = candidatesById.get(review.id);
    review.recommendation = "promoted_after_fur_review";
    review.targetUse = promotion.almanacTargetUse ?? "published_proverb";
    review.reviewedAt = REVIEWED_AT;
    review.promotedAt = REVIEWED_AT;
    review.recommendedFur = promotion.fur ?? candidate.fur;
    review.recommendedIt = promotion.it ?? candidate.it;
    review.reason = promotion.reason;
    continue;
  }

  if (archiveOnly.has(review.id)) {
    review.recommendation = "archive_only";
    review.reviewedAt = REVIEWED_AT;
    review.reason = archiveOnly.get(review.id);
    continue;
  }

  if (variantsNotSelected.has(review.id)) {
    review.recommendation = "variant_not_selected";
    review.reviewedAt = REVIEWED_AT;
    review.reason = variantsNotSelected.get(review.id);
  }
}

reviewArchive.reviewedAt = REVIEWED_AT;
reviewArchive.recommendations.promoted_after_fur_review =
  "Candidato revisionato IT/FUR e promosso nel repertorio pubblicato.";
reviewArchive.recommendations.variant_not_selected =
  "Variante chiusa e non selezionata per evitare duplicazioni o ambiguità.";

const sortedSchedule = Object.fromEntries(
  Object.entries(schedule.dailyProverbs)
    .filter(([key]) => key !== "default")
    .sort(([left], [right]) => left.localeCompare(right)),
);
sortedSchedule.default = schedule.dailyProverbs.default;
schedule.dailyProverbs = sortedSchedule;

const remainingProvisional = reviewArchive.records.filter(
  (record) =>
    !promotedIds.has(record.id) &&
    (record.recommendation === "needs_context" || record.recommendation === "hold"),
);
if (remainingProvisional.length) {
  throw new Error(
    `La coda non è chiusa: ${remainingProvisional.map((record) => record.id).join(", ")}`,
  );
}

const audit = {
  schemaVersion: 1,
  batchId: "legacy-candidate-finalization-batch-02",
  reviewedAt: REVIEWED_AT,
  purpose:
    "Chiusura completa dei candidati Ostermann residui: promozione controllata o decisione editoriale finale.",
  counts: {
    promoted: promotions.length,
    archiveOnly: archiveOnly.size,
    variantNotSelected: variantsNotSelected.size,
    provisionalRemaining: remainingProvisional.length,
  },
  promoted: promotions.map((entry) => ({
    id: entry.id,
    almanacTargetUse: entry.almanacTargetUse ?? "almanac_generic",
    ...(entry.scheduleDate ? { scheduleDate: entry.scheduleDate } : {}),
    ...(entry.months ? { months: entry.months } : {}),
    ...(entry.dateRanges ? { dateRanges: entry.dateRanges } : {}),
    ...(entry.movableFeasts ? { movableFeasts: entry.movableFeasts } : {}),
    ...(entry.weatherTags ? { weatherTags: entry.weatherTags } : {}),
  })),
  archiveOnly: [...archiveOnly].map(([id, reason]) => ({ id, reason })),
  variantNotSelected: [...variantsNotSelected].map(([id, reason]) => ({ id, reason })),
  invariants: [
    "Nessun candidato resta in needs_context o hold.",
    "Le ricorrenze mobili usano esclusivamente offset dalla Pasqua.",
    "I testi stagionali o datati non entrano nella rotazione generica.",
    "Le varianti non selezionate restano tracciate nel catalogo sorgente.",
  ],
};

writeJson(proverbsPath, proverbs);
writeJson(reviewsPath, reviewArchive);
writeJson(schedulePath, schedule);
writeJson(
  path.join(AUDIT_DIR, "legacy-candidate-finalization-batch-02.json"),
  audit,
);

console.log(
  JSON.stringify(
    {
      publishedProverbs: proverbs.length,
      promoted: promotions.length,
      archiveOnlyFinalized: archiveOnly.size,
      variantsFinalized: variantsNotSelected.size,
      scheduleDates: Object.keys(schedule.dailyProverbs).filter((key) => key !== "default")
        .length,
      provisionalRemaining: remainingProvisional.length,
    },
    null,
    2,
  ),
);
