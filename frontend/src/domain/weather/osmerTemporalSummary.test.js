import { describe, expect, it } from "vitest";

import normalizedFixture from "../../tests/fixtures/PW20260606.normalized.json";
import { summarizeOsmerTemporalDay } from "./osmerTemporalSummary";

function projectedArea(projectedCondition) {
  return {
    source_kind: "official_projected",
    projected_condition: projectedCondition,
  };
}

describe("OSMER temporal day summary", () => {
  it("summarizes the real 07/06 A1-A9 fixture as a regional partly day, not rain", () => {
    const summary = summarizeOsmerTemporalDay(normalizedFixture.days[0]);

    expect(summary).toMatchObject({
      validDate: "2026-06-07",
      tabCondition: "partly",
      dominantDaytimeCondition: "partly",
      severeDaytimeCondition: null,
      confidence: "high",
      source: "areas9",
      reason: "plain_coast_majority",
    });
  });

  it("keeps the following A1-A9 fixture day partly when mountain rain is localized", () => {
    const summary = summarizeOsmerTemporalDay(normalizedFixture.days[1]);

    expect(summary).toMatchObject({
      validDate: "2026-06-08",
      tabCondition: "partly",
      source: "areas9",
      reason: "plain_coast_majority",
    });
  });

  it("lets a severe storm win only when it reaches plain or coast and is geographically broad", () => {
    const summary = summarizeOsmerTemporalDay({
      valid_date: "2026-06-10",
      areas9: {
        A1: projectedArea("temporale variabile"),
        A2: projectedArea("pioggia intensa"),
        A3: projectedArea("pioggia intensa"),
        A4: projectedArea("pioggia intensa"),
        A5: projectedArea("temporale variabile"),
        A6: projectedArea("temporale variabile"),
        A7: projectedArea("temporale variabile"),
        A8: projectedArea("temporale variabile"),
        A9: projectedArea("temporale variabile"),
      },
    });

    expect(summary).toMatchObject({
      tabCondition: "storm",
      dominantDaytimeCondition: "storm",
      severeDaytimeCondition: "storm",
      confidence: "high",
      source: "areas9",
      reason: "severe_diffuse_storm",
    });
  });

  it("does not let an isolated mountain storm override fair plain and coast", () => {
    const summary = summarizeOsmerTemporalDay({
      valid_date: "2026-06-12",
      areas9: {
        A1: projectedArea("temporale variabile"),
        A2: projectedArea("poco nuvoloso"),
        A3: projectedArea("poco nuvoloso"),
        A4: projectedArea("poco nuvoloso"),
        A5: projectedArea("sereno"),
        A6: projectedArea("sereno"),
        A7: projectedArea("sereno"),
        A8: projectedArea("sereno"),
        A9: projectedArea("sereno"),
      },
    });

    expect(summary).toMatchObject({
      tabCondition: "partly",
      dominantDaytimeCondition: "sun",
      severeDaytimeCondition: null,
      source: "areas9",
      reason: "plain_coast_majority",
    });
  });

  it("keeps a stable regional tab when wind is focused on eastern plain and coast", () => {
    const summary = summarizeOsmerTemporalDay({
      valid_date: "2026-06-11",
      areas9: {
        A1: projectedArea("poco nuvoloso"),
        A2: projectedArea("poco nuvoloso"),
        A3: projectedArea("poco nuvoloso"),
        A4: projectedArea("poco nuvoloso"),
        A5: projectedArea("sereno"),
        A6: projectedArea("sereno"),
        A7: projectedArea("sereno"),
        A8: {
          ...projectedArea("sereno"),
          wind_alert: true,
        },
        A9: {
          ...projectedArea("vento con cielo sereno"),
          wind_alert: true,
          symbols: {
            vento: { id: "wind", code: 15 },
          },
        },
      },
    });

    expect(summary).toMatchObject({
      tabCondition: "partly",
      dominantDaytimeCondition: "sun",
      severeDaytimeCondition: null,
      source: "areas9",
      reason: "plain_coast_majority",
    });
  });

  it("keeps night residual rain out of the main tab when the day improves from morning", () => {
    const summary = summarizeOsmerTemporalDay({
      valid_date: "2026-06-11",
      text: "Nella notte residui rovesci con venti sostenuti. Dal mattino cielo in genere poco nuvoloso o sereno.",
    });

    expect(summary).toMatchObject({
      tabCondition: "sun",
      dominantDaytimeCondition: "sun",
      nightResidualCondition: "rain",
      confidence: "medium",
      source: "text",
      reason: "night_residual_daytime_improves",
    });
  });

  it("uses text fallback for mountain-localized rain when A1-A9 are unavailable", () => {
    const summary = summarizeOsmerTemporalDay({
      text: "Al mattino cielo in prevalenza sereno o poco nuvoloso. Nel pomeriggio poco nuvoloso su pianura e costa, variabile sulla zona montana dove saranno possibili locali piogge o rovesci.",
    });

    expect(summary).toMatchObject({
      tabCondition: "partly",
      source: "text",
      reason: "localized_mountain_rain_plain_coast_fair",
    });
  });
});
