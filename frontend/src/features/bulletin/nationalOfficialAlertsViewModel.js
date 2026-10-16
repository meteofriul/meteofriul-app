const COPY = {
  it: {
    authority: "Dipartimento della Protezione Civile",
    cautious: "Il Comune ricade in più zone: viene mostrato il livello più cautelativo.",
    complete: "Quadro completo",
    day: "Validità",
    green: "Nessuna criticità segnalata",
    hydraulic: "Rischio idraulico",
    hydrogeological: "Rischio idrogeologico",
    levels: {
      green: "Verde",
      yellow: "Gialla",
      orange: "Arancione",
      red: "Rossa",
    },
    noTransmission: "Dato non trasmesso per una o più componenti",
    partial: "Quadro parziale",
    risks: "Fenomeni",
    sourceLink: "Consulta il bollettino ufficiale",
    thunderstorm: "Temporali",
    title: "Allerte e criticità",
    zones: "Zone di allerta",
  },
  fur: {
    authority: "Dipartiment de Protezion Civîl",
    cautious: "Il Comun al riclâf in plui zonis: al ven mostrât il nivel plui cautelatîf.",
    complete: "Cuadri complet",
    day: "Validitât",
    green: "Nissune criticitât segnalade",
    hydraulic: "Risi idraulic",
    hydrogeological: "Risi idrogjologic",
    levels: {
      green: "Vert",
      yellow: "Zale",
      orange: "Naranç",
      red: "Rosse",
    },
    noTransmission: "Dât no trasmetût par une o plui components",
    partial: "Cuadri parziâl",
    risks: "Fenomens",
    sourceLink: "Consulte il boletin uficiâl",
    thunderstorm: "Temporâi",
    title: "Alertis e criticitâts",
    zones: "Zonis di alerte",
  },
};

const SOURCE_URL = "https://mappe.protezionecivile.gov.it/it/mappe-rischi/bollettino-di-criticita/index.html";
const LEVEL_RANK = { green: 0, yellow: 1, orange: 2, red: 3 };

function formatDate(value, language) {
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) return String(value || "");
  return new Intl.DateTimeFormat(language === "fur" ? "it-IT" : "it-IT", {
    day: "numeric",
    month: "long",
    timeZone: "Europe/Rome",
  }).format(parsed);
}

function maxLevel(records) {
  return records.reduce((highest, record) => (
    (LEVEL_RANK[record?.level] ?? -1) > (LEVEL_RANK[highest] ?? -1)
      ? record.level
      : highest
  ), null);
}

export function buildNationalOfficialAlertsViewModel(payload, { language = "it" } = {}) {
  if (!payload) return null;
  const copy = COPY[language === "fur" ? "fur" : "it"];
  const records = Array.isArray(payload.records) ? payload.records : [];
  const days = [...new Set(records.map(record => record.forecast_day).filter(Boolean))]
    .sort()
    .map((date) => {
      const dayRecords = records.filter(record => record.forecast_day === date);
      const activeRisks = [...new Set(dayRecords
        .filter(record => (LEVEL_RANK[record.level] || 0) > 0)
        .map(record => copy[record.risk] || record.risk))];
      const level = maxLevel(dayRecords) || "green";
      return {
        activeRisks,
        date,
        dateLabel: formatDate(`${date}T12:00:00+02:00`, language),
        level,
        levelLabel: copy.levels[level] || level,
      };
    });
  const zoneNames = [...new Map(records.map(record => [
    record.zone_id,
    String(record.zone_name || record.zone_id || "").trim(),
  ])).values()].filter(Boolean);

  return {
    active: Boolean(payload.active),
    authority: copy.authority,
    cautiousMessage: payload.conservative_multi_zone_display ? copy.cautious : "",
    completenessLabel: payload.complete ? copy.complete : copy.partial,
    days,
    greenLabel: copy.green,
    highestLevel: payload.highest_level || "green",
    municipality: String(payload.municipality?.name || "").trim(),
    noTransmissionMessage: payload.complete ? "" : copy.noTransmission,
    sourceLink: copy.sourceLink,
    sourceUrl: SOURCE_URL,
    title: copy.title,
    zoneNames,
    zonesLabel: copy.zones,
  };
}
