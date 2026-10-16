import fs from "node:fs";
import path from "node:path";

const DEFAULT_OUTPUT_DIR = "backend_dryrun_staging/exports";
const HISTORICAL_REVIEW_PATH = "frontend/src/data/discover/dailyHistoryHistoricalEventsReview.json";
const PROFILES_REVIEW_PATH = "frontend/src/data/discover/dailyHistoryProminentProfilesReview.json";
const TOP_LIMIT = 800;
const EXCLUDED_TYPES = new Set(["Morte"]);

const DISCOVER_FILES = [
  "frontend/src/data/discover/localMemory.json",
  "frontend/src/data/discover/dailyHistoryReviewPack.json",
  "frontend/src/data/discover/dailyHistoryExpandedReview.json",
  "frontend/src/data/discover/dailyHistoryLightEditorialBatch.json",
  "frontend/src/data/discover/dailyHistoryCandidates.json",
  "frontend/src/data/discover/dailyHistoryMemoryFinalReview.json",
  "frontend/src/data/discover/dailyHistoryMemoryPromotionReview.json",
  "frontend/src/data/discover/dailyHistoryHistoricalEventsReview.json",
  "frontend/src/data/discover/dailyHistoryProminentProfilesReview.json",
];

const CORE_PLACES = new Set([
  "aquileia",
  "cividale del friuli",
  "gorizia",
  "grado",
  "pordenone",
  "sacile",
  "san daniele del friuli",
  "san vito al tagliamento",
  "spilimbergo",
  "tolmezzo",
  "trieste",
  "udine",
]);

const POSITIVE_RULES = [
  ["vajont", 45, "memoria_storica"],
  ["terremoto", 40, "memoria_storica"],
  ["assedio", 36, "memoria_storica"],
  ["battaglia", 34, "memoria_storica"],
  ["resistenza", 32, "memoria_storica"],
  ["rivolta", 30, "memoria_storica"],
  ["patriarcato", 28, "memoria_storica"],
  ["patriarca", 22, "memoria_storica"],
  ["nobel", 42, "scienza_cultura"],
  ["fisico", 24, "scienza_territorio"],
  ["matematico", 24, "scienza_territorio"],
  ["astronomo", 22, "scienza_territorio"],
  ["scienziato", 22, "scienza_territorio"],
  ["universita", 18, "scienza_territorio"],
  ["sincrotrone", 22, "scienza_territorio"],
  ["scrittore", 28, "arte_cultura"],
  ["poeta", 28, "arte_cultura"],
  ["filosofo", 26, "arte_cultura"],
  ["linguista", 26, "lingua_cultura"],
  ["friulano", 20, "lingua_cultura"],
  ["friulana", 20, "lingua_cultura"],
  ["vocabolario", 30, "lingua_cultura"],
  ["pittore", 24, "arte_cultura"],
  ["scultore", 24, "arte_cultura"],
  ["architetto", 20, "arte_cultura"],
  ["teatro", 18, "arte_cultura"],
  ["compositore", 18, "arte_cultura"],
  ["umanista", 20, "arte_cultura"],
  ["aquileia", 16, "luoghi_patrimonio"],
  ["cividale", 16, "luoghi_patrimonio"],
  ["mosaico", 20, "luoghi_patrimonio"],
  ["basilica", 20, "luoghi_patrimonio"],
  ["archeolog", 20, "luoghi_patrimonio"],
  ["castello", 12, "luoghi_patrimonio"],
];

const HISTORICAL_EVENT_PRIORITY_KEYWORDS = [
  "assedio",
  "battaglia",
  "vajont",
  "terremoto",
  "resistenza",
  "liberazione",
  "rivolta",
  "trattato",
  "occupazione",
  "redipuglia",
  "isonzo",
  "prima guerra",
];

const NOISE_RULES = [
  ["calciatore", -80, "sport_generico"],
  ["allenatore", -70, "sport_generico"],
  ["dirigente sportivo", -70, "sport_generico"],
  ["cestista", -65, "sport_generico"],
  ["pallavolista", -65, "sport_generico"],
  ["sciatore", -45, "sport_generico"],
  ["giornalista televisivo", -55, "media_leggero"],
  ["conduttore televisivo", -55, "media_leggero"],
  ["cantante", -35, "pop_leggero"],
  ["azienda", -65, "ente_o_impresa"],
  ["societa", -60, "ente_o_impresa"],
  ["strada regionale", -70, "infrastruttura_minore"],
  ["comune italiano", -70, "voce_geografica_generica"],
  ["ente di decentramento", -70, "voce_amministrativa"],
  ["denominazione di origine", -55, "voce_tecnica"],
];

const GENERIC_MEDIA_PROFILE_KEYWORDS = [
  "giornalista",
  "opinionista",
  "pubblicista",
  "conduttore televisivo",
  "conduttrice televisiva",
];

const GENERIC_OCCUPATION_PROFILE_KEYWORDS = [
  "docente",
  "imprenditore",
  "imprenditrice",
  "insegnante",
  "professore",
  "professoressa",
];

const DURABLE_PROFILE_KEYWORDS = [
  "accademico dei lincei",
  "archeologo",
  "archeologa",
  "astronomo",
  "astronoma",
  "fisico",
  "fisica",
  "generale",
  "glottologo",
  "glottologa",
  "imperatore",
  "imperatrice",
  "lessicografo",
  "lessicografa",
  "linguista",
  "matematico",
  "matematica",
  "nobel",
  "patriarca",
  "re d'italia",
  "regina",
  "scienziato",
  "scienziata",
  "storico",
  "storica",
  "storiografo",
  "storiografa",
];

