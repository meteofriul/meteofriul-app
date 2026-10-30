import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

const harness = vi.hoisted(() => ({ pilot: false }));

// Inspect route composition without mounting data loaders or changing storage.
vi.mock("react", async (importOriginal) => ({
  ...await importOriginal(),
  useCallback: callback => callback,
  useEffect: () => {},
  useRef: initial => ({ current: initial }),
  useState: initial => [typeof initial === "function" ? initial() : initial, vi.fn()],
  useSyncExternalStore: (_subscribe, getSnapshot) => getSnapshot(),
}));
vi.mock("../services/localWeatherPilot", async (importOriginal) => ({
  ...await importOriginal(),
  isDefinitiveAppExperience: () => harness.pilot,
  isLocalWeatherPilot: () => harness.pilot,
}));

import { AppRoutes } from "./AppRoutes";
import { WeatherSectionNav } from "../features/weather/WeatherSectionNav";
import { WeatherSwipeShell } from "../features/weather/WeatherSwipeShell";
import { LocationContext } from "../ui/components/LocationContext";

afterEach(() => { harness.pilot = false; });

// The market dialog is a sibling of the primary route inside Suspense.
const primaryRoute = route => Array.isArray(route.props.children) ? route.props.children[0] : route.props.children;

function weatherRoute(activeTab, { locked = false, language = "it", theme = "light" } = {}) {
  const onNavigate = vi.fn();
  const onLocationSearchOpen = vi.fn();
  const route = AppRoutes({
    activeLocation: { city: "Pordenone", istatCode: "093033" },
    activeTab,
    copy: { placeholders: {} },
    language,
    onLocationSearchOpen,
    onNavigate,
    reportSubmissionLocked: locked,
    theme,
  });
  const shell = primaryRoute(route);
  const navigation = shell.props.children[0];
  const shellChildren = [...navigation.props.children, ...shell.props.children.slice(1)].filter(Boolean);
  const locationContext = shellChildren.find(child => child?.type === LocationContext);
  const nav = shellChildren.find(child => child?.type === WeatherSectionNav);
  const title = shellChildren.find(child => child?.props?.className === "mf-weather-route-title");
  const view = shellChildren.at(-1);
  return { locationContext, nav, navigation, onLocationSearchOpen, onNavigate, shell, shellChildren, title, view };
}

