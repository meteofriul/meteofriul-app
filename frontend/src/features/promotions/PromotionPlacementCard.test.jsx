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
    expect(markup).toContain("mf-home-promotion__body--with-headline");
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

  it("renders only selected text rows while keeping advertising and action visible", () => {
    const markup = renderToStaticMarkup(
      <PromotionPlacementCard
        campaigns={[{
          ...campaign,
          location: "Pordenone",
          category: "Salone",
          businessAddress: "Via Roma 12",
          visibleFields: ["city", "title"],
        }]}
        now={0}
      />,
    );
    expect(markup).toContain("Pubblicità");
    expect(markup).toContain("Pordenone");
    expect(markup).toContain("Una proposta del territorio");
    expect(markup).toContain("Scopri ora");
    expect(markup).not.toContain("Attività locale");
    expect(markup).not.toContain("Descrizione promozionale.");
    expect(markup).not.toContain("Via Roma 12");
    expect(markup).not.toContain("Salone");
    expect(markup).toContain("Scopri ora: Pordenone");
  });

  it("uses a selected detail as the accessible name when the primary row is hidden", () => {
    const markup = renderToStaticMarkup(
      <PromotionPlacementCard
        campaigns={[{
          ...campaign,
          category: "Marketing, comunicazione e media",
          visibleFields: ["category"],
        }]}
        now={0}
      />,
    );
    expect(markup).toContain("Scopri ora: Marketing, comunicazione e media");
    expect(markup).not.toContain("Attività locale");
    expect(markup).not.toContain("mf-home-promotion__body--with-headline");
  });
});
