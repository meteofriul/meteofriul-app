import { describe, expect, it } from "vitest";

import { getPilotWhyContentForDate } from "./pilotWhyContent";
import { createPilotWhyVisit, getPilotWhyContentForVisit } from "./pilotWhyVisit";

describe("pilot Why route visit", () => {
  it("keeps the selected question for the whole Discover visit", () => {
    const selected = getPilotWhyContentForDate("it", "2026-09-08");
    const visit = createPilotWhyVisit(selected.id);

    expect(getPilotWhyContentForVisit({ date: "2026-09-09", language: "it", visit }).id)
      .toBe(selected.id);
    expect(getPilotWhyContentForVisit({ date: "2026-09-10", language: "it", visit }).id)
      .toBe(selected.id);
  });

  it("uses the daily question for a new Discover visit after leaving", () => {
    const reenteredVisit = createPilotWhyVisit();
    const daily = getPilotWhyContentForDate("it", "2026-09-09");

    expect(getPilotWhyContentForVisit({
      date: "2026-09-09",
      language: "it",
      visit: reenteredVisit,
    }).id).toBe(daily.id);
  });
});
