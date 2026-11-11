import { API_BASE } from "./apiConfig";

export const EMPTY_EDITORIAL_ADVICE = Object.freeze({ item: null, nextChangeAt: null });

export function normalizeEditorialAdvice(payload, now = Date.now()) {
  if (payload?.schemaVersion !== 1) return EMPTY_EDITORIAL_ADVICE;
  const nextChange = Date.parse(payload.nextChangeAt || "");
  const nextChangeAt = Number.isFinite(nextChange) && nextChange > now ? nextChange : null;
  const item = payload.item;
  if (!item) return { item: null, nextChangeAt };
  const start = Date.parse(item.startAt || "");
  const end = Date.parse(item.endAt || "");
  if (![start, end].every(Number.isFinite) || !(start <= now && now < end)
    || !item.id || item.enabled !== true
    || !["advice", "news", "message"].includes(item.type)
    || typeof item.title !== "string" || !item.title.trim() || item.title.length > 80
    || typeof item.message !== "string" || !item.message.trim() || item.message.length > 400) {
    return EMPTY_EDITORIAL_ADVICE;
  }
  return { item: { id: String(item.id || ""), type: item.type,
    title: item.title.trim(), message: item.message.trim(), startAt: item.startAt, endAt: item.endAt },
  nextChangeAt: nextChangeAt || end };
}

export async function fetchEditorialAdvice({ apiBase = API_BASE, fetchImpl = globalThis.fetch, now = Date.now } = {}) {
  try {
    const response = await fetchImpl(`${String(apiBase || "").replace(/\/$/, "")}/editorial/home-advice`, {
      cache: "no-store", headers: { Accept: "application/json" }, method: "GET",
    });
    if (!response?.ok) return EMPTY_EDITORIAL_ADVICE;
    return normalizeEditorialAdvice(await response.json(), now());
  } catch {
    return EMPTY_EDITORIAL_ADVICE;
  }
}
