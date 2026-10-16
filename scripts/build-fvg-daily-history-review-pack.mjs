import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_SOURCE = "backend_dryrun_staging/exports/discover_daily_history_master_triage.json";
const DEFAULT_OUTPUT = "frontend/src/data/discover/dailyHistoryReviewPack.json";
const DEFAULT_LOCAL_MEMORY = "frontend/src/data/discover/localMemory.json";
const MASTER_SOURCE_REF = "external/fvg/accadde_oggi_fvg_completo_esteso_metadata.json";
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function toPortablePath(filePath) {
  const relativePath = path.relative(REPO_ROOT, path.resolve(filePath));
  if (relativePath && !relativePath.startsWith("..") && !path.isAbsolute(relativePath)) {
    return relativePath.split(path.sep).join("/");
  }
  return `external/${path.basename(path.resolve(filePath))}`;
}

const ALLOWED_CATEGORIES = new Set([
  "arte_cultura",
  "luoghi_patrimonio",
  "scienza_territorio",
  "tradizione_costume",
]);

const BLOCKED_TEXT = [
  "allenatore",
  "assassinio",
  "battaglia",
  "calciatore",
  "cimitero",
  "disastro",
  "eccidio",
  "ente di decentramento",
  "ente locale",
  "guerra",
  "incidente",
  "militare",
  "nazista",
  "partigiano",
  "partito",
  "patriota",
  "politico",
  "rivolta",
  "societa",
  "strage",
  "terrorista",
  "tragedia",
  "zona d'operazioni",
];

const PRELIMINARY_REVIEW_DECISIONS = {
  Q116645606: {
    status: "archive_after_review",
    reason: "Opera/tema iconografico non abbastanza chiaro dal record sorgente: non e' una memoria giornaliera autonoma.",
  },
  Q24934543: {
    status: "archive_after_review",
    reason: "Premio/riconoscimento interessante, ma non abbastanza forte come Memoria del giorno.",
  },
  Q3792641: {
    status: "archive_after_review",
    reason: "Quotidiano rilevante per Trieste, ma la data non e' abbastanza leggibile per rubrica breve.",
  },
  Q1777: {
    status: "archive_after_review",
    reason: "Figura storica antica legata ad Aquileia, ma richiede fonte/contesto piu' forte.",
  },
  Q46734: {
    status: "archive_after_review",
    reason: "Figura romana legata ad Aquileia, ma richiede contesto storico piu' robusto prima di una card breve.",
  },
  Q216478: {
    status: "copy_candidate",
    reason: "Italo Svevo e' un riferimento culturale chiaro e comprensibile.",
  },
  Q112362: {
    status: "copy_candidate",
    reason: "Alessandro Moissi e' un profilo culturale leggibile e legato a Trieste.",
  },
  Q187199: {
    status: "copy_candidate",
    reason: "Carlo Rubbia e' un profilo scientifico forte e comprensibile.",
  },
  Q1501713: {
    status: "copy_candidate",
    reason: "Giorgio Mainerio consente una memoria culturale breve e territoriale.",
  },
  Q3978261: {
    status: "hold_after_review",
    reason: "Anteprima fonte incoerente: parla di Pier Paolo Pasolini, non di Susanna Pasolini.",
  },
  Q1748033: {
    status: "archive_after_review",
    reason: "Profilo artistico interessante ma non prioritario per Memoria del giorno.",
  },
  Q1525133: {
    status: "copy_candidate",
    reason: "Gino von Finetti e' un profilo artistico adatto a rubrica leggera.",
  },
  Q3932450: {
    status: "copy_candidate",
    reason: "Remo Anzovino e' cultura musicale contemporanea locale, buona per Scopri.",
  },
  Q2857502: {
    status: "copy_candidate",
    reason: "Antonio Zucchelli permette una pillola su viaggio, scrittura e Gradisca.",
  },
  Q597895: {
    status: "copy_candidate",
    reason: "Max Fabiani e' un profilo architettonico forte tra Gorizia e area mitteleuropea.",
  },
  Q3061672: {
    status: "hold_after_review",
    reason: "Data troppo recente/futura nel corpus 2026: da non usare senza controllo dedicato.",
  },
  Q575523: {
    status: "archive_after_review",
    reason: "Profilo dinastico medievale poco immediato per card giornaliera.",
  },
  Q93637502: {
    status: "archive_after_review",
    reason: "Biotopo interessante, ma e' una scheda luogo/ente piu' che una memoria giornaliera.",
  },
  Q16571333: {
    status: "copy_candidate",
    reason: "Laura Sturma Fanelli e' profilo culturale; da rendere umano e non enciclopedico.",
  },
  Q1391772: {
    status: "archive_after_review",
    reason: "Patriarca di Aquileia: utile per archivio, meno per rubrica breve.",
  },
  Q3776550: {
    status: "archive_after_review",
    reason: "Patriarca di Aquileia: utile per archivio, meno per rubrica breve.",
  },
  Q27150629: {
    status: "archive_after_review",
    reason: "Profilo medievale complesso, non prima scelta come memoria rapida.",
  },
  Q4893980: {
    status: "copy_candidate",
    reason: "Teologo e storico legato a Cividale: possibile pillola culturale sobria.",
  },
  Q3898933: {
    status: "archive_after_review",
    reason: "Patriarca di Aquileia: utile per archivio, meno per rubrica breve.",
  },
  Q3772816: {
    status: "archive_after_review",
    reason: "Patriarca di Aquileia: utile per archivio, meno per rubrica breve.",
  },
  Q3506847: {
    status: "archive_after_review",
    reason: "Patriarca di Aquileia: utile per archivio, meno per rubrica breve.",
  },
  Q84296: {
    status: "copy_candidate",
    reason: "Boltzmann a Duino e' una memoria scientifica forte e comprensibile.",
  },
  Q3737610: {
    status: "archive_after_review",
    reason: "Profilo scientifico valido, ma non abbastanza territoriale per la card giornaliera principale.",
  },
};

