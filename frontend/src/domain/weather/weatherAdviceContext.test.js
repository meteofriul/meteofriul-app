import { describe, expect, it } from "vitest";

import { getWeatherGroup } from "./weatherAdviceContext";

describe("weatherAdviceContext", () => {
  it.each([
    ["Sun", "sun"],
    ["MostlyClearNight", "sun"],
    ["PartlyCloudyNight", "cloud"],
    ["OvercastNight", "cloud"],
    ["HeavyRain", "rain"],
    ["ExtremeRain", "rain"],
    ["Sleet", "rain"],
    ["StrongStorm", "storm"],
    ["StormHail", "storm"],
    ["Hail", "storm"],
    ["Mist", "fog"],
    ["Haze", "fog"],
    ["LowCloudFog", "fog"],
    ["Wind", "wind"],
  ])("maps %s to the expected advice weather group", (type, group) => {
    expect(getWeatherGroup(type)).toBe(group);
  });
});