const ARTISTIC_PROFILE_KEYWORDS = [
  "architetto",
  "architetta",
  "artista",
  "cantautore",
  "cantautrice",
  "compositore",
  "compositrice",
  "fumettista",
  "filosofo",
  "filosofa",
  "illustratore",
  "illustratrice",
  "organista",
  "pittore",
  "pittrice",
  "poeta",
  "poetessa",
  "regista",
  "sceneggiatore",
  "sceneggiatrice",
  "scultore",
  "scultrice",
  "scrittore",
  "scrittrice",
];

const SUBSTANTIAL_PROFILE_KEYWORDS = [
  "agronomo",
  "agronoma",
  "antropologo",
  "antropologa",
  "botanico",
  "botanica",
  "comandante",
  "critico letterario",
  "critica letteraria",
  "diplomatico",
  "diplomatica",
  "economista",
  "editore",
  "editrice",
  "filologo",
  "filologa",
  "geografo",
  "geografa",
  "giurista",
  "grecista",
  "igienista",
  "informatico",
  "informatica",
  "intellettuale",
  "letterato",
  "letterata",
  "mecenate",
  "naturalista",
  "partigian",
  "patriota",
  "saggista",
  "sociologo",
  "sociologa",
  "teologo",
  "teologa",
  "traduttore",
  "traduttrice",
  "umanista",
  "veterinario",
  "veterinaria",
];

const LOCAL_IDENTITY_KEYWORDS = [
  "dialettale",
  "lingua friulana",
];

const HIGH_DISTINCTION_KEYWORDS = [
  "accademico dei lincei",
  "fondatore",
  "fondatori",
  "grande maestro",
  "mecenate",
  "nobel",
  "padre fondatore",
  "pioniere",
  "premio feltrinelli",
  "senatore del regno",
  "uomo di primo piano",
];