const COPY_DRAFTS = {
  Q216478: {
    it: {
      title: "Nasce Italo Svevo",
      body: "Il 19 dicembre 1861 nasce a Trieste Aron Hector Schmitz, che con il nome Italo Svevo portera' la citta' dentro la letteratura europea.",
      note: "Bozza breve da review: tenere tono culturale, non enciclopedico.",
    },
    fur: {
      title: "Al nas Italo Svevo",
      body: "Ai 19 di Dicembar dal 1861 al nas a Triest Aron Hector Schmitz, che cul non Italo Svevo al puartarà la citât dentri te leterature europeane.",
      note: "Bozze FUR da review umana: controllare grafia e tono prima di approvare.",
    },
  },
  Q112362: {
    it: {
      title: "Nasce Alessandro Moissi",
      body: "Il 2 aprile 1879 nasce a Trieste Alessandro Moissi, attore cresciuto tra lingue e confini, destinato a diventare una voce importante del teatro europeo.",
      note: "Bozza breve da review: profilo teatrale, senza appesantire con biografia completa.",
    },
    fur: {
      title: "Al nas Alessandro Moissi",
      body: "Ai 2 di Avrîl dal 1879 al nas a Triest Alessandro Moissi, atôr cressût tra lenghis e confins, destinât a deventâ une vôs impuartante dal teatri european.",
      note: "Bozze FUR da review umana: controllare forma di atôr/teatri e resa naturale.",
    },
  },
  Q187199: {
    it: {
      title: "Nasce Carlo Rubbia",
      body: "Il 31 marzo 1934 nasce a Gorizia Carlo Rubbia, fisico che ricevera' il Nobel per la fisica nel 1984.",
      note: "Bozza breve da review: memoria scientifica semplice e riconoscibile.",
    },
    fur: {
      title: "Al nas Carlo Rubbia",
      body: "Ai 31 di Març dal 1934 al nas a Gurize Carlo Rubbia, fisic che al ricevarà il Premi Nobel pe fisiche tal 1984.",
      note: "Bozze FUR da review umana: verificare toponimo Gurize e formula Premi Nobel.",
    },
  },
  Q1501713: {
    it: {
      title: "Giorgio Mainerio e la musica antica",
      body: "Il 4 maggio 1582 muore ad Aquileia Giorgio Mainerio, musicista ricordato anche per la Schiarazula marazula.",
      note: "Bozza breve da review: utile per collegare Aquileia, musica e tradizione.",
    },
    fur: {
      title: "Giorgio Mainerio e la musiche antighe",
      body: "Ai 4 di Mai dal 1582 al mûr a Aquilee Giorgio Mainerio, musicist ricuardât ancje pe Schiarazula marazula.",
      note: "Bozze FUR da review umana: lasciare il titolo del brano invariato.",
    },
  },
  Q1525133: {
    it: {
      title: "Gino de Finetti, artista di confine",
      body: "Il 5 agosto 1955 muore Gino de Finetti, pittore e illustratore formato tra Trieste, Monaco e l'Europa centrale.",
      note: "Bozza breve da review: verificare resa finale del nome prima della pubblicazione.",
    },
    fur: {
      title: "Gino de Finetti, artist di confin",
      body: "Ai 5 di Avost dal 1955 al mûr Gino de Finetti, pitôr e ilustradôr formât tra Triest, Monic e l'Europe centrâl.",
      note: "Bozze FUR da review umana: controllare resa di Monic/Europa centrâl.",
    },
  },
};

