import { afterEach, describe, expect, it, vi } from "vitest";
import * as sunCycle from "../../domain/almanac/sunCycle";
import { selectUvCurveSamples } from "./uvCurveWindow";

afterEach(() => vi.restoreAllMocks());

const HOUR = 3600000;
const point = { latitude: 45.9564, longitude: 12.6615 };
const clock = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Rome", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const calendar = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Rome", year: "numeric", month: "2-digit", day: "2-digit" });
function modelFor(date, valueAt = () => 0, now) {
  const reference = Date.parse(`${date}T12:00:00Z`);
  const today = Array.from({ length: 50 }, (_, index) => {
    const time = reference + (index - 25) * HOUR;
    return { time, value: valueAt(Number(clock.format(time).slice(0, 2)), time) };
  }).filter(sample => calendar.format(sample.time) === date);
  const currentTime = now ? Date.parse(now) : reference;
  return { today, now: currentTime, current: today.find(sample => sample.time <= currentTime && currentTime < sample.time + HOUR) };
}
const endpoints = samples => [clock.format(samples[0].time), clock.format(samples.at(-1).time)];
const daytimeValues = hour => hour >= 9 && hour <= 16 ? 1.4 : 0;

describe("selectUvCurveSamples", () => {
  it("uses real bracketing sunrise and sunset hours in September at Pordenone", () => {
    const model = modelFor("2026-09-10", daytimeValues);
    const result = selectUvCurveSamples(model, point);
    expect(endpoints(result)).toEqual(["06:00", "20:00"]);
    expect(result).toHaveLength(15);
    expect(result.every(sample => model.today.includes(sample))).toBe(true);
    expect(result.map(sample => sample.time)).toEqual(model.today.slice(6, 21).map(sample => sample.time));
  });

  it.each([
    ["winter", "2026-12-21", ["07:00", "17:00"]],
    ["summer", "2026-06-21", ["05:00", "22:00"]],
  ])("uses the %s solar window instead of a fixed 06–20 range", (_season, date, expected) => {
    expect(endpoints(selectUvCurveSamples(modelFor(date), point))).toEqual(expected);
  });

  it("keeps positive real nighttime samples and their neighboring zero samples", () => {
    const model = modelFor("2026-09-10", hour => [3, 12, 22].includes(hour) ? 0.2 : 0);
    const result = selectUvCurveSamples(model, point);
    expect(endpoints(result)).toEqual(["02:00", "23:00"]);
    expect(result.filter(sample => sample.value > 0)).toEqual(model.today.filter(sample => sample.value > 0));
  });

  it("does not widen the solar axis for a zero current nighttime value", () => {
    const model = modelFor("2026-09-10", daytimeValues, "2026-09-10T21:30:00Z");
    const result = selectUvCurveSamples(model, point);
    expect(model.current.value).toBe(0);
    expect(result).not.toContain(model.current);
    expect(endpoints(result)).toEqual(["06:00", "20:00"]);
    expect(model.today).toHaveLength(24);
  });

  it("uses today's Rome date just after local midnight, while UTC is still yesterday", () => {
    const solar = vi.spyOn(sunCycle, "getSunCycle");
    const model = modelFor("2026-09-10", daytimeValues, "2026-09-09T22:05:00Z");
    expect(endpoints(selectUvCurveSamples(model, point))).toEqual(["06:00", "20:00"]);
    expect(solar).toHaveBeenLastCalledWith(expect.objectContaining({
      date: new Date("2026-09-10T10:00:00Z"), now: new Date("2026-09-10T10:00:00Z"), timeZone: "Europe/Rome",
    }));
    expect(selectUvCurveSamples(model, point)).toEqual(selectUvCurveSamples({ ...model, now: Date.parse("2026-09-10T12:00:00Z") }, point));
  });

  it.each([
    ["spring", "2026-03-29", "2026-03-28T23:05:00Z", 23, "10:00"],
    ["autumn", "2026-10-25", "2026-10-24T22:05:00Z", 25, "11:00"],
  ])("keeps real ordered samples across the %s DST transition", (_season, date, now, count, utcNoon) => {
    const solar = vi.spyOn(sunCycle, "getSunCycle");
    const model = modelFor(date, daytimeValues, now);
    const result = selectUvCurveSamples(model, point);
    expect(solar).toHaveBeenLastCalledWith(expect.objectContaining({ date: new Date(`${date}T${utcNoon}:00Z`) }));
    expect(model.today).toHaveLength(count);
    expect(result).toEqual(selectUvCurveSamples({ ...model, now: Date.parse(`${date}T12:00:00Z`) }, point));
    expect(result.every(sample => model.today.includes(sample))).toBe(true);
    expect(result.every((sample, index) => index === 0 || sample.time - result[index - 1].time === HOUR)).toBe(true);
    expect(result[0].time).toBeGreaterThan(model.today[0].time);
    expect(result.at(-1).time).toBeLessThan(model.today.at(-1).time);
  });

  it.each([undefined, null, {}, { latitude: NaN, longitude: 12 }, { latitude: 46, longitude: 181 }])("falls back to positives and one real zero on each side for missing or invalid point %j", invalidPoint => {
    const model = modelFor("2026-09-10", daytimeValues);
    const result = selectUvCurveSamples(model, invalidPoint);
    expect(endpoints(result)).toEqual(["08:00", "17:00"]);
    expect(result).toEqual(model.today.slice(8, 18));
  });

  it("preserves the whole zero series when neither usable coordinates nor positives exist", () => {
    const model = modelFor("2026-09-10");
    expect(selectUvCurveSamples(model)).toBe(model.today);
  });

  it("uses solar hours even when all real values are zero", () => {
    const result = selectUvCurveSamples(modelFor("2026-09-10"), point);
    expect(endpoints(result)).toEqual(["06:00", "20:00"]);
    expect(result.every(sample => sample.value === 0)).toBe(true);
  });

  it.each(["2026-06-21", "2026-12-21"])("falls back when the sun cycle is polar on %s", date => {
    const model = modelFor(date, daytimeValues);
    expect(selectUvCurveSamples(model, { latitude: 89, longitude: 12 })).toEqual(selectUvCurveSamples(model));
  });

  it("never fabricates missing hours for a partial day", () => {
    const complete = modelFor("2026-09-10", daytimeValues);
    const model = { ...complete, today: complete.today.slice(10, 16) };
    expect(selectUvCurveSamples(model, point)).toEqual(model.today);
    expect(selectUvCurveSamples(model, point).every(sample => model.today.includes(sample))).toBe(true);
  });

  it.each([[0, 4], [21, 24]])("retains at least two available real samples when a partial zero series is outside daylight (%s–%s)", (start, end) => {
    const model = modelFor("2026-09-10");
    model.today = model.today.slice(start, end);
    const result = selectUvCurveSamples(model, point);
    expect(result).toHaveLength(2);
    expect(result.every(sample => model.today.includes(sample))).toBe(true);
  });

  it("preserves a one-sample or empty source rather than inventing a second point", () => {
    const single = modelFor("2026-09-10").today.slice(0, 1);
    expect(selectUvCurveSamples({ today: single }, point)).toBe(single);
    expect(selectUvCurveSamples({ today: [] }, point)).toEqual([]);
    expect(selectUvCurveSamples(null, point)).toEqual([]);
  });
});
