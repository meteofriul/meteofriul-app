import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { WeatherSectionNav } from "./WeatherSectionNav";
import { getWeatherSectionNavCopy } from "./weatherSectionNavCopy";

describe("WeatherSectionNav", () => {
  it("renders localized routes and marks the active section", () => {
    const markup = renderToStaticMarkup(
      <WeatherSectionNav activeId="bulletin" language="it" onNavigate={() => {}} />,
    );

    expect(markup).toContain('<nav aria-label="Sezioni meteo"');
    expect(markup).toContain("Previsioni");
    expect(markup).toMatch(/<button[^>]*aria-current="page"[^>]*>Bollettino<\/button>/);
    expect(markup).toContain("Tempo reale");
  });

  it("uses Friulian labels and navigates through route ids", () => {
    const onNavigate = vi.fn();
    const navigation = WeatherSectionNav({
      activeId: "weather",
      language: "fur",
      onNavigate,
    });

    expect(getWeatherSectionNavCopy("fur").ariaLabel).toBe("Sezions meteo");
    expect(getWeatherSectionNavCopy("fur").changeLocationLabel).toBe("Cambie");
    expect(renderToStaticMarkup(navigation)).toContain("Timp reâl");
    navigation.props.children[2].props.onClick();
    expect(onNavigate).toHaveBeenCalledWith("live");
  });

  it("supports the app navigation lock through the disabled prop", () => {
    const markup = renderToStaticMarkup(
      <WeatherSectionNav activeId="weather" disabled language="it" />,
    );

    expect(markup.match(/disabled=""/g)).toHaveLength(3);
  });

  it("adds the compact pilot presentation without changing route semantics", () => {
    const onNavigate = vi.fn();
    const navigation = WeatherSectionNav({
      activeId: "live",
      compact: true,
      language: "it",
      onNavigate,
    });
    const markup = renderToStaticMarkup(navigation);

    expect(markup).toContain('class="mf-weather-section-nav mf-weather-section-nav--compact"');
    expect(markup.match(/<button/g)).toHaveLength(3);
    expect(markup).toMatch(/<button[^>]*aria-current="page"[^>]*>Tempo reale<\/button>/);
    navigation.props.children[0].props.onClick();
    expect(onNavigate).toHaveBeenCalledWith("weather");
  });
});
