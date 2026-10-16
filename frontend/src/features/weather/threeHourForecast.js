const HOUR = 3600000;
const number = (value) => typeof value === "number" && Number.isFinite(value) ? value : null;
const format = (value) => new Intl.NumberFormat("it-IT", { maximumFractionDigits: 2 }).format(value);
const clock = (value) => new Intl.DateTimeFormat("it-IT", {
  hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome",
}).format(new Date(value));

export function buildThreeHourForecast(items) {
  if (!items.length) return [];
  const first = Date.parse(items[0].timestamp);
  return items.filter((item) => (Date.parse(item.timestamp) - first) % (3 * HOUR) === 0)
    .map((item) => {
      const start = Date.parse(item.timestamp);
      const end = start + 3 * HOUR;
      const intervals = items.filter((candidate) => {
        const from = Date.parse(candidate.intervalStart);
        const to = Date.parse(candidate.intervalEnd);
        return from >= start && to <= end && to - from === HOUR;
      }).sort((a, b) => Date.parse(a.intervalStart) - Date.parse(b.intervalStart));
      const complete = intervals.length === 3 && intervals.every((entry, index) => (
        Date.parse(entry.intervalStart) === start + index * HOUR
      ));
      const rain = intervals.map((entry) => number(entry.values?.precipitation));
      const gusts = intervals.map((entry) => number(entry.values?.windGusts));
      const total = complete && rain.every((value) => value !== null)
        ? rain.reduce((sum, value) => sum + value, 0) : null;
      const gust = complete && gusts.every((value) => value !== null) ? Math.max(...gusts) : null;
      return {
        ...item,
        rainWindow: `${clock(start)}–${clock(end)}`,
        rainTotalValue: total,
        rainTotal: total === null ? null : `${format(total)} mm`,
        rainCalculation: total === null ? null : `${rain.map(format).join(" + ")} = ${format(total)} mm`,
        periodGust: gust === null ? null : `${format(gust)} km/h`,
      };
    });
}
