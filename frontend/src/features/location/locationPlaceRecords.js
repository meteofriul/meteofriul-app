import {
  normalizeLocalityIdentity,
  normalizeLocationResolution,
  normalizeMunicipalityIdentity,
} from "../../domain/geo/locationIdentity";

export function toAppLocation(place) {
  const latitude = place.latitude == null || place.latitude === "" ? null : Number(place.latitude);
  const longitude = place.longitude == null || place.longitude === "" ? null : Number(place.longitude);
  const isStoredLocation = Boolean(place.municipality);
  const fallbackName = String(
    place.displayName
      || (typeof place.locality === "string" ? place.locality : place.locality?.name)
      || place.name
      || place.city
      || "",
  ).trim();
  const municipality = normalizeMunicipalityIdentity(place.municipality, {
    fallbackIstatCode: place.istatCode,
    fallbackName: place.city || place.name,
    fallbackProvince: place.province,
    fallbackProvinceName: place.provinceName,
  });
  const city = String(municipality?.name || place.city || place.name || "").trim();
  const locality = place.locality
    ? normalizeLocalityIdentity(place.locality, { fallbackName })
    : normalizeLocalityIdentity({
        name: fallbackName || city,
        kind: "municipality",
        source: "manual_search",
      });
  const resolution = normalizeLocationResolution(place.resolution);
  const dataPoint = place.dataPoint || (
    Number.isFinite(latitude) && Number.isFinite(longitude)
      ? {
          lat: latitude,
          lon: longitude,
          source: String(
            place.provider || (place.istatCode ? "municipality_catalog" : "nominatim_search"),
          ).trim(),
        }
      : null
  );
  const region = String(place.admin1 || place.region || place.state || "").trim();
  const countryCode = String(place.countryCode || place.country_code || "").trim().toUpperCase();
  const country = String(place.country || place.countryName || place.country_name || "").trim();
  const regionCode = String(
    place.regionCode
      || place.region_code
      || place.admin1Code
      || place.admin1_code
      || "",
  ).trim().toUpperCase();
  const appLocation = {
    city,
    displayName: fallbackName || city,
    region,
    province: municipality?.province || place.province,
    provinceName: municipality?.provinceName || place.provinceName,
    istatCode: municipality?.istatCode || place.istatCode,
    locality,
    municipality: municipality || {
      name: city,
      istatCode: place.istatCode,
      province: place.province,
      provinceName: place.provinceName,
      source: "manual_search",
    },
    lat: Number.isFinite(latitude) ? latitude : null,
    lon: Number.isFinite(longitude) ? longitude : null,
    source: isStoredLocation ? "manual_recent" : "manual",
  };

  if (countryCode) appLocation.countryCode = countryCode;
  if (country) appLocation.country = country;
  if (regionCode) appLocation.regionCode = regionCode;
  if (place.provider) appLocation.provider = String(place.provider).trim();
  if (place.providerId || place.provider_id) {
    appLocation.providerId = String(place.providerId || place.provider_id).trim();
  }
  if (dataPoint) appLocation.dataPoint = dataPoint;
  if (resolution) appLocation.resolution = resolution;

  return appLocation;
}

export function toPlaceRecord(location) {
  return {
    name: location.displayName || location.locality?.name || location.city,
    city: location.city,
    displayName: location.displayName,
    admin1: location.region,
    regionCode: location.regionCode,
    country: location.country,
    countryCode: location.countryCode,
    provider: location.provider,
    providerId: location.providerId,
    province: location.province,
    provinceName: location.provinceName,
    istatCode: location.istatCode,
    latitude: location.lat,
    longitude: location.lon,
    dataPoint: location.dataPoint,
    locality: location.locality,
    municipality: location.municipality,
    positionAccuracyM: location.positionAccuracyM,
    positionCapturedAt: location.positionCapturedAt,
    resolution: location.resolution,
    source: location.source,
  };
}
