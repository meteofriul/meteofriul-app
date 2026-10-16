import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { LocationContext } from "./LocationContext";

describe("LocationContext", () => {
  it("forwards the route lock to its change action", () => {
    const markup = renderToStaticMarkup(
      <LocationContext city="Pordenone" disabled onChange={() => {}} />,
    );

    expect(markup).toContain("Pordenone");
    expect(markup).toMatch(/<button[^>]*disabled=""[^>]*>/);
  });
});
