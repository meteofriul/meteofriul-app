import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createPilotWeatherPrefetchBridge,
  getPilotWeatherPrefetchReader,
  PILOT_WEATHER_PREFETCH_API_BASE as baseUrl,
} from "./pilotWeatherPrefetch";

const istatCode = "093033";
const request = {
  provider: "icon2i",
  path: `runs/20260908T000000Z/municipalities/${istatCode}.json`,
  sha256: "a".repeat(64),
};
const response = { baseUrl, ...request, body: '{"real":"bytes"}\n', etag: '"etag-1"' };
function setup(overrides = {}) {
  const plugin = {
    configure: vi.fn().mockResolvedValue({ available: true }),
    readObject: vi.fn().mockResolvedValue(response),
    clear: vi.fn().mockResolvedValue({ available: true }),
    ...overrides,
  };
  return { plugin, bridge: createPilotWeatherPrefetchBridge({ plugin, isEnabled: () => true }) };
}
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe("pilot-only native immutable prefetch bridge", () => {
  it("does nothing in the normal browser runtime", () => {
    expect(getPilotWeatherPrefetchReader({ baseUrl, istatCode })).toBeNull();
  });

  it("requires enabled native pilot, exact cloud origin and a municipality", async () => {
    const { plugin, bridge } = setup();
    for (const origin of ["http://127.0.0.1:8781", "/__local-weather-pilot", `${baseUrl}/`, `${baseUrl}.evil`]) {
      expect(bridge.readerFor({ baseUrl: origin, istatCode })).toBeNull();
    }
    expect(bridge.readerFor({ baseUrl, istatCode: "../093033" })).toBeNull();
    expect(createPilotWeatherPrefetchBridge({ plugin }).readerFor({ baseUrl, istatCode })).toBeNull();
    await Promise.resolve();
    expect(plugin.configure).not.toHaveBeenCalled();
  });

  it("configures once, coalesces reads, and returns only untrusted body/etag", async () => {
    const { plugin, bridge } = setup();
    const first = bridge.readerFor({ baseUrl, istatCode });
    const second = bridge.readerFor({ baseUrl, istatCode });
    expect(await Promise.all([first(request), second(request)])).toEqual([
      { body: response.body, etag: response.etag }, { body: response.body, etag: response.etag },
    ]);
    expect(plugin.configure).toHaveBeenCalledTimes(1);
    expect(plugin.configure).toHaveBeenCalledWith({ baseUrl, istatCode });
    expect(plugin.readObject).toHaveBeenCalledTimes(1);
    expect(plugin.readObject).toHaveBeenCalledWith({ baseUrl, istatCode, ...request });
  });

  it.each([
    { path: "latest.json" },
    { path: "../../secret" },
    { path: "runs/20260908T000000Z/municipalities/030129.json" },
    { provider: "legacy" },
    { sha256: "missing" },
  ])("refuses mutable or out-of-scope lookups %j", async (change) => {
    const { plugin, bridge } = setup();
    expect(await bridge.readerFor({ baseUrl, istatCode })({ ...request, ...change })).toBeNull();
    expect(plugin.readObject).not.toHaveBeenCalled();
  });

  it.each([
    { baseUrl: "https://wrong.example" }, { provider: "cams_europe" },
    { path: "latest.json" }, { sha256: "b".repeat(64) },
    { body: null }, { etag: null }, { available: false },
  ])("ignores mismatched native response %j", async (change) => {
    const { bridge } = setup({ readObject: vi.fn().mockResolvedValue({ ...response, ...change }) });
    expect(await bridge.readerFor({ baseUrl, istatCode })(request)).toBeNull();
  });

  it("allows the CAMS immutable family release but not its mutable pointer", async () => {
    const { plugin, bridge } = setup();
    const reader = bridge.readerFor({ baseUrl, istatCode });
    const family = { ...request, provider: "families/cams", path: "runs/20260908T000000Z/release.json" };
    plugin.readObject.mockResolvedValue({ ...response, ...family });
    expect(await reader(family)).toEqual({ body: response.body, etag: response.etag });
    expect(await reader({ ...family, path: "latest.json" })).toBeNull();
    expect(plugin.readObject).toHaveBeenCalledTimes(1);
  });

  it("does not use an object after location changes or after cancellation", async () => {
    let release;
    const { bridge, plugin } = setup({ readObject: vi.fn(() => new Promise(resolve => { release = resolve; })) });
    const reader = bridge.readerFor({ baseUrl, istatCode });
    const pending = reader(request);
    await vi.waitFor(() => expect(plugin.readObject).toHaveBeenCalledTimes(1));
    bridge.readerFor({ baseUrl, istatCode: "030129" });
    release(response);
    expect(await pending).toBeNull();
    expect(await reader(request)).toBeNull();
    const controller = new AbortController();
    controller.abort();
    const newReader = bridge.readerFor({ baseUrl, istatCode: "030129" });
    expect(await newReader({ ...request, signal: controller.signal })).toBeNull();
  });

  it("shares bounded waiting and never reads late after bridge timeout", async () => {
    vi.useFakeTimers();
    let configure;
    const { plugin, bridge } = setup({ configure: vi.fn(() => new Promise(resolve => { configure = resolve; })) });
    const pending = bridge.readerFor({ baseUrl, istatCode })(request);
    await vi.advanceTimersByTimeAsync(500);
    expect(await pending).toBeNull();
    configure({ available: true });
    await vi.advanceTimersByTimeAsync(0);
    expect(plugin.readObject).not.toHaveBeenCalled();
  });

  it("ignores plugin errors and retries configuration on a later request", async () => {
    const { bridge, plugin } = setup();
    plugin.configure.mockRejectedValueOnce(new Error("bridge unavailable"));
    expect(await bridge.readerFor({ baseUrl, istatCode })(request)).toBeNull();
    expect(await bridge.readerFor({ baseUrl, istatCode })(request)).toEqual({ body: response.body, etag: response.etag });
    expect(plugin.configure).toHaveBeenCalledTimes(2);
    plugin.readObject.mockRejectedValueOnce(new Error("disk unavailable"));
    expect(await bridge.readerFor({ baseUrl, istatCode })(request)).toBeNull();
  });

  it.each(["configure", "readObject"])("discards an in-flight %s if native support becomes unavailable", async (method) => {
    let enabled = true;
    let release;
    const { plugin } = setup({ [method]: vi.fn(() => new Promise(resolve => { release = resolve; })) });
    const bridge = createPilotWeatherPrefetchBridge({ plugin, isEnabled: () => enabled });
    const pending = bridge.readerFor({ baseUrl, istatCode })(request);
    await vi.waitFor(() => expect(plugin[method]).toHaveBeenCalledOnce());
    enabled = false;
    release(method === "configure" ? { available: true } : response);
    expect(await pending).toBeNull();
    if (method === "configure") expect(plugin.readObject).not.toHaveBeenCalled();
  });

  it("clears only native staging and rejects results already in flight", async () => {
    let release;
    const { bridge, plugin } = setup({ readObject: vi.fn(() => new Promise(resolve => { release = resolve; })) });
    const reader = bridge.readerFor({ baseUrl, istatCode });
    const pending = reader(request);
    await vi.waitFor(() => expect(plugin.readObject).toHaveBeenCalledTimes(1));
    expect(await bridge.clear()).toBe(true);
    release(response);
    expect(await pending).toBeNull();
    expect(await reader(request)).toBeNull();
    expect(plugin.clear).toHaveBeenCalledOnce();
    bridge.readerFor({ baseUrl, istatCode });
    await vi.waitFor(() => expect(plugin.configure).toHaveBeenCalledTimes(2));
  });
});
