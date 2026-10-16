const ALERT_SEVERITY_RANK = {
  yellow: 1,
  orange: 2,
  red: 3,
};

export const OFFICIAL_ALERT_STATES = Object.freeze({
  ACTIVE: "active",
  DIAGNOSTIC: "diagnostic",
  EXPIRED: "expired",
  INACTIVE_CONFIRMED: "inactive_confirmed",
  STALE: "stale",
  UNAVAILABLE: "unavailable",
});

const KNOWN_OFFICIAL_ALERT_STATES = new Set(Object.values(OFFICIAL_ALERT_STATES));

const CONFIRMED_INACTIVE_SOURCE_MODES = new Set([
  "arpa_pcr_mirror",
  "github_actions_arpa_pcr_mirror",
  "github_actions_official_page",
  "github_actions_official_widget",
  "official_page",
  "official_widget",
  "official_validity_expired",
]);

const UNAVAILABLE_SOURCE_MODES = new Set([
  "official_alerts_unavailable_fast_fallback",
]);

const DIAGNOSTIC_SOURCE_MODES = new Set([
  "github_actions_dpc_national_criticity_fallback",
  "github_actions_dpc_national_criticity_no_active_fvg_unverified",
]);

const ALERT_SEVERITY_ALIASES = {
  1: "yellow",
  2: "orange",
  3: "red",
  allerta1: "yellow",
  allerta2: "orange",
  allerta3: "red",
  arancio: "orange",
  arancione: "orange",
  gialla: "yellow",
  giallo: "yellow",
  livello1: "yellow",
  livello2: "orange",
  livello3: "red",
  orange: "orange",
  red: "red",
  rossa: "red",
  rosso: "red",
  yellow: "yellow",
};

const ALERT_PHENOMENON_ALIASES = {
  bora: "wind",
  caldo: "heat",
  cold: "cold",
  freddo: "cold",
  fog: "fog",
  foschia: "fog",
  ghiaccio: "ice",
  grandine: "hail",
  hail: "hail",
  heat: "heat",
  ice: "ice",
  nebbia: "fog",
  neve: "snow",
  pioggia: "rain",
  piogge: "rain",
  rain: "rain",
  rovesci: "rain",
  snow: "snow",
  temporale: "storm",
  temporali: "storm",
  thunderstorm: "storm",
  vento: "wind",
  wind: "wind",
};

function hasDisplayValue(value) {
  return value !== null && value !== undefined && value !== "";
}

function normalizeAlertText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function normalizeStateToken(value) {
  return normalizeAlertText(value).replace(/\s+/g, "_");
}

