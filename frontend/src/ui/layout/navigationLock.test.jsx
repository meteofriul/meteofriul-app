import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { Home, MapPin } from "lucide-react";

import { BottomNavigation } from "./BottomNavigation";
import { isPullRefreshDisabled } from "./navigationLockPolicy";

describe("report submission navigation lock", () => {
  it("disables navigation away from the active tab during submission", () => {
    const markup = renderToStaticMarkup(
      <BottomNavigation
        activeTab="live"
        copy={{ tabs: { home: "Home", live: "Territorio" } }}
        navigationLocked
        onTabChange={() => {}}
        tabs={[
          { Icon: Home, id: "home" },
          { Icon: MapPin, id: "live" },
        ]}
      />,
    );

    expect(markup).toMatch(/<button[^>]*disabled=""[^>]*>.*Home/s);
    expect(markup).toMatch(/<button[^>]*aria-current="page"[^>]*>.*Territorio/s);
  });

  it("disables pull-to-refresh for the complete report submission lock", () => {
    const onRuntimeRefresh = vi.fn();

    expect(isPullRefreshDisabled({ navigationLocked: true, onRuntimeRefresh })).toBe(true);
    expect(isPullRefreshDisabled({ navigationLocked: false, onRuntimeRefresh })).toBe(false);
    expect(isPullRefreshDisabled({ navigationLocked: false, onRuntimeRefresh: null })).toBe(true);
  });
});
