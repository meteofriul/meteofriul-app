import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getUiShellCopy } from "../../app/uiShellCopy";
import { AlmanacCulture, DiscoverCard, DiscoverView } from "./DiscoverView";
import { buildPilotCalendarSummary } from "./pilotCalendarSummary";
import { isLocalWeatherPilot } from "../../services/localWeatherPilot";
import { getPilotWhyContentForDate } from "./pilotWhyContent";

const experience = vi.hoisted(() => vi.fn(() => false));

const promotionCampaign = {
  advertiserDailyCap: 3,
  advertiserId: "sponsor",
  campaignDailyCap: 3,
  ctaLabel: "Scopri ora",
  enabled: true,
  id: "discover-promotion",
  placements: ["discover"],
  placementAssignments: {
    discover: { cardNumber: 1, mode: "rotation" },
  },
  text: "Descrizione promozionale.",
  title: "Attività locale",
  url: "https://example.test/",
};

vi.mock("../../services/localWeatherPilot", async (importOriginal) => ({
  ...await importOriginal(),
  isDefinitiveAppExperience: experience,
  isLocalWeatherPilot: experience,
}));

function detectedPordenone() {
  return {
    city: "Pordenone", istatCode: "093033", province: "PN", regionCode: "IT-36",
    source: "browser_geolocation", lat: 45.9567, lon: 12.6605,
    municipality: { name: "Pordenone", istatCode: "093033", province: "PN", source: "istat_boundaries" },
    dataPoint: { lat: 45.9567, lon: 12.6605, source: "municipality_catalog" },
    resolution: { status: "resolved", municipalityResolved: true, boundaryDistanceM: 500 },
    positionAccuracyM: 20, positionCapturedAt: new Date().toISOString(),
  };
}

afterEach(() => {
  vi.mocked(isLocalWeatherPilot).mockReturnValue(false);
  vi.useRealTimers();
});

