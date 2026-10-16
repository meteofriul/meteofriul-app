const MAX_FORMATTERS = 32;
const formatters = new Map();

// Only explicit zones are reusable across calls: a device timezone can change
// while the app is alive, so implicit-local formatters retain native semantics.
export function getDateTimeFormatter(locale, options) {
  if (typeof options?.timeZone !== "string") {
    return new Intl.DateTimeFormat(locale, options);
  }
  const key = JSON.stringify([locale, Object.entries(options).sort(([a], [b]) => a.localeCompare(b))]);
  let formatter = formatters.get(key);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat(locale, options);
    if (formatters.size >= MAX_FORMATTERS) formatters.delete(formatters.keys().next().value);
    formatters.set(key, formatter);
  }
  return formatter;
}
