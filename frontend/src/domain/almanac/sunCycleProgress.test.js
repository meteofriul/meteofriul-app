import { expect, it } from "vitest";
import { getSunCycle } from "./sunCycle";

function at(value) { const now = new Date(value); return getSunCycle({ date: now, now }).cycle; }
it("advances through daylight", () => {
  const morning = at("2026-09-06T07:00:00Z");
  const afternoon = at("2026-09-06T14:00:00Z");
  expect(morning.isDay).toBe(true);
  expect(afternoon.progress).toBeGreaterThan(morning.progress);
});
it("advances through midnight toward the next sunrise", () => {
  const evening = at("2026-09-06T20:00:00Z");
  const night = at("2026-09-07T02:00:00Z");
  expect(evening.isDay).toBe(false);
  expect(night.isDay).toBe(false);
  expect(night.start).toBe(evening.start);
  expect(night.end).toBe(evening.end);
  expect(night.progress).toBeGreaterThan(evening.progress);
});
it.each(["2026-03-29T01:30:00Z", "2026-10-25T01:30:00Z"])("keeps night progress bounded across clock changes: %s", value => {
  const cycle = at(value);
  expect(cycle.isDay).toBe(false);
  expect(cycle.progress).toBeGreaterThanOrEqual(0);
  expect(cycle.progress).toBeLessThanOrEqual(100);
});
