import {
  getWeatherIconProps,
  isIconLocalPilotWeather,
  normalizeWeatherData,
} from "./normalizedWeather";
import { getConditionContext, getWeatherGroup } from "./weatherAdviceContext";

const HOUR_MS = 60 * 60 * 1000;
const FORECAST_WINDOW_HOURS = 12;
const ADVERSE_PRIORITY = Object.freeze({
  storm: 5,
  snow: 4,
  rain: 3,
  fog: 2,
  wind: 1,
});

const COPY = Object.freeze({
  it: Object.freeze({
    title: "Consigliato",
    cold: "Aria pungente: meglio vestirsi a strati, soprattutto nelle ore più fredde.",
    fog: "Con la nebbia il mondo si accorcia: rallenta e aumenta le distanze.",
    heat: "Il sole scalda: cerca un po’ d’ombra e porta con te dell’acqua.",
    rain: "Ombrello a portata di mano: nelle prossime ore potrebbe tornare utile.",
    snow: "Strade d’inverno: controlla le condizioni prima di partire e guida con prudenza.",
    stable: "Il tempo tiene: una buona occasione per stare all’aperto.",
    storm: "Se il cielo brontola, niente attese: cerca subito riparo.",
    temperature: "Giornata a strati: qualcosa da togliere o rimettere farà comodo.",
    wind: "Raffiche in arrivo: metti al sicuro gli oggetti leggeri e muoviti con attenzione.",
  }),
  fur: Object.freeze({
    title: "Conseât",
    cold: "Aiâr frêt: miôr vistîsi a strâts, massime tes oris plui fredes.",
    fog: "Cu la fumate il mont si scurte: sbasse la velocitât e ten plui distance.",
    heat: "Il soreli al scjalde: cîr un pôc di ombrene e puarte cun te de aghe.",
    rain: "Ombrele a puartade di man: tes prossimis oris e podarès coventâ.",
    snow: "Stradis di unvier: controle lis condizions prime di partî e vuide cun prudence.",
    stable: "Il timp al ten: une buine ocasion par stâ fûr.",
    storm: "Se al tone, no sta spietâ: cîr daurman ripar.",
    temperature: "Zornade a strâts: alc di gjavâ o tornâ a meti al vignarà ben.",
    wind: "Rafichis in rivade: met in sigurece i ogjets lizêrs e moviti cun atenzion.",
  }),
});

function getLanguageKey(language) {
  return language === "fur" ? "fur" : "it";
}

function getTimestamp(value) {
  if (value === null || value === undefined || value === "") return null;
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : null;
}

function selectForecastWindow(slots, now) {
  const ordered = (Array.isArray(slots) ? slots : [])
    .map((slot) => ({ slot, timestamp: getTimestamp(slot?.time) }))
    .filter(({ timestamp }) => timestamp !== null)
    .sort((left, right) => left.timestamp - right.timestamp);
  if (!ordered.length) return [];

  const requestedNow = getTimestamp(now);
  const start = requestedNow === null
    ? ordered[0].timestamp
    : Math.floor(requestedNow / HOUR_MS) * HOUR_MS;
  const end = start + FORECAST_WINDOW_HOURS * HOUR_MS;

  return ordered
    .filter(({ timestamp }) => timestamp >= start && timestamp < end)
    .map(({ slot }) => slot);
}

function getSlotAdvice(slot) {
  const icon = getWeatherIconProps(slot);
  const weatherGroup = getWeatherGroup(icon.type);
  const context = getConditionContext(slot, weatherGroup);

  return {
    context,
    group: context.adviceGroup,
    temperature: Number.isFinite(Number(context.temperature))
      ? Number(context.temperature)
      : null,
  };
}

function selectAdviceGroup(samples) {
  const adverse = samples
    .filter(({ group }) => Object.prototype.hasOwnProperty.call(ADVERSE_PRIORITY, group))
    .sort((left, right) => ADVERSE_PRIORITY[right.group] - ADVERSE_PRIORITY[left.group]);
  if (adverse.length) return adverse[0].group;

  const temperatures = samples
    .map(({ temperature }) => temperature)
    .filter(Number.isFinite);
  if (!temperatures.length) return "stable";

  const minimum = Math.min(...temperatures);
  const maximum = Math.max(...temperatures);
  if (maximum >= 28) return "heat";
  if (minimum <= 5) return "cold";
  if (maximum - minimum >= 6) return "temperature";

  return "stable";
}

/**
 * Derives a compact, deterministic suggestion from the next ICON forecast
 * slots. It never reads or interprets the narrative OSMER bulletin.
 */
export function buildIconLocalAdvice(
  weatherState,
  { language = "it", now = null } = {},
) {
  const rawCurrent = weatherState?.rawCurrent || weatherState?.current?.raw || null;
  if (
    !rawCurrent
    || !isIconLocalPilotWeather(rawCurrent)
    || weatherState?.isStale
    || ["empty", "error", "stale"].includes(weatherState?.status)
  ) return null;

  const normalized = weatherState?.current?.type
    ? weatherState.current
    : normalizeWeatherData(rawCurrent);
  const availableSlots = normalized.hourlyForecast?.length
    ? normalized.hourlyForecast
    : normalized.hourlyNext12h;
  const slots = selectForecastWindow(availableSlots, now);
  if (!slots.length) return null;

  const group = selectAdviceGroup(slots.map(getSlotAdvice));
  const copy = COPY[getLanguageKey(language)];

  return Object.freeze({
    group,
    label: copy[group],
    source: "icon2i",
    title: copy.title,
    windowHours: FORECAST_WINDOW_HOURS,
  });
}