function parseArgs(argv) {
  const args = {
    source: DEFAULT_SOURCE,
    output: DEFAULT_OUTPUT,
    localMemory: DEFAULT_LOCAL_MEMORY,
    limit: 30,
    maxPerPlace: 4,
    maxPerCategory: 12,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--source") {
      args.source = argv[index + 1];
      index += 1;
    } else if (arg === "--output") {
      args.output = argv[index + 1];
      index += 1;
    } else if (arg === "--local-memory") {
      args.localMemory = argv[index + 1];
      index += 1;
    } else if (arg === "--limit") {
      args.limit = Number.parseInt(argv[index + 1], 10);
      index += 1;
    } else if (arg === "--max-per-place") {
      args.maxPerPlace = Number.parseInt(argv[index + 1], 10);
      index += 1;
    } else if (arg === "--max-per-category") {
      args.maxPerCategory = Number.parseInt(argv[index + 1], 10);
      index += 1;
    }
  }

  return args;
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(path.resolve(filePath), "utf8").replace(/^\uFEFF/, ""));
}

function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLocaleLowerCase("it-IT");
}

function hasBlockedText(candidate) {
  const haystack = normalizeText([
    candidate.title?.it,
    candidate.sourceTitle,
    candidate.detailPreview,
    candidate.place,
    candidate.category,
  ].join(" "));

  return BLOCKED_TEXT.some((blocked) => haystack.includes(normalizeText(blocked)));
}

function getAllCandidates(source) {
  return (source.days || []).flatMap((day) => (
    (day.candidates || []).map((candidate) => ({
      ...candidate,
      sourceDayKey: candidate.sourceDayKey || day.dayKey,
      dateAnchor: candidate.dateAnchor || day.dateAnchor,
    }))
  ));
}

function recordsFrom(source) {
  if (Array.isArray(source)) return source;
  return Array.isArray(source?.records) ? source.records : [];
}

function collectKnownWikidataIds(...sources) {
  return new Set(sources.flatMap((source) => (
    recordsFrom(source).flatMap((record) => [
      record.wikidataId,
      record.source?.wikidataId,
    ])
  )).filter(Boolean));
}

function isReviewCandidate(candidate) {
  if (candidate.publicationTriage !== "review_for_light_daily") return false;
  if (!ALLOWED_CATEGORIES.has(candidate.category)) return false;
  if (candidate.editorialClass !== "A" && candidate.editorialClass !== "B") return false;
  if (hasBlockedText(candidate)) return false;
  return true;
}

