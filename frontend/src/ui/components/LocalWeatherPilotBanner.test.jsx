import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getLocalWeatherPilotNow,
  getLocalWeatherPilotTestNow,
  isLocalWeatherPilot,
} from "../../services/localWeatherPilot";
import { buildLocalWeatherPilotMetadata, getLocalPilotFreshness } from "../../domain/weather/localWeatherPilotMetadata";
import { LocalWeatherPilotBanner } from "./LocalWeatherPilotBanner";

vi.mock("../../services/localWeatherPilot", () => ({
  getLocalWeatherPilotNow: vi.fn(() => Date.now()),
  getLocalWeatherPilotTestNow: vi.fn(() => null),
  isLocalWeatherPilot: vi.fn(),
}));

const metadata = {
  run_utc: "2026-09-03T00:00:00Z", valid_at_utc: "2026-09-03T16:00:00Z",
  cams_run_utc: "2026-09-03T00:00:00Z", cams_valid_at_utc: "2026-09-03T16:00:00Z",
  cams_available: true, cams_status: "fresh", cams_product_status: "experimental_model_snapshot",
  cams_freshness: { status: "fresh" }, cams_delivery: { provenance: "network" },
  icon_delivery: { provenance: "network" },
  first_forecast_at_utc: "2026-09-03T16:00:00Z",
  last_forecast_at_utc: "2026-09-05T15:00:00Z",
  forecast_point_count: 48, forecast_interval_count: 47, status: "fresh",
};

