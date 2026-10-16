export function getTemperatureSeverity(value, mode = "current") {
  const temperature = Number(value);

  if (!Number.isFinite(temperature)) return "normal";

  if (temperature <= -5) return "freezing";
  if (temperature <= 0) return "cold";

  if (mode === "min") return "normal";

  if (temperature >= 35) return "extreme-hot";
  if (temperature >= 32) return "very-hot";
  if (temperature >= 28) return "hot";

  return "normal";
}
