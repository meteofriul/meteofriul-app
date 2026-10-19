import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { BackgroundLocationDisclosure } from "./BackgroundLocationDisclosure";
import { getBackgroundLocationDisclosureCopy } from "./backgroundLocationDisclosureCopy";
import {
  getAutomaticLocationToggleAction,
  getNotificationToggleAction,
} from "./notificationToggleAction";
import { SettingsView } from "./SettingsView";

function getVersionFooter(html) {
  const footers = html.match(/<footer\b[^>]*class="[^"]*\bmf-settings-version\b[^"]*"[^>]*>[\s\S]*?<\/footer>/g) || [];

  expect(footers).toHaveLength(1);
  return footers[0];
}

function getVersionText(html) {
  return getVersionFooter(html).replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
}

describe("SettingsView", () => {
  it.each(["it", "fur"])("shows only the installed Android version in %s", (language) => {
    const html = renderToStaticMarkup(
      <SettingsView appVersion={{ platform: "android", version: "0.1.13+300030" }} language={language} />,
    );

    expect(getVersionText(html)).toBe("0.1.13");
    expect(html).not.toContain("mf-settings-row--version");
  });

  it.each(["it", "fur"])("places the minimal %s version footer last, after support and outside every panel", (language) => {
    const html = renderToStaticMarkup(
      <SettingsView appVersion={{ platform: "android", version: "1.0.1+300012" }} language={language} />,
    );
    const footer = getVersionFooter(html);
    const footerStart = html.indexOf(footer);
    const supportStart = html.indexOf("mf-settings-panel--support");

    expect(supportStart).toBeGreaterThan(-1);
    expect(footerStart).toBeGreaterThan(supportStart);
    expect(html.slice(0, footerStart)).toMatch(/<\/section>\s*$/);
    expect(html.slice(footerStart + footer.length)).toMatch(/^\s*<\/div>\s*<\/section>\s*$/);
    expect(footer).not.toContain("mf-settings-row");
    expect(footer).not.toContain("mf-settings-panel");
    expect(footer).not.toContain("lucide-");
    expect(footer).not.toMatch(/<(?:svg|img|button|a|h[1-6])\b/);
  });

  it.each([
    ["it", "unknown", "Non disponibile"],
    ["it", "", "Non disponibile"],
    ["fur", undefined, "No disponibile"],
  ])("does not invent a native version when unavailable (%s, %s)", (language, version, expected) => {
    const html = renderToStaticMarkup(
      <SettingsView appVersion={{ platform: "android", version }} language={language} />,
    );

    expect(getVersionText(html)).toBe(`${language === "fur" ? "Version" : "Versione"} ${expected} · Android`);
    expect(getVersionText(html)).not.toContain("unknown");
    expect(html).not.toContain("300012");
  });

  it.each(["1.0.0-private.4", "1.0.1-private.4+300012"])("preserves private identity without exposing the build number %s", (version) => {
    const html = renderToStaticMarkup(
      <SettingsView appVersion={{ platform: "android", version }} />,
    );

    expect(getVersionText(html)).toBe(version.replace(/\+\d+$/, ""));
  });

  it.each([
    ["it", true, "Anteprima Web"],
    ["fur", true, "Anteprime Web"],
    ["it", false, "Web"],
    ["fur", false, "Web"],
  ])("distinguishes the Web package from Android (%s, preview %s)", (language, development, label) => {
    const html = renderToStaticMarkup(
      <SettingsView appVersion={{ platform: "web", version: "1.0.0", development }} language={language} />,
    );

    expect(getVersionText(html)).toBe(`${language === "fur" ? "Version" : "Versione"} 1.0.0 · ${label}`);
    expect(getVersionText(html)).not.toContain("Android");
    expect(html).not.toContain("300012");
  });

  it.each([
    ["it", "Versione Non disponibile · Web"],
    ["fur", "Version No disponibile · Web"],
  ])("keeps a localized minimal footer when version information is absent in %s", (language, expected) => {
    const html = renderToStaticMarkup(<SettingsView language={language} />);

    expect(getVersionText(html)).toBe(expected);
    expect(getVersionFooter(html)).not.toMatch(/<(?:svg|img)\b/);
    expect(getVersionText(html)).not.toContain("unknown");
    expect(html).not.toContain("300012");
  });

  it("uses the prominent Play disclosure before opening background-location settings", () => {
    const html = renderToStaticMarkup(
      <BackgroundLocationDisclosure
        copy={getBackgroundLocationDisclosureCopy("it")}
        onCancel={() => {}}
        onContinue={() => {}}
      />,
    );

    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain("raccoglie dati sulla posizione");
    expect(html).toContain("anche quando l’app è chiusa o non è in uso");
    expect(html).toContain("aggiornare il Comune degli Avvisi meteo locali");
    expect(html).toContain("preparare il meteo della località");
    expect(html).toContain("non vengono conservate nel profilo sul server");
    expect(html).toContain("non un tracciamento continuo");
    expect(html).toContain(">Continua nelle impostazioni</button>");
    expect(html).toContain(">Non ora</button>");
  });

  it("uses a direct Continue action before the startup GPS prompt", () => {
    const html = renderToStaticMarkup(
      <BackgroundLocationDisclosure
        context="startup"
        copy={getBackgroundLocationDisclosureCopy("it", { context: "startup" })}
        onCancel={() => {}}
        onContinue={() => {}}
      />,
    );

    expect(html).toContain(">Continua</button>");
    expect(html).not.toContain("Continua nelle impostazioni");
    expect(html).toContain("mf-settings-disclosure--startup");
    expect(html).toContain("lucide-map-pin");
    expect(html).toContain("non un tracciamento continuo");
  });

  it("combines privacy, sources and credits in the public information link", () => {
    const html = renderToStaticMarkup(
      <SettingsView activeLocation={{ city: "Pordenone" }} language="it" />,
    );

    expect(html).toContain("Informazioni");
    expect(html).toContain("Tema");
    expect(html).toContain("Informativa privacy, fonti e crediti");
    expect(html).toContain("Dati, permessi, contenuti e immagini");
    expect(html).toContain("Sostieni Meteo Friûl");
    expect(html.match(/Sostieni Meteo Friûl/g)).toHaveLength(1);
    expect(html).toContain(
      "Se Meteo Friûl ti è utile, puoi contribuire volontariamente ai costi dei servizi",
    );
    expect(html).not.toMatch(/pubblicitari|promozionali|sponsorizzati/i);
    expect(html).toContain("costi dei servizi");
    expect(html).toContain("mantenerla attiva, affidabile e aggiornata");
    expect(html).toContain("Nessuna funzione riservata");
    expect(html).not.toContain("Contributi non ancora attivi");
    expect(html).toContain("Sostieni su Ko-fi");
    expect(html).toContain('data-support-state="ready"');
    expect(html).toContain('href="https://ko-fi.com/meteofriul"');
    expect(html).toContain("lucide-heart-handshake");
    expect(html).toContain("mf-settings-panel--support");
    expect(html).toContain("mf-settings-panel__heading");
    expect(html).toContain("mf-settings-panel__leading-icon");
    expect(html).not.toContain("mf-settings-support__icon");
    expect(html).toContain("Meteo Friûl");
    expect(html).toContain("meteofriul.it");
    expect(html).toContain('href="https://meteofriul.it"');
    expect(html).toContain('src="/branding/icon_launcher_any_mf-r5-20260927-192.png"');
    expect(html).toContain('aria-label="Apri il sito Meteo Friûl"');
    expect(html).toContain(">Informativa privacy, fonti e crediti</strong>");
    expect(html).toContain('aria-label="Apri l’informativa privacy, fonti e crediti"');
    expect(html).toContain('href="https://meteofriul.it/privacy/"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).toContain(">Cache<");
    expect(html).not.toContain("Privacy e permessi");
    expect(html).not.toContain("Posizione e notifiche");
    expect(html).not.toContain("Preferenze");
    expect(html).not.toContain("Interfaccia e contenuti disponibili.");
    expect(html).not.toContain("Tema dell'app.");
    expect(html).not.toContain("Dati e aggiornamenti");
    expect(html).not.toContain("Bollettino OSMER");
    expect(html).not.toContain("Dati salvati");
    expect(html).not.toContain("Meteo, bollettino, eventi");
    expect(html).not.toContain("ARPA FVG - OSMER");
    expect(html).toContain("Apri");
    expect(html).not.toContain("aria-label=\"Apri\"");
    expect(html).not.toContain(">Apri</span>");
    expect(html).toContain("mf-settings-row__description");
    expect(html).toContain("lucide-navigation");
    expect(html).toContain("lucide-languages");
    expect(html).toContain("lucide-eraser");
    expect(html).toContain("mf-settings-row--prominent");
    expect(html).not.toContain("lucide-book-open");
    expect(html).toContain("lucide-triangle-alert");
    expect(html).toContain("lucide-shield-check");
    expect(html).toContain("lucide-bell-ring");
    expect(html).not.toContain("lucide-shield-alert");
    expect(html).not.toContain("lucide-trash-2");
    expect(html).not.toContain("lucide-database");
    expect(html).toContain("role=\"switch\"");
    expect(html).toContain("aria-label=\"Disattiva Allerte\"");
    expect(html).toContain("aria-label=\"Disattiva Avvisi\"");
    expect(html).toContain("aria-label=\"Lingua: Furlan\"");
    expect(html).toContain(">Italiano<");
    expect(html).not.toContain("data-notification-runtime");
    expect(html).not.toContain("Questo browser non supporta le notifiche web");
    const switches = html.match(/<button[^>]*role="switch"[^>]*>/g) || [];
    expect(switches).toHaveLength(4);
    const locationSwitch = switches.find((button) => button.includes('aria-label="Attiva Posizione"'));
    const languageSwitch = switches.find((button) => button.includes("Lingua: Furlan"));
    expect(locationSwitch).toBeDefined();
    expect(languageSwitch).toBeDefined();
    expect(locationSwitch).not.toContain("disabled");
    expect(languageSwitch).not.toContain("disabled");
    expect(switches
      .filter((button) => (
        !button.includes('aria-label="Attiva Posizione"')
        && !button.includes("Lingua: Furlan")
      ))
      .every((button) => button.includes("disabled")))
      .toBe(true);
    expect(html).toMatch(/aria-pressed="true"[^>]*>Sistema<\/button>/);
    expect(html).not.toContain("Avvisi locali");
    expect(html).not.toContain("Aggiornamento manuale");
    expect(html).not.toContain("Crediti immagini");
    expect(html).not.toContain("mf-image-credits-list");
    expect(html.indexOf("Informazioni")).toBeLessThan(html.indexOf("Sostieni Meteo Friûl"));
  });

  it("renders disabled notification preferences independently", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        language="it"
        notificationPreferences={{ officialAlerts: false, weatherNotices: true }}
      />,
    );

    expect(html).toContain("aria-label=\"Attiva Allerte\"");
    expect(html).toContain("aria-checked=\"false\"");
    expect(html).toContain("aria-label=\"Disattiva Avvisi\"");
    expect(html).toContain("aria-checked=\"true\"");
  });

  it.each([
    ["it", "Disponibili solo in Friuli Venezia Giulia"],
    ["fur", "Disponibilis dome in Friûl Vignesie Julie"],
  ])("keeps OSMER alerts visibly unavailable outside FVG in %s", (language, unavailableCopy) => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{
          city: "Roma",
          countryCode: "IT",
          region: "Lazio",
          regionCode: "IT-62",
        }}
        language={language}
        notificationPreferences={{ officialAlerts: true, weatherNotices: true }}
        notificationRuntime={{
          connected: true,
          permission: "granted",
          platform: "android",
          readOnly: false,
          status: "connected",
        }}
        productScope={{ sources: { osmer: { status: "unsupported" } } }}
      />,
    );

    const alertSwitch = (html.match(/<button[^>]*role="switch"[^>]*>/g) || [])
      .find((button) => button.includes(language === "fur" ? "Alertis:" : "Allerte:"));
    const noticeSwitch = (html.match(/<button[^>]*role="switch"[^>]*>/g) || [])
      .find((button) => button.includes(language === "fur" ? "Avîs" : "Avvisi"));

    expect(html).toContain(unavailableCopy);
    expect(alertSwitch).toContain('aria-checked="false"');
    expect(alertSwitch).toContain("disabled");
    expect(noticeSwitch).toContain('aria-checked="true"');
    expect(noticeSwitch).not.toContain("disabled");
  });

  it("offers a separate, initially off national alert choice for an exact manual Android municipality", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{
          city: "Roma",
          countryCode: "IT",
          municipality: { istatCode: "058091", name: "Roma" },
          regionCode: "IT-62",
          source: "manual",
        }}
        language="it"
        notificationPreferences={{ officialAlerts: true, weatherNotices: true }}
        notificationRuntime={{ permission: "granted", platform: "android", readOnly: false }}
        productScope={{ sources: {
          nationalAlerts: { status: "enabled" },
          osmer: { status: "unsupported" },
        } }}
      />,
    );

    expect(html).toContain("Allerte per Roma");
    expect(html).toContain("non alla posizione GPS");
    expect(html).toContain('aria-label="Attiva Allerte per Roma"');
    expect(html).toMatch(/aria-checked="false" aria-label="Attiva Allerte per Roma"/);
    expect(html).not.toContain("Disponibili solo in Friuli Venezia Giulia");
  });

  it.each(["web", "android"])('keeps national alerts unavailable without an Android manual choice (%s)', (platform) => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{
          city: "Roma",
          countryCode: "IT",
          municipality: { istatCode: "058091", name: "Roma" },
          regionCode: "IT-62",
          source: platform === "web" ? "manual" : "capacitor_geolocation",
        }}
        notificationPreferences={{ nationalOfficialAlerts: true, officialAlerts: true }}
        notificationRuntime={{ permission: "granted", platform, readOnly: false }}
        productScope={{ sources: {
          nationalAlerts: { status: "enabled" },
          osmer: { status: "unsupported" },
        } }}
      />,
    );

    expect(html).not.toContain("Allerte per Roma");
    expect(html).toMatch(/aria-checked="false" aria-label="Allerte:/);
  });

  it("keeps the compact preference labels in Furlan", () => {
    const html = renderToStaticMarkup(
      <SettingsView activeLocation={{ city: "Pordenone" }} language="fur" />,
    );

    expect(html).toContain("Lenghe");
    expect(html).toContain('aria-checked="true" aria-label="Lenghe: Italian"');
    expect(html).toContain(">Furlan<");
    expect(html).toContain("Teme");
    expect(html).toContain("Pordenon");
    expect(html).toContain("Sosten Meteo Friûl");
    expect(html).toContain("coscj dai servizis");
    expect(html).not.toContain("I contribûts no son ancjemò atîfs");
    expect(html).toContain('aria-label="Vierç il sît Meteo Friûl"');
    expect(html).toContain(">Informative su la privacy, fonts e credits</strong>");
    expect(html).toContain('aria-label="Vierç la informative su la privacy, fonts e credits"');
    expect(html).toContain('href="https://meteofriul.it/fur/privacy/"');
    expect(html).toContain(
      "Se Meteo Friûl ti covente, tu puedis contribuî in mût volontari ai coscj dai servizis",
    );
    expect(html).not.toMatch(/publicitaris|promozionâi|sponsorizâts/i);
    expect(html).not.toContain("Preferencis");
    expect(html).not.toContain("Interface e contignûts disponibii.");
  });

  it("shows the active locality with its municipality as administrative context", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{
          city: "Fontanafredda",
          displayName: "Vigonovo",
          locality: { id: "irdat:vigonovo", name: "Vigonovo" },
          municipality: {
            istatCode: "093022",
            name: "Fontanafredda",
            province: "PN",
          },
        }}
        autoLocationEnabled
        deviceLocationStatus={{
          status: "success",
          city: "Fontanafredda",
          displayName: "Vigonovo",
        }}
        language="it"
      />,
    );

    expect(html.match(/>Località</g)).toHaveLength(1);
    expect(html).toContain("Vigonovo");
    expect(html.match(/>Vigonovo</g)).toHaveLength(1);
    expect(html).toContain("Comune di Fontanafredda (PN)");
    expect(html).toContain(">Attiva<");
  });

  it("shows a disabled Ko-fi call to action until a support URL is configured", () => {
    const html = renderToStaticMarkup(
      <SettingsView activeLocation={{ city: "Pordenone" }} language="it" supportUrl={null} />,
    );
    const supportBlock = html.match(
      /<div class="mf-settings-support" data-support-state="preview">[\s\S]*?<\/div>/,
    )?.[0];

    expect(supportBlock).toBeTruthy();
    expect(supportBlock).not.toContain("<a");
    expect(supportBlock).toContain("<button");
    expect(supportBlock).toContain("disabled");
    expect(supportBlock).toContain("Sostieni su Ko-fi");
    expect(supportBlock).not.toContain("href=");
    expect(supportBlock).not.toMatch(/stripe|paypal|buymeacoffee|data-payment/i);
  });

  it("opens only a configured HTTPS Ko-fi URL outside the app", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        language="it"
        supportUrl="https://ko-fi.com/meteofriul"
      />,
    );

    expect(html).toContain('data-support-state="ready"');
    expect(html).toContain('href="https://ko-fi.com/meteofriul"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).not.toContain("Contributi non ancora attivi");
  });

  it("delegates a configured Ko-fi destination to the external-open adapter", () => {
    let openedUrl = null;
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        language="it"
        onSupportOpen={(url) => {
          openedUrl = url;
        }}
        supportUrl="https://ko-fi.com/meteofriul"
      />,
    );

    expect(html).toContain('href="https://ko-fi.com/meteofriul"');
    expect(html).toContain('target="_blank"');
    expect(openedUrl).toBeNull();
  });

  it("rejects a non-Ko-fi support URL", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        language="it"
        supportUrl="https://ko-fi.com.example.org/not-ko-fi"
      />,
    );

    expect(html).toContain('data-support-state="preview"');
    expect(html).not.toContain('href="https://ko-fi.com.example.org/not-ko-fi"');
  });

  it("keeps transient Android notification registration silent", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        language="it"
        notificationRuntime={{ connected: false, platform: "android", status: "connecting" }}
      />,
    );

    expect(html).not.toContain("data-notification-runtime");
    expect(html).not.toContain("Collegamento notifiche in corso");
    const androidSwitches = html.match(/<button[^>]*role="switch"[^>]*>/g) || [];
    expect(androidSwitches).toHaveLength(4);
    expect(androidSwitches.every((button) => !button.includes("disabled"))).toBe(true);
  });

  it("hides redundant notification status when the device is connected", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        language="it"
        notificationRuntime={{ connected: true, platform: "android", status: "connected" }}
      />,
    );

    expect(html).not.toContain("data-notification-runtime");
    expect(html).not.toContain("Allerte attive su questo dispositivo");
    expect(html).not.toContain("Avvisi meteo in verifica");
  });

  it("does not claim local coverage without an eligible canonical target", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Claut" }}
        language="it"
        notificationRuntime={{
          connected: true,
          localTargetEligible: false,
          platform: "android",
          status: "connected",
        }}
      />,
    );

    expect(html).toContain("Allerte attive");
    expect(html).toContain("scegli un Comune valido o aggiorna la posizione");
    expect(html).not.toContain("Avvisi meteo in verifica");
  });

  it("does not claim official alerts when only weather notices lack a valid target", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Claut" }}
        language="it"
        notificationPreferences={{ officialAlerts: false, weatherNotices: true }}
        notificationRuntime={{
          connected: true,
          localTargetEligible: false,
          platform: "android",
          status: "connected",
        }}
      />,
    );

    expect(html).toContain("Per ricevere gli Avvisi scegli un Comune valido");
    expect(html).not.toContain("Allerte attive");
  });

  it("keeps background permission inside the automatic-location row", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Fontanafredda", displayName: "Vigonovo" }}
        autoLocationEnabled
        backgroundLocationRuntime={{
          available: true,
          backgroundPermission: false,
          configured: false,
          trackingActive: false,
        }}
        language="it"
        notificationRuntime={{
          connected: true,
          platform: "android",
          status: "connected",
        }}
        onBackgroundLocationSettingsOpen={() => {}}
      />,
    );

    expect(html).toContain('data-background-location-status="permission_required"');
    expect(html).toContain(">Consenti sempre<");
    expect(html).toContain('aria-checked="true" aria-label="Disattiva Posizione"');
    expect(html).not.toContain(">Posizione sempre<");
    expect(html).not.toContain("Posizione per gli Avvisi");
    expect(html).not.toContain("Android rileva periodicamente la posizione");
    expect(html).not.toContain("Ultima verifica");
  });

  it("shows the compact active status under automatic location", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Fontanafredda", displayName: "Vigonovo" }}
        autoLocationEnabled
        backgroundLocationRuntime={{
          available: true,
          backgroundPermission: true,
          configured: true,
          lastDisplayName: "Vigonovo",
          lastSuccessAt: Date.UTC(2026, 7, 17, 10, 20),
          trackingActive: true,
        }}
        language="it"
        notificationRuntime={{ connected: true, platform: "android", status: "connected" }}
      />,
    );

    expect(html).toContain('data-background-location-status="active"');
    expect(html).toContain("Attiva anche ad app chiusa");
    expect(html).not.toContain("Posizione per gli Avvisi");
    expect(html).not.toContain("Ultima verifica");
    expect(html).not.toContain("45.99");
    expect(html).not.toContain("12.55");
    expect(html).toContain('aria-checked="true" aria-label="Disattiva Posizione"');
  });

  it("uses the singular active background-location status in Furlan", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        autoLocationEnabled
        backgroundLocationRuntime={{
          available: true,
          backgroundPermission: true,
          configured: true,
          trackingActive: true,
        }}
        language="fur"
        notificationRuntime={{ connected: true, platform: "android", status: "connected" }}
      />,
    );

    expect(html).toContain("Ative ancje cu la app sierade");
    expect(html).not.toContain("Atîfs ancje cu la app sierade");
  });

  it("keeps the automatic-location row off when the location mode is disabled", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        backgroundLocationRuntime={{
          available: true,
          backgroundPermission: false,
          configured: false,
          trackingActive: false,
        }}
        language="it"
        notificationRuntime={{ connected: true, platform: "android", status: "connected" }}
        onBackgroundLocationSettingsOpen={() => {}}
      />,
    );

    expect(html).toContain('data-background-location-status="automatic_location_required"');
    expect(html).toContain("Non rilevata");
    expect(html).toContain('aria-checked="false" aria-label="Attiva Posizione"');
    expect(html).not.toContain(">Posizione sempre<");
  });

  it("keeps foreground location active while first-run notification registration completes", () => {
    const transitioningHtml = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        autoLocationEnabled
        backgroundLocationRuntime={{
          available: true,
          backgroundPermission: true,
          configured: false,
          trackingActive: false,
        }}
        language="it"
        notificationRuntime={{
          connected: false,
          permission: "granted",
          platform: "android",
          status: "registering",
        }}
      />,
    );
    const failedHtml = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        autoLocationEnabled
        backgroundLocationRuntime={{
          available: true,
          backgroundPermission: false,
          configured: false,
          lastStatus: "settings_unavailable",
          trackingActive: false,
        }}
        language="it"
        notificationRuntime={{ connected: true, platform: "android", status: "connected" }}
      />,
    );

    expect(transitioningHtml).toContain('data-background-location-status="checking"');
    expect(transitioningHtml).toContain(">Attiva<");
    expect(transitioningHtml).not.toContain("Attivazione in corso");
    expect(transitioningHtml).not.toContain("temporaneamente non disponibile");
    expect(failedHtml).toContain('data-background-location-status="error"');
    expect(failedHtml).toContain("Posizione in background temporaneamente non disponibile");
    expect(failedHtml).toContain('aria-checked="true" aria-label="Disattiva Posizione"');
  });

  it("hides the background status and settings action when Avvisi are disabled", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        autoLocationEnabled
        backgroundLocationRuntime={{
          available: true,
          backgroundPermission: false,
          configured: false,
          trackingActive: false,
        }}
        language="it"
        notificationPreferences={{ officialAlerts: true, weatherNotices: false }}
        notificationRuntime={{ connected: true, platform: "android", status: "connected" }}
        onBackgroundLocationSettingsOpen={() => {}}
      />,
    );

    expect(html).not.toContain("data-background-location-status");
    expect(html).not.toContain(">Posizione sempre<");
  });

  it("routes the Android permission prompt through the two notification switches", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        language="it"
        notificationRuntime={{
          connected: false,
          permission: "prompt",
          platform: "android",
          status: "permission_prompt",
        }}
      />,
    );

    expect(html).toContain('data-notification-runtime="android_permission_prompt"');
    expect(html).toContain("Autorizza le notifiche");
    expect(html).toContain('aria-label="Attiva Allerte"');
    expect(html).toContain('aria-label="Attiva Avvisi"');
    expect(html).not.toContain(">Autorizza notifiche</button>");
  });

  it("opens Android settings only for an enable gesture after permission was denied", () => {
    expect(getNotificationToggleAction({
      enabled: true,
      permission: "denied",
      platform: "android",
    })).toBe("open_settings");
    expect(getNotificationToggleAction({
      enabled: false,
      permission: "denied",
      platform: "android",
    })).toBe("update_preference");
    expect(getNotificationToggleAction({
      enabled: true,
      permission: "granted",
      platform: "android",
    })).toBe("update_preference");
    expect(getNotificationToggleAction({
      enabled: true,
      permission: "denied",
      platform: "web",
    })).toBe("update_preference");
    expect(getNotificationToggleAction({
      enabled: true,
      permission: "prompt",
      platform: "android",
    })).toBe("request_permission");
  });

  it("opens background settings instead of disabling an already automatic location", () => {
    expect(getAutomaticLocationToggleAction({
      autoLocationEnabled: true,
      backgroundLocationState: "permission_required",
      enabled: true,
    })).toBe("open_background_settings");
    expect(getAutomaticLocationToggleAction({
      autoLocationEnabled: true,
      backgroundLocationState: "active",
      enabled: false,
    })).toBe("disable_location");
    expect(getAutomaticLocationToggleAction({
      autoLocationEnabled: false,
      backgroundLocationState: "automatic_location_required",
      enabled: true,
    })).toBe("enable_location");
  });

  it("shows blocked Android notifications as off without a permanent settings link", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        language="it"
        notificationPreferences={{ officialAlerts: true, weatherNotices: true }}
        notificationRuntime={{
          connected: false,
          permission: "denied",
          platform: "android",
          status: "permission_denied",
        }}
      />,
    );

    expect(html).toContain('data-notification-runtime="android_permission_denied"');
    expect(html).toContain("Notifiche bloccate nelle impostazioni Android");
    expect(html).toContain('aria-label="Attiva Allerte"');
    expect(html).toContain('aria-label="Attiva Avvisi"');
    expect(html).not.toContain(">Autorizza notifiche</button>");
  });

  it("does not request notification permission when both preferences are disabled", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        language="it"
        notificationPreferences={{ officialAlerts: false, weatherNotices: false }}
        notificationRuntime={{
          connected: false,
          permission: "prompt",
          platform: "android",
          status: "permission_prompt",
        }}
      />,
    );

    expect(html).not.toContain("data-notification-runtime");
    expect(html).not.toContain(">Autorizza notifiche</button>");
  });

  it("enables configured web preferences and an explicit browser permission action", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        language="it"
        notificationRuntime={{
          connected: false,
          permission: "prompt",
          platform: "web",
          readOnly: false,
          status: "permission_prompt",
        }}
      />,
    );

    expect(html).toContain('data-notification-runtime="web_permission_prompt"');
    expect(html).toContain("Autorizza le notifiche");
    const webSwitches = html.match(/<button[^>]*role="switch"[^>]*>/g) || [];
    expect(webSwitches).toHaveLength(4);
    expect(webSwitches.every((button) => !button.includes("disabled"))).toBe(true);
    expect(html).toContain(">Autorizza notifiche</button>");
  });

  it("keeps Web notification controls read-only while enrollment is Android-only", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        language="it"
        notificationRuntime={{
          connected: false,
          permission: "unsupported",
          platform: "web",
          readOnly: true,
          reason: "web_enrollment_disabled",
          status: "not_configured",
        }}
      />,
    );

    expect(html).toContain('data-notification-runtime="web_enrollment_disabled"');
    expect(html).toContain("Le notifiche Web non sono attive in questa fase");
    expect(html).toContain("app Android Meteo Friûl");
    expect(html).not.toContain(">Autorizza notifiche</button>");
    const webSwitches = html.match(/<button[^>]*role="switch"[^>]*>/g) || [];
    expect(webSwitches).toHaveLength(4);
    expect(webSwitches.filter((button) => button.includes("disabled"))).toHaveLength(2);
  });

  it("shows only allowlisted Web Push diagnostics with actionable copy", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        language="it"
        notificationRuntime={{
          connected: false,
          errorCategory: "fcm",
          errorCode: "messaging/fid-registration-failed",
          platform: "web",
          readOnly: false,
          status: "error",
        }}
      />,
    );

    expect(html).toContain('data-notification-runtime="web_error"');
    expect(html).toContain('data-notification-error-category="fcm"');
    expect(html).toContain('data-notification-error-code="messaging/fid-registration-failed"');
    expect(html).toContain("Firebase non ha completato la registrazione");
    expect(html).toContain("Riferimento tecnico: messaging/fid-registration-failed");

    const unknownHtml = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        language="it"
        notificationRuntime={{
          connected: false,
          errorCategory: "unknown",
          errorCode: "secret/raw-error",
          platform: "web",
          readOnly: false,
          status: "error",
        }}
      />,
    );
    expect(unknownHtml).toContain("Collegamento non riuscito");
    expect(unknownHtml).not.toContain("secret/raw-error");
  });

  it("presents automatic location as an explicit mode that can be disabled", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Pordenone", source: "browser_geolocation" }}
        autoLocationEnabled
        deviceLocationStatus={{ status: "success", city: "Pordenone" }}
        language="it"
      />,
    );

    expect(html).toContain(">Attiva<");
    expect(html).toContain('aria-label="Disattiva Posizione"');
    expect(html).not.toContain('aria-label="Aggiorna posizione"');
  });

  it("keeps a previous GPS fix separate after a manual municipality is selected", () => {
    const html = renderToStaticMarkup(
      <SettingsView
        activeLocation={{ city: "Trieste", source: "manual" }}
        autoLocationEnabled={false}
        deviceLocationStatus={{ status: "last_known", city: "Pordenone" }}
        language="it"
      />,
    );

    expect(html).toContain("Trieste");
    expect(html).toContain("Ultima rilevazione: Pordenone");
    expect(html).toContain('aria-label="Attiva Posizione"');
    expect(html).not.toContain('aria-label="Aggiorna posizione"');
    expect(html).not.toContain("Automatica");
  });
});
