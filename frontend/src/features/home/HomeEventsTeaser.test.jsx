import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HomeEventsTeaser } from "./HomeEventsTeaser";

function buildEvents(image = "") {
  return {
    actionLabel: "Eventi",
    countLabel: "12 eventi",
    items: [
      {
        dateLabel: "Oggi",
        id: "featured-event",
        image,
        location: "Pordenone",
        title: "Evento consigliato",
      },
    ],
    tagsLabel: "Dettagli evento",
    title: "Eventi vicino a te",
  };
}

describe("HomeEventsTeaser", () => {
  it("renders the featured event image as a lazy decorative preview", () => {
    const markup = renderToStaticMarkup(
      <HomeEventsTeaser
        events={buildEvents("https://example.com/event-preview.jpg")}
        onOpen={() => {}}
      />,
    );

    expect(markup).toContain("mf-home-events-card__icon--image");
    expect(markup).toContain('src="https://example.com/event-preview.jpg"');
    expect(markup).toContain('loading="lazy"');
    expect(markup).toContain('alt=""');
    expect(markup).toContain("mf-home-events-card__details");
    expect(markup).toContain("Pordenone");
    expect(markup).toContain("Oggi");
    expect(markup).not.toContain("mf-home-events-card__tags");
  });

  it("keeps the ticket fallback when the event has no image", () => {
    const markup = renderToStaticMarkup(
      <HomeEventsTeaser events={buildEvents()} onOpen={() => {}} />,
    );

    expect(markup).not.toContain("mf-home-events-card__icon--image");
    expect(markup).toContain("lucide-ticket");
  });
});
