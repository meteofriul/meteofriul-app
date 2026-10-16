function cleanText(value) {
  return String(value || "").trim();
}

function normalizeToken(value) {
  return cleanText(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function compactRecord(record) {
  return Object.fromEntries(
    Object.entries(record).filter(([, value]) => value !== "" && value != null),
  );
}

export function normalizeLocalityIdentity(value, { fallbackName = "" } = {}) {
  const record = value && typeof value === "object" ? value : {};
  const name = cleanText(
    typeof value === "string" ? value : record.name || record.displayName || fallbackName,
  );

  if (!name) return null;

  return compactRecord({
    id: cleanText(record.id),
    name,
    kind: cleanText(record.kind || record.type),
    source: cleanText(record.source),
    datasetVersion: cleanText(record.datasetVersion || record.dataset_version),
  });
}

export function normalizeMunicipalityIdentity(
  value,
  {
    fallbackIstatCode = "",
    fallbackName = "",
    fallbackProvince = "",
    fallbackProvinceName = "",
  } = {},
) {
  const record = value && typeof value === "object" ? value : {};
  const name = cleanText(typeof value === "string" ? value : record.name || fallbackName);
  const istatCode = cleanText(
    record.istatCode || record.istat_code || record.istat || fallbackIstatCode,
  );
  const province = cleanText(record.province || fallbackProvince).toUpperCase();
  const provinceName = cleanText(
    record.provinceName || record.province_name || fallbackProvinceName,
  );

  if (!name && !istatCode) return null;

  return compactRecord({
    istatCode,
    name,
    province,
    provinceName,
    source: cleanText(record.source),
    datasetVersion: cleanText(record.datasetVersion || record.dataset_version),
  });
}

export function normalizeLocationDataPoint(value) {
  if (!value || typeof value !== "object") return null;
  if (value.lat == null || value.lat === "" || value.lon == null || value.lon === "") {
    return null;
  }

  const lat = Number(value.lat);
  const lon = Number(value.lon);
  const source = cleanText(value.source);
  if (
    !Number.isFinite(lat)
    || lat < -90
    || lat > 90
    || !Number.isFinite(lon)
    || lon < -180
    || lon > 180
    || ![
      "rafvg_irdat_5000",
      "municipality_catalog",
      "nominatim_place",
      "nominatim_search",
    ].includes(source)
  ) return null;

  return { lat, lon, source };
}

export function normalizeLocationResolution(value) {
  if (!value || typeof value !== "object") return null;

  const status = cleanText(value.status);
  const municipalityResolved = value.municipalityResolved ?? value.municipality_resolved;
  const localityCorroborated = value.localityCorroborated ?? value.locality_corroborated;
  const rawBoundaryDistanceM = value.boundaryDistanceM ?? value.boundary_distance_m;
  const boundaryDistanceM = rawBoundaryDistanceM == null || rawBoundaryDistanceM === ""
    ? null
    : Number(rawBoundaryDistanceM);
  const matchMethod = cleanText(value.matchMethod ?? value.match_method);
  const rawDistanceM = value.distanceM ?? value.distance_m;
  const distanceM = rawDistanceM == null || rawDistanceM === ""
    ? null
    : Number(rawDistanceM);
  const rawRunnerUpDistanceM = value.runnerUpDistanceM ?? value.runner_up_distance_m;
  const runnerUpDistanceM = rawRunnerUpDistanceM == null || rawRunnerUpDistanceM === ""
    ? null
    : Number(rawRunnerUpDistanceM);
  const result = compactRecord({
    status,
    municipalityResolved: typeof municipalityResolved === "boolean"
      ? municipalityResolved
      : null,
    localityCorroborated: typeof localityCorroborated === "boolean"
      ? localityCorroborated
      : null,
    matchMethod: ["name", "nearest"].includes(matchMethod) ? matchMethod : null,
    distanceM: Number.isFinite(distanceM) && distanceM >= 0 ? distanceM : null,
    runnerUpDistanceM: Number.isFinite(runnerUpDistanceM) && runnerUpDistanceM >= 0
      ? runnerUpDistanceM
      : null,
    boundaryDistanceM: Number.isFinite(boundaryDistanceM) && boundaryDistanceM >= 0
      ? boundaryDistanceM
      : null,
  });

  return Object.keys(result).length ? result : null;
}

export function getLocationMunicipality(location) {
  if (!location || typeof location !== "object") return null;

  return normalizeMunicipalityIdentity(location.municipality, {
    fallbackIstatCode: location.istatCode || location.istat,
    fallbackName: location.city || location.name,
    fallbackProvince: location.province,
    fallbackProvinceName: location.provinceName,
  });
}

export function getLocationLocality(location) {
  if (typeof location === "string") {
    return normalizeLocalityIdentity(location);
  }
  if (!location || typeof location !== "object") return null;

  return normalizeLocalityIdentity(location.locality, {
    fallbackName: location.displayName || location.city || location.name,
  });
}

export function getLocationMunicipalityName(location) {
  if (typeof location === "string") return cleanText(location);
  return getLocationMunicipality(location)?.name || cleanText(location?.city || location?.name);
}

export function getLocationPrimaryName(location) {
  if (typeof location === "string") return cleanText(location);

  return cleanText(
    location?.displayName
      || getLocationLocality(location)?.name
      || getLocationMunicipalityName(location),
  );
}

export function getLocationLocalityKey(location) {
  const locality = getLocationLocality(location);
  const municipality = getLocationMunicipality(location);
  const municipalityKey = cleanText(municipality?.istatCode)
    || normalizeToken(municipality?.name || getLocationMunicipalityName(location));

  if (locality?.id) return `id:${normalizeToken(locality.id)}|municipality:${municipalityKey}`;

  const localityName = normalizeToken(locality?.name || getLocationPrimaryName(location));
  if (!localityName) return "";

  return `name:${localityName}|municipality:${municipalityKey}`;
}

export function hasDistinctLocality(location) {
  const localityName = normalizeToken(getLocationLocality(location)?.name);
  const municipalityName = normalizeToken(getLocationMunicipalityName(location));

  return Boolean(localityName && municipalityName && localityName !== municipalityName);
}
