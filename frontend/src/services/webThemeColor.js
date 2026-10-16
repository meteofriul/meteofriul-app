export const WEB_THEME_COLOR = Object.freeze({
  light: "#091D3D",
  dark: "#08213A",
});

export function syncWebThemeColor(theme, { documentLike = globalThis.document } = {}) {
  const meta = documentLike?.querySelector?.('meta[name="theme-color"]');
  if (!meta) return false;

  meta.setAttribute("content", theme === "dark" ? WEB_THEME_COLOR.dark : WEB_THEME_COLOR.light);
  return true;
}