function countBy(records, keyFn) {
  return records.reduce((acc, record) => {
    const key = keyFn(record) || "missing";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function pickBalancedCandidates(candidates, args) {
  const selected = [];
  const byPlace = new Map();
  const byCategory = new Map();
  const usedDays = new Set();

  for (const candidate of candidates) {
    if (selected.length >= args.limit) break;
    if (usedDays.has(candidate.sourceDayKey)) continue;

    const placeCount = byPlace.get(candidate.place) || 0;
    const categoryCount = byCategory.get(candidate.category) || 0;
    if (placeCount >= args.maxPerPlace) continue;
    if (categoryCount >= args.maxPerCategory) continue;

    selected.push(candidate);
    usedDays.add(candidate.sourceDayKey);
    byPlace.set(candidate.place, placeCount + 1);
    byCategory.set(candidate.category, categoryCount + 1);
  }

  return selected;
}

function toReviewRecord(candidate, index) {
  const reviewDecision = PRELIMINARY_REVIEW_DECISIONS[candidate.wikidataId] || {
    status: "review_pending",
    reason: "Da valutare manualmente.",
  };
  const copyDraft = COPY_DRAFTS[candidate.wikidataId] || null;
  const isCopyCandidate = reviewDecision.status === "copy_candidate";

  return {
    id: `daily-history-review-${candidate.dateAnchor}-${index + 1}`,
    sourceCandidateId: candidate.sourceCandidateId,
    wikidataId: candidate.wikidataId,
    sourceDayKey: candidate.sourceDayKey,
    dateAnchor: candidate.dateAnchor,
    title: candidate.title,
    sourceTitle: candidate.sourceTitle,
    year: candidate.year,
    place: candidate.place,
    type: candidate.type,
    category: candidate.category,
    score: candidate.score,
    editorialClass: candidate.editorialClass,
    reviewStatus: reviewDecision.status,
    editorialStatus: isCopyCandidate ? "light_copy_candidate" : "light_candidate_for_review",
    languageStatus: {
      it: "not_started",
      fur: "not_started",
    },
    source: {
      type: "master_triage_candidate",
      label: "Master Accadde oggi FVG esteso",
      path: MASTER_SOURCE_REF,
      wikipediaUrl: candidate.wikipediaUrl || null,
      wikidataId: candidate.wikidataId || null,
      confidence: "candidate_only",
    },
    reviewGuidance: {
      allowedSurface: "light_daily_rubric_after_review",
      copyTone: "breve, umano, prudente",
      doNotPublishAutomatically: true,
      needsHumanSelection: true,
      preliminaryDecision: reviewDecision.status,
      preliminaryReason: reviewDecision.reason,
    },
    copyDraft,
    detailPreview: candidate.detailPreview,
    readyForUi: false,
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const source = readJson(args.source);
  const localMemory = readJson(args.localMemory);
  const knownWikidataIds = collectKnownWikidataIds(localMemory);
  const candidates = getAllCandidates(source)
    .filter(isReviewCandidate)
    .filter((candidate) => !knownWikidataIds.has(candidate.wikidataId))
    .sort((a, b) => b.score - a.score || a.sourceDayKey.localeCompare(b.sourceDayKey, "it-IT"));
  const selected = pickBalancedCandidates(candidates, args);
  const records = selected.map(toReviewRecord);
  const payload = {
    schemaVersion: 1,
    purpose: "Coda piccola di candidati Accadde oggi da review umana. Non letta dalla UI.",
    sourceInput: {
      triageOutput: toPortablePath(args.source),
      masterSource: MASTER_SOURCE_REF,
    },
    policy: {
      noAutomaticPublication: true,
      readyForUiDefault: false,
      oneCandidatePerDay: true,
      balancedByPlace: true,
      excludesSensitiveKeywords: true,
    },
    summary: {
      totalAvailableAfterFilter: candidates.length,
      selectedRecords: records.length,
      byReviewStatus: countBy(records, (record) => record.reviewStatus),
      byEditorialStatus: countBy(records, (record) => record.editorialStatus),
      byCategory: countBy(records, (record) => record.category),
      byPlace: countBy(records, (record) => record.place),
      byType: countBy(records, (record) => record.type),
      recordsWithItDraft: records.filter((record) => Boolean(record.copyDraft?.it)).length,
      recordsWithFurDraft: records.filter((record) => Boolean(record.copyDraft?.fur)).length,
    },
    records,
  };

  const outputPath = path.resolve(args.output);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");

  console.log(`Selected ${records.length} review candidates from ${candidates.length} filtered records.`);
  console.log(`Output: ${outputPath}`);
  console.log(JSON.stringify(payload.summary, null, 2));
}

main();
