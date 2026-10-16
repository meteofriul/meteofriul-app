import { getDateTimeFormatter } from '../../domain/dateTimeFormatters.js';

const day = (time) => getDateTimeFormatter('en-CA', { timeZone: 'Europe/Rome', year: 'numeric', month: '2-digit', day: '2-digit' }).format(time);
export const UV_DOCUMENT_MAX_AGE_MS = 48 * 3600000;

export function isVerifiedUvDocument(document) {
  const run = Date.parse(document?.run_at);
  if (document?.schema !== 'pilot-uv-v1' || document.unit !== '1'
      || !Number.isFinite(run)
      || !Array.isArray(document.grid) || !document.grid.length
      || !Array.isArray(document.hours) || document.hours.length !== 72) return false;
  if (!document.grid.every(point => Array.isArray(point) && point.length === 2
      && Number.isFinite(point[0]) && Math.abs(point[0]) <= 90
      && Number.isFinite(point[1]) && Math.abs(point[1]) <= 180)) return false;
  return document.hours.every((hour, index) => hour && Date.parse(hour.time) === run + index * 3600000
    && Array.isArray(hour.values) && hour.values.length === document.grid.length
    && hour.values.every(value => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 50));
}

export function isValidUvDocument(document, now = Date.now()) {
  const run = Date.parse(document?.run_at);
  return isVerifiedUvDocument(document) && Number.isFinite(now)
    && now >= run && now - run <= UV_DOCUMENT_MAX_AGE_MS;
}

export function uvForecast(document, point, now = Date.now()) {
  const run = Date.parse(document?.run_at);
  if (!isVerifiedUvDocument(document) || !Number.isFinite(now) || now < run
      || !Number.isFinite(point?.latitude) || !Number.isFinite(point?.longitude)) return null;
  let index = -1, distance = Infinity;
  document.grid.forEach(([lat, lon], i) => {
    const d = Math.hypot(lat-point.latitude, (lon-point.longitude)*Math.cos(point.latitude*Math.PI/180));
    if (d < distance) { distance = d; index = i; }
  });
  if (distance > 0.5 || index < 0) return null;
  const hours = document.hours.map((hour, i) => ({ time: Date.parse(hour.time), value: hour.values?.[index], i }));
  if (hours.some(h => h.time !== run+h.i*3600000 || typeof h.value !== 'number' || !Number.isFinite(h.value) || h.value < 0 || h.value > 50)) return null;
  const pertinent = hours.find(h => h.time <= now && now < h.time+3600000);
  const current = pertinent ?? hours.findLast(h => h.time <= now);
  if (!current) return null;
  const todayKey = day(now);
  const today = hours.filter(h => day(h.time) === todayKey);
  // Do not label a partial day as a full daily maximum (DST days have 23/25 h).
  const complete = today.length >= 23 && getDateTimeFormatter('en-GB', { timeZone: 'Europe/Rome', hour: '2-digit', hourCycle: 'h23' }).format(today[0].time) === '00'
    && getDateTimeFormatter('en-GB', { timeZone: 'Europe/Rome', hour: '2-digit', hourCycle: 'h23' }).format(today.at(-1).time) === '23';
  const peak = complete ? today.reduce((best, hour) => hour.value > best.value ? hour : best) : null;
  const sourceFresh = isValidUvDocument(document, now);
  return { current, maximum: peak?.value ?? null, peakTime: peak?.time ?? null, run,
    today: today.map(({ time, value }) => ({ time, value })), now, complete,
    currentIsCurrent: Boolean(pertinent), currentUsable: Boolean(pertinent) && sourceFresh, sourceFresh };
}
