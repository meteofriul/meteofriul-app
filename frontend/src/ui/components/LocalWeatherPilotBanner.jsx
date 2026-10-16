import { useEffect, useState } from "react";

import {
  getLocalWeatherPilotNow,
  getLocalWeatherPilotTestNow,
  isLocalWeatherPilot,
} from "../../services/localWeatherPilot";
import { getLocalPilotFreshness } from "../../domain/weather/localWeatherPilotMetadata";

function formatSourceTime(value) {
  const timestamp = value ? Date.parse(value) : NaN;
  return Number.isFinite(timestamp)
    ? new Intl.DateTimeFormat("it-IT", {
      dateStyle: "short", timeStyle: "short", timeZone: "UTC",
    }).format(timestamp) + " UTC"
    : "non disponibile";
}

function formatDelivery(delivery) {
  switch (delivery?.provenance) {
    case "network": return "origine rete";
    case "validated_cache": return "cache verificata dal server";
    case "offline_cache": return "cache offline verificata";
    case "network_fallback_cache": return `cache verificata dopo errore di rete${delivery.fallback_reason ? ` (${delivery.fallback_reason})` : ""}`;
    case "cache": return "origine cache locale";
    default: return null;
  }
}

function formatForecastShape(freshness) {
  const points = freshness.forecastPointCount;
  const intervals = freshness.forecastIntervalCount;
  if (points === null) return "Vista oraria ICON non verificabile.";
  if (points <= 0) return "Vista oraria ICON non disponibile.";
  return `Vista oraria ICON: ${points} punti (${intervals} intervalli orari).`;
}

export function LocalWeatherPilotBanner({ error = null, metadata = null, now }) {
  const enabled = isLocalWeatherPilot();
  const testNow = getLocalWeatherPilotTestNow();
  const [clock, setClock] = useState(() => getLocalWeatherPilotNow());
  useEffect(() => {
    if (!enabled || now !== undefined || testNow) return undefined;
    const timer = setInterval(() => setClock(getLocalWeatherPilotNow()), 60_000);
    return () => clearInterval(timer);
  }, [enabled, now, testNow]);
  if (!enabled) return null;

  const freshness = getLocalPilotFreshness(metadata, now ?? testNow ?? clock);
  const camsAvailable = metadata?.cams_available === true;
  const camsPending = metadata?.cams_pending === true || metadata?.cams_status === "pending";
  const camsStatusKnown = metadata?.cams_available !== undefined || Boolean(metadata?.cams_status);
  const camsUnavailable = Boolean(metadata) && camsStatusKnown && !camsAvailable && !camsPending;
  const camsFreshnessStatus = metadata?.cams_freshness?.status || metadata?.cams_status || null;
  const camsStale = camsAvailable && camsFreshnessStatus === "stale";
  const iconDelivery = formatDelivery(metadata?.icon_delivery);
  const camsDelivery = formatDelivery(metadata?.cams_delivery);
  const sourceSummary = camsAvailable
    ? "ICON-2I + CAMS"
    : camsPending ? "ICON-2I · CAMS IN CARICAMENTO"
      : camsUnavailable ? "ICON-2I · CAMS NON DISPONIBILE" : "ICON-2I";
  return (
    <aside
      aria-label={camsAvailable
        ? "Pilota meteo locale ICON e CAMS"
        : camsPending ? "Pilota meteo locale ICON; CAMS in caricamento" : "Pilota meteo locale ICON"}
      data-testid="local-weather-pilot-banner"
      style={{ border: "1px solid #a87924", borderRadius: 12, padding: "12px 16px", margin: "0 0 12px", background: "#fff7e4", color: "#493619", fontSize: 13, lineHeight: 1.5 }}
    >
      <strong>TEST LOCALE · {sourceSummary} · {freshness.label}</strong>
      {testNow ? (
        <div>OROLOGIO METEO SIMULATO · {formatSourceTime(testNow)} · sequenza scheduler accelerata.</div>
      ) : null}
      <div>Home e condizioni locali: previsioni di modello, non osservazioni. {testNow
        ? "I puntatori locali possono avanzare durante questa prova controllata."
        : "Lo snapshot ICON non si aggiorna automaticamente; ricaricare rilegge lo stesso file."}</div>
      <div>ICON · corsa {formatSourceTime(metadata?.run_utc)} · dato {formatSourceTime(metadata?.valid_at_utc)}{iconDelivery ? ` · ${iconDelivery}` : ""}.</div>
      {camsAvailable ? (
        <div>CAMS · corsa {formatSourceTime(metadata?.cams_run_utc)} · dato {formatSourceTime(metadata?.cams_valid_at_utc)} · {camsStale ? "DATATO" : camsFreshnessStatus === "fresh" ? "aggiornato" : "freschezza non verificabile"}{camsDelivery ? ` · ${camsDelivery}` : ""}. Griglia e corsa separate da ICON.</div>
      ) : camsPending ? (
        <div>CAMS in caricamento asincrono; la previsione ICON è già visibile e resta utilizzabile.</div>
      ) : camsUnavailable ? (
        <div>CAMS non disponibile in questo aggiornamento; la previsione ICON resta visibile e non è stato applicato alcun fallback meteo.</div>
      ) : (
        <div>Disponibilità CAMS non ancora verificata; la previsione ICON resta separata.</div>
      )}
      <div>{formatForecastShape(freshness)}</div>
      <div>Non disponibili nel pilota: 5 giorni completi ICON, probabilità di precipitazione e visibilità. Percepita: Steadman all’ombra. Precipitazioni in mm, inclusa l’acqua equivalente della neve.</div>
      <div>{camsAvailable
        ? "Pollini CAMS sperimentali: concentrazioni senza livelli sanitari o AQI."
        : camsPending ? "Pollini CAMS in caricamento."
          : "Pollini CAMS non disponibili."} Bollettino ufficiale OSMER e allerte restano separati e invariati.</div>
      {error ? <div role="status">Diagnostica locale: {String(error)}</div> : null}
    </aside>
  );
}
