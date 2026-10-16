export function normalizeUnitSystem(value) {
  return value === "imperial" ? "imperial" : "metric";
}

export function convertTemperature(value, unitSystem = "metric") {
  const number = Number(value);

  if (!Number.isFinite(number)) return null;

  if (normalizeUnitSystem(unitSystem) === "imperial") {
    return (number * 9) / 5 + 32;
  }

  return number;
}

export function formatTemperature(value, unitSystem = "metric", digits = 0) {
  const converted = convertTemperature(value, unitSystem);

  if (converted === null) return null;

  return digits > 0 ? converted.toFixed(digits) : String(Math.round(converted));
}

export function convertWindSpeed(value, unitSystem = "metric") {
  const number = Number(value);

  if (!Number.isFinite(number)) return null;

  if (normalizeUnitSystem(unitSystem) === "imperial") {
    return number / 1.609344;
  }

  return number;
}

export function formatWindSpeed(value, unitSystem = "metric", digits = 0) {
  const converted = convertWindSpeed(value, unitSystem);

  if (converted === null) return null;

  return digits > 0 ? converted.toFixed(digits) : String(Math.round(converted));
}

export function getTemperatureUnitLabel(unitSystem = "metric") {
  return normalizeUnitSystem(unitSystem) === "imperial" ? "°F" : "°C";
}

export function getWindUnitLabel(unitSystem = "metric") {
  return normalizeUnitSystem(unitSystem) === "imperial" ? "mph" : "km/h";
}
