import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HomeBulletinSummary } from "./HomeBulletinSummary";

describe("HomeBulletinSummary", () => {
  it("renders advice as a soft callout without a competing title", () => {
    const markup = renderToStaticMarkup(
      <HomeBulletinSummary
        bulletin={{
          actionLabel: "Apri il bollettino",
          advice: {
            group: "rain",
            label: "Ombrello a portata di mano: nelle prossime ore potrebbe tornare utile.",
            source: "icon2i",
            title: "Consigliato",
          },
          dateLabel: "Oggi · OSMER 12:12",
          headline: "Cielo variabile",
          icon: { type: "Cloud" },
          title: "Sintesi",
        }}
        onOpen={() => {}}
      />,
    );

    expect(markup).toContain('data-advice-source="icon2i"');
    expect(markup).toContain('data-advice-status="ready"');
    expect(markup).not.toContain("Consigliato");
    expect(markup).toContain("Ombrello a portata di mano");
    expect(markup).toContain("mf-home-bulletin-card__advice-icon");
    expect(markup).toContain("mf-home-bulletin--summary");
    expect(markup).not.toContain("mf-home-bulletin-card__icon--weather");
  });

  it("reserves the callout height with a discreet skeleton while advice is pending", () => {
    const markup = renderToStaticMarkup(
      <HomeBulletinSummary
        bulletin={{
          actionLabel: "Apri il bollettino",
          advice: null,
          adviceStatus: "pending",
          body: "",
          dateLabel: "Oggi · OSMER 12:12",
          headline: "Cielo variabile",
          icon: { type: "Cloud" },
          title: "Sintesi",
        }}
      />,
    );

    expect(markup).toContain('data-advice-status="pending"');
    expect(markup).toContain("mf-home-bulletin-card__advice-skeleton-copy");
    expect(markup).not.toContain("Consigliato");
  });

  it("keeps the OSMER headline above the published editorial message", () => {
    const markup = renderToStaticMarkup(<HomeBulletinSummary bulletin={{
      title: "Sintesi", headline: "Cielo variabile", dateLabel: "Oggi · OSMER 12:12",
      advice: { source: "editorial", group: "message", type: "message",
        title: "Meteo Friûl ti accompagna", label: "Scopri cosa fare oggi." },
    }} />);
    expect(markup).toContain('data-advice-source="editorial"');
    expect(markup.indexOf("Cielo variabile")).toBeLessThan(markup.indexOf("Meteo Friûl ti accompagna"));
    expect(markup).toContain("Scopri cosa fare oggi.");
  });
});
