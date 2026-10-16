// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { isLocalWeatherPilot } from "../../services/localWeatherPilot";
import { COMMUNITY_IDENTITY_STORAGE_KEY } from "../community/communityIdentity";
import {
  LIVE_REPORT_CLIENT_ID_KEY,
  LIVE_REPORT_SESSION_CLIENT_ID_KEY,
} from "../../services/liveApi";
import { SettingsView } from "./SettingsView";

const experience = vi.hoisted(() => vi.fn(() => true));

vi.mock("../../services/localWeatherPilot", () => ({
  isDefinitiveAppExperience: experience,
  isLocalWeatherPilot: experience,
  getLocalWeatherPilotNow: () => Date.now(),
  getLocalWeatherPilotTestNow: () => null,
}));
let container;
let root;

beforeEach(() => {
  vi.clearAllMocks();
  isLocalWeatherPilot.mockReturnValue(true);
  localStorage.removeItem(COMMUNITY_IDENTITY_STORAGE_KEY);
  localStorage.removeItem(LIVE_REPORT_CLIENT_ID_KEY);
  sessionStorage.removeItem(LIVE_REPORT_SESSION_CLIENT_ID_KEY);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  container.id = "root";
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  localStorage.removeItem(COMMUNITY_IDENTITY_STORAGE_KEY);
  localStorage.removeItem(LIVE_REPORT_CLIENT_ID_KEY);
  sessionStorage.removeItem(LIVE_REPORT_SESSION_CLIENT_ID_KEY);
  delete globalThis.IS_REACT_ACT_ENVIRONMENT;
});

it("delegates every compact pilot preference to the existing handlers", async () => {
  const onLanguageSelect = vi.fn();
  const onLocationSearchOpen = vi.fn();
  const onRuntimeCacheReset = vi.fn(() => ({ ok: true }));
  const onSupportOpen = vi.fn();
  const onThemePreferenceChange = vi.fn();

  await act(async () => {
    root.render(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        onLanguageSelect={onLanguageSelect}
        onLocationSearchOpen={onLocationSearchOpen}
        onRuntimeCacheReset={onRuntimeCacheReset}
        onSupportOpen={onSupportOpen}
        onThemePreferenceChange={onThemePreferenceChange}
      />,
    );
  });

  const buttonByText = (text) => [...container.querySelectorAll("button")]
    .find((button) => button.textContent.trim() === text);

  await act(async () => buttonByText("Furlan").click());
  await act(async () => buttonByText("Scuro").click());
  await act(async () => container.querySelector('button[aria-label="Cambia"]').click());
  await act(async () => container.querySelector('button[aria-label="Svuota"]').click());
  await act(async () => container.querySelector('a[aria-label="Sostieni su Ko-fi"]').click());

  expect(onLanguageSelect).toHaveBeenCalledWith("fur");
  expect(onThemePreferenceChange).toHaveBeenCalledWith("dark");
  expect(onLocationSearchOpen).toHaveBeenCalledTimes(1);
  expect(onRuntimeCacheReset).toHaveBeenCalledTimes(1);
  expect(container.textContent).toContain("Cache svuotata");
  expect(onSupportOpen).toHaveBeenCalledWith("https://ko-fi.com/meteofriul");
});

it("announces cache success only after the asynchronous reset completes", async () => {
  let settle;
  const onRuntimeCacheReset = vi.fn(() => new Promise(resolve => { settle = resolve; }));
  await act(async () => {
    root.render(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        onRuntimeCacheReset={onRuntimeCacheReset}
      />,
    );
  });

  const button = container.querySelector('button[aria-label="Svuota"]');
  await act(async () => { button.click(); });
  expect(button.getAttribute("aria-busy")).toBe("true");
  expect(button.disabled).toBe(true);
  expect(container.textContent).toContain("Svuotamento in corso…");
  expect(container.textContent).not.toContain("Cache svuotata");

  await act(async () => { settle({ ok: true }); });
  expect(button.getAttribute("aria-busy")).toBeNull();
  expect(button.disabled).toBe(false);
  expect(container.textContent).toContain("Cache svuotata");
});

it("reports an incomplete cache reset instead of claiming success", async () => {
  const onRuntimeCacheReset = vi.fn().mockResolvedValue({ ok: false });
  await act(async () => {
    root.render(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        onRuntimeCacheReset={onRuntimeCacheReset}
      />,
    );
  });

  await act(async () => {
    container.querySelector('button[aria-label="Svuota"]').click();
  });

  expect(container.textContent).toContain("Pulizia incompleta. Riprova.");
  expect(container.textContent).not.toContain("Cache svuotata");
});

