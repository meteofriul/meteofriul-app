import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { BulletinView } from "./BulletinView";
import { buildBulletinViewModel } from "./bulletinViewModel";

const copy = { placeholders: { bulletinTitle: "Bollettino" } };
const now = Date.parse("2026-08-30T09:25:00Z");

describe("Bulletin without duplicated local indicators", () => {
  it.each(["it", "fur"])("keeps forecast and days but no local or radar card in %s", (language) => {
    const model = buildBulletinViewModel({}, { language, now, allowFixtureFallback: true });
    const html = renderToStaticMarkup(
      <BulletinView
        copy={copy}
        language={language}
        localModel={{ title: "A Pordenone", metrics: [{ id: "humidity", label: "Umidità", value: "56%" }] }}
        model={model}
      />,
    );

    expect(html).toContain("mf-bulletin-map-card");
    expect(html).toContain('role="tablist"');
    expect(html).toContain("mf-bulletin-summary");
    expect(html).toContain("mf-bulletin-summary__link");
    expect(html).not.toContain("mf-bulletin-view--story");
    expect(html).not.toContain("mf-bulletin-source-footer");
    expect(html).not.toContain("mf-bulletin-radar-card");
    expect(html).not.toContain("mf-bulletin-local-card");
    expect(html).not.toContain("A Pordenone");
  });

  it.each(["it", "fur"])("composes the pilot bulletin as a map-led story with one discreet source footer in %s", (language) => {
    const model = buildBulletinViewModel({}, { language, now, allowFixtureFallback: true });
    const html = renderToStaticMarkup(
      <BulletinView copy={copy} language={language} model={model} storyLayout />,
    );
    const document = new JSDOM(html).window.document;
    const mapCard = document.querySelector(".mf-bulletin-map-card");
    const panel = mapCard?.querySelector('[role="tabpanel"]');
    const summary = panel?.querySelector(".mf-bulletin-summary");
    const sourceFooter = panel?.querySelector(".mf-bulletin-source-footer");
    const sourceLink = sourceFooter?.querySelector("a");
    const activeTab = mapCard?.querySelector('[role="tab"][aria-selected="true"]');

    expect(html).toContain("mf-bulletin-view--story");
    expect(summary).not.toBeNull();
    expect(sourceFooter).not.toBeNull();
    expect(document.querySelectorAll(".mf-bulletin-source-footer")).toHaveLength(1);
    expect(panel?.getAttribute("aria-labelledby")).toBe(activeTab?.id);
    expect(activeTab?.getAttribute("aria-controls")).toBe(panel?.id);
    expect(html).not.toContain("mf-bulletin-summary__link");
    expect(html).not.toContain("mf-bulletin-map-meta");
    expect(summary?.querySelector(".mf-bulletin-summary__reliability")?.textContent).toContain(model.days[0].reliability);
    expect(sourceFooter?.textContent).toContain(model.source.label);
    expect(sourceFooter?.textContent).toContain(model.source.updatedLabel);
    expect(sourceFooter?.textContent).toContain(model.source.linkLabel);
    expect(sourceLink?.getAttribute("href")).toBe(model.source.url);
    expect(sourceLink?.getAttribute("rel")).toBe("noreferrer");
    expect(sourceLink?.getAttribute("target")).toBe("_blank");
  });

  it("does not reserve an empty reliability row in the pilot story", () => {
    const model = buildBulletinViewModel({}, { language: "it", now, allowFixtureFallback: true });
    const modelWithoutReliability = {
      ...model,
      days: model.days.map((day, index) => index === 0 ? { ...day, reliability: "" } : day),
    };
    const html = renderToStaticMarkup(
      <BulletinView copy={copy} language="it" model={modelWithoutReliability} storyLayout />,
    );

    expect(html).not.toContain("mf-bulletin-summary__reliability");
    expect(html).not.toContain("mf-bulletin-map-meta");
  });

  it("preserves the official alert block and its anchor", () => {
    const model = {
      ...buildBulletinViewModel({}, { language: "it", now }),
      alert: {
        label: "Allerta arancione",
        languageNotice: "Test uficiâl in talian - FUR in revision",
        meta: "Protezione Civile FVG",
        paragraphs: ["Test di segnalazione ufficiale."],
        tone: "orange",
        validityLabel: "Fino alle 24:00",
      },
    };
    const html = renderToStaticMarkup(<BulletinView copy={copy} language="it" model={model} />);

    expect(html).toContain('id="official-alerts" tabindex="-1"');
    expect(html).toContain('data-alert-tone="orange"');
    expect(html).toContain("Test di segnalazione ufficiale.");
    expect(html).toContain("Test uficiâl in talian - FUR in revision");
    expect(html).toContain("Fino alle 24:00");
  });

  it("removes the unused local polling from Bulletin while retaining Home data and radar polling", () => {
    const source = readFileSync(new URL("../../app/AppRoutes.jsx", import.meta.url), "utf8");

    expect(source).not.toContain("loadBulletinLocalData");
    expect(source).not.toContain("setLocalDataState");
    expect(source).not.toContain("BULLETIN_LOCAL_AUTO_REFRESH_INTERVAL_MS");
    expect(source).toContain("buildBulletinLocalViewModel(homeData.weather");
    expect(source).toContain("subscribeToHomeSolarClock(setDeviceNow)");
    expect(source).toContain("BULLETIN_RADAR_AUTO_REFRESH_INTERVAL_MS");
    expect(source).toContain("storyLayout={isDefinitiveAppExperience()}");
  });
});
