import { describe, expect, it, vi } from "vitest";

import {
  COMMUNITY_REPORT_SHARE_BASE_URL,
  buildCommunityReportShareUrl,
  buildCommunitySharePayload,
  consumeCommunityReportShareTarget,
  getCommunityReportIstatCode,
  readCommunityReportShareTarget,
  shareCommunityPayload,
} from "./communityShare";

const groupId = "group-rain:093033:994321";
const payload = buildCommunitySharePayload({
  groupId,
  legalNote: "Zona indicativa",
  place: "Pordenone",
  timeLabel: "Adesso",
  typeLabel: "Pioggia",
});

describe("community share", () => {
  it("builds the public report page path without leaking local or QA URLs", () => {
    expect(payload).toEqual({
      text: "Pioggia · Pordenone · Adesso · Zona indicativa",
      title: "Pioggia · Pordenone",
      url: `${COMMUNITY_REPORT_SHARE_BASE_URL}?segnalazione=group-rain%3A093033%3A994321`,
    });
    expect(payload.url).toBe(
      "https://meteofriul.it/?segnalazione=group-rain%3A093033%3A994321",
    );
    expect(payload.url).not.toMatch(/127\.0\.0\.1|localhost|communityReportQa/u);
  });

  it("accepts only bounded public IDs and derives the municipality scope", () => {
    expect(buildCommunityReportShareUrl(groupId)).toBe(payload.url);
    expect(getCommunityReportIstatCode(groupId)).toBe("093033");
    expect(buildCommunityReportShareUrl("../../private?token=secret"))
      .toBe(COMMUNITY_REPORT_SHARE_BASE_URL);
  });

  it("reads and consumes a report target from the app deep link", () => {
    expect(readCommunityReportShareTarget(
      `?tab=live&segnalazione=${encodeURIComponent(groupId)}`,
    )).toEqual({ groupId, istatCode: "093033" });
    expect(readCommunityReportShareTarget(
      `?tab=live&report=${encodeURIComponent(groupId)}&istat=invalid`,
    )).toEqual({ groupId, istatCode: "093033" });
    expect(readCommunityReportShareTarget("?tab=live&report=%2Fprivate"))
      .toBeNull();

    const replaceState = vi.fn();
    const windowApi = {
      history: { replaceState, state: { preserved: true } },
      location: {
        href: `https://meteofriul.app/?tab=live&segnalazione=${encodeURIComponent(groupId)}#map`,
      },
    };
    expect(consumeCommunityReportShareTarget(windowApi)).toBe(true);
    expect(replaceState).toHaveBeenCalledWith(
      { preserved: true },
      "",
      "/?tab=live#map",
    );
  });

  it("uses the deterministic clipboard path in a browser even when Web Share exists", async () => {
    const share = vi.fn().mockResolvedValue(undefined);
    const writeText = vi.fn().mockResolvedValue(undefined);

    await expect(shareCommunityPayload(payload, {
      navigatorApi: { clipboard: { writeText }, share },
    })).resolves.toEqual({ method: "clipboard", ok: true });

    expect(share).not.toHaveBeenCalled();
    expect(writeText).toHaveBeenCalledWith(
      `${payload.text}\n${payload.url}`,
    );
  });

  it("opens the native Capacitor share sheet on Android with text and public link", async () => {
    const nativeShare = vi.fn().mockResolvedValue({ activityType: "" });
    const webShare = vi.fn().mockResolvedValue(undefined);
    const writeText = vi.fn().mockResolvedValue(undefined);

    await expect(shareCommunityPayload(payload, {
      nativeDialogTitle: "Condividi la segnalazione Meteo Friûl",
      nativeShareApi: { share: nativeShare },
      navigatorApi: { clipboard: { writeText }, share: webShare },
      preferNativeShare: true,
      preferWebShare: true,
    })).resolves.toEqual({ method: "native-share", ok: true });

    expect(nativeShare).toHaveBeenCalledWith({
      ...payload,
      dialogTitle: "Condividi la segnalazione Meteo Friûl",
    });
    expect(webShare).not.toHaveBeenCalled();
    expect(writeText).not.toHaveBeenCalled();
  });

  it("prefers Web Share in Android WebView when that API is available", async () => {
    const share = vi.fn().mockResolvedValue(undefined);

    await expect(shareCommunityPayload(payload, {
      navigatorApi: { canShare: () => true, share },
      preferWebShare: true,
    })).resolves.toEqual({ method: "web-share", ok: true });

    expect(share).toHaveBeenCalledWith(payload);
  });

  it("falls back to copying after a non-cancellation Web Share failure", async () => {
    const share = vi.fn().mockRejectedValue(new Error("share unavailable"));
    const writeText = vi.fn().mockResolvedValue(undefined);

    await expect(shareCommunityPayload(payload, {
      navigatorApi: { clipboard: { writeText }, share },
      preferWebShare: true,
    })).resolves.toEqual({ method: "clipboard", ok: true });

    expect(writeText).toHaveBeenCalledTimes(1);
  });

  it("falls back to Web Share when browser clipboard access is rejected", async () => {
    const share = vi.fn().mockResolvedValue(undefined);

    await expect(shareCommunityPayload(payload, {
      navigatorApi: {
        clipboard: { writeText: vi.fn().mockRejectedValue(new Error("blocked")) },
        share,
      },
    })).resolves.toEqual({ method: "web-share", ok: true });

    expect(share).toHaveBeenCalledWith(payload);
  });

  it.each([
    { canShare: () => false, label: "returns false" },
    { canShare: () => { throw new Error("unsupported"); }, label: "throws" },
  ])("copies instead when canShare $label", async ({ canShare }) => {
    const share = vi.fn().mockResolvedValue(undefined);
    const writeText = vi.fn().mockResolvedValue(undefined);

    await expect(shareCommunityPayload(payload, {
      navigatorApi: { canShare, clipboard: { writeText }, share },
      preferWebShare: true,
    })).resolves.toEqual({ method: "clipboard", ok: true });

    expect(share).not.toHaveBeenCalled();
    expect(writeText).toHaveBeenCalledTimes(1);
  });

  it("does not copy after the user cancels the Web Share sheet", async () => {
    const cancellation = Object.assign(new Error("cancelled"), { name: "AbortError" });
    const writeText = vi.fn().mockResolvedValue(undefined);

    await expect(shareCommunityPayload(payload, {
      navigatorApi: {
        clipboard: { writeText },
        share: vi.fn().mockRejectedValue(cancellation),
      },
      preferWebShare: true,
    })).resolves.toEqual({ ok: false, reason: "cancelled" });

    expect(writeText).not.toHaveBeenCalled();
  });

  it("returns an explicit unavailable result when neither route works", async () => {
    await expect(shareCommunityPayload(payload, {
      navigatorApi: {},
    })).resolves.toEqual({ ok: false, reason: "unavailable" });
  });
});
