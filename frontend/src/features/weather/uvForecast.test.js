import { expect, it } from 'vitest';
import { isValidUvDocument, isVerifiedUvDocument, uvForecast } from './uvForecast';
const run = Date.parse('2026-09-06T00:00:00Z');
const document = { schema: 'pilot-uv-v1', unit: '1', run_at: new Date(run).toISOString(), grid: [[46, 13]],
  hours: Array.from({ length: 72 }, (_, i) => ({ time: new Date(run+i*3600000).toISOString(), values: [i % 24 === 12 ? 5 : 0] })) };
it('shows zero and a complete daily maximum', () => {
  expect(uvForecast(document, { latitude: 46, longitude: 13 }, run+25*3600000).maximum).toBe(5);
  expect(uvForecast(document, { latitude: 46, longitude: 13 }, run+25*3600000).current.value).toBe(0);
});
it('retains a verified series after freshness expiry but rejects missing location and partial hours', () => {
  expect(uvForecast(document, null, run)).toBeNull();
  const retained = uvForecast(document, { latitude: 46, longitude: 13 }, run+49*3600000);
  expect(isValidUvDocument(document, run+49*3600000)).toBe(false);
  expect(isVerifiedUvDocument(document)).toBe(true);
  expect(retained).toMatchObject({ currentIsCurrent: true, currentUsable: false, sourceFresh: false });
  expect(uvForecast({ ...document, hours: [] }, { latitude: 46, longitude: 13 }, run)).toBeNull();
});
it('rejects malformed grids and values for any regional point without throwing', () => {
  for (const grid of [[null], [[46]], [[NaN, 13]], [[46, 181]], [[46, 13, 0]]]) {
    expect(isValidUvDocument({ ...document, grid }, run)).toBe(false);
    expect(uvForecast({ ...document, grid }, { latitude: 46, longitude: 13 }, run)).toBeNull();
  }
  const twoPoints = { ...document, grid: [[46, 13], [46.7, 13]], hours: document.hours.map(hour => ({ ...hour, values: [0, null] })) };
  expect(isValidUvDocument(twoPoints, run)).toBe(false);
});
it('recomputes the daily peak at Rome midnight instead of retaining yesterday', () => {
  const at = Date.parse('2026-09-06T22:00:00Z');
  const changing = { ...document, hours: document.hours.map(hour => ({ ...hour, values: [Date.parse(hour.time) < at ? 8 : 2] })) };
  expect(uvForecast(changing, { latitude: 46, longitude: 13 }, at).maximum).toBe(2);
  expect(isValidUvDocument(changing, run - 1)).toBe(false);
});

const HOUR = 3600000;
const point = { latitude: 46, longitude: 13 };
function hourlyDocument(runAt = run, valueAt = index => (index * 7) % 31 / 2) {
  return {
    ...document,
    run_at: new Date(runAt).toISOString(),
    hours: Array.from({ length: 72 }, (_, index) => ({
      time: new Date(runAt + index * HOUR).toISOString(),
      values: [valueAt(index, runAt + index * HOUR)],
    })),
  };
}
const samples = hours => hours.map(hour => ({ time: Date.parse(hour.time), value: hour.values[0] }));

it('exposes only the actual hourly samples of today in Rome without reshaping the forecast', () => {
  const source = hourlyDocument();
  const now = Date.parse('2026-09-07T10:37:00Z');
  const model = uvForecast(source, point, now);

  expect(model.today).toEqual(samples(source.hours.slice(22, 46)));
  expect(model.today).toHaveLength(24);
  expect(model.now).toBe(now);
  expect(model.complete).toBe(true);
  expect(model.current).toMatchObject(samples([source.hours[34]])[0]);
});

it('exposes a partial first day without fabricating midnight samples or a daily maximum', () => {
  const source = hourlyDocument();
  const model = uvForecast(source, point, run + 10 * HOUR);

  expect(model.today).toEqual(samples(source.hours.slice(0, 22)));
  expect(model.today[0].time).toBe(run); // 02:00 in Rome, not midnight.
  expect(model.complete).toBe(false);
  expect(model.maximum).toBeNull();
  expect(model.peakTime).toBeNull();
  expect(model.current).toMatchObject(samples([source.hours[10]])[0]);
});

