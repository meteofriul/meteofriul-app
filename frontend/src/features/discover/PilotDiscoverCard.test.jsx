import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PilotDiscoverCard } from "./PilotDiscoverCard";
import { getTraditionalSayingForDate } from "../../domain/discover/traditionalSayings";

const memory = {
  id: "memory-music", type: "musica", typeLabel: "Lingua e cultura",
  seasonLabel: "8 settembre", title: "Una memoria musicale",
  text: "Il testo completo della memoria, senza tagli o ricostruzioni.",
};
const render = (card, props = {}) => renderToStaticMarkup(<PilotDiscoverCard
  card={card} sourceLabel="Fonte verificata" {...props}
/>);

describe("PilotDiscoverCard", () => {
  it.each(["it", "fur"])("keeps memory metadata and all its text in %s, with the original music category", language => {
    const html = render(memory, { sectionId: "today-memory", language });
    const label = language === "fur" ? "Musiche" : "Musica";
    expect(html).toContain("mf-discover-card--memory");
    expect(html).toContain('data-editorial-tone="gold"');
    expect(html).toContain(label);
    expect(html).not.toContain("Lingua e cultura");
    expect(html.indexOf("8 settembre")).toBeLessThan(html.indexOf(label));
    expect(html).toContain(`<h3>${memory.title}</h3>`);
    expect(html).toContain(memory.text);
    expect(html).toContain('id="discover-card-memory-music" tabindex="-1"');
    expect(html).toContain('<footer class="mf-discover-editorial-source">Fonte verificata</footer>');
    expect(html).not.toMatch(/<button|<a\s|role="button"|<details|<svg|__icon|is-clamped/);
  });

  it.each(["today-memory", "territory-stories", "local-memory-secondary"])("preserves the memory anchor in %s", sectionId => {
    expect(render(memory, { sectionId })).toContain('id="discover-card-memory-music"');
  });

  it("renders a title-only saying as a single quotation without a redundant type label", () => {
    const html = render({ id: "saying", title: "Il carro senza timone finisce nel fosso.", text: "", typeLabel: "Detto popolare" }, { sectionId: "traditional-sayings" });
    expect(html).toContain('<span class="mf-discover-quote-mark" aria-hidden="true">“</span>');
    expect(html).toContain("<blockquote><p>Il carro senza timone finisce nel fosso.</p></blockquote>");
    expect(html.match(/Il carro senza timone/g)).toHaveLength(1);
    expect(html).not.toContain("Detto popolare");
    expect(html).not.toContain("<h3>");
  });

  it.each(["Proverbio", "Proverbi"])("quotes the almanac body once, not its generic %s heading", title => {
    const html = render({ id: "almanac", title, text: "La frase già selezionata." }, { sectionId: "traditional-sayings" });
    expect(html).toContain("<blockquote><p>La frase già selezionata.</p></blockquote>");
    expect(html).not.toContain(title);
    expect(html.match(/La frase già selezionata/g)).toHaveLength(1);
  });

  it("keeps thematic saying titles and commentary without misrepresenting them as literal quotations", () => {
    const html = render({ id: "themed", title: "San Macario e settembre", text: "Il tempo del 2 gennaio richiamava quello di settembre." }, { sectionId: "traditional-sayings" });
    expect(html).toContain("<h3>San Macario e settembre</h3>");
    expect(html).toContain("Il tempo del 2 gennaio richiamava quello di settembre.");
    expect(html).not.toContain("<blockquote>");
    expect(html).not.toContain("mf-discover-quote-mark");
  });

  it.each(["it", "fur"])("preserves the real San Macario title, commentary and source in %s", language => {
    const card = getTraditionalSayingForDate({ date: new Date("2026-01-02T12:00:00Z"), language });
    expect(card.id).toBe("saying-ostermann-san-macari-setembar");
    const html = render(card, { sectionId: "traditional-sayings", language, sourceLabel: card.sourceLabel });
    expect(html).toContain(`<h3>${card.title}</h3>`);
    expect(html).toContain(card.text);
    expect(html).toContain(card.sourceLabel);
    expect(html).not.toContain("<blockquote>");
  });

  it("shortens the Ostermann credit without changing other sources", () => {
    const ostermann = render(memory, {
      sourceLabel: "Da Ostermann 1894, con selezione editoriale Meteo Friul.",
    });

    expect(ostermann).toContain(">Ostermann 1894</footer>");
    expect(ostermann).not.toContain("con selezione editoriale Meteo Friul");
    expect(render(memory, { sourceLabel: "Museo Carnico" })).toContain(">Museo Carnico</footer>");
  });

  it.each([["rito", "gold"], ["calendario", "green"], ["agricoltura", "green"], ["astronomia", "sky"], ["unknown", "neutral"]])("assigns the %s accent by data category, not position", (type, tone) => {
    const html = render({ ...memory, type, typeLabel: "Categoria originale" }, { sectionId: "traditions" });
    expect(html).toContain(`data-editorial-tone="${tone}"`);
    expect(html).toContain("Categoria originale");
    expect(html.indexOf("Categoria originale")).toBeLessThan(html.indexOf("8 settembre"));
    expect(html).toContain(memory.text);
  });

  it("preserves long sources, missing metadata and text without adding empty slots", () => {
    const source = "Un archivio locale con una fonte molto lunga e verificata";
    const text = "Racconto completo. ".repeat(30);
    const html = render({ id: "long", title: "Racconto", text }, { sourceLabel: source });
    expect(html).toContain(text);
    expect(html).toContain(source);
    expect(html).not.toContain("mf-discover-editorial-meta");
    expect(html).not.toContain("undefined");
    expect(render({ id: "no-source", title: "Titolo" }, { sourceLabel: "" })).not.toContain("<footer");
  });
});
