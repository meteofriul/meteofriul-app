import { expect, it, vi } from "vitest";

vi.mock("react", async (importOriginal) => ({
  ...await importOriginal(),
  useRef: () => ({ current: null }),
}));

import { WeatherSwipeShell } from "./WeatherSwipeShell";
import { weatherSwipeTarget } from "./weatherSwipeTarget";
import { WEATHER_SECTION_IDS } from "./weatherSectionNavCopy";

it("moves between adjacent sections without wrapping", () => {
  const [first, middle, last] = WEATHER_SECTION_IDS;
  expect(weatherSwipeTarget(first, -100, 5, 200)).toBe(middle);
  expect(weatherSwipeTarget(middle, -100, 5, 200)).toBe(last);
  expect(weatherSwipeTarget(last, 100, 5, 200)).toBe(middle);
  expect(weatherSwipeTarget(first, 100, 5, 200)).toBeNull();
  expect(weatherSwipeTarget(last, -100, 5, 200)).toBeNull();
});
it("ignores vertical, short, diagonal and slow gestures", () => {
  for (const [dx, dy, ms] of [[20, 0, 100], [100, 150, 200], [100, 80, 200], [100, 0, 900]]) {
    expect(weatherSwipeTarget(WEATHER_SECTION_IDS[0], dx, dy, ms)).toBeNull();
  }
});

it("disabled mode preserves layout and children without installing any touch handlers", () => {
  const children = "Weather section contents";
  const shell = WeatherSwipeShell({ activeId: "weather", disabled: true, onNavigate: vi.fn(), children });
  expect(shell.type).toBe("div");
  expect(shell.props.className).toBe("mf-weather-route-shell");
  expect(shell.props.children).toBe(children);
  for (const event of ["onTouchStart", "onTouchMove", "onTouchCancel", "onTouchEnd"]) {
    expect(shell.props[event]).toBeUndefined();
  }
});

it("enabled legacy mode retains its touch handlers", () => {
  const shell = WeatherSwipeShell({ activeId: "weather", disabled: false, onNavigate: vi.fn() });
  for (const event of ["onTouchStart", "onTouchMove", "onTouchCancel", "onTouchEnd"]) {
    expect(shell.props[event]).toEqual(expect.any(Function));
  }
});