function normalizeSpaces(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function sentenceCaseOfficialAlert(text) {
  const cleanText = normalizeSpaces(text);
  if (!cleanText) return "";

  return cleanText
    .replace(/^DALLE ORE\b/i, "Dalle ore")
    .replace(/\bORE\b/g, "ore")
    .replace(/\bALLE\b/g, "alle")
    .replace(/\bDEL\b/g, "del")
    .replace(/\bALLERTA\b/g, ": allerta")
    .replace(/\bGIALLA\b/g, "gialla")
    .replace(/\bARANCIONE\b/g, "arancione")
    .replace(/\bROSSA\b/g, "rossa")
    .replace(/\bVERDE\b/g, "verde")
    .replace(/\bIDROGEOLOGICA\b/g, "idrogeologica")
    .replace(/\bIDROGEOLOGICO\b/g, "idrogeologico")
    .replace(/\bIDRAULICA\b/g, "idraulica")
    .replace(/\bIDRAULICO\b/g, "idraulico")
    .replace(/\bMETEOROLOGICA\b/g, "meteorologica")
    .replace(/\bMETEOROLOGICO\b/g, "meteorologico")
    .replace(/\bTEMPORALI\b/g, "temporali")
    .replace(/\bVENTO\b/g, "vento")
    .replace(/\bNEVE\b/g, "neve")
    .replace(/\bVALANGHE\b/g, "valanghe")
    .replace(/\bE\b/g, "e")
    .replace(/\bPER\b/g, "per")
    .replace(/\bSU TUTTO FVG\b/g, "su tutto FVG")
    .replace(/\bSU TUTTA LA REGIONE\b/g, "su tutta la regione")
    .replace(/\bidrogeologica\s+e\s+idrogeologica\s+per\s+temporali\b/gi, "idrogeologica per temporali")
    .replace(/\bidrogeologico\s+e\s+idrogeologico\s+per\s+temporali\b/gi, "idrogeologico per temporali")
    .replace(/\s+:\s+/g, ": ")
    .replace(/^:\s*allerta\b/i, "Allerta")
    .replace(/([^.])$/, "$1.");
}

function formatOfficialAlertParagraph(value) {
  let paragraph = normalizeSpaces(value).replace(/[.\s]+$/, "");
  if (!paragraph) return "";

  paragraph = paragraph.toLocaleLowerCase("it-IT");

  paragraph = paragraph
    .replace(/\bcriticita['’]/gi, "criticità")
    .replace(/\bpiu['’]/gi, "più")
    .replace(/\b(lunedi|martedi|mercoledi|giovedi|venerdi)['’]/gi, (match) => {
      const accents = {
        "lunedi'": "lunedì",
        "martedi'": "martedì",
        "mercoledi'": "mercoledì",
        "giovedi'": "giovedì",
        "venerdi'": "venerdì",
      };
      return accents[match.toLocaleLowerCase("it-IT").replace("’", "'")] || match;
    })
    .replace(/\be['’](?=\s|$)/gi, "è")
    .replace(/\s+allerta\s+(gialla|arancione|rossa)\s+per\b/i, ": allerta $1 per")
    .replace(/\bfvg\b/gi, "FVG")
    .replace(/^./u, (character) => character.toLocaleUpperCase("it-IT"));

  return `${paragraph}.`;
}

function removeOfficialAlertAddresses(value) {
  return normalizeSpaces(value)
    .replace(/\s*(?:Maggiori informazioni su|Documento di allerta):\s*https?:\/\/\S+/gi, "")
    .trim();
}

function splitOfficialAlertSentences(value) {
  return normalizeSpaces(value)
    .split(/\.(?=\s+[A-ZÀ-ÖØ-Þ])/u)
    .map(formatOfficialAlertParagraph)
    .filter(Boolean);
}

export function formatOfficialAlertContent(alert) {
  const officialText = normalizeSpaces(alert?.official_text);
  const fallbackText = formatOfficialAlertText(alert);

  if (!officialText || !/\bALLERTA\s+REGIONALE\b/i.test(officialText)) {
    return { includesValidity: false, paragraphs: fallbackText ? [fallbackText] : [], text: fallbackText };
  }

  const narrative = removeOfficialAlertAddresses(officialText)
    .replace(/^#AllertameteoFVG\s*-\s*/i, "")
    .trim();
  const paragraphs = splitOfficialAlertSentences(narrative);
  const text = paragraphs[0] || "";

  return { includesValidity: true, paragraphs, text };
}

function getAlertCandidateText(alert) {
  const candidates = [
    alert?.shortLabel,
    alert?.label,
    alert?.typeLabel,
    alert?.phenomenon,
    alert?.event,
    alert?.headline,
    alert?.title,
    alert?.description,
    alert?.message,
    alert?.official_text,
    alert?.push_body,
  ];

  return candidates.filter(hasDisplayValue).map(String);
}

export function getOfficialAlertRecords(value) {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.alerts)) return value.alerts;
  return [];
}

function getOfficialAlertsPayload(value) {
  if (Array.isArray(value)) return { active: value.length > 0, alerts: value };
  return value && typeof value === "object" ? value : null;
}

function getOfficialAlertsSourceMode(payload) {
  return normalizeStateToken(payload?.source_mode || payload?.sourceMode || payload?.source?.mode);
}

function getOfficialAlertsCacheStatus(payload) {
  return normalizeStateToken(payload?.cache?.status || payload?.cacheStatus);
}

function getOfficialAlertsCacheReason(payload) {
  return normalizeStateToken(payload?.cache?.reason || payload?.cacheReason);
}

function getOfficialAlertsExplicitState(payload) {
  const state = normalizeStateToken(payload?.state || payload?.alert_state || payload?.alertState);
  return KNOWN_OFFICIAL_ALERT_STATES.has(state) ? state : "";
}

function getOfficialAlertFetchedAt(payload) {
  return payload?.fetched_at || payload?.fetchedAt || payload?.cache?.fetched_at || "";
}

function getOfficialAlertExpiresAt(payload, alerts = []) {
  const explicit = payload?.expires_at || payload?.expiresAt || "";
  if (explicit) return explicit;

  return alerts
    .map((alert) => alert?.valid_to || alert?.validTo || alert?.expires_at || alert?.expiresAt || "")
    .filter(Boolean)
    .sort()
    .at(-1) || "";
}

function getTimestamp(value) {
  if (!value) return null;
  const date = new Date(value);
  const time = date.getTime();
  return Number.isFinite(time) ? time : null;
}

function getNowTimestamp(now) {
  const value = typeof now === "function" ? now() : now;
  if (value === undefined || value === null) return Date.now();
  if (Number.isFinite(Number(value))) return Number(value);
  return getTimestamp(value) ?? Date.now();
}

function isOfficialAlertCurrent(alert, nowTimestamp) {
  const validTo = getTimestamp(
    alert?.valid_to || alert?.validTo || alert?.expires_at || alert?.expiresAt,
  );
  return validTo === null || validTo > nowTimestamp;
}

function getSourceAuthority(sourceMode, state) {
  if (sourceMode.includes("dpc_national")) return "national_dpc";
  if (
    sourceMode.includes("arpa_pcr_mirror") ||
    sourceMode.includes("official_telegram") ||
    sourceMode.includes("official_validity_expired") ||
    sourceMode.includes("official_page") ||
    sourceMode.includes("official_widget") ||
    sourceMode.includes("protezione_civile")
  ) {
    return "regional_fvg";
  }
  if (state === OFFICIAL_ALERT_STATES.UNAVAILABLE) return "backend_fallback";
  return "unknown";
}

function getFreshness(state, fetchedAt) {
  if (state === OFFICIAL_ALERT_STATES.STALE || state === OFFICIAL_ALERT_STATES.EXPIRED) return "stale";
  if (state === OFFICIAL_ALERT_STATES.UNAVAILABLE || state === OFFICIAL_ALERT_STATES.DIAGNOSTIC) return "unknown";
  return fetchedAt ? "fresh" : "unknown";
}

function getConfidence({ sourceAuthority, state }) {
  if (state === OFFICIAL_ALERT_STATES.ACTIVE && sourceAuthority === "regional_fvg") return "high";
  if (state === OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED && sourceAuthority === "regional_fvg") return "high";
  if (state === OFFICIAL_ALERT_STATES.ACTIVE && sourceAuthority === "national_dpc") return "medium";
  if (state === OFFICIAL_ALERT_STATES.ACTIVE) return "medium";
  return "low";
}

export function classifyOfficialAlertState(value, { now } = {}) {
  const payload = getOfficialAlertsPayload(value);
  const alerts = getOfficialAlertRecords(value);
  const nowTimestamp = getNowTimestamp(now);
  const actionableAlerts = alerts.filter(
    (alert) => isActionableOfficialAlert(alert) && isOfficialAlertCurrent(alert, nowTimestamp),
  );
  const sourceMode = getOfficialAlertsSourceMode(payload);
  const cacheStatus = getOfficialAlertsCacheStatus(payload);
  const cacheReason = getOfficialAlertsCacheReason(payload);
  const explicitState = getOfficialAlertsExplicitState(payload);
  const fetchedAt = getOfficialAlertFetchedAt(payload);
  const expiresAt = getOfficialAlertExpiresAt(payload, alerts);
  const error = normalizeStateToken(payload?.error || payload?.cache?.error);
  const warning = normalizeSpaces(payload?.warning || "");
  const expiresAtTime = getTimestamp(expiresAt);
  const isExpired = expiresAtTime !== null && expiresAtTime <= nowTimestamp;
  const activeFlag = payload?.active;
  let state = OFFICIAL_ALERT_STATES.UNAVAILABLE;

  if (!payload) {
    state = OFFICIAL_ALERT_STATES.UNAVAILABLE;
  } else if (isExpired) {
    state = OFFICIAL_ALERT_STATES.EXPIRED;
  } else if (cacheStatus === "stale") {
    state = OFFICIAL_ALERT_STATES.STALE;
  } else if (
    cacheStatus === "unavailable" ||
    UNAVAILABLE_SOURCE_MODES.has(sourceMode) ||
    error === "official_alerts_unavailable"
  ) {
    state = OFFICIAL_ALERT_STATES.UNAVAILABLE;
  } else if (DIAGNOSTIC_SOURCE_MODES.has(sourceMode) || sourceMode.includes("dpc_national")) {
    state = OFFICIAL_ALERT_STATES.DIAGNOSTIC;
  } else if (explicitState) {
    state = explicitState;
  } else if (actionableAlerts.length > 0 && activeFlag !== false) {
    state = OFFICIAL_ALERT_STATES.ACTIVE;
  } else if (activeFlag === false && CONFIRMED_INACTIVE_SOURCE_MODES.has(sourceMode)) {
    state = OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED;
  }

  const sourceAuthority = getSourceAuthority(sourceMode, state);
  const freshness = getFreshness(state, fetchedAt);
  const confidence = getConfidence({ sourceAuthority, state });

  return {
    actionableAlerts,
    active: state === OFFICIAL_ALERT_STATES.ACTIVE,
    alerts,
    cacheReason,
    cacheStatus,
    canClearPreviousAlert: state === OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED,
    canNotify: state === OFFICIAL_ALERT_STATES.ACTIVE,
    canShowBanner: state === OFFICIAL_ALERT_STATES.ACTIVE,
    confidence,
    count: actionableAlerts.length,
    error,
    expiresAt,
    fetchedAt,
    freshness,
    sourceAuthority,
    sourceMode,
    state,
    warning,
  };
}

export function getOfficialAlertSeverityKey(alert) {
  const candidates = [
    alert?.severity,
    alert?.level,
    alert?.color,
    alert?.colour,
    alert?.warningLevel,
    alert?.alertLevel,
    alert?.risk,
    alert?.code,
  ];

  for (const candidate of candidates) {
    if (!hasDisplayValue(candidate)) continue;

    const normalized = normalizeAlertText(candidate).replace(/\s+/g, "");
    const severityKey = ALERT_SEVERITY_ALIASES[normalized];

    if (severityKey) return severityKey;
  }

  for (const text of getAlertCandidateText(alert)) {
    const normalized = normalizeAlertText(text);
    const tokens = normalized.split(" ");
    const severityKey = tokens.map((token) => ALERT_SEVERITY_ALIASES[token]).find(Boolean);

    if (severityKey) return severityKey;
  }

  return "";
}

export function isActionableOfficialAlert(alert) {
  if (!alert || typeof alert !== "object") return false;

  const rawLevel = normalizeAlertText(alert.level || alert.severity || alert.color || alert.warningLevel);
  if (rawLevel === "verde" || rawLevel === "green" || rawLevel === "0") return false;

  return Boolean(
    getOfficialAlertSeverityKey(alert) ||
    getAlertCandidateText(alert).some((text) => normalizeAlertText(text).includes("allerta")) ||
    alert.id,
  );
}

export function getActionableOfficialAlerts(value, { now } = {}) {
  const nowTimestamp = getNowTimestamp(now);
  return getOfficialAlertRecords(value).filter(
    (alert) => isActionableOfficialAlert(alert) && isOfficialAlertCurrent(alert, nowTimestamp),
  );
}

export function getNextOfficialAlertExpiryAt(value, { now } = {}) {
  const payload = getOfficialAlertsPayload(value);
  const nowTimestamp = getNowTimestamp(now);
  const expiryCandidates = getOfficialAlertRecords(value)
    .filter(isActionableOfficialAlert)
    .map((alert) => getTimestamp(
      alert?.valid_to || alert?.validTo || alert?.expires_at || alert?.expiresAt,
    ));
  const payloadExpiry = getTimestamp(payload?.expires_at || payload?.expiresAt);

  if (payloadExpiry !== null) expiryCandidates.push(payloadExpiry);

  const futureExpiries = expiryCandidates.filter((timestamp) => (
    timestamp !== null && timestamp > nowTimestamp
  ));

  return futureExpiries.length > 0 ? Math.min(...futureExpiries) : null;
}

export function getPrimaryOfficialAlert(value, options = {}) {
  return [...getActionableOfficialAlerts(value, options)].sort((left, right) => {
    const severityDelta =
      (ALERT_SEVERITY_RANK[getOfficialAlertSeverityKey(right)] || 0) -
      (ALERT_SEVERITY_RANK[getOfficialAlertSeverityKey(left)] || 0);
    if (severityDelta) return severityDelta;

    const publishedDelta =
      (getTimestamp(right?.published_at || right?.publishedAt) || 0) -
      (getTimestamp(left?.published_at || left?.publishedAt) || 0);
    if (publishedDelta) return publishedDelta;

    const numberDelta =
      (Number(right?.alert_number || right?.alertNumber) || 0) -
      (Number(left?.alert_number || left?.alertNumber) || 0);
    if (numberDelta) return numberDelta;

    return String(left?.id || "").localeCompare(String(right?.id || ""));
  })[0] || null;
}

export function getHighestOfficialAlertSeverityKey(value, options = {}) {
  return getActionableOfficialAlerts(value, options)
    .map(getOfficialAlertSeverityKey)
    .filter(Boolean)
    .sort((left, right) => ALERT_SEVERITY_RANK[right] - ALERT_SEVERITY_RANK[left])[0] || "";
}

export function getOfficialAlertPhenomenonKey(alert) {
  for (const text of getAlertCandidateText(alert)) {
    const normalized = normalizeAlertText(text);
    const tokens = normalized.split(" ");
    const phenomenonKey = tokens.map((token) => ALERT_PHENOMENON_ALIASES[token]).find(Boolean);

    if (phenomenonKey) return phenomenonKey;
  }

  return "";
}

function isConciseAlertLabel(value) {
  const label = String(value || "").trim();

  return label.length > 0 && label.length <= 24 && !label.includes(":");
}

export function getOfficialAlertSpecificLabel(alert, copy = {}) {
  const phenomenonKey = getOfficialAlertPhenomenonKey(alert);

  if (phenomenonKey && copy.officialAlertPhenomenonLabels?.[phenomenonKey]) {
    return copy.officialAlertPhenomenonLabels[phenomenonKey];
  }

  return getAlertCandidateText(alert).find(isConciseAlertLabel) || "";
}

export function buildOfficialAlertSummary(value, copy = {}, options = {}) {
  const alertState = classifyOfficialAlertState(value, options);
  if (alertState.state !== OFFICIAL_ALERT_STATES.ACTIVE) return null;

  const alertItems = alertState.actionableAlerts;
  const alertCount = alertItems.length;

  if (alertCount <= 0) return null;

  const severityKey = getHighestOfficialAlertSeverityKey(alertItems, options);
  const severityLabel = severityKey ? copy.officialAlertSeverityLabels?.[severityKey] : "";
  const label =
    severityLabel ||
    (alertCount === 1
      ? getOfficialAlertSpecificLabel(alertItems[0], copy) || copy.officialAlertSingleLabel || copy.alertsLabel
      : `${alertCount} ${copy.officialAlertMultipleLabel || copy.alertsLabel}`);

  return {
    action: {
      anchor: "official-alerts",
      tab: "bulletin",
      type: "tab-anchor",
    },
    count: alertCount,
    isOfficial: true,
    label,
    level: severityKey || null,
    source: "official-alerts",
    tone: severityKey || "neutral",
  };
}

export function formatOfficialAlertText(alert) {
  const officialText = normalizeSpaces(alert?.official_text);

  if (officialText) {
    return sentenceCaseOfficialAlert(officialText);
  }

  return normalizeSpaces(alert?.push_body || alert?.title);
}
