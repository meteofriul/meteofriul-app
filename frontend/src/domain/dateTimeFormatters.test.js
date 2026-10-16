import { describe, expect, it } from "vitest";
import { getDateTimeFormatter } from "./dateTimeFormatters";

describe("reusable date formatters", () => {
  it("reuses an explicit-zone formatter without conflating locale or format options", () => {
    const options = { timeZone: "Europe/Rome", hour: "2-digit", minute: "2-digit", hourCycle: "h23" };
    const formatter = getDateTimeFormatter("it-IT", options);
    expect(getDateTimeFormatter("it-IT", { ...options })).toBe(formatter);
    expect(getDateTimeFormatter("en-US", options)).not.toBe(formatter);
    expect(getDateTimeFormatter("it-IT", { ...options, timeZone: "UTC" })).not.toBe(formatter);
    expect(getDateTimeFormatter("it-IT", { ...options, second: "2-digit" })).not.toBe(formatter);
  });

  it("preserves both Rome DST transitions and a different timezone", () => {
    const instants = ["2026-03-29T00:30:00Z", "2026-03-29T01:30:00Z", "2026-10-25T00:30:00Z", "2026-10-25T01:30:00Z"];
    for (const timeZone of ["Europe/Rome", "UTC", "Pacific/Honolulu"]) {
      const options = { timeZone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" };
      const native = new Intl.DateTimeFormat("en-GB", options);
      const cached = getDateTimeFormatter("en-GB", options);
      for (const instant of instants) {
        const date = new Date(instant);
        expect(cached.format(date)).toBe(native.format(date));
        expect(cached.formatToParts(date)).toEqual(native.formatToParts(date));
      }
    }
  });

  it("does not retain the implicit device timezone or suppress native errors", () => {
    const options = { month: "long" };
    expect(getDateTimeFormatter("it-IT", options)).not.toBe(getDateTimeFormatter("it-IT", options));
    expect(() => getDateTimeFormatter("it-IT", { timeZone: "invalid/timezone" })).toThrow(RangeError);
  });
});
