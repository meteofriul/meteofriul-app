import { renderToStaticMarkup } from "react-dom/server";
import { Children } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HomeQuickGrid } from "./HomeQuickGrid";
import { isLocalWeatherPilot } from "../../services/localWeatherPilot";
import { getPilotWhyContentForDate } from "../discover/pilotWhyContent";

const experience = vi.hoisted(() => vi.fn(() => false));

vi.mock("../../services/localWeatherPilot", async importOriginal => ({
  ...await importOriginal(),
  isDefinitiveAppExperience: experience,
  isLocalWeatherPilot: experience,
}));

afterEach(() => vi.mocked(isLocalWeatherPilot).mockReturnValue(false));

function getTerritoryCard(markup) {
  return markup.match(
    /<article\b[^>]*class="[^"]*\bmf-home-quick-card--territory\b[^"]*"[^>]*>[\s\S]*?<\/article>/,
  )?.[0] || "";
}

function getAlmanacCard(markup) {
  return markup.match(
    /<article\b[^>]*class="[^"]*\bmf-home-quick-card--almanac\b[^"]*"[^>]*>[\s\S]*?<\/article>/,
  )?.[0] || "";
}

describe("HomeQuickGrid compact data", () => {
  it.each([
    ["it", "eventi in programma"],
    ["fur", "evenis in program"],
  ])("keeps the %s event count out of a featured-event banner", (language, caption) => {
    const markup = renderToStaticMarkup(
      <HomeQuickGrid
        events={{
          countLabel: language === "fur" ? "489 evenis" : "489 eventi",
          countValue: "489",
          items: [{
            dateLabel: "17 SET",
            location: "Pordenone",
            title: "Jazz River",
          }],
          title: language === "fur" ? "Evenis dongje di te" : "Eventi vicino a te",
        }}
        language={language}
      />,
    );

    expect(markup).toContain("mf-home-quick-events__banner--fallback");
    expect(markup).toContain("Jazz River");
    expect(markup).toContain("17 SET · Pordenone");
    expect(markup).not.toContain("mf-home-quick-events__count");
    expect(markup).not.toContain("489");
    expect(markup).not.toContain(caption);
  });

  it("renders the featured poster without duplicating the navigation event count", () => {
    const markup = renderToStaticMarkup(
      <HomeQuickGrid
        events={{
          countCaption: "eventi oggi",
          countValue: "23",
          items: [{
            dateLabel: "17 SET",
            image: "https://example.test/festival.jpg",
            location: "Pordenone",
            title: "Festival",
          }],
          title: "Eventi vicino a te",
        }}
        language="it"
      />,
    );

    expect(markup).toContain("mf-home-quick-events__banner--image");
    expect(markup).toContain('src="https://example.test/festival.jpg"');
    expect(markup).toContain('loading="lazy"');
    expect(markup).toContain('alt=""');
    expect(markup).toContain("Festival");
    expect(markup).toContain("17 SET · Pordenone");
    expect(markup).not.toContain("mf-home-quick-events__count");
    expect(markup).not.toContain("23");
    expect(markup).not.toContain("eventi oggi");
    expect(markup).not.toContain("eventi in programma");
  });

  it.each([
    ["it", "Evento in evidenza", "Eventi vicino a te"],
    ["fur", "Event in evidence", "Evenis dongje di te"],
  ])("uses the existing heading only for an explicitly selected %s Home event", (language, heading, ordinaryHeading) => {
    const events = {
      items: [{ id: "cinema", title: "Le Giornate del Cinema Muto", featured: true }],
    };
    const marked = renderToStaticMarkup(<HomeQuickGrid events={events} language={language} />);
    const ordinary = renderToStaticMarkup(
      <HomeQuickGrid events={{ items: [{ ...events.items[0], featured: false }] }} language={language} />,
    );

    expect(marked).toContain(`<h2 id="home-quick-events-title">${heading}</h2>`);
    expect(ordinary).toContain(`<h2 id="home-quick-events-title">${ordinaryHeading}</h2>`);
    expect(marked).not.toContain("mf-home-quick-events__featured");
    expect(ordinary).not.toContain("mf-home-quick-events__featured");
  });

  it("uses a category fallback when the featured event has no usable poster", () => {
    const markup = renderToStaticMarkup(
      <HomeQuickGrid
        events={{
          countCaption: "evento oggi",
          countValue: "1",
          items: [{
            category: "musica",
            dateLabel: "17 SET",
            location: "Pordenone",
            title: "Concerto",
          }],
          title: "Eventi vicino a te",
        }}
        language="it"
      />,
    );

    expect(markup).toContain("mf-home-quick-events__banner--fallback");
    expect(markup).toContain('data-category="musica"');
    expect(markup).toContain("lucide-music");
    expect(markup).not.toContain("<img");
    expect(markup).not.toContain("mf-home-quick-events__count");
    expect(markup).not.toContain("evento oggi");
  });

  it("keeps the count-based empty state when there is no featured event", () => {
    const markup = renderToStaticMarkup(
      <HomeQuickGrid
        events={{
          countCaption: "eventi in programma",
          countValue: "0",
          items: [],
          message: "Nessun evento disponibile",
          title: "Eventi vicino a te",
        }}
        language="it"
      />,
    );

    expect(markup).not.toContain("mf-home-quick-events__banner");
    expect(markup).toContain('<div class="mf-home-quick-events__count"><strong>0</strong><span>eventi in programma</span></div>');
    expect(markup).toContain("Nessun evento disponibile");
  });

  it.each(["it", "fur"])("keeps remote promotions hidden and replaces the fourth content tile with the %s question", language => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    const onNavigate = vi.fn();
    const now = "2026-09-08";
    const content = getPilotWhyContentForDate(language, now);
    const tree = HomeQuickGrid({ language, now, onNavigate });
    const html = renderToStaticMarkup(tree);
    const tiles = Children.toArray(tree.props.children);
    expect(tiles).toHaveLength(5);
    expect(html.match(/<article\b/g)).toHaveLength(4);
    expect(html).not.toContain("mf-home-promotion");
    expect(html).not.toContain("mf-home-quick-card--almanac");
    expect(html).toContain("mf-home-quick-card--why");
    const whyCard = html.match(/<article\b[^>]*class="[^"]*\bmf-home-quick-card--why\b[^"]*"[^>]*>[\s\S]*?<\/article>/)?.[0] || "";
    expect(whyCard).not.toContain("mf-home-quick-card__icon");
    expect(whyCard).not.toContain("mf-home-quick-card__chevron");
    expect(whyCard).not.toContain("lucide-compass");
    expect(whyCard.match(/lucide-arrow-right/g)).toHaveLength(1);
    expect(whyCard.match(/<button\b/g)).toHaveLength(1);
    expect(html.match(/class="mf-home-quick-card__icon"/g)).toHaveLength(2);
    expect(html.match(/mf-home-quick-card__chevron/g)).toHaveLength(2);
    expect(html).toContain(content.rubric);
    expect(whyCard).toContain(`<small class="mf-home-quick-why__meta">${content.category}</small>`);
    expect(html).toContain(content.question);
    expect(html).toContain(`aria-label="${content.actionLabel}"`);
    expect(html).toContain('mf-home-quick-why__cta');
    if (content.lead) expect(whyCard).not.toContain(content.lead);
    content.answer.forEach(paragraph => expect(html).not.toContain(paragraph));
    tiles[4].props.onOpen();
    expect(onNavigate).toHaveBeenCalledExactlyOnceWith("discover", { anchor: content.anchor, whyId: content.id });
  });

  it("does not show a fake CTA when navigation is not available", () => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    const now = "2026-09-08";
    const html = renderToStaticMarkup(<HomeQuickGrid now={now} />);
    expect(html).toContain(getPilotWhyContentForDate("it", now).question);
    expect(html).not.toContain("mf-home-quick-why__cta");
    expect(html).not.toContain("mf-home-quick-memory__cta");
    expect(html).not.toContain("<button");
  });

  it.each([
    ["it", "Memoria del giorno", "8 settembre", "Musica", "Leggi"],
    ["fur", "Memorie dal dì", "8 Setembar", "Musiche", "Lei"],
  ])("presents the pilot %s memory as a mini-article without changing its content or destination", (language, heading, date, category, cta) => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    const onNavigate = vi.fn();
    const territory = {
      anchor: "discover-card-memory-0908-glauco-venier",
      heading,
      type: "musica",
      typeLabel: language === "fur" ? "Lenghe e culture" : "Lingua e cultura",
      seasonLabel: date,
      title: "Glauco Venier, dal Friuli al jazz internazionale",
      text: "L’8 settembre 1962 nasce a Sedegliano Glauco Venier. Pianista e compositore, costruisce una carriera internazionale nel jazz.",
    };
    const tree = HomeQuickGrid({ language, onNavigate, territory });
    const card = getTerritoryCard(renderToStaticMarkup(tree));
    expect(card).toContain("mf-home-quick-card--memory");
    expect(card).toContain(`>${heading}</h2>`);
    expect(card).toContain(`<small>${date} · ${category}</small>`);
    expect(card).toContain(`<strong>${territory.title}</strong>`);
    expect(card).toContain(`<p>${territory.text}</p>`);
    expect(card).toContain(`aria-hidden="true">${cta}<svg`);
    expect(card).toContain(`aria-label="${cta}: ${territory.title}"`);
    expect(card).not.toContain("mf-home-quick-card__icon");
    expect(card).not.toContain("mf-home-quick-card__chevron");
    expect(card).not.toContain("lucide-map-pinned");
    expect(card.match(/lucide-arrow-right/g)).toHaveLength(1);
    expect(card.match(/<button\b/g)).toHaveLength(1);
    Children.toArray(tree.props.children)[3].props.onOpen();
    expect(onNavigate).toHaveBeenCalledExactlyOnceWith("discover", { anchor: territory.anchor });
  });

  it("keeps other pilot categories from their metadata rather than inferring them from the title", () => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    const card = getTerritoryCard(renderToStaticMarkup(<HomeQuickGrid territory={{
      title: "Una storia di musica", type: "scienza", typeLabel: "Scienza e territorio", seasonLabel: "6 settembre",
    }} />));
    expect(card).toContain("<small>6 settembre · Scienza e territorio</small>");
    expect(card).not.toContain("· Musica");
  });

  it.each([
    ["it", "Memoria del giorno", "Francesco Maria Franceschinis, matematica e insegnamento", "Apri in Scopri"],
    ["fur", "Memorie dal dì", "Francesco Maria Franceschinis, matematiche e insegnament", "Vierç in Scuvierç"],
  ])("presents the %s daily-memory rubric with a labelled action", (language, heading, title, action) => {
    const markup = renderToStaticMarkup(
      <HomeQuickGrid
        language={language}
        onNavigate={() => {}}
        territory={{
          anchor: "discover-card-memory-0906",
          heading,
          metaLabel: language === "fur" ? "Sience e teritori · 6 di Setembar" : "Scienza e territorio · 6 settembre",
          text: language === "fur" ? "Une storie furlane leade ae date di vuê." : "Una storia friulana legata alla data di oggi.",
          title,
        }}
      />,
    );
    const territoryCard = getTerritoryCard(markup);

    expect(territoryCard).toContain(`>${heading}</h2>`);
    expect(territoryCard).toContain(title);
    expect(territoryCard).toContain(`aria-label="${action}: ${title}`);
    expect(territoryCard).not.toContain("Porden");
    expect(territoryCard).not.toContain(language === "fur" ? ">Comun<" : ">Comune<");
    expect(territoryCard).toContain('type="button"');
    expect(territoryCard).toContain("mf-home-quick-card__icon");
    expect(territoryCard).toContain("mf-home-quick-card__chevron");
    expect(territoryCard).not.toContain("mf-home-quick-card--memory");
    expect(territoryCard).not.toContain("mf-home-quick-memory__cta");
  });

  it("keeps the first three hours in sequence from a partial 23-hour reservoir", () => {
    const items = Array.from({ length: 23 }, (_, index) => ({
      ariaLabel: `Ora ${index}`,
      icon: { type: "Sun" },
      temperature: `${index}°`,
      time: `${String(index % 24).padStart(2, "0")}:00`,
      dayLabel: index < 24 ? "Oggi" : "31/08",
      timestamp: `2026-08-${index < 24 ? "30" : "31"}T${String(index % 24).padStart(2, "0")}:00:00Z`,
    }));
    const markup = renderToStaticMarkup(
      <HomeQuickGrid hourly={{ items, title: "Prossime 48 ore" }} language="it" />,
    );

    expect(markup).toMatch(/<small>Oggi<\/small><time[^>]*>00:00<\/time>/);
    expect(markup).toMatch(/<small>Oggi<\/small><time[^>]*>01:00<\/time>/);
    expect(markup).toMatch(/<small>Oggi<\/small><time[^>]*>02:00<\/time>/);
    expect(markup).not.toContain(">11:00<");
    expect(markup).not.toContain(">22:00<");
  });

  it("makes every night sample explicit while reserving the large moon for clear sky", () => {
    const items = [
      { ariaLabel: "23:00 sereno", icon: { night: true, type: "ClearNight" }, temperature: "24°", time: "23:00", timestamp: "2026-09-16T21:00:00Z" },
      { ariaLabel: "00:00 nuvoloso", icon: { night: true, type: "MostlyClearNight" }, temperature: "23°", time: "00:00", timestamp: "2026-09-16T22:00:00Z" },
      { ariaLabel: "01:00 coperto", icon: { night: true, type: "OvercastNight" }, temperature: "22°", time: "01:00", timestamp: "2026-09-16T23:00:00Z" },
    ];
    const markup = renderToStaticMarkup(<HomeQuickGrid hourly={{ items }} language="it" />);

    expect(markup.match(/mf-home-quick-forecast__moon/g)).toHaveLength(1);
    expect(markup.match(/mf-home-meteocon-icon/g)).toHaveLength(2);
    expect(markup.match(/mf-home-quick-forecast__night-crescent/g)).toHaveLength(2);
    expect(markup.match(/mf-home-quick-forecast__icon-surface/g)).toHaveLength(3);
    expect(markup.match(/data-phase="night"/g)).toHaveLength(3);
    expect(markup).not.toContain('data-phase="day"');
  });

  it.each([
    ["it", "Santo del giorno", "San Zaccaria, profeta", "Apri l'almanacco"],
    ["fur", "Sant dal dì", "Sant Zaccaria, profete", "Vierç l'almanac"],
  ])("keeps the %s Home almanac focused on the saint", (language, label, saint, action) => {
    const markup = renderToStaticMarkup(
      <HomeQuickGrid
        almanac={{
          actionLabel: action,
          body: saint,
          dateLabel: language === "fur" ? "Domenie 6 Setembar" : "Domenica 6 settembre",
          moon: { cycleProgress: 63, phase: language === "fur" ? "Ultin cuart" : "Ultimo quarto" },
          saintLabel: saint,
          title: language === "fur" ? "Almanac" : "Almanacco",
        }}
        language={language}
        onNavigate={() => {}}
      />,
    );
    const card = getAlmanacCard(markup);

    expect(card).toContain(label);
    expect(card).toContain(saint);
    expect(card).toContain("lucide-book-open-text");
    expect(card).toContain(`aria-label="${action.replace("'", "&#x27;")}:`);
    expect(card).not.toContain(language === "fur" ? "Ultin cuart" : "Ultimo quarto");
    expect(card).not.toContain("mf-moon-phase-icon");
    expect(markup).not.toContain("mf-home-quick-card--why");
  });
});
