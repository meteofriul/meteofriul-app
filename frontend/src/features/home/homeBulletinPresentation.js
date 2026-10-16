import { buildOsmerLocalAdviceSnapshot } from "../../domain/weather/osmerLocalAdviceSnapshot";
import { buildIconLocalAdvice } from "../../domain/weather/iconLocalAdvice";

const COPY = {
  it: {
    officialFallbackHeadline: "Previsione non disponibile",
    today: "Oggi",
    updatedAt: "{day} · OSMER {time}",
    staleAt: "{day} · OSMER {time} · non aggiornato",
    adviceTitle: "Consigliato",
  },
  fur: {
    officialFallbackHeadline: "Prevision no disponibile",
    today: "Vuê",
    updatedAt: "{day} · OSMER {time}",
    staleAt: "{day} · OSMER {time} · no inzornât",
    adviceTitle: "Conseât",
  },
};

function getLanguageKey(language) {
  return language === "fur" ? "fur" : "it";
}

function compactOfficialText(text) {
  const normalized = String(text || "").replace(/\s+/g, " ").trim();
  if (!normalized) return "";

  const firstSentence = normalized.match(/^[^.!?]+[.!?]?/)?.[0]?.trim() || normalized;
  if (firstSentence.length <= 112) return firstSentence;

  const candidate = firstSentence.slice(0, 109).trim();
  const lastSpace = candidate.lastIndexOf(" ");
  const compact = lastSpace >= 64 ? candidate.slice(0, lastSpace) : candidate;

  return `${compact.trim()}...`;
}

function buildOfficialTextPresentation(text) {
  const normalized = String(text || "").replace(/\s+/g, " ").trim();
  if (!normalized) return { body: "", headline: "" };

  const firstSentence = normalized.match(/^[^.!?]+[.!?]?/)?.[0]?.trim() || normalized;
  const remainingText = normalized.slice(firstSentence.length).trim();
  const conditionText = firstSentence
    .replace(/^AGGIORNAMENTO(?:\s+OSMER)?\s*[:\-–—]\s*/iu, "")
    .trim();
  const compactHeadline = compactOfficialText(conditionText);
  const headline = compactHeadline.endsWith("...")
    ? compactHeadline
    : compactHeadline.replace(/[.!?]+$/u, "").trim();

  return {
    body: compactOfficialText(remainingText),
    headline,
  };
}

function getEmissionTime(value) {
  const text = String(value || "").trim();
  if (!text) return "";

  const explicitTime = text.match(/(?:^|\s)(\d{2}:\d{2})(?:\s|$)/)?.[1];
  if (explicitTime) return explicitTime;

  const date = new Date(text);
  if (!Number.isFinite(date.getTime())) return "";

  return new Intl.DateTimeFormat("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Rome",
  }).format(date);
}

function getDayContextLabel(day, language) {
  const copy = COPY[getLanguageKey(language)];
  if (day?.id === "today") return copy.today;

  return String(day?.compactDateLabel || day?.date || "").trim();
}

function buildEmissionLabel(
  value,
  { day = null, isStale = false, language = "it", fallback = "" } = {},
) {
  const copy = COPY[getLanguageKey(language)];
  const time = getEmissionTime(value);
  if (!time) return fallback;

  const dayLabel = getDayContextLabel(day, language) || fallback;

  return (isStale ? copy.staleAt : copy.updatedAt)
    .replace("{day}", dayLabel)
    .replace("{time}", time);
}

export function buildHomeBulletinPresentation(
  bulletinModel,
  {
    advicePending = false,
    language = "it",
    location = null,
    now = null,
    weatherState = null,
  } = {},
) {
  const day = bulletinModel?.days?.[0] || null;
  if (!day || bulletinModel?.status === "unavailable") return null;

  const copy = COPY[getLanguageKey(language)];
  const localSnapshot = buildOsmerLocalAdviceSnapshot(
    day.osmerStructuredDay || day,
    location,
  );
  const iconAdvice = buildIconLocalAdvice(weatherState, { language, now });
  const adviceStatus = iconAdvice
    ? "ready"
    : advicePending
      ? "pending"
      : "unavailable";

  if (localSnapshot) {
    return {
      advice: iconAdvice,
      adviceStatus,
      dateLabel: buildEmissionLabel(localSnapshot.issuedAt, {
        day,
        language,
        fallback: day.date,
      }),
      headline: localSnapshot.headline,
      icon: localSnapshot.icon,
      kind: "local_structured",
      raw: localSnapshot,
      snapshotKey: localSnapshot.snapshotKey,
      sourceLabel: bulletinModel.source?.label || "OSMER ARPA FVG",
    };
  }

  const isStale = bulletinModel?.status === "stale_visible";
  const officialText = buildOfficialTextPresentation(day.text);

  return {
    advice: iconAdvice,
    adviceStatus,
    body: adviceStatus === "unavailable" ? officialText.body : "",
    dateLabel: buildEmissionLabel(day.emission, {
      day,
      isStale,
      language,
      fallback: day.date,
    }),
    headline: officialText.headline || copy.officialFallbackHeadline,
    icon: { type: "Cloud" },
    kind: "official_text",
    raw: day,
    snapshotKey: ["official", day.emission || "unknown", day.forecastDate || "unknown"].join(":"),
    sourceLabel: bulletinModel.source?.label || "OSMER ARPA FVG",
  };
}
