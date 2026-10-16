import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { HomeOfficialAlertCard } from "./HomeOfficialAlertCard";

const ALERT = {
  action: { anchor: "official-alerts", tab: "bulletin", type: "tab-anchor" },
  label: "Allerta arancione",
  meta: "Protezione Civile FVG",
  text: "Temporali forti sulla regione.",
  tone: "orange",
  validityLabel: "Valida fino alle 18:00 del 6 settembre",
};

describe("HomeOfficialAlertCard", () => {
  it("shows the official source, level, phenomenon and validity as visible content", () => {
    const markup = renderToStaticMarkup(
      <HomeOfficialAlertCard alert={ALERT} language="it" onOpen={() => {}} />,
    );

    expect(markup).toContain('data-alert-tone="orange"');
    expect(markup).toContain(">Allerta ufficiale<");
    expect(markup).toContain("Protezione Civile FVG");
    expect(markup).toContain(">Allerta arancione</strong>");
    expect(markup).toContain("Temporali forti sulla regione.");
    expect(markup).toContain("Valida fino alle 18:00 del 6 settembre");
    expect(markup).toContain("lucide-triangle-alert");
    expect(markup).toContain('aria-label="Apri nel bollettino: Allerta arancione"');
  });

  it("uses a native button only when the card has a working action", () => {
    const onOpen = vi.fn();
    const card = HomeOfficialAlertCard({ alert: ALERT, language: "it", onOpen });
    const teaserElement = card.props.children;
    const teaser = teaserElement.type(teaserElement.props);
    const action = teaser.props.children[0];

    expect(action.type).toBe("button");
    expect(action.props.type).toBe("button");
    action.props.onClick();
    expect(onOpen).toHaveBeenCalledOnce();

    const inertMarkup = renderToStaticMarkup(
      <HomeOfficialAlertCard alert={ALERT} language="it" />,
    );
    expect(inertMarkup).not.toContain("<button");
  });

  it("localizes the fixed card chrome in Friulian", () => {
    const markup = renderToStaticMarkup(
      <HomeOfficialAlertCard
        alert={{
          ...ALERT,
          label: "Alerte narant",
          languageNotice: "Test uficiâl in talian - FUR in revision",
        }}
        language="fur"
        onOpen={() => {}}
      />,
    );

    expect(markup).toContain(">Alerte uficiâl<");
    expect(markup).toContain(">ALERTE<");
    expect(markup).toContain("Test uficiâl in talian - FUR in revision");
    expect(markup).toContain('aria-label="Vierç tal boletin: Alerte narant"');
  });
});
