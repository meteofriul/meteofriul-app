import { describe, expect, it } from "vitest";
import { buildThreeHourForecast } from "./threeHourForecast";

function slots() {
  return Array.from({ length: 7 }, (_, index) => ({
    timestamp: new Date(Date.UTC(2026, 8, 6, 10 + index)).toISOString(),
    intervalStart: new Date(Date.UTC(2026, 8, 6, 9 + index)).toISOString(),
    intervalEnd: new Date(Date.UTC(2026, 8, 6, 10 + index)).toISOString(),
    values: { precipitation: index === 0 ? 99 : index / 10, windGusts: index + 10 },
  }));
}

describe("three-hour forecast", () => {
  it("sums forward intervals, excluding the preceding hour, and takes the maximum gust", () => {
    const result = buildThreeHourForecast(slots());
    expect(result).toHaveLength(3);
    expect(result[0]).toMatchObject({ rainTotal: "0,6 mm", rainCalculation: "0,1 + 0,2 + 0,3 = 0,6 mm", periodGust: "13 km/h", rainWindow: "12:00–15:00" });
    expect(result[2].rainTotal).toBeNull();
  });
  it("does not claim a complete total when an hour is missing", () => {
    const items = slots();
    items[2].values.precipitation = null;
    expect(buildThreeHourForecast(items)[0].rainTotal).toBeNull();
    expect(buildThreeHourForecast(slots().filter((_, index) => index !== 2))[0].rainTotal).toBeNull();
  });
});
