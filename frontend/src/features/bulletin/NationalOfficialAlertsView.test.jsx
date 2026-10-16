import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { NationalOfficialAlertsView } from "./NationalOfficialAlertsView";

const copy = { placeholders: { bulletinTitle: "Bollettino" } };
const payload = {
  active: true,
  complete: true,
  conservative_multi_zone_display: true,
  highest_level: "yellow",
  municipality: { name: "Urbino" },
  records: [
    { forecast_day: "2026-09-26", level: "green", risk: "hydraulic", zone_id: "DPC:Marc-1", zone_name: "Marche 1" },
    { forecast_day: "2026-09-26", level: "yellow", risk: "thunderstorm", zone_id: "DPC:Marc-2", zone_name: "Marche 2" },
    { forecast_day: "2026-09-27", level: "green", risk: "hydraulic", zone_id: "DPC:Marc-1", zone_name: "Marche 1" },
  ],
};

describe("NationalOfficialAlertsView", () => {
  it("explains conservative multi-zone display and links the official source", () => {
    const html = renderToStaticMarkup(
      <NationalOfficialAlertsView copy={copy} language="it" state={{ data: payload }} />,
    );

    expect(html).toContain("Urbino");
    expect(html).toContain("Marche 1 · Marche 2");
    expect(html).toContain("livello più cautelativo");
    expect(html).toContain("Temporali");
    expect(html).toContain("mappe.protezionecivile.gov.it");
  });

  it("has Friulian interface copy without translating official zone names", () => {
    const html = renderToStaticMarkup(
      <NationalOfficialAlertsView copy={copy} language="fur" state={{ data: payload }} />,
    );

    expect(html).toContain("Alertis e criticitâts");
    expect(html).toContain("Marche 1 · Marche 2");
  });

  it("distinguishes a legacy place without ISTAT from an unavailable source", () => {
    const html = renderToStaticMarkup(
      <NationalOfficialAlertsView
        copy={copy}
        state={{ error: "Codice ISTAT del Comune mancante", status: "error" }}
      />,
    );
    expect(html).toContain("Comune per le allerte non verificato");
    expect(html).toContain("Scegli di nuovo il Comune");
    expect(html).not.toContain("Allerte temporaneamente non disponibili");
  });
});
