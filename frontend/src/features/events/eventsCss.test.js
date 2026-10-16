import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const directory = path.dirname(fileURLToPath(import.meta.url));
const css = fs.readFileSync(path.join(directory, "events.css"), "utf8");
const neutralCss = fs.readFileSync(path.join(directory, "../../ui/neutralSurfaces.css"), "utf8");

function rule(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return css.match(new RegExp(`^${escaped}\\s*\\{([^}]+)\\}`, "m"))?.[1] || "";
}

describe("events filter design system", () => {
  it("uses compact count badges without reintroducing a second segmented-control style", () => {
    const count = rule(".mf-events-time-tabs__count");
    const activeCount = rule(
      ".mf-events-time-tabs .mf-weather-section-nav__item.is-active .mf-events-time-tabs__count",
    );

    expect(count).toContain("min-width: 22px");
    expect(count).toContain("height: 20px");
    expect(count).toContain("background: #e2e8f0");
    expect(count).toContain("color: #475569");
    expect(activeCount).toContain("background: #fff");
    expect(activeCount).toContain("color: #075a9f");
    expect(neutralCss).toContain(
      ".mf-events-time-tabs:not(.mf-weather-section-nav--compact)",
    );
  });

  it("keeps inactive categories neutral and reserves brand blue for selection", () => {
    const inactive = rule(".mf-events-category-scroll button");
    const active = rule(".mf-events-category-scroll button.is-active");
    const darkInactive = rule('html[data-theme="dark"] .mf-events-category-scroll button');
    const darkActive = rule('html[data-theme="dark"] .mf-events-category-scroll button.is-active');

    expect(inactive).toContain("border: 1px solid #cbd5e1");
    expect(inactive).toContain("background: rgba(255, 255, 255, 0.76)");
    expect(inactive).toContain("color: #334155");
    expect(inactive).not.toContain("var(--event-accent)");
    expect(active).toContain("linear-gradient(135deg, #0277b5 0%, #0369a1 100%)");
    expect(active).toContain("color: #fff");
    expect(active).not.toContain("background: var(--event-accent)");
    expect(darkInactive).toContain("background: rgba(255, 255, 255, 0.05)");
    expect(darkInactive).toContain("color: #94a3b8");
    expect(darkActive).toContain("linear-gradient(135deg, #0277b5 0%, #0369a1 100%)");
  });

  it("retains category identity only through a small decorative accent dot", () => {
    const dot = rule(".mf-events-filter__dot");

    expect(dot).toContain("width: 6px");
    expect(dot).toContain("height: 6px");
    expect(dot).toContain("border-radius: 50%");
    expect(dot).toContain("background: var(--event-accent)");
  });

  it("keeps the source neutral and the mixed-list category tag softly colour-coded", () => {
    const badges = rule(".mf-events-card__badges");
    const source = rule(".mf-events-card__badges .mf-events-card__source");
    const category = rule(".mf-events-card__badges .mf-events-category");
    const music = rule(".mf-events-card__badges .mf-events-category--musica");
    const family = rule(".mf-events-card__badges .mf-events-category--famiglia");
    const conference = rule(".mf-events-card__badges .mf-events-category--convegni");
    const darkSource = rule(
      'html[data-theme="dark"] .mf-events-card__badges .mf-events-card__source',
    );
    const darkCategory = rule(
      'html[data-theme="dark"] .mf-events-card__badges .mf-events-category',
    );

    expect(badges).toContain("display: flex");
    expect(badges).toContain("align-items: center");
    expect(badges).toContain("flex-wrap: nowrap");
    expect(source).toContain("color: #64748b");
    expect(category).toContain("background: var(--event-card-tag-bg)");
    expect(category).toContain("color: var(--event-card-tag-ink)");
    expect(music).toContain("--event-card-tag-bg: rgba(168, 85, 247, 0.1)");
    expect(music).toContain("--event-card-tag-ink: #7e22ce");
    expect(family).toContain("--event-card-tag-bg: rgba(245, 158, 11, 0.12)");
    expect(conference).toContain("--event-card-tag-bg: rgba(2, 132, 199, 0.1)");
    expect(css).toContain("--event-card-tag-bg: rgba(249, 115, 22, 0.1)");
    expect(css).toContain("--event-card-tag-ink: #c2410c");
    expect(darkSource).toContain("color: #94a3b8");
    expect(darkCategory).toContain("background: var(--event-card-tag-bg-dark)");
  });

  it("keeps the event location compact and lighter than the title", () => {
    const location = rule(".mf-events-card__main p");
    const locationText = rule(".mf-events-card__main p span");

    expect(location).toContain("display: inline-flex");
    expect(location).toContain("font-weight: 600");
    expect(locationText).toContain("white-space: nowrap");
    expect(locationText).toContain("text-overflow: ellipsis");
  });
});
