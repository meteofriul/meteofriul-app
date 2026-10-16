import { describe, expect, it } from "vitest";

import { getPushNavigationTarget } from "./pushDeepLink";

describe("pushDeepLink", () => {
  it("opens only allow-listed app tabs", () => {
    expect(getPushNavigationTarget({
      notification: { data: { tab: "bulletin" } },
    })).toEqual({ tab: "bulletin" });
    expect(getPushNavigationTarget({
      notification: { data: { deep_link: "meteo-friul://open?tab=live" } },
    })).toEqual({ tab: "live" });
    expect(getPushNavigationTarget({
      notification: { data: { deep_link: "https://malicious.example/delete" } },
    })).toBeNull();
  });

  it("routes official and local weather notifications to Bollettino", () => {
    expect(getPushNavigationTarget({ data: { type: "official_alert" } }))
      .toEqual({ tab: "bulletin" });
    expect(getPushNavigationTarget({
      notification: { data: { type: "local_weather_notice" } },
    })).toEqual({ tab: "bulletin" });
    expect(getPushNavigationTarget({ data: { category: "weather_notices" } }))
      .toEqual({ tab: "bulletin" });
  });

  it("opens a national alert only for the same current Comune", () => {
    const notification = {
      data: { type: "national_official_alert", tab: "bulletin", municipality_istat: "058091" },
    };
    expect(getPushNavigationTarget(notification, { currentMunicipalityIstat: "058091" }))
      .toEqual({ tab: "bulletin" });
    expect(getPushNavigationTarget(notification, { currentMunicipalityIstat: "041067" }))
      .toBeNull();
    expect(getPushNavigationTarget(notification)).toBeNull();
    expect(getPushNavigationTarget({ data: { type: "national_official_alert", tab: "bulletin" } }, {
      currentMunicipalityIstat: "058091",
    })).toBeNull();
  });
});
