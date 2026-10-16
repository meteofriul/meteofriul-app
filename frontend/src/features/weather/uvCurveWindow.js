import { getSunCycle } from "../../domain/almanac/sunCycle";

const TIME_ZONE = "Europe/Rome";
const HOUR_MS = 3600000;
const calendar = new Intl.DateTimeFormat("en-CA", {
  timeZone: TIME_ZONE, year: "numeric", month: "2-digit", day: "2-digit",
});
const clock = new Intl.DateTimeFormat("en-GB", {
  timeZone: TIME_ZONE, hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
const minutes = value => {
  if (!/^\d{2}:\d{2}$/.test(value)) return null;
  const [hours, rest] = value.split(":").map(Number);
  return hours < 24 && rest < 60 ? hours * 60 + rest : null;
};

function daylightWindow(model, samples, point) {
  if (!Number.isFinite(point?.latitude) || Math.abs(point.latitude) > 90
      || !Number.isFinite(point?.longitude) || Math.abs(point.longitude) > 180) return null;
  const reference = model.now ?? model.current?.time ?? samples[0].time;
  if (!Number.isFinite(reference)) return null;
  const date = Object.fromEntries(calendar.formatToParts(reference).map(part => [part.type, part.value]));
  const utcNoon = Date.UTC(Number(date.year), Number(date.month) - 1, Number(date.day), 12);
  // Anchor to noon on the forecast's Rome date, not the UTC date at local midnight.
  // At noon the DST transition has already settled in either direction.
  const localHour = Number(clock.format(utcNoon).split(":")[0]);
  const localNoon = new Date(utcNoon + (12 - localHour) * HOUR_MS);
  const sun = getSunCycle({
    date: localNoon, now: localNoon, latitude: point.latitude, longitude: point.longitude, timeZone: TIME_ZONE,
  });
  const sunrise = minutes(sun.sunrise), sunset = minutes(sun.sunset);
  if (sunrise === null || sunset === null || sunset <= sunrise) return null;
  const sampleMinutes = samples.map(sample => minutes(clock.format(sample.time)));
  let start = sampleMinutes.findLastIndex(value => value <= sunrise);
  let end = sampleMinutes.findIndex(value => value >= sunset);
  if (start < 0) start = 0;
  if (end < 0) end = samples.length - 1;
  return [start, end];
}

// Presentation-only selection: every returned object remains an original hourly
// forecast sample. No interpolation, zero padding or change to UV validity.
export function selectUvCurveSamples(model, point) {
  const samples = model?.today || [];
  if (samples.length < 2) return samples;
  const firstPositive = samples.findIndex(sample => sample.value > 0);
  const lastPositive = samples.findLastIndex(sample => sample.value > 0);
  const positiveWindow = firstPositive < 0 ? null : [
    Math.max(0, firstPositive - 1), Math.min(samples.length - 1, lastPositive + 1),
  ];
  const solarWindow = daylightWindow(model, samples, point);
  if (!solarWindow && !positiveWindow) return samples;
  let [start, end] = solarWindow || positiveWindow;
  // Do not hide a real positive forecast outside the computed daylight window.
  if (positiveWindow) {
    start = Math.min(start, positiveWindow[0]);
    end = Math.max(end, positiveWindow[1]);
  }
  if (start === end) {
    if (end < samples.length - 1) end += 1;
    else start = Math.max(0, start - 1);
  }
  return samples.slice(start, end + 1);
}
