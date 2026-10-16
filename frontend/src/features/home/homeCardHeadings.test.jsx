import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { getHomeStaticViewModel } from "./homeFixture";
import { HomeView } from "./HomeView";

const EXPECTED_COPY = {
  it: ["Evoluzione oraria", "Eventi vicino a te", "Dal territorio", "Almanacco"],
  fur: ["Evoluzion orarie", "Evenis dongje di te", "Dal teritori", "Almanac"],
};

function getQuickCards(markup) {
  return [...markup.matchAll(/<article\b[^>]*class="[^"]*\bmf-home-quick-card\b[^"]*"[^>]*>[\s\S]*?<\/article>/g)]
    .map((match) => match[0]);
}

function getQuickActions(markup) {
  return [...markup.matchAll(/<button\b[^>]*class="[^"]*\bmf-home-quick-card__action\b[^"]*"[^>]*><\/button>/g)]
    .map((match) => match[0]);
}

function renderHome(language, interactive = true) {
  const fixture = getHomeStaticViewModel(language);
  const model = { ...fixture, weather: { ...fixture.weather, alertSummary: null } };

  return renderToStaticMarkup(
    <HomeView language={language} model={model} onNavigate={interactive ? vi.fn() : undefined} />,
  );
}

describe("Home quick-card headings", () => {
  it.each(["it", "fur"])("keeps the four %s headings semantic and inside clean cards", (language) => {
    const markup = renderHome(language);
    const cards = getQuickCards(markup);

    expect(cards).toHaveLength(4);
    cards.forEach((card, index) => {
      expect(card).toMatch(/<header\b[^>]*class="mf-home-quick-card__header"/);
      expect(card).toContain(`<h2 id="home-quick-`);
      expect(card).toContain(`>${EXPECTED_COPY[language][index]}</h2>`);
    });
    expect(markup).not.toContain("mf-home-events-card");
    expect(markup).not.toContain("mf-home-almanac-card");
  });

  it.each(["it", "fur"])("uses four labelled native %s actions", (language) => {
    const markup = renderHome(language);
    const cards = getQuickCards(markup);
    const actions = getQuickActions(markup);

    expect(actions).toHaveLength(4);
    actions.forEach((action) => {
      expect(action).toContain('type="button"');
      expect(action).toMatch(/aria-label="[^"]+"/);
      expect(action).not.toMatch(/<h[1-6]\b/);
    });
    expect(getQuickActions(cards[0])).toHaveLength(1);
    expect(getQuickActions(cards[1])).toHaveLength(1);
    expect(getQuickActions(cards[2])).toHaveLength(1);
    expect(getQuickActions(cards[3])).toHaveLength(1);
  });

  it.each(["it", "fur"])("shows a single chevron only on each interactive %s card", (language) => {
    const cards = getQuickCards(renderHome(language));

    expect(cards[0].match(/\blucide-chevron-right\b/g)).toHaveLength(1);
    expect(cards[1].match(/\blucide-chevron-right\b/g)).toHaveLength(1);
    expect(cards[2].match(/\blucide-chevron-right\b/g)).toHaveLength(1);
    expect(cards[3].match(/\blucide-chevron-right\b/g)).toHaveLength(1);
  });

  it.each(["it", "fur"])("preserves semantic %s headings when navigation is unavailable", (language) => {
    const markup = renderHome(language, false);
    const cards = getQuickCards(markup);

    expect(getQuickActions(markup)).toHaveLength(0);
    expect(cards).toHaveLength(4);
    cards.forEach((card, index) => {
      expect(card).toContain(`>${EXPECTED_COPY[language][index]}</h2>`);
      expect(card).not.toContain("lucide-chevron-right");
    });
  });
});
