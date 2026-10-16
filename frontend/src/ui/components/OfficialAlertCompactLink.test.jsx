import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { OfficialAlertCompactLink } from "./OfficialAlertCompactLink";

const ALERT = {
  label: "Allerta arancione",
  meta: "Protezione Civile FVG",
  tone: "orange",
  validityLabel: "Valida fino alle 18:00 del 6 settembre",
};

describe("OfficialAlertCompactLink", () => {
  it.each(["yellow", "orange", "red"])(
    "uses icon, text and the %s tone without changing structure",
    (tone) => {
      const markup = renderToStaticMarkup(
        <OfficialAlertCompactLink
          alert={{ ...ALERT, tone }}
          language="it"
          onOpen={() => {}}
        />,
      );

      expect(markup).toContain(`data-alert-tone="${tone}"`);
      expect(markup).toContain("lucide-triangle-alert");
      expect(markup).toContain("Protezione Civile FVG");
      expect(markup).toContain("Allerta arancione");
      expect(markup).toContain("Valida fino alle 18:00 del 6 settembre");
      expect(markup).toContain("lucide-chevron-right");
      expect(markup).toContain('type="button"');
    },
  );

  it("uses a localized, complete accessible name and source fallback", () => {
    const markup = renderToStaticMarkup(
      <OfficialAlertCompactLink
        alert={{ label: "Alerte zale", tone: "yellow" }}
        language="fur"
        onOpen={() => {}}
      />,
    );

    expect(markup).toContain("Protezion Civîl FVG");
    expect(markup).toContain(
      'aria-label="Vierç tal boletin: Alerte zale. Font: Protezion Civîl FVG"',
    );
  });

  it("invokes the native button action and remains readable without an action", () => {
    const onOpen = vi.fn();
    const interactive = OfficialAlertCompactLink({ alert: ALERT, onOpen });

    expect(interactive.type).toBe("button");
    interactive.props.onClick();
    expect(onOpen).toHaveBeenCalledOnce();

    const inertMarkup = renderToStaticMarkup(
      <OfficialAlertCompactLink alert={ALERT} />,
    );
    expect(inertMarkup).toContain('class="mf-official-alert-compact"');
    expect(inertMarkup).not.toContain("<button");
  });

  it("renders nothing without a displayable alert", () => {
    expect(OfficialAlertCompactLink({ alert: null })).toBeNull();
    expect(OfficialAlertCompactLink({ alert: {} })).toBeNull();
  });

  it("keeps one minimum geometry while severity selectors only change color tokens", () => {
    const css = readFileSync(new URL("./officialAlertCompactLink.css", import.meta.url), "utf8");

    expect(css).toMatch(/\.mf-official-alert-compact\s*\{[\s\S]*?min-height:\s*68px/);
    expect(css).toContain('html[data-theme="dark"] .mf-official-alert-compact[data-alert-tone="yellow"]');
    expect(css).toContain('html[data-theme="dark"] .mf-official-alert-compact[data-alert-tone="orange"]');
    expect(css).toContain('html[data-theme="dark"] .mf-official-alert-compact[data-alert-tone="red"]');
    for (const tone of ["yellow", "orange", "red"]) {
      const rule = css.match(
        new RegExp(`\\.mf-official-alert-compact\\[data-alert-tone="${tone}"\\] \\{([^}]+)\\}`),
      )?.[1] || "";
      expect(rule).toContain("--mf-official-alert-");
      expect(rule).not.toMatch(/(?:height|padding|grid-template|margin)\s*:/);
    }
  });
});
