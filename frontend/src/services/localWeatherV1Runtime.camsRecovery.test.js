import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { harness, MINUTE, RUN_A, RUN_B, START } from "./camsRecoveryTestFixtures";
import { readLocalWeatherV1PersistedBundle } from "./localWeatherV1Runtime";

beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(START); });
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); });

describe("CAMS-only recovery after an accepted existing refresh opportunity", () => {
  it("does not turn unavailable into CAMS verification or renew the ICON verification on a CAMS-only failure", async () => {
    const h = harness();
    const initial = await h.fetch();
    expect(h.saved().camsVerifiedAt).toBeNull();
    vi.setSystemTime(START + MINUTE);
    const retry = await h.fetch({ retryUnavailableCams: true });
    expect(retry.current.source.cams.status).toBe("unavailable");
    expect(h.saved().camsVerifiedAt).toBeNull();
    expect(h.saved().verifiedAt).toBe(START);
    expect(retry.current.hourly_forecast).toEqual(initial.current.hourly_forecast);
    expect(h.observed[1].icon2i.fetchLatest).not.toHaveBeenCalled();
    expect(h.observed[1].icon2i.fetchManifest).not.toHaveBeenCalled();
    expect(h.observed[1].icon2i.fetchMunicipality).not.toHaveBeenCalled();
  });

  it("does not redownload any component when the accepted opportunity finds both still verified", async () => {
    const h = harness({ available: true });
    await h.fetch();
    expect(h.saved().camsVerifiedAt).toBe(START);
    vi.setSystemTime(START + MINUTE);
    expect((await h.fetch({ retryUnavailableCams: true })).current.data_quality.cams_run_utc).toBe(RUN_A);
    expect(h.bundleFetcher).toHaveBeenCalledTimes(1);
    expect(h.saved().camsVerifiedAt).toBe(START);
  });

  it("revalidates ICON normally after its verification window instead of extending it through failed CAMS retries", async () => {
    const h = harness();
    await h.fetch();
    vi.setSystemTime(START + MINUTE);
    await h.fetch({ retryUnavailableCams: true });
    h.publish();
    vi.setSystemTime(START + 10 * MINUTE);
    expect((await h.fetch({ retryUnavailableCams: true })).current.data_quality.cams_run_utc).toBe(RUN_B);
    expect(h.bundleFetcher.mock.lastCall[1].retainedIconBundle).toBeUndefined();
    expect(h.observed[2].icon2i.fetchLatest).toHaveBeenCalledTimes(1);
    expect(h.observed[2].camsPollen.fetchLatest).toHaveBeenCalledTimes(1);
  });

  it("does not retain an ICON window that becomes unusable while its deferred CAMS retry is completing", async () => {
    vi.setSystemTime(Date.parse("2026-09-10T01:59:58Z"));
    const h = harness();
    const originalFetch = h.bundleFetcher.getMockImplementation();
    h.bundleFetcher.mockImplementationOnce(async (...args) => {
      const bundle = await originalFetch(...args);
      return { ...bundle, current: { ...bundle.current,
        hourly_forecast: bundle.current.hourly_forecast.slice(0, 12) } };
    });
    await h.fetch();
    h.publish();
    const originalFactory = h.clientFactory.getMockImplementation();
    h.clientFactory.mockImplementationOnce(options => {
      const clients = originalFactory(options);
      const latest = clients.camsPollen.fetchLatest.getMockImplementation();
      clients.camsPollen.fetchLatest.mockImplementationOnce(() => new Promise(resolve => {
        setTimeout(async () => resolve(await latest()), 3000);
      }));
      return clients;
    });
    const update = vi.fn();
    await h.fetch({ retryUnavailableCams: true, deferCams: true, onCamsUpdate: update });
    await vi.advanceTimersByTimeAsync(3010);
    expect(update).not.toHaveBeenCalled();
    expect(readLocalWeatherV1PersistedBundle("Pordenone", h.options)).toBeNull();
    // Rejection must also release the in-flight entry, so a later existing
    // opportunity can obtain a usable ICON window rather than getting stuck.
    await h.fetch({ retryUnavailableCams: true, deferCams: true });
    await vi.advanceTimersByTimeAsync(10);
    expect(h.bundleFetcher).toHaveBeenCalledTimes(3);
    expect(h.observed[2].icon2i.fetchLatest).toHaveBeenCalledTimes(1);
  });

  it("rejects the old retry after a newer CAMS revocation without removing or overwriting the replacement", async () => {
    const h = harness();
    await h.fetch();
    h.state.available = true;
    let releaseOld;
    const originalFactory = h.clientFactory.getMockImplementation();
    h.clientFactory.mockImplementationOnce(options => {
      const clients = originalFactory(options);
      const latest = clients.camsPollen.fetchLatest.getMockImplementation();
      clients.camsPollen.fetchLatest.mockImplementationOnce(() => new Promise(resolve => {
        releaseOld = async () => resolve(await latest());
      }));
      return clients;
    });
    const update = vi.fn();
    await h.fetch({ retryUnavailableCams: true, deferCams: true, onCamsUpdate: update });
    h.publish();
    h.clientFactory.mockImplementationOnce(options => {
      const clients = originalFactory(options);
      const latest = clients.camsPollen.fetchLatest.getMockImplementation();
      clients.camsPollen.fetchLatest.mockImplementationOnce(async () => {
        const result = await latest();
        result.document.disabled_run_ids = ["20260909T000000Z"];
        return result;
      });
      return clients;
    });
    await h.fetch({ force: true });
    releaseOld();
    await vi.advanceTimersByTimeAsync(10);
    expect(update).not.toHaveBeenCalled();
    expect(h.saved().bundle.current.data_quality.cams_run_utc).toBe(RUN_B);
    expect(h.saved().bundle.current.source.cams.evidence.family.disabled_run_ids).toContain("20260909T000000Z");
  });

  it("releases deferred deduplication even if an internal clock failure prevents building the terminal supplement", async () => {
    const h = harness();
    let modelNow = START;
    h.options.now = () => modelNow;
    await h.fetch();
    h.publish();
    let release;
    const originalFactory = h.clientFactory.getMockImplementation();
    h.clientFactory.mockImplementationOnce(options => {
      const clients = originalFactory(options);
      const latest = clients.camsPollen.fetchLatest.getMockImplementation();
      clients.camsPollen.fetchLatest.mockImplementationOnce(() => new Promise(resolve => {
        release = async () => resolve(await latest());
      }));
      return clients;
    });
    const update = vi.fn();
    await h.fetch({ retryUnavailableCams: true, deferCams: true, onCamsUpdate: update });
    modelNow = NaN;
    release();
    await vi.advanceTimersByTimeAsync(10);
    expect(update).not.toHaveBeenCalled();
    expect(h.saved().camsVerifiedAt).toBeNull();
    modelNow = START;
    await h.fetch({ retryUnavailableCams: true, deferCams: true, onCamsUpdate: update });
    await vi.advanceTimersByTimeAsync(10);
    expect(h.bundleFetcher).toHaveBeenCalledTimes(3);
    expect(update.mock.lastCall[0].current.data_quality.cams_run_utc).toBe(RUN_B);
    expect(update.mock.lastCall[1]).toEqual({ lifecycle: "final" });
  });
});
