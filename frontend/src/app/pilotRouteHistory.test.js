import { describe, expect, it } from "vitest";
import { createPilotRouteHistory } from "./pilotRouteHistory";

describe("pilot route history", () => {
  it("returns from Settings to its actual origin, then through previous pages", () => {
    const history = createPilotRouteHistory();
    history.visit("weather");
    history.visit("bulletin");
    history.visit("settings");
    expect(history.back()).toBe("bulletin");
    expect(history.back()).toBe("weather");
    expect(history.back()).toBe("home");
    expect(history.back()).toBe("home");
  });
  it("does not create duplicate entries on repeated navigation", () => {
    const history = createPilotRouteHistory("events");
    history.visit("settings");
    history.visit("settings");
    expect(history.back()).toBe("events");
    expect(history.back()).toBe("home");
  });
  it("resets the trail when Home is explicitly selected", () => {
    const history = createPilotRouteHistory("weather");
    history.visit("events");
    history.visit("home");
    history.visit("discover");
    expect(history.back()).toBe("home");
  });
  it("normalizes invalid routes and preserves a Home root in a long session", () => {
    const history = createPilotRouteHistory("invalid");
    expect(history.back()).toBe("home");
    for (let i = 0; i < 80; i += 1) history.visit(i % 2 ? "events" : "weather");
    for (let i = 0; i < 31; i += 1) history.back();
    expect(history.back()).toBe("home");
    expect(history.visit("invalid")).toBe("home");
  });
});
