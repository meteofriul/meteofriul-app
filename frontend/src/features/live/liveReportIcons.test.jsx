// @vitest-environment jsdom

import { renderToStaticMarkup } from "react-dom/server";
import {
  CircleCheck,
  CloudFog,
  CloudHail,
  CloudLightning,
  CloudRain,
  Gem,
  Snowflake,
  Wind,
} from "lucide-react";
import { describe, expect, it } from "vitest";

import { getLiveViewCopy } from "../../copy/liveViewCopy";
import { CommunityReportForm } from "./LiveView";
import { LIVE_REPORT_ICONS, PILOT_LIVE_REPORT_ICONS } from "./liveReportIcons";

const expectedLegacyIcons = {
  fog: CloudFog,
  hail: CloudHail,
  ice: Snowflake,
  quiet: CircleCheck,
  rain: CloudRain,
  snow: Snowflake,
  storm: CloudLightning,
  wind: Wind,
};

const expectedPilotIcons = {
  ...expectedLegacyIcons,
  ice: Gem,
};

function renderReportForm({ pilotStyle = false } = {}) {
  const copy = getLiveViewCopy("it");
  const options = Object.keys(expectedLegacyIcons).map((id) => ({
    id,
    label: copy.reportTypes[id],
  }));
  const host = document.createElement("div");

  host.innerHTML = renderToStaticMarkup(
    <CommunityReportForm
      copy={copy}
      locations={[]}
      maxDistanceKm={5}
      onClose={() => {}}
      onLocate={() => Promise.resolve({ ok: false, reason: "unavailable" })}
      onSubmit={() => Promise.resolve({ ok: true })}
      options={options}
      pilotStyle={pilotStyle}
      previewOnly
    />,
  );

  return host;
}

describe("live report icon mapping", () => {
  it("keeps the complete legacy mapping unchanged", () => {
    expect(Object.keys(LIVE_REPORT_ICONS).sort())
      .toEqual(Object.keys(expectedLegacyIcons).sort());
    expect(LIVE_REPORT_ICONS).toEqual(expectedLegacyIcons);
    expect(Object.isFrozen(LIVE_REPORT_ICONS)).toBe(true);
    expect(LIVE_REPORT_ICONS.ice).toBe(Snowflake);
    expect(LIVE_REPORT_ICONS.ice).toBe(LIVE_REPORT_ICONS.snow);
  });

  it("provides a complete pilot mapping with a dedicated ice glyph", () => {
    expect(Object.keys(PILOT_LIVE_REPORT_ICONS).sort())
      .toEqual(Object.keys(expectedPilotIcons).sort());
    expect(PILOT_LIVE_REPORT_ICONS).toEqual(expectedPilotIcons);
    expect(Object.isFrozen(PILOT_LIVE_REPORT_ICONS)).toBe(true);
    expect(PILOT_LIVE_REPORT_ICONS.ice).toBe(Gem);
    expect(PILOT_LIVE_REPORT_ICONS.ice).not.toBe(PILOT_LIVE_REPORT_ICONS.snow);
  });

  it("renders every form glyph with the requested heavy rounded white-badge stroke", () => {
    const host = renderReportForm({ pilotStyle: true });

    Object.keys(expectedPilotIcons).forEach((id) => {
      const option = host.querySelector(`.mf-live-report-option--${id}`);
      const glyph = option?.querySelector("svg");

      expect(option).not.toBeNull();
      expect(glyph).not.toBeNull();
      expect(glyph.getAttribute("stroke")).toBe("currentColor");
      expect(Number(glyph.getAttribute("stroke-width"))).toBeGreaterThanOrEqual(2);
      expect(Number(glyph.getAttribute("stroke-width"))).toBeLessThanOrEqual(2.5);
      expect(glyph.getAttribute("stroke-linecap")).toBe("round");
      expect(glyph.getAttribute("stroke-linejoin")).toBe("round");
    });
  });

  it("renders Gem only in the pilot ice option and preserves Snowflake in legacy", () => {
    const legacyForm = renderReportForm();
    const pilotForm = renderReportForm({ pilotStyle: true });
    const legacyIceGlyph = legacyForm.querySelector(".mf-live-report-option--ice svg");
    const pilotIceGlyph = pilotForm.querySelector(".mf-live-report-option--ice svg");

    expect(legacyIceGlyph?.classList.contains("lucide-snowflake")).toBe(true);
    expect(legacyIceGlyph?.classList.contains("lucide-gem")).toBe(false);
    expect(pilotIceGlyph?.classList.contains("lucide-gem")).toBe(true);
    expect(pilotIceGlyph?.classList.contains("lucide-snowflake")).toBe(false);
  });
});
