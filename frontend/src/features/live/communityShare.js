import { Share } from "@capacitor/share";

export const COMMUNITY_REPORT_SHARE_BASE_URL = "https://meteofriul.it/";

const COMMUNITY_REPORT_ID_PATTERN = /^[a-z0-9][a-z0-9._:-]{0,199}$/iu;
const COMMUNITY_REPORT_ISTAT_PATTERN = /^\d{6}$/u;

function hasFunction(value) {
  return typeof value === "function";
}

function buildClipboardText(payload) {
  return [payload?.text, payload?.url].filter(Boolean).join("\n");
}

export function normalizeCommunityReportGroupId(value) {
  const normalized = String(value || "").trim();
  return COMMUNITY_REPORT_ID_PATTERN.test(normalized) ? normalized : "";
}

export function getCommunityReportIstatCode(groupId) {
  const normalized = normalizeCommunityReportGroupId(groupId);
  const match = /^group-[a-z0-9_-]+:(\d{6}):\d+$/iu.exec(normalized);
  return match?.[1] || "";
}

export function buildCommunityReportShareUrl(groupId) {
  const normalized = normalizeCommunityReportGroupId(groupId);
  if (!normalized) return COMMUNITY_REPORT_SHARE_BASE_URL;

  const url = new URL(COMMUNITY_REPORT_SHARE_BASE_URL);
  url.searchParams.set("segnalazione", normalized);
  return url.href;
}

export function readCommunityReportShareTarget(
  search = globalThis.window?.location?.search || "",
) {
  const params = new URLSearchParams(search);
  const groupId = normalizeCommunityReportGroupId(
    params.get("segnalazione") || params.get("report"),
  );
  if (!groupId) return null;

  const declaredIstatCode = String(params.get("istat") || "").trim();
  const istatCode = COMMUNITY_REPORT_ISTAT_PATTERN.test(declaredIstatCode)
    ? declaredIstatCode
    : getCommunityReportIstatCode(groupId);

  return { groupId, istatCode };
}

export function consumeCommunityReportShareTarget(windowApi = globalThis.window) {
  if (!windowApi?.location?.href || !windowApi?.history?.replaceState) return false;

  const url = new URL(windowApi.location.href);
  const hadTarget = url.searchParams.has("segnalazione")
    || url.searchParams.has("report")
    || url.searchParams.has("istat");
  if (!hadTarget) return false;

  url.searchParams.delete("segnalazione");
  url.searchParams.delete("report");
  url.searchParams.delete("istat");
  windowApi.history.replaceState(
    windowApi.history.state,
    "",
    `${url.pathname}${url.search}${url.hash}`,
  );
  return true;
}

export function buildCommunitySharePayload({
  groupId,
  legalNote,
  place,
  timeLabel,
  typeLabel,
} = {}) {
  return {
    text: [typeLabel, place, timeLabel, legalNote].filter(Boolean).join(" · "),
    title: [typeLabel, place].filter(Boolean).join(" · "),
    url: buildCommunityReportShareUrl(groupId),
  };
}

export async function shareCommunityPayload(
  payload,
  {
    nativeDialogTitle = "",
    nativeShareApi = Share,
    navigatorApi = globalThis.navigator,
    preferNativeShare = false,
    preferWebShare = false,
  } = {},
) {
  const capacitorShare = hasFunction(nativeShareApi?.share)
    ? nativeShareApi.share.bind(nativeShareApi)
    : null;
  const webShare = hasFunction(navigatorApi?.share)
    ? navigatorApi.share.bind(navigatorApi)
    : null;
  const clipboardWrite = hasFunction(navigatorApi?.clipboard?.writeText)
    ? navigatorApi.clipboard.writeText.bind(navigatorApi.clipboard)
    : null;
  let canWebShare = true;
  if (hasFunction(navigatorApi?.canShare)) {
    try {
      canWebShare = navigatorApi.canShare(payload) === true;
    } catch {
      canWebShare = false;
    }
  }

  const copyToClipboard = async () => {
    if (!clipboardWrite) return null;
    await clipboardWrite(buildClipboardText(payload));
    return { method: "clipboard", ok: true };
  };

  if (preferNativeShare && capacitorShare) {
    try {
      await capacitorShare({
        ...payload,
        ...(nativeDialogTitle ? { dialogTitle: nativeDialogTitle } : {}),
      });
      return { method: "native-share", ok: true };
    } catch (error) {
      if (error?.name === "AbortError") return { ok: false, reason: "cancelled" };
      // Keep Web Share and clipboard as bounded fallbacks if the native bridge
      // is temporarily unavailable in a mismatched WebView/native build.
    }
  }

  if (preferWebShare && webShare && canWebShare) {
    try {
      await webShare(payload);
      return { method: "web-share", ok: true };
    } catch (error) {
      if (error?.name === "AbortError") return { ok: false, reason: "cancelled" };
      try {
        const copied = await copyToClipboard();
        if (copied) return copied;
      } catch {
        return { ok: false, reason: "unavailable" };
      }
      return { ok: false, reason: "unavailable" };
    }
  }

  try {
    const copied = await copyToClipboard();
    if (copied) return copied;
  } catch {
    // Some browsers expose Clipboard without granting write access. In that
    // case the Web Share API is still a valid fallback when it is available.
  }

  if (webShare && canWebShare) {
    try {
      await webShare(payload);
      return { method: "web-share", ok: true };
    } catch (error) {
      if (error?.name === "AbortError") return { ok: false, reason: "cancelled" };
    }
  }

  return { ok: false, reason: "unavailable" };
}
