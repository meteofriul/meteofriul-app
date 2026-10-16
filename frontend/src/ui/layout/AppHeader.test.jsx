import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, expect, it, vi } from "vitest";

import { getUiShellCopy } from "../../app/uiShellCopy";
import { buildCommunityIdentity } from "../../features/community/communityIdentity";
import { isLocalWeatherPilot } from "../../services/localWeatherPilot";
import { AppHeader } from "./AppHeader";

const experience = vi.hoisted(() => vi.fn(() => false));

vi.mock("../../services/localWeatherPilot", () => ({
  isDefinitiveAppExperience: experience,
  isLocalWeatherPilot: experience,
}));

beforeEach(() => {
  isLocalWeatherPilot.mockReset();
  isLocalWeatherPilot.mockReturnValue(false);
});

function renderHeader(language = "it", props = {}) {
  return renderToStaticMarkup(
    <AppHeader copy={getUiShellCopy(language)} language={language} {...props} />,
  );
}

it("keeps the shared header mark outside localPilot", () => {
  const html = renderHeader();

  expect(html).toContain('src="/brand/logo-eagle-mark.webp"');
  expect(html).not.toContain('src="/brand/pilot-r4/meteo-eventi-friul-mark-192.png"');
  expect(html).not.toContain("mf-brand--friulora");
  expect(html).toContain("Meteo, eventi e territorio");
  expect(html).toContain('aria-label="Cambia lingua IT/FUR"');
  expect(html).toContain('aria-label="Apri impostazioni"');
  expect(html).toContain("lucide-settings");
  expect(html).not.toContain("mf-header-profile-button");
});

it("keeps the shared Furlan header unchanged outside localPilot", () => {
  const html = renderHeader("fur");

  expect(html).toContain('src="/brand/logo-eagle-mark.webp"');
  expect(html).not.toContain('src="/brand/pilot-r4/meteo-eventi-friul-mark-192.png"');
  expect(html).not.toContain("mf-brand--friulora");
  expect(html).toContain("Meteo, events e teritori");
  expect(html).toContain('aria-label="Cjambie lenghe IT/FUR"');
  expect(html).toContain('aria-label="Vierç impostazions"');
});

it("uses only the r4 mark in the localPilot header", () => {
  isLocalWeatherPilot.mockReturnValue(true);
  const html = renderHeader();

  expect(html).toContain('src="/brand/pilot-r4/meteo-eventi-friul-mark-192.png"');
  expect(html).not.toContain('src="/brand/meteo-eventi-friul-text-header.png"');
  expect(html).not.toContain('src="/brand/logo-eagle-mark.webp"');
  expect(html).not.toContain('aria-label="Meteo Friûl"');
  expect(html).toContain('<span class="mf-brand-title__accessible">METEO FRIÛL</span>');
  expect(html).toContain('<span aria-hidden="true" class="mf-brand-title__visual">');
  expect(html).toContain('class="mf-brand-title__accented-u">U<svg');
  expect(html).toContain('class="mf-brand-title__circumflex"');
  expect(html).toContain('class="mf-brand-title__underline"');
  expect(html.match(/METEO FRIÛL/g)).toHaveLength(1);
  expect(html).toContain("Meteo ed eventi per il tempo libero");
  expect(html).not.toContain("Meteo ed eventi sul territorio");
  expect(html).not.toContain('aria-label="Cambia lingua IT/FUR"');
  expect(html).not.toContain("lucide-languages");
  expect(html).toContain('aria-label="Apri impostazioni"');
  expect(html).toContain("mf-header-profile-button");
  expect(html).toContain("lucide-user-round");
  expect(html).not.toContain("lucide-settings");
});

it("uses the active anonymous avatar in the pilot profile action", () => {
  isLocalWeatherPilot.mockReturnValue(true);
  const html = renderHeader("it", {
    communityIdentity: buildCommunityIdentity({
      placeName: "Pordenon",
      revision: 2,
      subjectId: "acuile",
    }),
  });

  expect(html).toContain('class="mf-community-avatar mf-header-profile-button__avatar"');
  expect(html).toContain('data-subject="acuile"');
  expect(html).toContain("height:40px;width:40px");
  expect(html).toContain("scale(1.4)");
  expect(html).not.toContain("lucide-user-round");
});

it("localizes the simplified pilot tagline in Furlan", () => {
  isLocalWeatherPilot.mockReturnValue(true);
  const html = renderHeader("fur");

  expect(html).toContain('<span class="mf-brand-title__accessible">METEO FRIÛL</span>');
  expect(html).toContain('aria-hidden="true" class="mf-brand-title__visual"');
  expect(html).toContain("Meteo e events pal timp libar");
  expect(html).not.toContain("Meteo ed eventi per il tempo libero");
  expect(html).not.toContain("Meteo e events sul teritori");
  expect(html).not.toContain('aria-label="Cjambie lenghe IT/FUR"');
  expect(html).toContain('aria-label="Vierç impostazions"');
});

it.each([
  ["alert", "Apri impostazioni, allerta meteo attiva"],
  ["location", "Apri impostazioni, posizione automatica attiva"],
])("announces the pilot profile status without overlaying the avatar for a real %s state", (profileStatus, accessibleLabel) => {
  isLocalWeatherPilot.mockReturnValue(true);
  const html = renderHeader("it", { profileStatus });

  expect(html).toContain(`aria-label="${accessibleLabel}"`);
  expect(html).not.toContain("mf-header-profile-button__status");
  expect(html).not.toContain("data-profile-status");
});

it("localizes the pilot profile status in Furlan", () => {
  isLocalWeatherPilot.mockReturnValue(true);
  const html = renderHeader("fur", { profileStatus: "alert" });

  expect(html).toContain('aria-label="Vierç impostazions, alerte meteo ative"');
});

it("does not invent a pilot profile status badge", () => {
  isLocalWeatherPilot.mockReturnValue(true);
  const html = renderHeader();

  expect(html).not.toContain("mf-header-profile-button__status");
  expect(html).not.toContain("data-profile-status");
});

it("hides only the redundant pilot profile action on the settings route", () => {
  isLocalWeatherPilot.mockReturnValue(true);
  const html = renderHeader("it", { hidePilotProfileAction: true });

  expect(html).toContain('src="/brand/pilot-r4/meteo-eventi-friul-mark-192.png"');
  expect(html).toContain('<span class="mf-brand-title__accessible">METEO FRIÛL</span>');
  expect(html).not.toContain("mf-header-profile-button");
  expect(html).not.toContain("lucide-user-round");
});

it("keeps the ordinary settings action even when the pilot-only flag is set", () => {
  const html = renderHeader("it", { hidePilotProfileAction: true });

  expect(html).toContain('aria-label="Apri impostazioni"');
  expect(html).toContain("lucide-settings");
});
