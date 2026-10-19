// Reader compatibility only. UI measurements remain null; tolerance is for notices.
const SPECS = {
  precipitation_mm: [0.1, "mm", 1],
  liquid_rain_mm: [0.1, "mm", 2],
  snow_water_equivalent_mm: [0.02, "mm_swe", 2],
};
const record = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const keys = (value, expected) => record(value)
  && Object.keys(value).sort().join(",") === [...expected].sort().join(",");
const number = (value) => typeof value === "number" && Number.isFinite(value) && value >= 0;

export function isValidIconAccumulationQuality(value, row) {
  if (!keys(value, ["schema_version", "fields"]) || value.schema_version !== "icon-accumulation-tolerance.v1"
      || !keys(value.fields, Object.keys(SPECS))) return false;
  return Object.entries(SPECS).every(([variable, [tolerance, unit, count]]) => {
    const q = value.fields[variable];
    if (!keys(q, ["state", "unit", "known_component_sum_mm", "unquantified_components",
      "resolution_budget_mm", "tolerance_mm", "reason"]) || q.unit !== unit || q.tolerance_mm !== tolerance
      || !number(q.known_component_sum_mm) || !number(q.resolution_budget_mm)
      || !Number.isInteger(q.unquantified_components) || q.unquantified_components < 0
      || q.unquantified_components > count) return false;
    if (["known_zero", "quantified"].includes(q.state)) {
      return number(row[variable]) && row[variable] === q.known_component_sum_mm
        && q.unquantified_components === 0 && q.resolution_budget_mm === 0 && q.reason === null
        && (q.state === "known_zero") === (q.known_component_sum_mm === 0);
    }
    if (q.state === "resolution_tolerance_verified") {
      return row[variable] === null && q.unquantified_components > 0
        && q.reason === null && q.resolution_budget_mm <= tolerance;
    }
    return q.state === "unavailable" && row[variable] === null && ["missing_or_invalid_accumulation",
      "resolution_metadata_missing", "resolution_budget_exceeded"].includes(q.reason);
  });
}
