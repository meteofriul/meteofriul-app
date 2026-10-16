import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { HomeTeaserCard } from "./HomeTeaserCard";

describe("HomeTeaserCard", () => {
  it("uses a single native button to invoke the supplied card action", () => {
    const onOpen = vi.fn();
    const card = HomeTeaserCard({
      className: "mf-home-bulletin-card",
      heading: "Sintesi",
      headingId: "home-bulletin-title",
      label: "Bollettino: Sole e nubi",
      onOpen,
    });
    const action = card.props.children[0];

    expect(action.type).toBe("button");
    expect(action.props.type).toBe("button");
    expect(action.props["aria-label"]).toBe("Bollettino: Sole e nubi");
    expect(onOpen).not.toHaveBeenCalled();
    action.props.onClick();
    expect(onOpen).toHaveBeenCalledOnce();
  });

  it("does not create an inert button without an action", () => {
    const markup = renderToStaticMarkup(
      <HomeTeaserCard className="mf-home-events-card" heading="Eventi vicino a te" headingId="events-title" />,
    );

    expect(markup).not.toContain("<button");
    expect(markup).toContain('<h2 id="events-title">Eventi vicino a te</h2>');
  });

  it("retains the former large title size and permits wrapping instead of shrinking metadata", () => {
    const css = readFileSync(new URL("./home.css", import.meta.url), "utf8");
    const titleRule = css.match(/\.mf-home-card-heading h2 \{([^}]+)\}/)?.[1];
    const headerRule = css.match(/\.mf-home-card-heading \{([^}]+)\}/)?.[1];
    const metaRule = css.match(/\.mf-home-card-heading__meta \{([^}]+)\}/)?.[1];

    expect(titleRule).toContain("font-size: var(--mf-text-xl)");
    expect(headerRule).toContain("flex-wrap: wrap");
    expect(metaRule).toContain("font-size: var(--mf-text-sm)");
    expect(css).toContain(".mf-home-teaser-action:focus-visible");
  });
});