describe("weather route swipe isolation", () => {
  it.each(["weather", "bulletin", "live"])("disables page gestures only in the pilot on %s while keeping section buttons usable", activeTab => {
    harness.pilot = true;
    const {
      locationContext,
      nav,
      navigation,
      onNavigate,
      shell,
      shellChildren,
      title,
      view,
    } = weatherRoute(activeTab);
    expect(shell.type).toBe(WeatherSwipeShell);
    expect(shell.props.disabled).toBe(true);
    expect(navigation.props.className.includes("mf-section-navigation--sticky")).toBe(activeTab === "bulletin");
    expect(title).toBeUndefined();
    expect(shellChildren[0].type).toBe(LocationContext);
    expect(shellChildren[1].type).toBe(WeatherSectionNav);
    expect(locationContext.props.city).toBe("Pordenone");
    expect(locationContext.props.className).toBe("mf-route-location-context mf-weather-route-context");
    expect(locationContext.props.changeLabel).toBeUndefined();
    expect(locationContext.props.disabled).toBeUndefined();
    expect(locationContext.props.onChange).toBeUndefined();
    expect(renderToStaticMarkup(locationContext)).not.toContain("<button");
    expect(view.props.onLocationSearchOpen).toBeUndefined();
    expect(nav.props.compact).toBe(true);
    expect(renderToStaticMarkup(WeatherSectionNav(nav.props))).toContain(
      'class="mf-weather-section-nav mf-weather-section-nav--compact"',
    );
    expect(nav.props.disabled).toBe(false);
    expect(view.props.showEmbeddedWeatherLocation).toBe(false);
    const buttons = WeatherSectionNav(nav.props).props.children;
    expect(buttons.map(button => button.props.children)).toEqual(["Previsioni", "Bollettino", "Tempo reale"]);
    for (const button of buttons) {
      expect(button.props.disabled).toBe(false);
      button.props.onClick();
    }
    expect(onNavigate.mock.calls.map(([tab]) => tab)).toEqual(["weather", "bulletin", "live"]);
  });

  it.each(["weather", "bulletin", "live"])("preserves the beta swipe on %s", activeTab => {
    harness.pilot = false;
    const { locationContext, nav, navigation, shell, title, view } = weatherRoute(activeTab);
    expect(shell.props.disabled).toBe(false);
    expect(navigation.props.className).not.toContain("mf-section-navigation--sticky");
    expect(nav.props.compact).toBe(false);
    expect(renderToStaticMarkup(WeatherSectionNav(nav.props))).not.toContain(
      "mf-weather-section-nav--compact",
    );
    expect(nav.props.disabled).toBe(false);
    expect(locationContext).toBeUndefined();
    expect(title?.props.children).toBe("Meteo");
    expect(view.props.showEmbeddedWeatherLocation).toBe(true);
    expect(view.props.onLocationSearchOpen).toBeUndefined();
  });

  it("localizes the shared pilot context before the section navigation", () => {
    harness.pilot = true;
    const { locationContext, nav, shellChildren } = weatherRoute("weather", { language: "fur" });

    expect(shellChildren.indexOf(locationContext)).toBeLessThan(shellChildren.indexOf(nav));
    expect(locationContext.props.city).toBe("Pordenon");
    expect(locationContext.props.changeLabel).toBeUndefined();
    expect(renderToStaticMarkup(locationContext)).not.toContain("Cambie");
  });

  it.each([false, true])("still locks gestures and buttons while a report is being submitted (pilot=%s)", pilot => {
    harness.pilot = pilot;
    const { locationContext, nav, onNavigate, shell } = weatherRoute("live", { locked: true });
    expect(shell.props.disabled).toBe(true);
    expect(nav.props.disabled).toBe(true);
    if (pilot) expect(locationContext.props.onChange).toBeUndefined();
    const buttons = WeatherSectionNav(nav.props).props.children;
    expect(buttons.every(button => button.props.disabled)).toBe(true);
    buttons[0].props.onClick();
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it.each(["it", "fur"])("assigns the live content to the flexible grid track in %s, including short screens", language => {
    harness.pilot = true;
    const { shell, navigation, view } = weatherRoute("live", { language });
    const children = shell.props.children.filter(Boolean);
    const css = readFileSync(new URL("../features/live/live.css", import.meta.url), "utf8");
    const routeRules = [...css.matchAll(
      /\.mf-app-main--territory-fit > \.mf-weather-route-shell\s*\{([^}]+)\}/g,
    )];
    const templates = routeRules.map(([, rule]) => rule.match(/grid-template-rows:\s*([^;]+)/)?.[1]).filter(Boolean);

    expect(children[0]).toBe(navigation);
    expect(children.at(-1)).toBe(view);
    expect(templates.length).toBeGreaterThanOrEqual(2);
    for (const template of templates) {
      const tracks = template.match(/minmax\([^)]*\)|[^\s]+/g);
      // Auto-placement must put the actual route in the flexible track,
      // not leave that track empty after the navigation was grouped.
      expect(tracks).toHaveLength(children.length);
      expect(tracks.at(-1)).toMatch(/^minmax\(.+,\s*1fr\)$/);
    }
  });

  it("forwards the resolved theme to the territory route", () => {
    harness.pilot = true;
    const { view } = weatherRoute("live", { theme: "dark" });

    expect(view.props.theme).toBe("dark");
  });

  it.each(["home", "events", "discover"])("does not expose a quick location action on %s", activeTab => {
    const onLocationSearchOpen = vi.fn();
    const route = AppRoutes({
      activeLocation: { city: "Pordenone", istatCode: "093033" },
      activeTab,
      copy: { placeholders: {} },
      language: "it",
      onLocationSearchOpen,
      onNavigate: vi.fn(),
    });

    expect(primaryRoute(route).props.onLocationSearchOpen).toBeUndefined();
  });

  it("keeps location changes available from Settings", () => {
    const onLocationSearchOpen = vi.fn();
    const route = AppRoutes({
      activeLocation: { city: "Pordenone", istatCode: "093033" },
      activeTab: "settings",
      copy: { placeholders: {} },
      language: "it",
      onLocationSearchOpen,
      onNavigate: vi.fn(),
    });

    expect(primaryRoute(route).props.onLocationSearchOpen).toBe(onLocationSearchOpen);
  });
});
