const COPY = {
  it: {
    label: "Dati meteo locali",
    wind: "Vento",
    humidity: "Umidità",
    pressure: "Pressione",
    precipitation: "Pioggia",
    pollen: "Pollini",
    unavailable: "Dato non disponibile",
    pollenUnavailable: "Dati pollinici non disponibili",
    pollenPending: "Dati pollinici in arrivo",
    pollenPendingValue: "In arrivo",
    pollenValues: {
      low: "Basso",
      medium: "Medio",
      high: "Alto",
      "very-high": "Molto alto",
      available: "Dati",
      unavailable: "—",
    },
  },
  fur: {
    label: "Dâts meteo locâi",
    wind: "Vint",
    humidity: "Umiditât",
    pressure: "Pression",
    precipitation: "Pluie",
    pollen: "Polins",
    unavailable: "Dât no disponibil",
    pollenUnavailable: "Dâts sui polins no disponibii",
    pollenPending: "Dâts sui polins in rivade",
    pollenPendingValue: "In rivade",
    pollenValues: {
      low: "Bas",
      medium: "Medi",
      high: "Alt",
      "very-high": "Une vore alt",
      available: "Dâts",
      unavailable: "—",
    },
  },
};

const METRIC_IDS = ["wind", "humidity", "pressure", "precipitation"];

function readText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function readMetricValue(value) {
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "";
  return readText(value);
}

function buildMetricItem(id, metric, copy) {
  const fullLabel = readText(metric?.label) || copy[id];
  const formattedValue = readMetricValue(metric?.value);
  const available = Boolean(formattedValue && formattedValue !== "—");
  // Values and source selection already belong to the bulletin model. Only
  // separate its supported unit suffixes; do not parse, round or convert them.
  const parts = available ? formattedValue.match(/^(.+?)\s*(km\/h|hPa|mm|%)$/) : null;
  const detail = available ? readText(metric?.detail) : "";

  return {
    id,
    label: id === "pressure" ? "Press." : fullLabel,
    value: available ? (parts ? parts[1].trim() : formattedValue) : "—",
    unit: parts ? parts[2] : "",
    ariaLabel: [
      `${fullLabel}: ${available ? formattedValue : copy.unavailable}`,
      detail,
    ].filter(Boolean).join(", "),
    ...(metric?.tone ? { tone: metric.tone } : {}),
  };
}

function buildPollenItem(pollen, copy) {
  const label = readText(pollen?.label) || copy.pollen;
  const status = readText(pollen?.status).toLowerCase();
  const pending = status === "pending";
  const explicitlyUnavailable = pollen?.available === false || status === "unavailable";

  if (pending) {
    return {
      id: "pollen",
      label,
      value: copy.pollenPendingValue,
      unit: "",
      ariaLabel: `${label}: ${copy.pollenPending}`,
      tone: "pending",
    };
  }

  if (explicitlyUnavailable) {
    return {
      id: "pollen",
      label,
      value: copy.pollenValues.unavailable,
      unit: "",
      ariaLabel: `${label}: ${copy.pollenUnavailable}`,
      tone: "unavailable",
    };
  }

  const pollenValues = Array.isArray(pollen?.values)
    ? pollen.values
      .map((entry) => ({
        displayValue: readText(entry?.displayValue),
        label: readText(entry?.label),
        value: entry?.value === null
          || entry?.value === undefined
          || (typeof entry.value === "string" && readText(entry.value) === "")
          ? Number.NaN
          : Number(entry.value),
      }))
      .filter((entry) => Number.isFinite(entry.value) && entry.value >= 0)
    : [];
  const strongest = pollenValues.reduce(
    (current, entry) => (!current || entry.value > current.value ? entry : current),
    null,
  );

  if (strongest) {
    const unit = readText(pollen?.units) || "grani/m³";
    const value = strongest.displayValue || new Intl.NumberFormat("it-IT", {
      maximumFractionDigits: 2,
    }).format(strongest.value);
    const strongestSpecies = strongest.value > 0
      ? pollenValues.filter((entry) => entry.value === strongest.value && entry.label)
      : [];
    const species = strongestSpecies.length === 1 ? strongestSpecies[0].label : "";

    return {
      id: "pollen",
      label: species || label,
      value,
      unit,
      ariaLabel: `${species || label}: ${value} ${unit}`,
      tone: "available",
    };
  }

  const knownTone = Object.hasOwn(copy.pollenValues, pollen?.tone);
  const tone = knownTone
      ? pollen.tone
      : pollen?.available === true ? "available" : "unavailable";
  const value = copy.pollenValues[tone];
  const available = tone !== "unavailable";
  const level = available ? (readText(pollen?.level) || value) : copy.pollenUnavailable;
  const detail = available ? readText(pollen?.detail) : "";
  const strongestLabel = readText(pollen?.strongestLabel);

  return {
    id: "pollen",
    label,
    value,
    unit: "",
    ariaLabel: [
      `${label}: ${level}`,
      detail ? [strongestLabel, detail].filter(Boolean).join(": ") : "",
    ].filter(Boolean).join(", "),
    tone,
  };
}

export function buildHomeLocalMetricsViewModel(localWeather, { language = "it" } = {}) {
  if (!localWeather) return null;

  const copy = COPY[language === "fur" ? "fur" : "it"];
  const metrics = Array.isArray(localWeather.metrics) ? localWeather.metrics : [];

  return {
    label: readText(localWeather.currentDataLabel) || copy.label,
    description: [
      readText(localWeather.observationLabel),
      readText(localWeather.detailsSourceLabel) || readText(localWeather.sourceLabel),
    ].filter(Boolean).join(" · "),
    weatherDescription: readText(localWeather.observationLabel),
    items: [
      ...METRIC_IDS.map((id) => buildMetricItem(id, metrics.find((metric) => metric?.id === id), copy)),
      buildPollenItem(localWeather.pollen, copy),
    ],
  };
}
