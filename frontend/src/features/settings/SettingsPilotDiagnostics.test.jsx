import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, expect, it, vi } from "vitest";
import { SettingsView } from "./SettingsView";
import { isLocalWeatherPilot } from "../../services/localWeatherPilot";

const experience = vi.hoisted(() => vi.fn(() => false));

vi.mock("../../services/localWeatherPilot", () => ({
  isDefinitiveAppExperience: experience,
  isLocalWeatherPilot: experience,
  getLocalWeatherPilotNow: () => Date.now(),
  getLocalWeatherPilotTestNow: () => null,
}));
beforeEach(() => {
  vi.clearAllMocks();
  isLocalWeatherPilot.mockReturnValue(false);
});

function getSwitch(html, label) {
  const tag = (html.match(/<button[^>]*role="switch"[^>]*>/g) || [])
    .find((candidate) => candidate.includes(`aria-label="${label}"`));

  expect(tag).toBeTruthy();
  return tag;
}

function getSettingsRow(html, label) {
  const labelMarkup = `<span class="mf-settings-row__label">${label}</span>`;
  const labelStart = html.indexOf(labelMarkup);
  const rowStart = html.lastIndexOf('<div class="mf-settings-row', labelStart);
  const rowEnd = html.indexOf("</div>", labelStart);

  expect(labelStart).toBeGreaterThan(-1);
  expect(rowStart).toBeGreaterThan(-1);
  expect(rowEnd).toBeGreaterThan(labelStart);
  return html.slice(rowStart, rowEnd + "</div>".length);
}

it("keeps technical diagnostics out of the ordinary app", () => {
  isLocalWeatherPilot.mockReturnValue(false);
  const html = renderToStaticMarkup(<SettingsView />);
  expect(html).not.toContain("Diagnostica tecnica");
  expect(html).not.toContain("cache pilota");
  expect(html).toContain('src="/branding/icon_launcher_any_mf-r5-20260927-192.png"');
  expect(html).not.toContain('src="/brand/pilot-r4/meteo-eventi-friul-mark-192.png"');
});

it("uses three compact definitive groups without technical diagnostics", () => {
  isLocalWeatherPilot.mockReturnValue(true);
  const html = renderToStaticMarkup(<SettingsView />);

  expect(html).toContain("mf-tab-page--settings-pilot");
  expect(html).toContain('class="mf-tab-page__title--hidden"');
  expect(html).toContain("mf-settings-view--pilot");
  expect(html.match(/mf-settings-panel--pilot-group/g)).toHaveLength(3);
  expect(html.match(/mf-settings-identity/g)?.length).toBeGreaterThanOrEqual(1);
  expect(html).toContain('aria-labelledby="mf-settings-community-alias"');
  expect(html).toContain("Sentinella Meteo");
  expect(html).toContain("Senza registrazione • Nome ed email non richiesti");
  expect(html).toContain('aria-label="Cambia alias"');
  expect(html).toContain("Rango non disponibile");
  expect(html).not.toContain("Contributi oggi:");
  expect(html).toMatch(/Segnalazioni totali: <strong class="mf-settings-identity__stat-value">0<\/strong>/);
  expect(html.indexOf("mf-settings-identity"))
    .toBeLessThan(html.indexOf("mf-settings-panel mf-settings-panel--pilot-group"));
  expect(html).toContain("Preferenze generali");
  expect(html).toContain("Info e progetto");
  expect(html).toContain('aria-label="Lingua"');
  expect(html).toContain('aria-pressed="true" class="mf-settings-segment is-active" type="button">Italiano');
  expect(html).toContain('aria-pressed="false" class="mf-settings-segment" type="button">Furlan');
  expect(html).not.toContain("Lingua: Furlan");
  expect(html.match(/role="switch"/g)).toHaveLength(3);
  expect(html.match(/data-pilot-web-read-only="true"/g)).toHaveLength(2);
  expect(html).toContain("Solo nell’app Android");
  expect(getSwitch(html, "Allerte: Solo nell’app Android")).toContain('aria-checked="false"');
  expect(getSwitch(html, "Allerte: Solo nell’app Android")).toContain("disabled");
  expect(getSwitch(html, "Avvisi: Solo nell’app Android")).toContain('aria-checked="false"');
  expect(getSwitch(html, "Avvisi: Solo nell’app Android")).toContain("disabled");
  expect(html).not.toContain("Le notifiche Web non sono attive in questa fase");
  expect(html).toContain('aria-label="Sostieni su Ko-fi"');
  expect(html).toContain('href="https://ko-fi.com/meteofriul"');
  expect(html).toContain("Aiuta Meteo Friûl a restare attiva, affidabile e aggiornata.");
  expect(html).not.toMatch(/pubblicitari|promozionali|sponsorizzati/i);
  expect(html).not.toContain("mf-settings-diagnostics");
  expect(html).not.toContain("Diagnostica tecnica");
  expect(html).not.toContain("cache pilota");
  expect(html).toContain('src="/brand/pilot-r4/meteo-eventi-friul-mark-192.png"');
  expect(html).not.toContain('src="/brand/meteo-eventi-friul-text-header.png"');
  expect(html).not.toContain('src="/branding/icon_launcher_any_mf-r5-20260927-192.png"');
  expect(html).toContain("mf-settings-product-link--brand");
  expect(html).toContain("mf-settings-row--alert");
  expect(html).toContain("mf-settings-row--notice");
  expect(html).toContain("mf-settings-product-link--privacy");
  expect(html).toContain("mf-settings-row--cache");
  expect(html).toContain("mf-settings-product-link--support");
  expect(html).toContain("lucide-triangle-alert");
  expect(html).toContain("lucide-shield-check");
  expect(html).toContain("lucide-eraser");
  expect(html).toContain("lucide-bell-ring");
  expect(html).toContain("lucide-heart-handshake");
  expect(html).not.toContain("lucide-gauge");
  expect(html).not.toContain("lucide-shield-alert");
  expect(html).not.toContain("lucide-trash-2");
  expect(html).not.toContain("lucide-database");
});

