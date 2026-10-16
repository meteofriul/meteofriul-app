import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

function readAndroidSource(relativePath) {
  return readFileSync(new URL(
    `../../android/app/src/main/java/com/meteofriul/app/location/${relativePath}`,
    import.meta.url,
  ), "utf8");
}

const locationWorker = readAndroidSource("MeteoBackgroundLocationWorker.java");
const weatherScheduler = readAndroidSource("MeteoBackgroundWeatherScheduler.java");

describe("native canonical weather prefetch contract", () => {
  it("parses a backend-approved data point and never forwards the raw GPS Location", () => {
    expect(locationWorker).toContain('payload.optJSONObject("data_point")');
    expect(locationWorker).toContain('"resolved".equals(status)');
    expect(locationWorker).toContain('"external_place".equals(status)');
    expect(locationWorker).toContain('"nominatim_place".equals(source)');
    expect(locationWorker).toContain("response.hasCanonicalWeatherPoint()");
    expect(locationWorker).toContain("response.canonicalLatitude");
    expect(locationWorker).toContain("response.canonicalLongitude");
    expect(locationWorker).not.toMatch(
      /MeteoBackgroundWeatherScheduler\.enqueue\([\s\S]{0,180}\blocation\s*,/,
    );
  });

  it("makes the scheduler accept coordinates rather than an Android Location object", () => {
    expect(weatherScheduler).not.toContain("android.location.Location");
    expect(weatherScheduler).toMatch(
      /public static void enqueue\([\s\S]*double latitude,[\s\S]*double longitude/,
    );
    expect(weatherScheduler).toContain(".putDouble(INPUT_LAT, latitude)");
    expect(weatherScheduler).toContain(".putDouble(INPUT_LON, longitude)");
  });
});
