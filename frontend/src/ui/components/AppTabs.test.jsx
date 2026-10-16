import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AppTabs } from "./AppTabs";
import { getNextAppTabIndex } from "./appTabsKeyboard";

describe("AppTabs", () => {
  it("renders a roving tab stop and explicit panel relationships", () => {
    const markup = renderToStaticMarkup(
      <AppTabs
        activeId="nearby"
        ariaLabel="Scegli una zona"
        items={[
          {
            ariaLabel: "Vicino, 5 webcam",
            controlsId: "webcam-panel",
            id: "nearby",
            label: "Vicino",
            meta: "(5)",
            tabId: "webcam-tab-nearby",
          },
          {
            ariaLabel: "Montagna, 6 webcam",
            controlsId: "webcam-panel",
            id: "mountain",
            label: "Montagna",
            meta: "(6)",
            tabId: "webcam-tab-mountain",
          },
        ]}
        onChange={() => {}}
      />,
    );

    expect(markup).toContain('aria-orientation="horizontal"');
    expect(markup).toContain('aria-label="Vicino, 5 webcam"');
    expect(markup).toContain('aria-controls="webcam-panel"');
    expect(markup).toContain('id="webcam-tab-nearby"');
    expect(markup).toContain('tabindex="0"');
    expect(markup).toContain('tabindex="-1"');
  });

  it("wraps arrows and supports Home and End", () => {
    expect(getNextAppTabIndex("ArrowLeft", 0, 4)).toBe(3);
    expect(getNextAppTabIndex("ArrowRight", 3, 4)).toBe(0);
    expect(getNextAppTabIndex("Home", 2, 4)).toBe(0);
    expect(getNextAppTabIndex("End", 1, 4)).toBe(3);
    expect(getNextAppTabIndex("Enter", 1, 4)).toBeNull();
  });
});
