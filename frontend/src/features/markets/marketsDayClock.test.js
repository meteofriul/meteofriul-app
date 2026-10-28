import { afterEach, describe, expect, it, vi } from "vitest";
import { subscribeToMarketsDayClock } from "./marketsDayClock";

afterEach(() => vi.useRealTimers());
describe("market calendar clock", () => {
  it.each(["2026-10-14T21:59:59Z", "2026-10-25T22:59:59Z"])("advances at Rome midnight from %s and disposes its timer", date => {
    vi.useFakeTimers(); vi.setSystemTime(new Date(date));
    const change = vi.fn();
    const stop = subscribeToMarketsDayClock(change);
    expect(change).toHaveBeenCalledOnce();
    vi.advanceTimersByTime(1000);
    expect(change).toHaveBeenCalledTimes(2);
    vi.advanceTimersByTime(60000);
    expect(change).toHaveBeenCalledTimes(2);
    stop();
    expect(vi.getTimerCount()).toBe(0);
  });
  it("refreshes after resuming a suspended page", () => {
    vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-15T10:00:00Z"));
    const documentRef = new EventTarget(), change = vi.fn();
    const stop = subscribeToMarketsDayClock(change, { documentRef });
    vi.setSystemTime(new Date("2026-10-17T10:00:00Z"));
    documentRef.dispatchEvent(new Event("visibilitychange"));
    expect(change).toHaveBeenCalledTimes(2);
    stop();
    vi.setSystemTime(new Date("2026-10-18T10:00:00Z"));
    documentRef.dispatchEvent(new Event("visibilitychange"));
    expect(change).toHaveBeenCalledTimes(2);
  });
});
