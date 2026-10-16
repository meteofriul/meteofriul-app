import { getTerritoryKind } from "../../domain/scope/productScope";

const COPY = {
  it: {
    animation: "Ultimi 90 minuti",
    eyebrow: "Osservazione in tempo reale",
    frameUnavailable: "Fotogramma radar non disponibile",
    hideLegend: "Nascondi la legenda radar",
    legend: ["Debole", "Moderata", "Intensa", "Forte", "Molto forte"],
    live: "LIVE",
    mapLabel: "Mappa radar delle precipitazioni sul Friuli Venezia Giulia",
    noPrecipitation: "Nessuna precipitazione rilevata",
    pause: "Metti in pausa",
    pauseButton: "Pausa",
    play: "Anima gli ultimi 90 minuti",
    rain: "Pioggia",
    replay: "Rivedi 90 minuti",
    replayPlay: "Rivedi gli ultimi 90 minuti",
    scale: "Intensità pioggia",
    scaleAria: "Scala dell'intensità della pioggia da 0 a 100 millimetri all'ora",
    showLegend: "Mostra la legenda radar",
    source: "Radar-DPC",
    staleEyebrow: "Ultima osservazione radar",
    staleNotice: "Radar non aggiornato. Stai rivedendo l'ultima sequenza disponibile.",
    timelineEnd: "Ora",
    timelineLabel: "Sequenza radar degli ultimi 90 minuti",
    timelineStart: "90 min fa",
    title: "Radar precipitazioni",
    unavailable: "Radar temporaneamente non disponibile",
    waiting: "Radar in attesa del prossimo fotogramma",
    unavailableDetail: "Il Bollettino resta disponibile. Riprova più tardi.",
  },
  fur: {
    animation: "Ultins 90 minûts",
    eyebrow: "Osservazion in timp reâl",
    frameUnavailable: "Imagjin radar no disponibile",
    hideLegend: "Plate la legjende radar",
    legend: ["Debile", "Moderade", "Intense", "Fuarte", "Une vore fuarte"],
    live: "LIVE",
    mapLabel: "Mape radar des precipitazions sul Friûl Vignesie Julie",
    noPrecipitation: "Nissune precipitazion rilevade",
    pause: "Met in pause",
    pauseButton: "Pause",
    play: "Anime i ultins 90 minûts",
    rain: "Pluie",
    replay: "Torne viôt 90 minûts",
    replayPlay: "Torne viôt i ultins 90 minûts",
    scale: "Intensitât de pluie",
    scaleAria: "Scjale de intensitât de pluie di 0 a 100 milimetris par ore",
    showLegend: "Mostre la legjende radar",
    source: "Radar-DPC",
    staleEyebrow: "Ultime osservazion radar",
    staleNotice: "Radar no inzornât. E ven mostrade la ultime secuence disponibile.",
    timelineEnd: "Cumò",
    timelineLabel: "Secuence radar dai ultins 90 minûts",
    timelineStart: "90 min fa",
    title: "Radar des precipitazions",
    unavailable: "Radar pal moment no disponibil",
    waiting: "Radar in spiete de prossime imagjin",
    unavailableDetail: "Il boletin al reste disponibil. Torne prove plui tart.",
  },
};

export const RADAR_CURRENT_MAX_AGE_MS = 20 * 60 * 1000;

function getCopy(language) {
  return COPY[language === "fur" ? "fur" : "it"];
}

function getScopedCopy(language, location) {
  const copy = getCopy(language);
  if (getTerritoryKind(location) !== "italy") return copy;

  return {
    ...copy,
    mapLabel: language === "fur"
      ? "Mape radar des precipitazions su la Italie"
      : "Mappa radar delle precipitazioni sull’Italia",
    unavailableDetail: language === "fur"
      ? "Torne prove plui tart."
      : "Riprova più tardi.",
  };
}

function getTimestamp(value) {
  if (Number.isFinite(Number(value))) {
    const numeric = Number(value);
    return numeric < 1e12 ? numeric * 1000 : numeric;
  }

  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : null;
}

function formatRadarTime(value, language) {
  const timestamp = getTimestamp(value);
  if (timestamp === null) return "";

  return new Intl.DateTimeFormat(language === "fur" ? "it-IT" : "it-IT", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
    timeZone: "Europe/Rome",
  }).format(new Date(timestamp));
}

function normalizeProduct(product, copy, language) {
  if (product.id !== "rain") return null;

  const timestamp = getTimestamp(product.time || product.updated_at);

  if (timestamp === null) return null;

  return {
    id: "rain",
    label: copy.rain,
    layer: String(product.layer || "").trim(),
    periodMinutes: Number(product.period_minutes) || 5,
    productType: String(product.product_type || "").trim(),
    style: String(product.style || "").trim(),
    time: new Date(timestamp).toISOString(),
    timeLabel: formatRadarTime(timestamp, language),
    unit: String(product.unit || "").trim(),
  };
}

function resolveNow(now) {
  const value = typeof now === "function" ? now() : now;
  const timestamp = Number(value);
  return Number.isFinite(timestamp) ? timestamp : Date.now();
}

function hasOldRadarProducts(products, now) {
  const newestTimestamp = Math.max(
    ...products.map((product) => getTimestamp(product.time) || 0),
  );

  return newestTimestamp > 0
    && resolveNow(now) - newestTimestamp > RADAR_CURRENT_MAX_AGE_MS;
}

export function buildBulletinRadarViewModel(
  dataState = {},
  { language = "it", location = null, now = Date.now } = {},
) {
  const copy = getScopedCopy(language, location);
  const payload = dataState?.payload;

  if (!payload) {
    if (dataState?.status !== "error") return null;

    return {
      available: false,
      copy,
      title: copy.title,
      unavailableDetail: copy.unavailableDetail,
      unavailableLabel: copy.unavailable,
    };
  }

  const product = (payload.products || [])
    .map((product) => normalizeProduct(product, copy, language))
    .find(Boolean);

  if (!product || !payload?.tiles?.base_url) return null;

  const lat = Number(payload?.location?.lat ?? location?.lat);
  const lon = Number(payload?.location?.lon ?? location?.lon);
  const isStale = Boolean(
    dataState.isStale
    || dataState.status === "stale"
    || payload.status === "stale"
    || hasOldRadarProducts([product], now),
  );

  return {
    animationLabel: isStale ? copy.replay : copy.animation,
    available: true,
    city: String(payload.city || location?.city || "").trim(),
    copy,
    eyebrowLabel: isStale ? copy.staleEyebrow : copy.eyebrow,
    isStale,
    legend: {
      ariaLabel: copy.scaleAria,
      label: copy.scale,
      labels: copy.legend,
      max: 100,
      min: 0,
      unit: product.unit || "mm/h",
    },
    links: payload.links || {},
    location: Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon } : null,
    playLabel: isStale ? copy.replayPlay : copy.play,
    product,
    sourceLabel: payload?.source?.label || copy.source,
    sourceUrl: payload?.source?.url || payload?.links?.platform || "",
    staleNotice: isStale ? copy.staleNotice : "",
    tiles: {
      baseUrl: String(payload.tiles.base_url).trim(),
      encoding: String(payload.tiles.encoding || "red_channel_normalized").trim(),
      format: String(payload.tiles.format || "webp").trim(),
      tileSize: Number(payload.tiles.tile_size) || 256,
      zoom: Number(payload.tiles.zoom) || 7,
    },
    title: copy.title,
  };
}
