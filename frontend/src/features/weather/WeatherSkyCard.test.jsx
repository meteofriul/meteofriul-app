import { it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { WeatherSkyCard } from "./WeatherSkyCard";

it("shows astronomy permanently without disclosure controls", () => {
  const html = renderToStaticMarkup(<WeatherSkyCard location={{ city: "Pordenone", lat: 45.9567, lon: 12.6605 }} now={new Date("2026-09-07T12:00:00Z")} />);
  expect(html).toContain("Sole e Luna");
  expect(html).toContain("Pordenone");
  expect(html).not.toContain("Durata della notte");
  expect(html).toContain("Culmine Sole");
  expect(html).toContain("Luna illuminata");
  expect(html).not.toContain("<details");
  expect(html).not.toContain("<summary");
  expect(html).not.toContain("<button");
});