it("regenerates only the local alias, retains focus and announces the result", async () => {
  await act(async () => {
    root.render(
      <SettingsView
        activeLocation={{ city: "Pordenone", istatCode: "093033" }}
      />,
    );
  });

  const button = container.querySelector('button[aria-label="Cambia alias"]');
  const alias = () => container.querySelector("#mf-settings-community-alias")?.textContent;
  const firstAlias = alias();

  button.focus();
  await act(async () => button.click());

  expect(alias()).not.toBe(firstAlias);
  expect(alias()).not.toContain("Pordenon");
  expect(document.activeElement).toBe(button);
  expect(container.querySelector('[role="status"]')?.textContent)
    .toBe(`Nuovo alias: ${alias()}`);
  expect(localStorage.getItem(COMMUNITY_IDENTITY_STORAGE_KEY)).not.toBeNull();
  expect(container.querySelector(".mf-settings-identity__avatar [data-subject]")).not.toBeNull();
});

it("shows the authoritative submission total and rank without progression copy", async () => {
  const communityReputationLoader = vi.fn().mockResolvedValue({
    max_daily_awards: 3,
    pending_reports: 2,
    points: 7,
    rank: { id: "lookout", min_points: 5, next_rank_at: 20 },
    total_reports: 12,
    validated_reports: 8,
  });
  localStorage.setItem(LIVE_REPORT_CLIENT_ID_KEY, "existing-community-client");

  await act(async () => {
    root.render(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        communityReputationLoader={communityReputationLoader}
      />,
    );
  });

  const stats = container.querySelector(".mf-settings-identity__stats");
  const values = [...stats.querySelectorAll(".mf-settings-identity__stat-value")];
  const reputation = stats.querySelector(".mf-settings-identity__reputation");

  expect(communityReputationLoader).toHaveBeenCalledWith({
    clientId: "existing-community-client",
  });
  expect(reputation.textContent).toBe("🏆Vuaite dal Timp·7pt");
  expect(reputation.getAttribute("aria-label"))
    .toBe("Rango Vuaite dal Timp: 7 punti convalidati. Segnalazioni convalidate: 8. Segnalazioni in attesa: 2");
  expect(stats.textContent).not.toContain("Contributi oggi");
  expect(stats.textContent).toContain("Segnalazioni totali: 12");
  expect(stats.textContent).not.toContain("Mancano");
  expect(values).toHaveLength(2);
  expect(values.map((value) => value.textContent)).toEqual(["7", "12"]);
});

it("does not turn local activity into points when reputation loading fails", async () => {
  const communityReputationLoader = vi.fn().mockRejectedValue(new Error("offline"));
  localStorage.setItem(LIVE_REPORT_CLIENT_ID_KEY, "existing-community-client");

  await act(async () => {
    root.render(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        communityReputationLoader={communityReputationLoader}
      />,
    );
  });

  const stats = container.querySelector(".mf-settings-identity__stats");

  expect(stats.textContent).toContain("Rango non disponibile");
  expect(stats.textContent).toContain("Segnalazioni totali: —");
  expect(stats.textContent).not.toContain("Contributi oggi");
  expect(stats.textContent).not.toContain("0 pt");
});

it("does not request reputation or create a client id when none exists", async () => {
  const communityReputationLoader = vi.fn();

  await act(async () => {
    root.render(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        communityReputationLoader={communityReputationLoader}
      />,
    );
  });

  expect(communityReputationLoader).not.toHaveBeenCalled();
  expect(localStorage.getItem(LIVE_REPORT_CLIENT_ID_KEY)).toBeNull();
  expect(sessionStorage.getItem(LIVE_REPORT_SESSION_CLIENT_ID_KEY)).toBeNull();
  expect(container.querySelector(".mf-settings-identity__stats")?.textContent)
    .toContain("Rango non disponibile");
});

it("uses an accessible icon-only back control beside the pilot title", async () => {
  await act(async () => {
    root.render(<SettingsView activeLocation={{ city: "Pordenone" }} />);
  });

  const topbar = container.querySelector(".mf-settings-topbar");
  const back = topbar?.querySelector('button[aria-label="Indietro"]');

  expect(back).not.toBeNull();
  expect(back.classList.contains("mf-settings-back--icon")).toBe(true);
  expect(back.textContent).toBe("");
  expect(back.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  expect(back.querySelector("svg")?.classList.contains("lucide-arrow-left")).toBe(true);
  expect(topbar?.querySelector("strong")?.textContent).toBe("Impostazioni");
  expect(topbar?.lastElementChild).toBe(topbar?.querySelector("strong"));
});

it("localizes and preserves the pilot back action in Furlan", async () => {
  const onSettingsBack = vi.fn();

  await act(async () => {
    root.render(
      <SettingsView
        activeLocation={{ city: "Pordenone" }}
        language="fur"
        onSettingsBack={onSettingsBack}
      />,
    );
  });

  const back = container.querySelector('button[aria-label="Indaûr"]');
  await act(async () => back.click());

  expect(onSettingsBack).toHaveBeenCalledTimes(1);
});
