import { getLocationMunicipality } from "../../domain/geo/locationIdentity";
import { isUsableNationalOfficialAlerts } from "../bulletin/nationalOfficialAlertsDataController";

const RANK = { yellow: 1, orange: 2, red: 3 };
const RISK_COPY = {
  it: {
    hydraulic: "rischio idraulico",
    hydrogeological: "rischio idrogeologico",
    thunderstorm: "temporali",
  },
  fur: {
    hydraulic: "risi idraulic",
    hydrogeological: "risi idrogjologic",
    thunderstorm: "temporâi",
  },
};
const COPY = {
  it: {
    authority: "Dipartimento della Protezione Civile",
    label: { yellow: "Allerta gialla", orange: "Allerta arancione", red: "Allerta rossa" },
    multiZone: "Il Comune ricade in più zone: consulta il bollettino per il dettaglio.",
    validity: "Previsione per il {date}",
  },
  fur: {
    authority: "Dipartiment de Protezion Civîl",
    label: { yellow: "Alerte zale", orange: "Alerte naranç", red: "Alerte rosse" },
    multiZone: "Il Comun al riclâf in plui zonis: consulte il boletin pal detai.",
    validity: "Prevision pal {date}",
  },
};

function dateLabel(day) {
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(String(day || ""))) return "";
  const parsed = new Date(`${day}T12:00:00Z`);
  if (!Number.isFinite(parsed.getTime())) return "";
  return new Intl.DateTimeFormat("it-IT", {
    day: "numeric",
    month: "long",
    timeZone: "Europe/Rome",
  }).format(parsed);
}

export function buildNationalHomeAlertPresentation(
  state,
  location,
  { language = "it", now = Date.now } = {},
) {
  const current = Number(typeof now === "function" ? now() : now);
  const payload = state?.data;
  const municipality = getLocationMunicipality(location);
  if (
    !Number.isFinite(current)
    || state?.error
    || state?.isStale
    || !isUsableNationalOfficialAlerts(payload, location, { now: () => current })
    || payload?.complete !== true
    || payload?.active !== true
    || payload.municipality?.name !== municipality?.name
    || payload.records.some(record => record?.transmission_status !== "transmitted")
  ) return null;

  const active = payload.records.filter(record => {
    const expires = Date.parse(String(record?.valid_to || ""));
    return Object.hasOwn(RANK, record?.level)
      && Number.isFinite(expires)
      && expires > current
      && dateLabel(record?.forecast_day);
  });
  if (!active.length) return null;

  const level = active.reduce((highest, record) => (
    RANK[record.level] > RANK[highest] ? record.level : highest
  ), "yellow");
  const firstDay = active.filter(record => record.level === level)
    .map(record => record.forecast_day)
    .sort()[0];
  const copy = COPY[language === "fur" ? "fur" : "it"];
  const risks = [...new Set(active
    .filter(record => record.level === level && record.forecast_day === firstDay)
    .map(record => RISK_COPY[language === "fur" ? "fur" : "it"][record.risk])
    .filter(Boolean))];
  if (!risks.length) return null;

  return {
    action: { tab: "bulletin", type: "tab-anchor" },
    isOfficial: true,
    label: copy.label[level],
    meta: copy.authority,
    source: "national-official-alerts",
    text: `${municipality.name}: ${risks.join(" · ")}.${payload.conservative_multi_zone_display ? ` ${copy.multiZone}` : ""}`,
    tone: level,
    validityLabel: copy.validity.replace("{date}", dateLabel(firstDay)),
  };
}