it('keeps the forecast-hour sample until the exact next hour without interpolating a current value', () => {
  const source = hourlyDocument(run, index => index % 12 + 0.4);
  const boundary = run + 35 * HOUR;
  const before = uvForecast(source, point, boundary - 1);
  const after = uvForecast(source, point, boundary);

  expect(before.current).toMatchObject(samples([source.hours[34]])[0]);
  expect(after.current).toMatchObject(samples([source.hours[35]])[0]);
  expect(before.today).toEqual(after.today);
  expect(before.now).toBe(boundary - 1);
  expect(after.now).toBe(boundary);
});

it('keeps the last real sample after coverage ends and marks it as not current', () => {
  const source = hourlyDocument(run, index => index / 10);
  const afterCoverage = run + 80 * HOUR;
  const model = uvForecast(source, point, afterCoverage);

  expect(model.current).toMatchObject(samples([source.hours.at(-1)])[0]);
  expect(model.currentIsCurrent).toBe(false);
  expect(model.currentUsable).toBe(false);
  expect(model.sourceFresh).toBe(false);
  expect(model.today).toEqual(samples(source.hours.slice(-2)));
  expect(model.maximum).toBeNull();
  expect(model.peakTime).toBeNull();
});

it('selects the current hour independently for each location without changing the shared series', () => {
  const source = hourlyDocument(run, index => index / 10);
  source.grid = [[46, 13], [46.7, 13]];
  source.hours = source.hours.map((hour, index) => ({ ...hour, values: [index / 10, 20 + index / 10] }));
  const now = run + 35 * HOUR;

  expect(uvForecast(source, { latitude: 46, longitude: 13 }, now).current.value).toBe(3.5);
  expect(uvForecast(source, { latitude: 46.7, longitude: 13 }, now).current.value).toBe(23.5);
  expect(source.hours[35].values).toEqual([3.5, 23.5]);
});

it.each([
  ['spring', '2026-03-28T00:00:00Z', '2026-03-29T10:00:00Z', '2026-03-28T23:00:00Z', 23, 0],
  ['autumn', '2026-10-24T00:00:00Z', '2026-10-25T10:00:00Z', '2026-10-24T22:00:00Z', 25, 2],
])('preserves the complete %s DST day and its real hourly timestamps', (_season, runAt, now, first, count, twoOClockCount) => {
  const source = hourlyDocument(Date.parse(runAt));
  const model = uvForecast(source, point, Date.parse(now));
  const firstTime = Date.parse(first);
  const clock = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Rome', hour: '2-digit', hourCycle: 'h23' });

  expect(model.complete).toBe(true);
  expect(model.today).toHaveLength(count);
  expect(model.today.map(hour => hour.time)).toEqual(Array.from({ length: count }, (_, index) => firstTime + index * HOUR));
  expect(model.today).toEqual(samples(source.hours.filter(hour => {
    const time = Date.parse(hour.time);
    return time >= firstTime && time < firstTime + count * HOUR;
  })));
  expect(clock.format(model.today[0].time)).toBe('00');
  expect(clock.format(model.today.at(-1).time)).toBe('23');
  expect(model.today.filter(hour => clock.format(hour.time) === '02')).toHaveLength(twoOClockCount);
  expect(model.maximum).toBe(Math.max(...model.today.map(hour => hour.value)));
});

it('preserves a valid all-zero day and the first sample as its tied maximum', () => {
  const model = uvForecast(hourlyDocument(run, () => 0), point, run + 36 * HOUR);

  expect(model.complete).toBe(true);
  expect(model.current.value).toBe(0);
  expect(model.today).toHaveLength(24);
  expect(model.today.every(hour => hour.value === 0)).toBe(true);
  expect(model.maximum).toBe(0);
  expect(model.peakTime).toBe(model.today[0].time);
});

it('keeps the first real daily peak rather than assuming noon or moving a tied peak', () => {
  const firstPeak = Date.parse('2026-09-07T09:00:00Z');
  const secondPeak = firstPeak + HOUR;
  const source = hourlyDocument(run, (_index, time) => time === firstPeak || time === secondPeak ? 7.3 : 0.5);
  const model = uvForecast(source, point, run + 36 * HOUR);

  expect(model.maximum).toBe(7.3);
  expect(model.peakTime).toBe(firstPeak); // 11:00 in Rome.
  expect(model.today.filter(hour => hour.value === model.maximum).map(hour => hour.time)).toEqual([firstPeak, secondPeak]);
});
