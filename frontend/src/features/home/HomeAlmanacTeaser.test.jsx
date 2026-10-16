import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HomeAlmanacTeaser } from "./HomeAlmanacTeaser";

function buildAlmanac(moon = null) {
  return {
    actionLabel: "Apri Almanacco",
    body: "San Pietro Giuliano Eymard",
    cardTitle: "L'almanacco del giorno",
    dateLabel: "Domenica 2 agosto",
    moon,
    moonLabel: "Luna",
    title: "Almanacco",
  };
}

describe("HomeAlmanacTeaser", () => {
  it("renders the current lunar phase from the Almanac model", () => {
    const markup = renderToStaticMarkup(
      <HomeAlmanacTeaser
        almanac={buildAlmanac({ cycleProgress: 63, phase: "Gibbosa calante" })}
        onOpen={() => {}}
      />,
    );

    expect(markup).toContain("mf-moon-phase-icon");
    expect(markup).toContain('data-cycle-progress="63"');
    expect(markup).toContain('/astronomy/moon-surface-nasa.webp');
    expect(markup).toContain("mf-home-almanac-card__details");
    expect(markup).toContain("Luna");
    expect(markup).toContain("Gibbosa calante");
    expect(markup).not.toContain("Tradizioni");
    expect(markup).not.toContain("mf-home-almanac-card__tags");
    expect(markup).not.toContain("lucide-moon-star");
  });

  it("keeps the familiar moon icon when phase data is unavailable", () => {
    const markup = renderToStaticMarkup(
      <HomeAlmanacTeaser almanac={buildAlmanac()} onOpen={() => {}} />,
    );

    expect(markup).not.toContain("mf-moon-phase-icon");
    expect(markup).toContain("lucide-moon-star");
  });

  it("does not repeat the lunar label when the phase already includes it", () => {
    const almanac = {
      ...buildAlmanac({ cycleProgress: 63, phase: "Lune calant plene" }),
      moonLabel: "Lune",
    };
    const markup = renderToStaticMarkup(
      <HomeAlmanacTeaser almanac={almanac} onOpen={() => {}} />,
    );

    expect(markup).toContain("Lune calant plene");
    expect(markup).not.toContain("<span>Lune</span>");
  });
});