function parseArgs(argv) {
  const args = {
    master: "",
    outputDir: DEFAULT_OUTPUT_DIR,
    topLimit: TOP_LIMIT,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--master") {
      args.master = argv[index + 1];
      index += 1;
    } else if (arg === "--output-dir") {
      args.outputDir = argv[index + 1];
      index += 1;
    } else if (arg === "--top-limit") {
      args.topLimit = Number.parseInt(argv[index + 1], 10);
      index += 1;
    }
  }

  if (!args.master) {
    throw new Error("Missing required --master <daily-history-master.json> argument.");
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

function display(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function getRowsFromDiscoverFile(filePath) {
  if (!fs.existsSync(filePath)) return [];
  const source = readJson(filePath);
  return source.records || source.candidates || source.items || [];
}

function buildKnownIndex() {
  const byId = new Map();
  const byWikidata = new Map();
  const byTitle = new Map();

  const getStatusRank = (status) => {
    if (status === "ready_for_ui") return 3;
    if (status === "ready_for_discover" || status === "ready_it" || status === "source_verified") return 2;
    if (status === "source_candidate") return 1;
    return 0;
  };

  const setKnown = (index, key, knownRecord) => {
    if (!key) return;
    const current = index.get(key);
    if (!current || getStatusRank(knownRecord.status) > getStatusRank(current.status)) {
      index.set(key, knownRecord);
    }
  };

  for (const filePath of DISCOVER_FILES) {
    for (const record of getRowsFromDiscoverFile(filePath)) {
      const sourceFile = path.basename(filePath);
      const title = display(record.title?.it || record.title || record.sourceTitle || record.wikipediaTitle);
      const normalizedTitle = normalizeText(title);
      const status = record.readyForUi
        ? "ready_for_ui"
        : record.editorialStatus || record.recommendation || record.batchDecision || record.status || "queued";
      const knownRecord = { sourceFile, status, title };

      const wikidataId = record.wikidataId || record.source?.wikidataId;
      setKnown(byId, record.id ? String(record.id) : "", knownRecord);
      setKnown(byWikidata, wikidataId ? String(wikidataId).toUpperCase() : "", knownRecord);
      setKnown(byTitle, normalizedTitle, knownRecord);
    }
  }

  return { byId, byWikidata, byTitle };
}

function classifyRecord(record, knownIndex) {
  const title = display(record.wikipediaTitle || record.Descrizione_Base);
  const base = display(record.Descrizione_Base);
  const detail = display(record.rawExtract);
  const text = normalizeText(`${title} ${base} ${detail} ${record.Luogo}`);
  const wikidataId = String(record.wikidataId || "").toUpperCase();
  const known = knownIndex.byWikidata.get(wikidataId) || knownIndex.byTitle.get(normalizeText(title));
  const reasons = [];
  const riskNotes = [];
  let category = "altro";
  let score = 0;

  if (record.Tipo === "Evento") score += 32;
  if (record.Tipo === "Morte") score += 12;
  if (record.Tipo === "Nascita") score += 10;
  reasons.push(`${record.Tipo || "Tipo non definito"} base`);

  const siteLinks = Number.parseInt(String(record.PunteggioSitelinks || "0"), 10);
  if (Number.isFinite(siteLinks)) {
    score += Math.min(26, Math.floor(siteLinks / 4));
    if (siteLinks >= 80) reasons.push("alta visibilita Wikidata");
  }

  if (CORE_PLACES.has(normalizeText(record.Luogo))) {
    score += 16;
    reasons.push("luogo FVG centrale");
  } else if (display(record.Luogo)) {
    score += 5;
  }

  if (detail.length >= 90) score += 8;
  if (detail.length >= 240) score += 4;

  for (const [keyword, bonus, ruleCategory] of POSITIVE_RULES) {
    if (!text.includes(keyword)) continue;
    score += bonus;
    if (category === "altro" || bonus >= 24) category = ruleCategory;
    reasons.push(keyword);
  }

  const hasHistoricalEventPriority = record.Tipo === "Evento"
    && HISTORICAL_EVENT_PRIORITY_KEYWORDS.some((keyword) => text.includes(keyword));
  if (hasHistoricalEventPriority) {
    score += 35;
    category = "memoria_storica";
    reasons.push("evento storico prioritario");
  }

  for (const [keyword, penalty, note] of NOISE_RULES) {
    if (!text.includes(keyword)) continue;
    score += penalty;
    riskNotes.push(note);
  }

  if (record.Tipo === "Nascita") {
    const recordYear = Number.parseInt(String(record.Anno || "0"), 10);
    const firstDetailSentence = detail.split(/[.!?]/u, 1)[0] || "";
    const profileRoleText = normalizeText(base.includes("(") ? base : `${base} ${firstDetailSentence}`);
    const hasGenericMediaSignal = GENERIC_MEDIA_PROFILE_KEYWORDS.some((keyword) => profileRoleText.includes(keyword));
    const hasGenericPoliticalSignal = /(?:^|[^a-z])politic[oa](?:$|[^a-z])/u.test(profileRoleText);
    const hasGenericOccupationSignal = GENERIC_OCCUPATION_PROFILE_KEYWORDS.some((keyword) => profileRoleText.includes(keyword));
    const hasDurableProfileSignal = DURABLE_PROFILE_KEYWORDS.some((keyword) => profileRoleText.includes(keyword));
    const hasArtisticProfileSignal = ARTISTIC_PROFILE_KEYWORDS.some((keyword) => profileRoleText.includes(keyword));
    const hasSubstantialProfileSignal = SUBSTANTIAL_PROFILE_KEYWORDS.some((keyword) => profileRoleText.includes(keyword));
    const hasLocalIdentitySignal = LOCAL_IDENTITY_KEYWORDS.some((keyword) => text.includes(keyword));
    const hasHighDistinctionSignal = HIGH_DISTINCTION_KEYWORDS.some((keyword) => text.includes(keyword));
    const hasEnoughVisibility = Number.isFinite(siteLinks) && siteLinks >= 25;
    const hasEnoughArtisticVisibility = hasArtisticProfileSignal && Number.isFinite(siteLinks) && siteLinks >= 10;
    const hasEnoughDurableVisibility = hasDurableProfileSignal && (
      hasHighDistinctionSignal || (Number.isFinite(siteLinks) && siteLinks >= 5)
    );
    const hasAnotherSubstantialRole = hasDurableProfileSignal
      || hasArtisticProfileSignal
      || hasSubstantialProfileSignal
      || hasLocalIdentitySignal
      || hasHighDistinctionSignal;
    const looksLivingOrContemporary = recordYear >= 1950 && /\be (un|una)\b/u.test(text);

    if ((hasGenericMediaSignal || hasGenericPoliticalSignal || hasGenericOccupationSignal) && !hasAnotherSubstantialRole) {
      score -= 55;
      riskNotes.push(hasGenericPoliticalSignal
        ? "profilo politico generico senza altro ruolo rilevante"
        : hasGenericMediaSignal
          ? "profilo mediatico generico senza altro ruolo rilevante"
          : "professione generica senza rilievo storico-culturale");
    }

    if (looksLivingOrContemporary && !hasHighDistinctionSignal && siteLinks < 60) {
      score -= 35;
      riskNotes.push("profilo contemporaneo o vivente da tenere in hold");
    }

    if (!detail && siteLinks < 10) {
      score -= 30;
      riskNotes.push("profilo senza estratto sufficiente per la review");
    }

    if (
      !hasEnoughDurableVisibility &&
      !hasLocalIdentitySignal &&
      !hasEnoughVisibility &&
      !hasEnoughArtisticVisibility
    ) {
      score -= 35;
      riskNotes.push("profilo sotto soglia di rilievo storico-culturale");
    }
  }

  if (known) {
    score -= known.status === "ready_for_ui" ? 150 : 90;
    riskNotes.push(`gia presente: ${known.sourceFile} / ${known.status}`);
  }

  if (/^0{2,3}/.test(String(record.Anno || ""))) {
    score -= 10;
    riskNotes.push("data antica da verificare");
  }
  const dateControl = record.GiornoMese === "01-01" || record.dayKey === "01-01"
    ? "controllare: possibile data annuale/placeholder"
    : "";

  if (record.Tipo === "Evento" && !/(apertura|assedio|battaglia|fondazione|inaugurazione|istituzione|liberazione|rivolta|terremoto|trattato|vajont)/i.test(text)) {
    score -= 22;
    riskNotes.push("evento senza azione storica chiara");
  }

  const lane = score >= 80
    ? "A_memoria_giorno"
    : score >= 58
      ? "B_review_prioritaria"
      : score >= 38
        ? "C_archivio_scopri"
        : "D_scarto_o_backlog";

  return {
    score,
    category,
    lane,
    editorialPriority: hasHistoricalEventPriority
      ? "1_evento_storico_data_prioritaria"
      : record.Tipo === "Evento"
        ? "2_evento_da_valutare"
        : category === "lingua_cultura" || category === "arte_cultura" || category === "scienza_territorio" || category === "scienza_cultura"
          ? "3_profilo_culturale_scientifico"
          : "4_altro",
    reasons: [...new Set(reasons)].slice(0, 8).join(", "),
    riskNotes: [...new Set(riskNotes)].join(", "),
    dateControl,
    known,
  };
}

function toCsvCell(value) {
  const raw = String(value ?? "");
  return `"${raw.replace(/"/g, '""')}"`;
}

function escapeXml(value) {
  return String(value ?? "")
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function getColumnName(index) {
  let value = index + 1;
  let name = "";
  while (value > 0) {
    const modulo = (value - 1) % 26;
    name = String.fromCharCode(65 + modulo) + name;
    value = Math.floor((value - modulo) / 26);
  }
  return name;
}

function buildCrc32Table() {
  return Array.from({ length: 256 }, (_, index) => {
    let crc = index;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = crc & 1 ? 0xedb88320 ^ (crc >>> 1) : crc >>> 1;
    }
    return crc >>> 0;
  });
}

const CRC32_TABLE = buildCrc32Table();

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc = CRC32_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function getDosDateTime(date = new Date()) {
  const year = Math.max(1980, date.getFullYear());
  const dosTime = (date.getHours() << 11) | (date.getMinutes() << 5) | Math.floor(date.getSeconds() / 2);
  const dosDate = ((year - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate();
  return { dosDate, dosTime };
}

function createZip(files) {
  const chunks = [];
  const centralDirectory = [];
  let offset = 0;
  const { dosDate, dosTime } = getDosDateTime();

  for (const file of files) {
    const nameBuffer = Buffer.from(file.name, "utf8");
    const dataBuffer = Buffer.from(file.content, "utf8");
    const checksum = crc32(dataBuffer);

    const localHeader = Buffer.alloc(30);
    localHeader.writeUInt32LE(0x04034b50, 0);
    localHeader.writeUInt16LE(20, 4);
    localHeader.writeUInt16LE(0, 6);
    localHeader.writeUInt16LE(0, 8);
    localHeader.writeUInt16LE(dosTime, 10);
    localHeader.writeUInt16LE(dosDate, 12);
    localHeader.writeUInt32LE(checksum, 14);
    localHeader.writeUInt32LE(dataBuffer.length, 18);
    localHeader.writeUInt32LE(dataBuffer.length, 22);
    localHeader.writeUInt16LE(nameBuffer.length, 26);
    localHeader.writeUInt16LE(0, 28);

    chunks.push(localHeader, nameBuffer, dataBuffer);

    const centralHeader = Buffer.alloc(46);
    centralHeader.writeUInt32LE(0x02014b50, 0);
    centralHeader.writeUInt16LE(20, 4);
    centralHeader.writeUInt16LE(20, 6);
    centralHeader.writeUInt16LE(0, 8);
    centralHeader.writeUInt16LE(0, 10);
    centralHeader.writeUInt16LE(dosTime, 12);
    centralHeader.writeUInt16LE(dosDate, 14);
    centralHeader.writeUInt32LE(checksum, 16);
    centralHeader.writeUInt32LE(dataBuffer.length, 20);
    centralHeader.writeUInt32LE(dataBuffer.length, 24);
    centralHeader.writeUInt16LE(nameBuffer.length, 28);
    centralHeader.writeUInt16LE(0, 30);
    centralHeader.writeUInt16LE(0, 32);
    centralHeader.writeUInt16LE(0, 34);
    centralHeader.writeUInt16LE(0, 36);
    centralHeader.writeUInt32LE(0, 38);
    centralHeader.writeUInt32LE(offset, 42);
    centralDirectory.push(centralHeader, nameBuffer);

    offset += localHeader.length + nameBuffer.length + dataBuffer.length;
  }

  const centralDirectoryBuffer = Buffer.concat(centralDirectory);
  const endRecord = Buffer.alloc(22);
  endRecord.writeUInt32LE(0x06054b50, 0);
  endRecord.writeUInt16LE(0, 4);
  endRecord.writeUInt16LE(0, 6);
  endRecord.writeUInt16LE(files.length, 8);
  endRecord.writeUInt16LE(files.length, 10);
  endRecord.writeUInt32LE(centralDirectoryBuffer.length, 12);
  endRecord.writeUInt32LE(offset, 16);
  endRecord.writeUInt16LE(0, 20);

  return Buffer.concat([...chunks, centralDirectoryBuffer, endRecord]);
}

function buildSheetXml(headers, rows) {
  const columnCount = headers.length;
  const rowCount = rows.length + 1;
  const lastColumn = getColumnName(columnCount - 1);
  const dimension = `A1:${lastColumn}${rowCount}`;
  const columnWidths = headers
    .map((header, index) => {
      const width = ["estratto_wikipedia", "descrizione_base", "motivi_score", "rischi_controlli"].includes(header)
        ? 42
        : ["decisione_umana", "note_utente", "titolo"].includes(header)
          ? 24
          : 16;
      return `<col min="${index + 1}" max="${index + 1}" width="${width}" customWidth="1"/>`;
    })
    .join("");

  const buildCell = (value, rowIndex, columnIndex, style = 0) => {
    const ref = `${getColumnName(columnIndex)}${rowIndex}`;
    const styleAttr = style ? ` s="${style}"` : "";
    return `<c r="${ref}" t="inlineStr"${styleAttr}><is><t>${escapeXml(value)}</t></is></c>`;
  };

  const headerRow = `<row r="1">${headers.map((header, index) => buildCell(header, 1, index, 1)).join("")}</row>`;
  const dataRows = rows
    .map((row, rowIndex) => {
      const excelRowIndex = rowIndex + 2;
      return `<row r="${excelRowIndex}">${headers.map((header, columnIndex) => buildCell(row[header], excelRowIndex, columnIndex)).join("")}</row>`;
    })
    .join("");

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="${dimension}"/>
  <sheetViews>
    <sheetView workbookViewId="0">
      <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
    </sheetView>
  </sheetViews>
  <cols>${columnWidths}</cols>
  <sheetData>${headerRow}${dataRows}</sheetData>
  <autoFilter ref="${dimension}"/>
</worksheet>`;
}

function writeXlsx(filePath, rows, sheetName, headers = REVIEW_HEADERS) {
  const files = [
    {
      name: "[Content_Types].xml",
      content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>`,
    },
    {
      name: "_rels/.rels",
      content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`,
    },
    {
      name: "xl/workbook.xml",
      content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="${escapeXml(sheetName)}" sheetId="1" r:id="rId1"/></sheets>
</workbook>`,
    },
    {
      name: "xl/_rels/workbook.xml.rels",
      content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`,
    },
    {
      name: "xl/styles.xml",
      content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/></cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>`,
    },
    {
      name: "xl/worksheets/sheet1.xml",
      content: buildSheetXml(headers, rows),
    },
  ];

  fs.writeFileSync(filePath, createZip(files));
}

const REVIEW_HEADERS = [
  "decisione_umana",
  "priorita_umana",
  "note_utente",
  "lane",
  "score",
  "punteggio_sitelinks",
  "categoria",
  "priorita_editoriale",
  "data",
  "controllo_data",
  "anno",
  "tipo",
  "luogo",
  "titolo",
  "descrizione_base",
  "estratto_wikipedia",
  "motivi_score",
  "rischi_controlli",
  "gia_in_scopri",
  "wikidata_id",
  "wikipedia_url",
  "fur_status",
];

const ITALIAN_SELECTION_HEADERS = [
  "decisione_umana",
  "priorita_umana",
  "note_utente",
  "proposta_audit",
  "motivo_audit",
  "record_id",
  "tipo_contenuto",
  "stato",
  "destinazione",
  "rango",
  "data_gg_mm",
  "anno",
  "luogo",
  "comune",
  "localita",
  "provincia",
  "livello_territoriale",
  "titolo",
  "copy_it",
  "fonte",
  "url",
  "wikidata_id",
  "tipo_fonte",
  "confidenza_fonte",
  "gia_nel_runtime",
  "it_canonico",
  "pubblicato",
  "stato_fur",
  "note_revisione",
];

function writeCsv(filePath, rows, headers = REVIEW_HEADERS) {

  const lines = [
    `\uFEFF${headers.join(";")}`,
    ...rows.map((row) => headers.map((header) => toCsvCell(row[header])).join(";")),
  ];

  fs.writeFileSync(filePath, `${lines.join("\n")}\n`, "utf8");
}

function isCleanReviewCandidate(row) {
  return ["A_memoria_giorno", "B_review_prioritaria"].includes(row.lane)
    && !row.controllo_data
    && !row.gia_in_scopri
    && !String(row.rischi_controlli || "").includes("profilo politico generico senza altro ruolo rilevante")
    && !String(row.rischi_controlli || "").includes("profilo mediatico generico senza altro ruolo rilevante")
    && !String(row.rischi_controlli || "").includes("professione generica senza rilievo storico-culturale")
    && !String(row.rischi_controlli || "").includes("profilo sotto soglia di rilievo storico-culturale")
    && !String(row.rischi_controlli || "").includes("profilo contemporaneo o vivente da tenere in hold")
    && !String(row.rischi_controlli || "").includes("profilo senza estratto sufficiente per la review");
}

function validateCleanReviewRows(rows) {
  const deathRows = rows.filter((row) => row.tipo === "Morte");
  const knownRows = rows.filter((row) => row.gia_in_scopri);
  const prematureFurRows = rows.filter(
    (row) => row.fur_status !== "non_avviato_attesa_selezione_it",
  );

  if (deathRows.length || knownRows.length || prematureFurRows.length) {
    throw new Error(JSON.stringify({
      message: "La coda pulita viola il contratto editoriale Scopri.",
      deathRows: deathRows.map((row) => row.wikidata_id || row.titolo),
      knownRows: knownRows.map((row) => row.wikidata_id || row.titolo),
      prematureFurRows: prematureFurRows.map((row) => row.wikidata_id || row.titolo),
    }));
  }
}

const ITALIAN_SELECTION_AUDIT = new Map([
  ["profile-copy-0404-giani-stuparich", ["KEEP_DAILY", "Letteratura e memoria triestina."]],
  ["history-event-0806-battaglia-doberdo", ["REUSE_EXISTING", "Collegare alla Sesta battaglia dell'Isonzo e normalizzare data e titolo."]],
  ["profile-copy-0910-leonardo-zanier", ["KEEP_DAILY", "Poesia, emigrazione e lavoro con forte legame carnico."]],
  ["history-event-1210-assedio-trieste-1813", ["REUSE_EXISTING", "Stesso fatto e Wikidata ID gia presenti nelle code canoniche."]],
  ["profile-copy-1014-giuseppe-levi", ["KEEP_ARCHIVE", "Scuola scientifica di primo piano, ma legame territoriale soprattutto anagrafico."]],
  ["profile-copy-0115-virgilio-giotti", ["KEEP_DAILY", "Poesia e identita triestina."]],
  ["profile-review-0317-bruno-pincherle", ["KEEP_DAILY", "Medicina, antifascismo e storia civile."]],
  ["profile-upgrade-1122-jacopo-pirona", ["REUSE_EXISTING", "Lessicografia e cultura friulana; aggiornare il record runtime esistente."]],
  ["profile-copy-0125-ivan-trinko", ["KEEP_DAILY", "Lingua e cultura delle Valli del Natisone."]],
  ["profile-copy-0928-mirko-basaldella", ["KEEP_DAILY", "Arte friulana del Novecento."]],
  ["profile-review-0329-tarcisio-petracco", ["KEEP_DAILY", "Resistenza e nascita dell'Universita di Udine."]],
  ["profile-review-1130-richard-mollier", ["KEEP_ARCHIVE", "Contributo internazionale alla termodinamica, piu adatto a un approfondimento."]],
  ["profile-copy-0608-luciano-petech", ["KEEP_ARCHIVE", "Profilo storico specialistico, piu adatto all'archivio."]],
  ["profile-review-0813-fabio-conforto", ["KEEP_ARCHIVE", "Profilo scientifico solido con legame territoriale limitato."]],
  ["profile-copy-0516-paolo-bozzi", ["KEEP_ARCHIVE", "Psicologia della percezione, adatta a un approfondimento."]],
  ["profile-archive-review-0817-theodor-daubler", ["KEEP_ARCHIVE", "Avanguardie letterarie e cultura di confine."]],
  ["profile-archive-review-0920-marij-kogoj", ["KEEP_ARCHIVE", "Musica slovena del Novecento e cultura di confine."]],
  ["profile-review-0414-luigi-carnera", ["KEEP_ARCHIVE", "Profilo scientifico prevalentemente biografico."]],
  ["profile-review-0726-giulio-krall", ["KEEP_ARCHIVE", "Profilo scientifico specialistico."]],
  ["profile-review-1230-sergio-doplicher", ["KEEP_ARCHIVE", "Profilo scientifico forte ma poco territoriale."]],
  ["profile-review-0731-antonio-mario-radmilli", ["KEEP_ARCHIVE", "Archeologia di rilievo nazionale con legame locale limitato."]],
  ["profile-copy-1031-andrej-budal", ["KEEP_ARCHIVE", "Scrittura, traduzione e cultura slovena di confine."]],
  ["profile-archive-review-0709-spiridon-gopcevic", ["HOLD", "Fonti discordanti: serve una scheda contestualizzata."]],
  ["history-event-0515-battaglia-tarvisio-1809", ["HOLD", "Data e titolo non coincidono: verificare 15 rispetto a 16-17 maggio."]],
]);

const EDITORIAL_LOCATION_OVERRIDES = new Map([
  ["history-event-0806-battaglia-doberdo", { comune: "Doberd\u00f2 del Lago", localita: "", provincia: "GO", livello: "comune" }],
  ["profile-copy-0910-leonardo-zanier", { comune: "Comeglians", localita: "Maranzanis", provincia: "UD", livello: "frazione" }],
  ["profile-copy-0125-ivan-trinko", { comune: "Savogna", localita: "Tercimonte", provincia: "UD", livello: "frazione" }],
  ["profile-copy-1031-andrej-budal", { comune: "Gorizia", localita: "Sant'Andrea", provincia: "GO", livello: "quartiere" }],
]);

const PROVINCE_BY_PLACE = new Map([
  ["dignano", "UD"],
  ["gorizia", "GO"],
  ["san giorgio della richinvelda", "PN"],
  ["tarvisio", "UD"],
  ["trieste", "TS"],
  ["udine", "UD"],
]);

function getEditorialLocation(record) {
  const override = EDITORIAL_LOCATION_OVERRIDES.get(record.id);
  if (override) return override;

  return {
    comune: record.place || "",
    localita: "",
    provincia: record.provinceCode || PROVINCE_BY_PLACE.get(normalizeText(record.place)) || "",
    livello: "comune",
  };
}

function getKnownSelectionRecord(record, knownIndex) {
  return knownIndex.byId.get(String(record.existingRecordId || ""))
    || knownIndex.byWikidata.get(String(record.wikidataId || "").toUpperCase())
    || knownIndex.byId.get(String(record.id))
    || knownIndex.byTitle.get(normalizeText(record.title));
}

function buildItalianSelectionRows(knownIndex) {
  const allowedDecisions = new Set([
    "copy_candidate",
    "it_archive_review_candidate",
    "it_review_candidate",
    "upgrade_existing_local_memory",
  ]);
  const sources = [
    { kind: "evento_storico", source: readJson(HISTORICAL_REVIEW_PATH) },
    { kind: "profilo", source: readJson(PROFILES_REVIEW_PATH) },
  ];

  return sources
    .flatMap(({ kind, source }) => (source.records || []).map((record) => ({ kind, record })))
    .filter(({ record }) => allowedDecisions.has(record.batchDecision) && record.copyDraft?.it)
    .map(({ kind, record }) => {
      const known = getKnownSelectionRecord(record, knownIndex);
      const location = getEditorialLocation(record);
      const [auditProposal = "DA_VALUTARE", auditReason = ""] = ITALIAN_SELECTION_AUDIT.get(record.id) || [];

      return {
        decisione_umana: "",
        priorita_umana: "",
        note_utente: "",
        proposta_audit: auditProposal,
        motivo_audit: auditReason,
        record_id: record.id,
        tipo_contenuto: kind,
        stato: record.batchDecision,
        destinazione: record.surface,
        rango: record.rank,
        data_gg_mm: record.dateIt,
        anno: record.year,
        luogo: record.place,
        comune: location.comune,
        localita: location.localita,
        provincia: location.provincia,
        livello_territoriale: location.livello,
        titolo: record.title,
        copy_it: record.copyDraft.it,
        fonte: record.source?.label || "",
        url: record.source?.url || "",
        wikidata_id: record.wikidataId || "",
        tipo_fonte: record.source?.type || "",
        confidenza_fonte: record.source?.confidence || "",
        gia_nel_runtime: known ? `${known.sourceFile} / ${known.status}` : "",
        it_canonico: known?.status === "source_verified" ? "SI" : "NO",
        pubblicato: known?.status === "ready_for_ui" || record.readyForUi === true ? "SI" : "NO",
        stato_fur: record.languageStatus?.fur || record.copyDraft?.fur || "not_started",
        note_revisione: record.reviewNotes || record.reason || "",
      };
    })
    .filter((row) => row.pubblicato !== "SI" && row.it_canonico !== "SI")
    .sort((left, right) => (
      String(left.destinazione).localeCompare(String(right.destinazione), "it")
      || String(left.data_gg_mm).localeCompare(String(right.data_gg_mm), "it")
      || String(left.titolo).localeCompare(String(right.titolo), "it")
    ));
}

function getExclusionReason(row) {
  const reasons = [];
  if (row.gia_in_scopri) reasons.push("gia presente o gia in coda Scopri");
  if (row.controllo_data) reasons.push(row.controllo_data);
  if (row.lane === "C_archivio_scopri") reasons.push("non abbastanza forte per Memoria del giorno, tenere per Archivio Scopri");
  if (row.lane === "D_scarto_o_backlog") reasons.push("score basso o rumore, tenere fuori dalla review principale");
  if (row.categoria === "altro") reasons.push("categoria non chiara");
  if (String(row.rischi_controlli || "").includes("evento senza azione storica chiara")) {
    reasons.push("evento senza fatto storico abbastanza preciso");
  }
  if (String(row.rischi_controlli || "").includes("profilo politico generico senza altro ruolo rilevante")) {
    reasons.push("profilo esclusivamente politico, senza altro contributo rilevante per Scopri");
  }
  if (String(row.rischi_controlli || "").includes("profilo mediatico generico senza altro ruolo rilevante")) {
    reasons.push("profilo esclusivamente mediatico, senza altro contributo rilevante per Scopri");
  }
  if (String(row.rischi_controlli || "").includes("professione generica senza rilievo storico-culturale")) {
    reasons.push("qualifica professionale generica, senza un contributo storico-culturale rilevante per Scopri");
  }
  if (String(row.rischi_controlli || "").includes("profilo sotto soglia di rilievo storico-culturale")) {
    reasons.push("profilo sotto la soglia storico-culturale concordata");
  }
  if (String(row.rischi_controlli || "").includes("profilo contemporaneo o vivente da tenere in hold")) {
    reasons.push("profilo contemporaneo o vivente: non entra nella rubrica storica senza decisione esplicita");
  }
  if (String(row.rischi_controlli || "").includes("profilo senza estratto sufficiente per la review")) {
    reasons.push("contenuto sorgente insufficiente per una review editoriale affidabile");
  }
  return [...new Set(reasons)].join("; ");
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const master = readJson(args.master);
  const knownIndex = buildKnownIndex();
  const includedMaster = master.filter((record) => !EXCLUDED_TYPES.has(record.Tipo));
  const excludedByType = master.length - includedMaster.length;

  const rows = includedMaster
    .map((record) => {
      const classification = classifyRecord(record, knownIndex);
      const known = classification.known;

      return {
        decisione_umana: "",
        priorita_umana: "",
        note_utente: "",
        lane: classification.lane,
        score: classification.score,
        punteggio_sitelinks: record.PunteggioSitelinks || "0",
        categoria: classification.category,
        priorita_editoriale: classification.editorialPriority,
        data: record.dayKey || record.GiornoMese,
        controllo_data: classification.dateControl,
        anno: record.Anno,
        tipo: record.Tipo,
        luogo: record.Luogo,
        titolo: display(record.wikipediaTitle || record.Descrizione_Base),
        descrizione_base: display(record.Descrizione_Base),
        estratto_wikipedia: display(record.rawExtract),
        motivi_score: classification.reasons,
        rischi_controlli: classification.riskNotes,
        gia_in_scopri: known ? `${known.sourceFile} / ${known.status}` : "",
        wikidata_id: record.wikidataId,
        wikipedia_url: record.wikipediaUrl,
        fur_status: "non_avviato_attesa_selezione_it",
      };
    })
    .sort((left, right) => {
      const priorityCompare = String(left.priorita_editoriale).localeCompare(String(right.priorita_editoriale));
      return priorityCompare || right.score - left.score;
    });

  const outputDir = path.resolve(args.outputDir);
  fs.mkdirSync(outputDir, { recursive: true });

  const shortlist = rows.filter((row) => !row.gia_in_scopri && row.lane !== "D_scarto_o_backlog").slice(0, args.topLimit);
  const cleanReview = rows.filter(isCleanReviewCandidate);
  validateCleanReviewRows(cleanReview);
  const italianSelection = buildItalianSelectionRows(knownIndex);
  const invalidItalianSelection = italianSelection.filter((row) => (
    row.pubblicato !== "NO"
    || !["not_started", "deferred_until_it_selection"].includes(row.stato_fur)
    || !row.provincia
    || row.proposta_audit === "DA_VALUTARE"
  ));
  if (invalidItalianSelection.length) {
    throw new Error(JSON.stringify({
      message: "La selezione IT contiene record pubblicati, FUR anticipato o metadati di audit incompleti.",
      recordIds: invalidItalianSelection.map((row) => row.record_id),
    }));
  }
  const historicalEvents = cleanReview.filter((row) => row.priorita_editoriale === "1_evento_storico_data_prioritaria");
  const excludedReview = rows
    .filter((row) => !isCleanReviewCandidate(row))
    .map((row) => ({
      ...row,
      note_utente: getExclusionReason(row),
    }));
  const fullPath = path.join(outputDir, "scopri_accadde_oggi_master_scrematura_full.csv");
  const shortlistPath = path.join(outputDir, "scopri_accadde_oggi_master_scrematura_top.csv");
  const cleanPath = path.join(outputDir, "scopri_accadde_oggi_candidati_puliti.csv");
  const historicalEventsPath = path.join(outputDir, "scopri_accadde_oggi_eventi_storici_prioritari.csv");
  const excludedPath = path.join(outputDir, "scopri_accadde_oggi_esclusi_motivati.csv");
  const fullXlsxPath = path.join(outputDir, "scopri_accadde_oggi_master_scrematura_full.xlsx");
  const shortlistXlsxPath = path.join(outputDir, "scopri_accadde_oggi_master_scrematura_top.xlsx");
  const cleanXlsxPath = path.join(outputDir, "scopri_accadde_oggi_candidati_puliti.xlsx");
  const historicalEventsXlsxPath = path.join(outputDir, "scopri_accadde_oggi_eventi_storici_prioritari.xlsx");
  const excludedXlsxPath = path.join(outputDir, "scopri_accadde_oggi_esclusi_motivati.xlsx");
  const jsonPath = path.join(outputDir, "scopri_accadde_oggi_master_scrematura_top.json");
  const cleanJsonPath = path.join(outputDir, "scopri_accadde_oggi_candidati_puliti.json");
  const italianSelectionCsvPath = path.join(outputDir, "scopri_selezione_it_da_confermare.csv");
  const italianSelectionXlsxPath = path.join(outputDir, "scopri_selezione_it_da_confermare.xlsx");
  const italianSelectionJsonPath = path.join(outputDir, "scopri_selezione_it_da_confermare.json");

  writeCsv(fullPath, rows);
  writeCsv(shortlistPath, shortlist);
  writeCsv(cleanPath, cleanReview);
  writeCsv(historicalEventsPath, historicalEvents);
  writeCsv(excludedPath, excludedReview);
  writeXlsx(fullXlsxPath, rows, "Scopri full");
  writeXlsx(shortlistXlsxPath, shortlist, "Scopri top");
  writeXlsx(cleanXlsxPath, cleanReview, "Candidati puliti");
  writeXlsx(historicalEventsXlsxPath, historicalEvents, "Eventi storici");
  writeXlsx(excludedXlsxPath, excludedReview, "Esclusi motivati");
  writeCsv(italianSelectionCsvPath, italianSelection, ITALIAN_SELECTION_HEADERS);
  writeXlsx(italianSelectionXlsxPath, italianSelection, "Selezione IT", ITALIAN_SELECTION_HEADERS);
  fs.writeFileSync(jsonPath, `${JSON.stringify({ generatedAt: new Date().toISOString(), total: rows.length, shortlist: shortlist.length, rows: shortlist }, null, 2)}\n`);
  fs.writeFileSync(cleanJsonPath, `${JSON.stringify({ generatedAt: new Date().toISOString(), total: rows.length, cleanReview: cleanReview.length, rows: cleanReview }, null, 2)}\n`);
  fs.writeFileSync(italianSelectionJsonPath, `${JSON.stringify({
    generatedAt: new Date().toISOString(),
    selection: italianSelection.length,
    furStarted: 0,
    rows: italianSelection,
  }, null, 2)}\n`);

  console.log(JSON.stringify({
    source: path.basename(args.master),
    sourceTotal: master.length,
    excludedByType,
    total: rows.length,
    shortlist: shortlist.length,
    cleanReview: cleanReview.length,
    historicalEvents: historicalEvents.length,
    italianSelectionToConfirm: italianSelection.length,
    excludedGenericPoliticalProfiles: rows.filter((row) => (
      String(row.rischi_controlli || "").includes("profilo politico generico senza altro ruolo rilevante")
    )).length,
    excludedGenericMediaProfiles: rows.filter((row) => (
      String(row.rischi_controlli || "").includes("profilo mediatico generico senza altro ruolo rilevante")
    )).length,
    excludedGenericOccupationProfiles: rows.filter((row) => (
      String(row.rischi_controlli || "").includes("professione generica senza rilievo storico-culturale")
    )).length,
    furWorkStartedInCleanReview: cleanReview.filter(
      (row) => row.fur_status !== "non_avviato_attesa_selezione_it",
    ).length,
    excludedReview: excludedReview.length,
    output: {
      fullCsv: fullPath,
      shortlistCsv: shortlistPath,
      cleanCsv: cleanPath,
      historicalEventsCsv: historicalEventsPath,
      excludedCsv: excludedPath,
      fullXlsx: fullXlsxPath,
      shortlistXlsx: shortlistXlsxPath,
      cleanXlsx: cleanXlsxPath,
      historicalEventsXlsx: historicalEventsXlsxPath,
      excludedXlsx: excludedXlsxPath,
      shortlistJson: jsonPath,
      cleanJson: cleanJsonPath,
      italianSelectionCsv: italianSelectionCsvPath,
      italianSelectionXlsx: italianSelectionXlsxPath,
      italianSelectionJson: italianSelectionJsonPath,
    },
  }, null, 2));
}

main();
