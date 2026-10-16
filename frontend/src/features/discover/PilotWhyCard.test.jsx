import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { PilotWhyCard } from "./PilotWhyCard";
import { getPilotWhyContent, getPilotWhyContentForDate } from "./pilotWhyContent";

describe("PilotWhyCard", () => {
  it.each(["it", "fur"])("shows the complete %s answer with an immediate lead and one discreet source", language => {
    const content = getPilotWhyContent(language);
    const html = renderToStaticMarkup(<PilotWhyCard content={content} />);
    expect(html).toContain(`<h3>${content.question}</h3>`);
    expect(html).toContain(`id="${content.anchor}" tabindex="-1"`);
    expect(html).toContain(`<strong class="mf-discover-why__lead">${content.lead}</strong>`);
    expect(html.match(/mf-discover-why__lead/g)).toHaveLength(1);
    expect(html.indexOf(content.lead)).toBeLessThan(html.indexOf(content.answer[0]));
    content.answer.forEach(paragraph => expect(html).toContain(paragraph));
    expect(html).toContain(`<span class="mf-discover-why__source-label">${content.sourcesLabel}</span>`);
    expect(html.match(/<a\s/g)).toHaveLength(1);
    expect(html).toContain(`href="${content.sources[0].url}"`);
    expect(html).toContain(content.sources[0].label);
    expect(html).not.toContain(content.sources[1].url);
    expect(content.sources).toHaveLength(2);
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).not.toMatch(/<details|<summary|<button|is-clamped/);
  });

  it("renders a declared catalogue source as text without inventing a link or lead", () => {
    const content = getPilotWhyContentForDate("it", "2026-09-09");
    const html = renderToStaticMarkup(<PilotWhyCard content={content} />);
    expect(content.lead).toBe("");
    expect(html).not.toContain("mf-discover-why__lead");
    expect(html).not.toContain("<a ");
    expect(html).toContain(`class="mf-discover-why__source-text">${content.sources[0].label}</span>`);
  });

  it("does not render an empty answer card", () => {
    expect(renderToStaticMarkup(<PilotWhyCard content={null} />)).toBe("");
  });
});