it.each([
  ["it", "Località predefinita", "Pordenone (PN)", "Cambia", "Comune di"],
  ["fur", "Localitât predefinide", "Pordenon (PN)", "Cambie", "Comun di"],
])("keeps the pilot default location concise and aligned in %s", (
  language,
  label,
  expectedLocation,
  actionLabel,
  redundantPrefix,
) => {
  isLocalWeatherPilot.mockReturnValue(true);
  const html = renderToStaticMarkup(
    <SettingsView
      activeLocation={{
        city: "Pordenone",
        displayName: "Pordenone",
        istatCode: "093033",
        province: "PN",
        municipality: {
          istatCode: "093033",
          name: "Pordenone",
          province: "PN",
        },
      }}
      language={language}
    />,
  );
  const row = getSettingsRow(html, label);

  expect(row).toContain("mf-settings-row--default-location");
  expect(row).toContain(`<span class="mf-settings-row__value">${expectedLocation}</span>`);
  expect(row.match(new RegExp(expectedLocation.replace(/[()]/g, "\\$&"), "g"))).toHaveLength(1);
  expect(row).toContain(`aria-label="${actionLabel}"`);
  expect(row.indexOf(expectedLocation)).toBeLessThan(row.indexOf(`aria-label="${actionLabel}"`));
  expect(row).not.toContain("mf-settings-row__description");
  expect(row).not.toContain(redundantPrefix);
});

it("keeps the ordinary settings structure outside the pilot", () => {
  isLocalWeatherPilot.mockReturnValue(false);
  const html = renderToStaticMarkup(<SettingsView />);

  expect(html).not.toContain("mf-tab-page--settings-pilot");
  expect(html).not.toContain("mf-settings-view--pilot");
  expect(html).not.toContain("mf-settings-panel--pilot-group");
  expect(html).not.toContain("mf-settings-identity");
  expect(html).not.toContain("data-pilot-web-read-only");
  expect(html).toContain('aria-label="Lingua: Furlan"');
  expect(getSwitch(html, "Disattiva Allerte")).toContain('aria-checked="true"');
  expect(getSwitch(html, "Disattiva Avvisi")).toContain('aria-checked="true"');
  expect(html).toContain("mf-settings-panel--support");
});

it("keeps the real notification state in the pilot Android app", () => {
  isLocalWeatherPilot.mockReturnValue(true);
  const html = renderToStaticMarkup(
    <SettingsView
      notificationPreferences={{ officialAlerts: true, weatherNotices: true }}
      notificationRuntime={{ connected: true, platform: "android", readOnly: false, status: "connected" }}
    />,
  );

  expect(html).not.toContain("data-pilot-web-read-only");
  expect(getSwitch(html, "Disattiva Allerte")).toContain('aria-checked="true"');
  expect(getSwitch(html, "Disattiva Allerte")).not.toContain("disabled");
  expect(getSwitch(html, "Disattiva Avvisi")).toContain('aria-checked="true"');
  expect(getSwitch(html, "Disattiva Avvisi")).not.toContain("disabled");
});

it("localizes the compact pilot groups in Furlan", () => {
  isLocalWeatherPilot.mockReturnValue(true);
  const html = renderToStaticMarkup(<SettingsView language="fur" />);

  expect(html).toContain("Preferencis gjenerâls");
  expect(html).toContain("Sentinele Meteo");
  expect(html).toContain("Cence regjistrazion • Non e e-mail no coventin");
  expect(html).toContain("Ranc no disponibil");
  expect(html).toContain("Segnalazions totâls:");
  expect(html).toContain('aria-label="Cambie alias"');
  expect(html).toContain("Notifichis");
  expect(html).toContain("Informazions e progjet");
  expect(html).toContain('aria-label="Lenghe"');
  expect(html).toContain(">Italian</button>");
  expect(html).toContain(">Furlan</button>");
  expect(html).toContain("Dome te app Android");
  expect(html).toContain("Sosten Meteo Friûl");
  expect(html).toContain("Jude Meteo Friûl a restâ atîf, afidabil e inzornât.");
  expect(html).not.toMatch(/publicitaris|promozionâi|sponsorizâts/i);
  expect(html).not.toContain("Diagnostiche tecniche");
  expect(html).not.toContain("cache pilot");
});
