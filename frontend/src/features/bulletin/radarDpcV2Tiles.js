const SRI_COLORS = Object.freeze({
  c0: [0.75, 0.90, 0.50],
  c1: [0.00, 0.80, 1.00],
  c2: [0.00, 0.80, 0.00],
  c3: [1.00, 1.00, 0.00],
  c4: [1.00, 0.65, 0.30],
  c5: [1.00, 0.00, 0.30],
  c6: [0.60, 0.00, 0.80],
});

function clamp01(value) {
  return Math.min(1, Math.max(0, value));
}

function smoothstep(edge0, edge1, value) {
  const normalized = clamp01((value - edge0) / Math.max(1e-6, edge1 - edge0));
  return normalized * normalized * (3 - (2 * normalized));
}

function mixColor(from, to, amount) {
  return from.map((value, index) => value + ((to[index] - value) * amount));
}

export function getSriRadarColor(value01) {
  const value = clamp01(value01);
  const first = mixColor(SRI_COLORS.c0, SRI_COLORS.c1, smoothstep(0, 0.08, value));
  const second = mixColor(SRI_COLORS.c2, SRI_COLORS.c3, smoothstep(0.12, 0.30, value));
  const third = mixColor(SRI_COLORS.c4, SRI_COLORS.c5, smoothstep(0.40, 0.70, value));
  const fourth = mixColor(third, SRI_COLORS.c6, smoothstep(0.70, 1, value));
  const lower = value < 0.20 ? first : second;
  const color = mixColor(lower, fourth, smoothstep(0.35, 1, value));

  return {
    alpha: smoothstep(0.01, 0.05, value),
    blue: color[2],
    green: color[1],
    red: color[0],
  };
}

// SRI intensity is one byte: evaluate the exact palette once per possible value,
// rather than allocating/interpolating several colors for every radar pixel.
const SRI_BYTE_COLORS = Array.from({ length: 256 }, (_, value) => (
  getSriRadarColor(value / 255)
));

export function colorizeSriRadarPixels(pixelData) {
  if (!(pixelData instanceof Uint8ClampedArray) || pixelData.length % 4 !== 0) {
    throw new TypeError("Dati pixel radar non validi");
  }

  let echoPixelCount = 0;

  for (let index = 0; index < pixelData.length; index += 4) {
    const sourceAlpha = pixelData[index + 3] / 255;
    const value = pixelData[index];

    if (sourceAlpha < 0.005 || value <= 0) {
      pixelData[index] = 0;
      pixelData[index + 1] = 0;
      pixelData[index + 2] = 0;
      pixelData[index + 3] = 0;
      continue;
    }

    const color = SRI_BYTE_COLORS[value];
    const alpha = color.alpha * sourceAlpha;

    if (alpha < 0.01) {
      pixelData[index + 3] = 0;
      continue;
    }

    pixelData[index] = Math.round(color.red * 255);
    pixelData[index + 1] = Math.round(color.green * 255);
    pixelData[index + 2] = Math.round(color.blue * 255);
    pixelData[index + 3] = Math.round(alpha * 255);
    echoPixelCount += 1;
  }

  return {
    echoPixelCount,
    hasEcho: echoPixelCount > 0,
  };
}

export function getRadarFrameStatus({ hadEcho = false, hadError = false } = {}) {
  if (hadError) return "error";
  return hadEcho ? "ready" : "empty";
}

function getUtcFrameParts(value) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) {
    throw new TypeError("Orario radar non valido");
  }

  return {
    day: String(date.getUTCDate()).padStart(2, "0"),
    hour: String(date.getUTCHours()).padStart(2, "0"),
    minute: String(date.getUTCMinutes()).padStart(2, "0"),
    month: String(date.getUTCMonth() + 1).padStart(2, "0"),
    year: String(date.getUTCFullYear()),
  };
}

export function buildDpcRadarTileUrl({
  baseUrl,
  coords,
  productType = "SRI",
  time,
}) {
  const normalizedBaseUrl = String(baseUrl || "").trim().replace(/\/$/, "");
  const normalizedProduct = String(productType || "").trim().toUpperCase();
  const x = Number(coords?.x);
  const y = Number(coords?.y);
  const z = Number(coords?.z);

  if (!normalizedBaseUrl || !/^[A-Z0-9_]+$/.test(normalizedProduct)) {
    throw new TypeError("Contratto tile radar non valido");
  }
  if (![x, y, z].every(Number.isInteger)) {
    throw new TypeError("Coordinate tile radar non valide");
  }

  const { day, hour, minute, month, year } = getUtcFrameParts(time);
  const filename = `${normalizedProduct.toLowerCase()}.webp`;

  return [
    normalizedBaseUrl,
    normalizedProduct,
    year,
    month,
    day,
    `${hour}${minute}`,
    z,
    x,
    y,
    filename,
  ].join("/");
}
