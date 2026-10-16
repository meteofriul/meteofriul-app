import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PromotionPlacementCard } from "./PromotionPlacementCard";

const campaign = {
  advertiserDailyCap: 3,
  advertiserId: "sponsor",
  campaignDailyCap: 3,
  ctaLabel: "Scopri ora",
  enabled: true,
  headline: "Una proposta del territorio",
  id: "campaign",
  placements: ["home", "events", "discover"],
  placementAssignments: {
    home: { cardNumber: 1, mode: "exclusive" },
    events: { cardNumber: 1, mode: "rotation" },
    discover: { cardNumber: 1, mode: "rotation" },
  },
  text: "Descrizione promozionale.",
  title: "Attività locale",
  url: "https://example.test/",
};

describe("PromotionPlacementCard", () => {
  it.each(["home", "events", "discover"])("renders the %s placement with the shared contract", (placement) => {
    const markup = renderToStaticMarkup(
      <PromotionPlacementCard campaigns={[campaign]} now={0} placement={placement} />,
    );

    expect(markup).toContain(`data-promotion-placement="${placement}"`);
    expect(markup).toContain("Pubblicità");
    expect(markup).toContain("Una proposta del territorio");
    expect(markup).toContain("Scopri ora: Attività locale");
    expect(markup).toContain('rel="sponsored noopener noreferrer"');
  });

  it("shows only the optional details present in the public payload", () => {
    const withDetails = renderToStaticMarkup(
      <PromotionPlacementCard
        campaigns={[{ ...campaign, category: "Marketing, comunicazione e media", businessAddress: "Via Roma 12" }]}
        now={0}
      />,
    );
    expect(withDetails).toContain("Marketing, comunicazione e media · Via Roma 12");
    const withoutDetails = renderToStaticMarkup(<PromotionPlacementCard campaigns={[campaign]} now={0} />);
    expect(withoutDetails).not.toContain("mf-home-promotion__details");
  });
});
