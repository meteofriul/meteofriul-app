// Keep the reviewed browser URL as an alias for the real local TEST app.
export const recentListPreviewEnabled = import.meta.env.DEV
  && ["127.0.0.1", "localhost", "[::1]"].includes(globalThis.location?.hostname)
  && globalThis.location?.pathname === "/community-list-preview.html";
