import { describe, expect, it } from "vitest";

import { buildEventPreviewModel } from "./eventPreview";

describe("event preview model", () => {
  it("prefers verified event details and builds a Maps destination without an API key", () => {
    const preview = buildEventPreviewModel({
      category: "cultura",
      categoryLabel: "Cultura",
      date: "dal 21 maggio al 6 settembre",
      dateChip: { accessibleLabel: "dal 21 maggio al 6 settembre" },
      image: "https://images.example.org/klimt.jpg",
      location: "Codroipo · 12 km",
      raw: {
        address: "Piazza Manin 10",
        description: "<p>Una mostra dedicata a <strong>Klimt</strong>.</p>",
        event_city: "Codroipo",
        official_site: "https://www.villamanin.it/mostre/klimt",
        venue: "Villa Manin",
      },
      source: "TurismoFVG",
      title: "Nuda Veritas. Klimt",
      url: "https://www.turismofvg.it/eventi/klimt",
    });

    expect(preview).toMatchObject({
      category: "cultura",
      dateLabel: "dal 21 maggio al 6 settembre",
      description: "Una mostra dedicata a Klimt.",
      location: "Villa Manin · Piazza Manin 10 · Codroipo",
      monogram: "N",
      pageUrl: "https://www.villamanin.it/mostre/klimt",
      source: "TurismoFVG",
      title: "Nuda Veritas. Klimt",
    });
    const directions = new URL(preview.directionsUrl);
    expect(directions.origin + directions.pathname).toBe("https://www.google.com/maps/dir/");
    expect(directions.searchParams.get("api")).toBe("1");
    expect(directions.searchParams.get("destination")).toBe("Villa Manin, Piazza Manin 10, Codroipo");
  });

  it("uses exact coordinates or the verified municipality centre", () => {
    const exact = buildEventPreviewModel({
      raw: {
        event_city: "Pordenone",
        lat: 45.9567,
        location_confidence: "exact",
        lon: 12.6605,
      },
      title: "Concerto in piazza",
    });
    const municipality = buildEventPreviewModel({
      raw: {
        event_city: "Pordenone",
        lat: 45.9567,
        location_confidence: "municipality",
        lon: 12.6605,
      },
      title: "Concerto in piazza",
    });

    expect(new URL(exact.directionsUrl).searchParams.get("destination")).toBe("45.9567,12.6605");
    expect(new URL(municipality.directionsUrl).searchParams.get("destination"))
      .toBe("45.9567,12.6605");
  });

  it("routes a verified SagreFVG venue to its exact coordinates", () => {
    const preview = buildEventPreviewModel({
      raw: {
        address: "Piazza Garibaldi",
        event_city: "Tiezzo",
        lat: 45.8918777,
        location_confidence: "exact",
        lon: 12.6728855,
        source: "SagreFVG",
        venue: "Tiezzo",
      },
      source: "SagreFVG",
      title: "Tiezzo di Azzano X (PN) – Festa Paesana 2026",
    });

    expect(preview.location).toBe("Tiezzo · Piazza Garibaldi");
    expect(new URL(preview.directionsUrl).searchParams.get("destination"))
      .toBe("45.8918777,12.6728855");
  });

  it("accepts only HTTPS event pages and trusted Google Maps links", () => {
    const trusted = buildEventPreviewModel({
      raw: {
        location_confidence: "exact",
        maps_url: "https://maps.app.goo.gl/abc123",
        official_site: "javascript:alert(1)",
      },
      title: "Evento",
      url: "https://events.example.org/evento",
    });
    const rejected = buildEventPreviewModel({
      raw: { maps_url: "https://maps.google.com.evil.example/maps/evento" },
      title: "Evento",
      url: "http://events.example.org/evento",
    });

    expect(trusted.pageUrl).toBe("https://events.example.org/evento");
    expect(trusted.directionsUrl).toBe("https://maps.app.goo.gl/abc123");
    expect(rejected.pageUrl).toBe("");
    expect(rejected.directionsUrl).toBe("");
  });

  it("keeps long provider descriptions compact", () => {
    const description = Array.from({ length: 90 }, () => "evento").join(" ");
    const preview = buildEventPreviewModel({ raw: { context: description }, title: "Titolo" });

    expect(preview.description.length).toBeLessThanOrEqual(361);
    expect(preview.description.endsWith("…")).toBe(true);
  });

  it("does not repeat a combined place after venue and municipality", () => {
    const preview = buildEventPreviewModel({
      raw: {
        event_city: "Codroipo",
        place: "Villa Manin - Codroipo",
        venue: "Villa Manin",
      },
      title: "Cena in bianco",
    });

    expect(preview.location).toBe("Villa Manin · Codroipo");
    expect(new URL(preview.directionsUrl).searchParams.get("destination"))
      .toBe("Villa Manin, Codroipo");
  });

  it("upgrades municipality directions when detail supplies a specific venue", () => {
    const preview = buildEventPreviewModel({
      raw: {
        event_city: "Pordenone",
        lat: 45.9567,
        location_confidence: "municipality",
        lon: 12.6605,
        place: "Largo S. Giorgio Arena Largo San Giorgio",
        venue: "Largo S. Giorgio Arena Largo San Giorgio",
      },
      title: "Cinema sotto le stelle 2026",
    });

    expect(new URL(preview.directionsUrl).searchParams.get("destination"))
      .toBe("Largo S. Giorgio Arena Largo San Giorgio, Pordenone");
  });

  it("opens the municipality when no more precise destination is known", () => {
    const preview = buildEventPreviewModel({ raw: { event_city: "Udine" }, title: "Evento" });
    expect(preview).not.toHaveProperty("searchUrl");
    expect(new URL(preview.directionsUrl).searchParams.get("destination")).toBe("Udine");
  });

  it("keeps the source link but offers no invented route for several towns", () => {
    const url = "https://www.turismofvg.it/eventi/festival";
    const preview = buildEventPreviewModel({
      raw: {
        event_city: "Udine, Trieste",
        location_confidence: "multiple_municipalities",
        url,
        venue: "varie sedi",
      },
      title: "Festival",
    });
    expect(preview.directionsUrl).toBe("");
    expect(preview.pageUrl).toBe(url);
  });

  it("does not treat an unverified street stored as city text as a municipality", () => {
    const preview = buildEventPreviewModel({
      raw: {
        event_city: "via Pirandello, 33, 33170 Pordenone",
        location_confidence: "city_text",
      },
      title: "Evento",
    });

    expect(preview.directionsUrl).toBe("");
  });

  it("prefers exact coordinates over a provider Maps link", () => {
    const preview = buildEventPreviewModel({
      raw: {
        lat: 45.9723922,
        lon: 12.6746172,
        location_confidence: "exact",
        maps_url: "https://maps.app.goo.gl/possibly-stale",
      },
      title: "Sagra di Sant’Agostino",
    });

    expect(new URL(preview.directionsUrl).searchParams.get("destination"))
      .toBe("45.9723922,12.6746172");
  });

  it("uses the first meaningful title character for the visual fallback", () => {
    expect(buildEventPreviewModel({ title: "  Èstate in musica" }).monogram).toBe("È");
    expect(buildEventPreviewModel({ title: "---42 storie" }).monogram).toBe("4");
  });
});
