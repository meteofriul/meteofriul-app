import { getLocationMunicipality } from "../domain/geo/locationIdentity";
import { API_BASE } from "./apiConfig";

const ISTAT_CODE = /^\d{6}$/u;

export function getNationalOfficialAlertsIstat(location) {
  const code = String(getLocationMunicipality(location)?.istatCode || "").trim();
  return ISTAT_CODE.test(code) ? code : "";
}

export function buildNationalOfficialAlertsUrl(
  location,
  { apiBase = API_BASE, force = false, now = Date.now } = {},
) {
  const municipalityIstat = getNationalOfficialAlertsIstat(location);
  if (!municipalityIstat) {
    throw new Error("Codice ISTAT del Comune mancante");
  }

  const base = String(apiBase || "").replace(/\/$/u, "");
  const params = new URLSearchParams({ municipality_istat: municipalityIstat });
  if (force) {
    params.set("_", String(typeof now === "function" ? now() : now));
  }
  return `${base}/weather/official-alerts/national?${params.toString()}`;
}

export async function fetchNationalOfficialAlertsPayload(
  location,
  {
    apiBase = API_BASE,
    fetchImpl = globalThis.fetch,
    force = false,
    now = Date.now,
  } = {},
) {
  if (typeof fetchImpl !== "function") throw new Error("Fetch non disponibile");

  const response = await fetchImpl(
    buildNationalOfficialAlertsUrl(location, { apiBase, force, now }),
    { cache: force ? "no-store" : "default" },
  );
  if (!response?.ok) {
    throw new Error("Risposta allerte nazionali non valida");
  }

  const payload = await response.json();
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("Dati allerte nazionali mancanti");
  }
  return payload;
}