describe("DiscoverView", () => {
  it.each(["it", "fur"])("labels the active manual municipality as selected in %s", (language) => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    const html = renderToStaticMarkup(<DiscoverView
      activeLocation={{ city: "Udine", region: "Friuli Venezia Giulia" }}
      municipalityLocation={{ city: "Pordenone", istatCode: "093033", province: "PN", source: "manual" }}
      copy={getUiShellCopy(language)} language={language}
    />);

    expect(html).toContain('id="discover-card-municipality-profile-pordenone"');
    expect(html).not.toContain('id="discover-card-municipality-profile-udine"');
    expect(html).toContain(language === "fur" ? "Comun selezionât" : "Comune selezionato");
    expect(html).not.toContain(language === "fur" ? "Comun individuât" : "Comune individuato");
  });

  it("preserves a pending-translation note and complete source in the pilot card", () => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    const html = renderToStaticMarkup(<DiscoverCard language="fur" sectionId="today-memory"
      furPendingLabel="Test in talian - FUR in revision"
      card={{ id: "pending", title: "Titolo approvato IT", text: "Testo integrale.", isFurPending: true, sourceLabel: "Archivio locale verificato" }}
    />);
    expect(html).toContain("Archivio locale verificato - Test in talian - FUR in revision");
    expect(html).toContain("Testo integrale.");
  });

  it.each(["it", "fur"])("keeps all pilot %s rubric cards visible with one sayings and one traditions group", (language) => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-08T12:00:00Z"));
    const html = renderToStaticMarkup(<DiscoverView
      activeLocation={{ city: "Pordenone", region: "Friuli Venezia Giulia" }}
      autoLocationEnabled
      deviceLocationStatus={{ status: "success", location: detectedPordenone() }}
      copy={getUiShellCopy(language)} language={language}
    />);

    expect(html).not.toContain("<details");
    expect(html).not.toContain("<summary");
    expect(html).toContain("mf-discover-calendar--pilot");
    expect(html).toContain("mf-discover-view--editorial");
    expect(html).toContain(language === "fur" ? "Comun individuât" : "Comune individuato");
    expect(html).not.toContain(language === "fur" ? "Comun dal dì" : "Comune del giorno");
    expect(html).toContain('class="mf-tab-page__title--hidden"');
    expect(html).toContain("mf-discover-card--editorial");
    const why = getPilotWhyContentForDate(language, "2026-09-08");
    expect(html).toContain(`<h3>${why.question}</h3>`);
    expect(html.match(new RegExp(`id="${why.anchor}"`, "g"))).toHaveLength(1);
    expect(html.indexOf('id="discover-why-title"')).toBeGreaterThan(html.indexOf('id="discover-calendar-title"'));
    expect(html.indexOf('id="discover-why-title"')).toBeLessThan(html.indexOf("mf-discover-card--municipality"));
    expect(html).not.toContain("mf-discover-card__icon");
    expect(html).toContain(language === "fur" ? "Musiche" : "Musica");
    expect(html.match(/id="discover-traditional-sayings"/g)).toHaveLength(1);
    expect(html.match(/id="discover-traditions"/g)).toHaveLength(1);
    expect(html).toContain(language === "fur" ? "Tradizions dal Friûl" : "Tradizioni del Friûl");
    expect(html).not.toContain('id="discover-rituals"');
    expect(html).not.toContain('id="discover-archive"');
    expect(html).not.toContain('id="discover-card-almanac-proverb"');
    expect(html.match(/class="mf-discover-earth-tip"/g)).toHaveLength(1);
    expect(html.indexOf('id="discover-traditions"')).toBeGreaterThan(html.indexOf('id="discover-traditional-sayings"'));
    expect(html.indexOf('id="discover-today-memory"')).toBeGreaterThan(html.indexOf("mf-discover-card--municipality"));
    const pageSource = html.match(/<p class="mf-discover-source">([\s\S]*?)<\/p>/)?.[1] || "";
    expect(pageSource).not.toContain("<svg");
    const cardIds = [...html.matchAll(/id="(discover-card-[^"]+)"/g)].map(match => match[1]);
    expect(new Set(cardIds).size).toBe(cardIds.length);
  });

  it("keeps the sponsor after the three opening Scopri blocks", () => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-08T12:00:00Z"));
    const html = renderToStaticMarkup(<DiscoverView
      activeLocation={{ city: "Pordenone", region: "Friuli Venezia Giulia" }}
      copy={getUiShellCopy("it")}
      language="it"
      promotionCampaigns={[promotionCampaign]}
    />);
    const sponsorPosition = html.indexOf('data-promotion-placement="discover"');

    expect(sponsorPosition).toBeGreaterThan(html.indexOf("mf-discover-card--municipality"));
    expect(sponsorPosition).toBeLessThan(html.indexOf('id="discover-today-memory"'));
  });

  it("keeps the question selected on Home when the civil day changes before Scopri opens", () => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    vi.useFakeTimers();
    const clicked = getPilotWhyContentForDate("it", "2026-09-08");
    vi.setSystemTime(new Date("2026-09-09T12:00:00Z"));
    const html = renderToStaticMarkup(<DiscoverView
      activeLocation={{ city: "Pordenone" }}
      copy={getUiShellCopy("it")}
      language="it"
      pilotWhyId={clicked.id}
    />);
    expect(html).toContain(clicked.question);
    expect(html).toContain(`id="${clicked.anchor}"`);
    expect(html).not.toContain(getPilotWhyContentForDate("it", "2026-09-09").question);
  });

  it("preserves legacy beta accordions and rubric groups", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-08T12:00:00Z"));
    const html = renderToStaticMarkup(<DiscoverView
      activeLocation={{ city: "Pordenone" }} copy={getUiShellCopy("it")} language="it"
    />);
    expect(html).toContain('<details class="mf-discover-calendar"');
    expect(html).toContain('id="discover-archive"');
    expect(html).not.toContain('id="discover-traditions"');
    expect(html).not.toContain("mf-discover-earth-tip");
    expect(html).not.toContain("mf-discover-calendar--pilot");
    expect(html).not.toContain("mf-discover-view--editorial");
    expect(html).not.toContain("mf-discover-card--editorial");
    expect(html).not.toContain("mf-location-change");
    expect(html).not.toContain(">Cambia<");
    expect(html).not.toContain('id="discover-why-title"');
    expect(html).toContain("mf-discover-card__icon");
  });

  it.each(["it", "fur"])("keeps the other-saints preview expandable inside the visible %s pilot card", (language) => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-07T12:00:00Z"));
    const html = renderToStaticMarkup(<DiscoverView
      activeLocation={{ city: "Pordenone" }} copy={getUiShellCopy(language)} language={language}
    />);
    expect(html).not.toContain("<details");
    expect(html).toContain("mf-discover-other-saints");
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('class="is-clamped"');
    expect(html).toContain(language === "fur" ? "Mostre altris…" : "Mostra altri…");
  });

  it.each([true, false])("preserves secondary memories and only removes their accordion in pilot=%s", (pilot) => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(pilot);
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-01T12:00:00Z"));
    const html = renderToStaticMarkup(<DiscoverView
      activeLocation={{ city: "Trieste", istatCode: "032006", province: "TS" }} copy={getUiShellCopy("it")} language="it"
    />);
    expect(html).toContain('id="discover-local-memory-secondary"');
    expect(html).toContain('id="discover-card-memory-secondary-0101-societa-minerva-1810"');
    expect(html.includes('<details class="mf-discover-more-memories"')).toBe(!pilot);
  });

  it("keeps the reviewed brief but excludes biographies and sources from the pilot calendar", () => {
    const original = { seasonLabel: "Estate", saint: { label: "Santa Regina, martire", nameDays: ["Regina"], body: "Nota CEI", biography: ["Testo Vatican News"], sourceLabel: "CEI", sourceUrl: "https://example.org", biographySource: "Vatican News" } };
    const result = buildPilotCalendarSummary(original);
    expect(result.saint.body).toBe("Nota CEI");
    expect(result.saint.biography).toEqual([]);
    expect(result.saint.sourceLabel).toBe("");
    expect(result.saint.sourceUrl).toBe("");
    expect(result.saint.biographySource).toBe("");
    expect(result.saint.nameDays).toEqual(["Regina"]);
    expect(result.seasonLabel).toBe("Estate");
    expect(original.saint.body).toBe("Nota CEI");
  });

  it.each([
    ["it", "Pietro Claver, sacerdote gesuita, assistette per oltre quarant'anni gli schiavi a Cartagena"],
    ["fur", "Pietro Claver, predi gesuite, al à assistût i sclâfs a Cartagena"],
  ])("shows the reviewed %s saint brief in the pilot without a visible source", (language, brief) => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-09T12:00:00Z"));
    const html = renderToStaticMarkup(<DiscoverView
      activeLocation={{ city: "Pordenone" }} copy={getUiShellCopy(language)} language={language}
    />);
    expect(html).toContain("mf-discover-calendar__brief");
    expect(html).toContain(brief.replace("'", "&#x27;"));
    expect(html).not.toContain("CEI - Martirologio Romano");
    expect(html).not.toContain("chiesacattolica.it");
    expect(html).not.toContain(language === "fur" ? ">Font:" : ">Fonte:");
  });
  it("migrates all earth tips and avoids an identical cultural text", () => {
    const html = renderToStaticMarkup(<AlmanacCulture language="it" copy={{}} calendar={{
      proverb: { title: "Proverbio", body: "Testo comune." },
      tradition: { label: "Tradizione", body: "Storia locale", source: "Fonte storica" },
      earth: { title: "Consiglio della terra", items: ["Primo consiglio", "Secondo consiglio"] },
    }} sections={[{ id: "traditional-sayings", title: "Detti", cards: [{ id: "existing", title: "Detto", text: "Testo comune." }] }]} />);
    expect(html.match(/Testo comune\./g)).toHaveLength(1);
    expect(html).toContain("Storia locale");
    expect(html).toContain("Fonte storica");
    expect(html).toContain("Primo consiglio");
    expect(html).toContain("Secondo consiglio");
    expect(html).not.toContain("<details");
    expect(html.match(/class="mf-discover-earth-tip"/g)).toHaveLength(1);
  });
  it("renders curated Scopri content instead of the lab placeholder", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-08T12:00:00Z"));
    const html = renderToStaticMarkup(
      <DiscoverView
        activeLocation={{ city: "Pordenone", region: "Friuli Venezia Giulia" }}
        copy={getUiShellCopy("it")}
        language="it"
      />,
    );

    expect(html).toContain("Scopri");
    expect(html).not.toContain('class="mf-tab-page__title--hidden"');
    expect(html).not.toContain("mf-discover-count");
    expect(html).not.toContain("mf-tab-page__title-meta");
    expect(html).toContain("Pordenone");
    expect(html).toContain("Comune del giorno");
    expect(html).toContain("Storia e territorio");
    expect(html).toContain("Tappe storiche");
    expect(html).toContain("Prima citazione nota di Portus Naonis");
    expect(html).toContain("Pordenone, città del Noncello");
    expect(html).toContain("Il porto sul Noncello favorì lo sviluppo");
    expect(html).not.toContain("A Pordenone");
    expect(html).not.toContain("Conosci Pordenone");
    expect(html).not.toContain("Pordenone è documentata nel 1204");
    expect(html).not.toContain(">Il comune<");
    expect(html.match(/Pordenone/g)).toHaveLength(1);
    expect(html).toContain("mf-discover-card--location");
    expect(html).toContain("mf-discover-card--municipality");
    expect(html).toContain("mf-discover-card--with-photo");
    expect(html).toContain('id="discover-card-municipality-profile-pordenone"');
    expect(html).toContain('tabindex="-1"');
    expect(html).toContain("mf-discover-card__kicker");
    expect(html).toContain("/municipalities/coats/093033-coat.png");
    expect(html).toContain("/municipalities/photos/093033-photo.webp");
    expect(html).toContain("mf-discover-focus__label");
    expect(html).toContain("Ostermann 1894");
    expect(html).not.toContain("Contenuti e ranking saranno importati con test.");
    expect(html).not.toContain("mf-discover-placeholder");
  });

  it("shows the municipality before daily rubrics, after the compact calendar", () => {
    const html = renderToStaticMarkup(
      <DiscoverView
        activeLocation={{ city: "Pordenone", region: "Friuli Venezia Giulia" }}
        copy={getUiShellCopy("it")}
        language="it"
      />,
    );
    const memoryPosition = html.indexOf('id="discover-today-memory"');
    const sayingPosition = html.indexOf('id="discover-traditional-sayings"');
    const archivePosition = html.indexOf('id="discover-archive"');
    const municipalityPosition = html.indexOf("mf-discover-card--municipality");

    expect(memoryPosition).toBeGreaterThan(-1);
    expect(sayingPosition).toBeGreaterThan(memoryPosition);
    expect(archivePosition).toBeGreaterThan(sayingPosition);
    expect(municipalityPosition).toBeLessThan(memoryPosition);
    expect(html.indexOf('mf-discover-calendar')).toBeLessThan(municipalityPosition);
  });

  it("does not render an empty metadata item for general sayings", () => {
    const html = renderToStaticMarkup(
      <DiscoverCard
        card={{
          id: "general-saying",
          seasonLabel: "",
          sourceLabel: "Ostermann 1876",
          text: "",
          title: "Un detto generale",
          typeLabel: "Detto popolare",
        }}
      />,
    );

    expect(html).toContain('<div class="mf-discover-card__meta"><span>Detto popolare</span></div>');
    expect(html).toContain('id="discover-card-general-saying"');
    expect(html).not.toContain("<span></span>");
  });

  it.each([
    ["Pordenone", "093033"],
    ["Udine", "030129"],
    ["Gorizia", "031007"],
    ["Trieste", "032006"],
  ])("renders the %s municipality profile with its reviewed visuals", (city, istatCode) => {
    const html = renderToStaticMarkup(
      <DiscoverView
        activeLocation={{ city, region: "Friuli Venezia Giulia" }}
        copy={getUiShellCopy("it")}
        language="it"
      />,
    );

    expect(html).toContain("mf-discover-card--municipality");
    expect(html).toContain("mf-discover-card--with-photo");
    expect(html).toContain(`/municipalities/coats/${istatCode}-coat.png`);
    expect(html).toContain(`/municipalities/photos/${istatCode}-photo.webp`);
    expect(html).toContain("Comune del giorno");
    expect(html.indexOf("Storia e territorio")).toBeGreaterThan(html.indexOf("mf-discover-card--municipality"));
    expect(html).not.toContain(`Conosci ${city}`);
  });

  it("renders an enriched municipality profile with its reviewed coat of arms", () => {
    const html = renderToStaticMarkup(
      <DiscoverView
        activeLocation={{
          city: "Cordenons",
          istatCode: "093017",
          region: "Friuli Venezia Giulia",
        }}
        copy={getUiShellCopy("it")}
        language="it"
      />,
    );

    expect(html).toContain("Comune del giorno");
    expect(html).toContain("Storia e territorio");
    expect(html).toContain("Cordenons, dalla Curtis Naonis alle risorgive");
    expect(html).not.toContain("Comune di Cordenons - Storia del Comune");
    expect(html).toContain("Tappe storiche");
    expect(html).toContain("Un diploma ricorda la corte regia di Cordenons");
    expect(html).toContain("Cordenons diventa comune autonomo");
    expect(html).toContain("mf-discover-card--municipality");
    expect(html).toContain("/municipalities/coats/093017-coat.png");
  });

  it("renders municipality milestones in FUR when reviewed copy is available", () => {
    const html = renderToStaticMarkup(
      <DiscoverView
        activeLocation={{
          city: "Cordenons",
          istatCode: "093017",
          region: "Friuli Venezia Giulia",
        }}
        copy={getUiShellCopy("fur")}
        language="fur"
      />,
    );

    expect(html).toContain("Comun dal dì");
    expect(html).toContain("Storie e teritori");
    expect(html).toContain("Tapis storichis");
    expect(html).toContain("Un diplome al ricuarde la curt regjie di Cordenons");
    expect(html).toContain("Cordenons al devente comun autonom");
  });

  it("renders the completed Stregna municipality timeline", () => {
    const html = renderToStaticMarkup(
      <DiscoverView
        activeLocation={{ city: "Stregna", istatCode: "030111" }}
        copy={getUiShellCopy("it")}
        language="it"
      />,
    );

    expect(html).toContain("Stregna, comunità della Banca di Merso");
    expect(html).toContain("mf-discover-card__timeline");
    expect(html).toContain("mf-discover-card--with-photo");
    expect(html).toContain("/municipalities/photos/030111-photo.webp");
    expect(html).toContain("Tappe storiche");
    expect(html).toContain("Stregna e Tribil passano sotto la Repubblica di Venezia");
    expect(html).toContain("Stregna è documentata come Comune dal 1806");
    expect(html).not.toContain("Wikipedia italiana - Stregna");
  });

  it("uses localized copy for FUR pending cards", () => {
    const html = renderToStaticMarkup(
      <DiscoverCard
        card={{
          id: "pending-fur",
          isFurPending: true,
          seasonLabel: "Dut l'an",
          sourceLabel: "Ostermann 1894",
          text: "Testo in italiano.",
          title: "Titolo italiano",
          typeLabel: "Archivio",
        }}
        furPendingLabel="Test in talian - FUR in revision"
      />,
    );

    expect(html).toContain("Ostermann 1894 - Test in talian - FUR in revision");
    expect(html).not.toContain("FUR in revisione");
  });
});
