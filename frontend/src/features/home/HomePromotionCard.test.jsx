import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HomePromotionCard } from "./HomePromotionCard";

const campaign = {
  advertiserDailyCap: 1,
  advertiserId: "ale-hair-studio",
  campaignDailyCap: 1,
  ctaLabel: "Scopri il salone",
  enabled: true,
  id: "ale-home",
  location: "Pordenone",
  placements: ["home"],
  placementAssignments: {
    home: { cardNumber: 1, mode: "exclusive" },
  },
  text: "Tagli e colore su misura.",
  title: "Ale Hair Studio",
  url: "https://alehairstudio.it/",
};

describe("HomePromotionCard", () => {
  it.each([
    ["it", "Pubblicità", "Scopri il salone"],
    ["fur", "Publicitât", "Scopri il salone"],
  ])("labels the %s placement as advertising and opens the sponsor site externally", (language, label, action) => {
    const markup = renderToStaticMarkup(
      <HomePromotionCard campaigns={[campaign]} language={language} now="2026-09-24T08:00:00+02:00" />,
    );

    expect(markup).toContain(label);
    expect(markup).toContain("Ale Hair Studio · Pordenone");
    expect(markup).toContain('href="https://alehairstudio.it/"');
    expect(markup).toContain('rel="sponsored noopener noreferrer"');
    expect(markup).toContain('target="_blank"');
    expect(markup).toContain(`${action}: Ale Hair Studio`);
    expect(markup).not.toMatch(/pixel|analytics|gps|geolocation/iu);
  });
});