describe("LocalWeatherPilotBanner", () => {
  beforeEach(() => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    vi.mocked(getLocalWeatherPilotNow).mockImplementation(() => Date.now());
    vi.mocked(getLocalWeatherPilotTestNow).mockReturnValue(null);
  });

  it("is absent outside the guarded local development mode, even with pilot data", () => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(false);
    expect(renderToStaticMarkup(<LocalWeatherPilotBanner metadata={metadata} />)).toBe("");
  });

  it("shows source dates, unsupported capabilities, experimental pollen and unchanged official data", () => {
    const markup = renderToStaticMarkup(<LocalWeatherPilotBanner metadata={metadata} now="2026-09-03T16:00:00Z" />);
    expect(markup).toContain("TEST LOCALE");
    expect(markup).toContain("ICON-2I + CAMS");
    expect(markup).toContain("03/09/26, 00:00 UTC");
    expect(markup).toContain("Vista oraria ICON: 48 punti (47 intervalli orari)");
    expect(markup).toContain("CAMS · corsa");
    expect(markup).toContain("aggiornato · origine rete");
    expect(markup).toContain("Lo snapshot ICON non si aggiorna automaticamente");
    expect(markup).toContain("5 giorni completi ICON");
    expect(markup).toContain("probabilità di precipitazione e visibilità");
    expect(markup).toContain("senza livelli sanitari o AQI");
    expect(markup).toContain("Bollettino ufficiale OSMER e allerte restano separati e invariati");
    expect(markup).not.toContain("Open-Meteo");
  });

  it("makes the accelerated scheduler clock explicit", () => {
    vi.mocked(getLocalWeatherPilotTestNow).mockReturnValue("2026-09-04T05:00:00Z");
    vi.mocked(getLocalWeatherPilotNow).mockReturnValue(Date.parse("2026-09-04T05:00:00Z"));
    const markup = renderToStaticMarkup(<LocalWeatherPilotBanner metadata={metadata} />);
    expect(markup).toContain("OROLOGIO METEO SIMULATO");
    expect(markup).toContain("sequenza scheduler accelerata");
    expect(markup).toContain("I puntatori locali possono avanzare");
    expect(markup).not.toContain("non si aggiorna automaticamente");
  });

  it("signals stale CAMS served from verified offline cache without degrading ICON", () => {
    const markup = renderToStaticMarkup(<LocalWeatherPilotBanner metadata={{
      ...metadata,
      cams_status: "stale",
      cams_freshness: { status: "stale" },
      cams_delivery: {
        provenance: "offline_cache",
        from_cache: true,
        network_fallback: true,
        fallback_reason: "transport_failure",
      },
    }} now="2026-09-03T16:00:00Z" />);
    expect(markup).toContain("CAMS · corsa");
    expect(markup).toContain("DATATO · cache offline verificata");
    expect(markup).toContain("ICON · corsa");
    expect(markup).not.toContain("CAMS NON DISPONIBILE");
  });

  it("keeps ICON visible while the asynchronous CAMS enrichment is pending", () => {
    const pendingMetadata = buildLocalWeatherPilotMetadata({
      primary_source: "icon2i_local_pilot",
      data_quality: {
        ...metadata,
        cams_status: "pending",
        cams_run_utc: null,
        cams_valid_at_utc: null,
      },
      source: { cams: { provider: "cams_europe_pollen", status: "pending" } },
      pollen_data: { status: "pending", diagnostic: null },
      hourly_forecast: [{ time: "2026-09-03T16:00:00Z", temperature: 22 }],
    });
    expect(pendingMetadata).toMatchObject({
      cams_pending: true,
      cams_available: false,
      cams_status: "pending",
      cams_product_status: "pending",
      cams_freshness: { status: null },
      cams_diagnostic: null,
    });

    const markup = renderToStaticMarkup(
      <LocalWeatherPilotBanner metadata={pendingMetadata} now="2026-09-03T16:00:00Z" />,
    );
    expect(markup).toContain("ICON-2I · CAMS IN CARICAMENTO");
    expect(markup).toContain("CAMS in caricamento asincrono");
    expect(markup).toContain("la previsione ICON è già visibile");
    expect(markup).toContain("Pollini CAMS in caricamento");
    expect(markup).not.toContain("CAMS NON DISPONIBILE");
    expect(markup).not.toContain("Pollini CAMS non disponibili");
    expect(markup).not.toContain("Pollini CAMS sperimentali");
  });

  it("keeps ICON visible without claiming CAMS or pollen when CAMS is unavailable", () => {
    const degraded = {
      ...metadata,
      cams_available: false,
      cams_status: "unavailable",
      cams_run_utc: null,
      cams_valid_at_utc: null,
      cams_diagnostic: { provider: "cams_europe_pollen", code: "HTTP_ERROR", stage: "manifest" },
    };
    const markup = renderToStaticMarkup(
      <LocalWeatherPilotBanner metadata={degraded} now="2026-09-03T16:00:00Z" />,
    );
    expect(markup).toContain("ICON-2I · CAMS NON DISPONIBILE");
    expect(markup).toContain("la previsione ICON resta visibile");
    expect(markup).toContain("Pollini CAMS non disponibili");
    expect(markup).not.toContain("ICON-2I + CAMS");
    expect(markup).not.toContain("Pollini CAMS sperimentali");
    expect(markup).not.toContain("Open-Meteo");
  });

  it("ages the source dynamically and does not reset freshness to retrieval time", () => {
    expect(getLocalPilotFreshness(metadata, "2026-09-03T19:00:00Z").label).toBe("Snapshot ICON datato");
    expect(getLocalPilotFreshness(metadata, "2026-09-04T07:00:00Z")).toMatchObject({
      label: "Snapshot ICON scaduto",
      coverageHours: 32,
      forecastPointCount: 33,
      forecastIntervalCount: 32,
    });
    const markup = renderToStaticMarkup(<LocalWeatherPilotBanner metadata={metadata} now="2026-09-04T07:00:00Z" />);
    expect(markup).toContain("Vista oraria ICON: 33 punti (32 intervalli orari)");
    expect(markup).not.toContain("insufficiente");
  });

  it("does not imply a loaded snapshot when data is unavailable", () => {
    const markup = renderToStaticMarkup(<LocalWeatherPilotBanner />);
    expect(markup).toContain("In attesa dello snapshot locale");
    expect(markup).toContain("Vista oraria ICON non verificabile");
    expect(markup).toContain("Disponibilità CAMS non ancora verificata");
    expect(markup).not.toContain("ICON-2I + CAMS");
    expect(markup).not.toContain("Pollini CAMS sperimentali");
  });

  it("shows the local load diagnostic without exposing it outside the pilot", () => {
    const markup = renderToStaticMarkup(
      <LocalWeatherPilotBanner error="ICON_UNAVAILABLE" now="2026-09-03T16:00:00Z" />,
    );
    expect(markup).toContain("Diagnostica locale: ICON_UNAVAILABLE");
    expect(markup).toContain('role="status"');

    vi.mocked(isLocalWeatherPilot).mockReturnValue(false);
    expect(renderToStaticMarkup(
      <LocalWeatherPilotBanner error="ICON_UNAVAILABLE" now="2026-09-03T16:00:00Z" />,
    )).toBe("");
  });

  it("only derives metadata from the exact pilot source and preserves source dates", () => {
    expect(buildLocalWeatherPilotMetadata({ primary_source: "open_meteo" })).toBeNull();
    expect(buildLocalWeatherPilotMetadata({ primary_source: "icon2i_local_pilot", data_quality: { ...metadata, cams_status: "stale" },
      source: { cams: { status: "available", evidence: {
        from_cache: true, not_modified: true, network_fallback: false,
        freshness: { status: "stale", freshUntil: "2026-09-03T00:00:00Z" },
      } } },
      pollen_data: { status: "experimental_model_snapshot", freshness: "stale" },
      hourly_forecast: [
        { time: "2026-09-04T10:00:00Z", temperature: 22 },
        { time: "2026-09-06T00:00:00Z", temperature: null },
      ] })).toMatchObject({
      run_utc: metadata.run_utc,
      first_forecast_at_utc: "2026-09-04T10:00:00.000Z",
      last_forecast_at_utc: "2026-09-04T10:00:00.000Z",
      forecast_point_count: 1,
      forecast_interval_count: 0,
      cams_available: true,
      cams_pending: false,
      cams_status: "stale",
      cams_product_status: "experimental_model_snapshot",
      cams_delivery: { provenance: "validated_cache", from_cache: true, not_modified: true },
      cams_freshness: { status: "stale", freshUntil: "2026-09-03T00:00:00Z" },
    });
  });

  it("carries the explicit degraded CAMS state into UI metadata", () => {
    const diagnostic = { provider: "cams_europe_pollen", status: "unavailable", code: "HTTP_ERROR" };
    expect(buildLocalWeatherPilotMetadata({
      primary_source: "icon2i_local_pilot",
      data_quality: { ...metadata, cams_status: "unavailable", cams_diagnostic: diagnostic },
      source: { cams: { status: "unavailable", diagnostic } },
      pollen_data: { status: "unavailable", diagnostic },
      hourly_forecast: [{ time: "2026-09-04T10:00:00Z", temperature: 22 }],
    })).toMatchObject({
      cams_available: false,
      cams_pending: false,
      cams_status: "unavailable",
      cams_diagnostic: diagnostic,
    });
  });
});
