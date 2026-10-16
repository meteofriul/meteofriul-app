import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { UvAdvice, UvValues, WeatherUvCard, WeatherUvContent } from "./WeatherUvCard";
import { uvLevel } from "./uvLevels";
import { UV_CACHE_KEY, UV_FORECAST_URL } from "./uvForecastRuntime";

describe("UV forecast card", () => {
  it('classifies rounded values at every boundary and rejects missing values', () => {
    for (const [value, expected] of [[0,'Basso'],[2.49,'Basso'],[2.5,'Moderato'],[5.49,'Moderato'],[5.9,'Alto'],[7.5,'Molto alto'],[10.5,'Estremo'],[20,'Estremo']]) expect(uvLevel(value).it).toBe(expected);
    for (const value of [null, undefined, -1, NaN, Infinity]) expect(uvLevel(value)).toBeNull();
  });
  it.each([
    [0.6, 'low'],
    [3, 'moderate'],
    [6, 'high'],
    [9, 'very-high'],
    [12, 'extreme'],
  ])('maps UV %s to the stable %s visual tone', (value, expected) => {
    expect(uvLevel(value).tone).toBe(expected);
  });
  it('does not mark a missing daily maximum', () => {
    const html = renderToStaticMarkup(<UvValues model={{ current: { time: 0, value: 0 }, maximum: null }} />);
    expect(html).not.toContain('data-uv-peak');
    expect(html).toContain('Giornata incompleta');
  });
  it("distinguishes the forecast for the current hour from the daily peak", () => {
    const model = { current: { time: Date.parse('2026-09-07T00:00:00Z'), value: 0 }, maximum: 5.9, peakTime: Date.parse('2026-09-07T11:00:00Z') };
    const html = renderToStaticMarkup(<UvValues model={model} />);
    const text = html.replace(/<[^>]*>/g, '');
    expect(html).toContain('Previsto adesso');
    expect(text).toContain('Bassoore');
    expect(html).toContain('02:00');
    expect(text).toContain('Picco previsto oggi');
    expect(text).toContain('Alto · 13:00');
    expect(html).toContain('5,9');
    expect(html).not.toContain('>Massimo<');
    expect(html).not.toContain('mf-weather-uv-scale');
    expect(html).toContain('Alto');
    const advice = renderToStaticMarkup(<UvAdvice model={model} />);
    expect(advice).toContain('Proteggi pelle e occhi');
    expect(advice).not.toContain('Nessuna crema');
    expect(advice).not.toContain('SPF 15');
  });
  it("does not present the diagnostic sample or zero as a live forecast", () => {
    const html = renderToStaticMarkup(<WeatherUvCard />);
    expect(html).toContain("Indice UV");
    expect(html).toContain("non ancora disponibile");
    expect(html).not.toContain("4,99");
    expect(html).not.toContain('mf-weather-uv-curve');
    expect(html).not.toContain('mf-weather-uv-scale__marker');
  });
  it("provides Friulian copy", () => {
    expect(renderToStaticMarkup(<WeatherUvCard language="fur" />)).toContain("Indiç UV");
  });
  it.each([
    ["it", "Previsione oraria della radiazione solare.", "Aggiornamento non disponibile"],
    ["fur", "Prevision orarie de radiazion solâr.", "Inzornament no disponibile"],
  ])("uses a neutral note for a retained usable forecast in %s", (language, expected, removed) => {
    const start = Date.parse("2026-09-14T06:00:00Z");
    const today = [
      { time: start, value: 2 },
      { time: start + 3600000, value: 3 },
    ];
    const html = renderToStaticMarkup(<WeatherUvContent
      compactDetail
      error={new Error("offline")}
      forecastDate="14/09/2026"
      language={language}
      model={{
        current: today[0],
        currentUsable: true,
        maximum: 3,
        peakTime: today[1].time,
        run: start,
        today,
      }}
      point={{ latitude: 45.9567, longitude: 12.6605 }}
      saved
    />);

    expect(html).toContain(expected);
    expect(html).not.toContain(removed);

    const ordinary = renderToStaticMarkup(<WeatherUvContent
      error={new Error("offline")}
      forecastDate="14/09/2026"
      language={language}
      model={{
        current: today[0],
        currentUsable: true,
        maximum: 3,
        peakTime: today[1].time,
        run: start,
        today,
      }}
      point={{ latitude: 45.9567, longitude: 12.6605 }}
      saved
    />);
    expect(ordinary).toContain(removed);
    expect(ordinary).not.toContain(expected);
  });
  it.each([
    ['it', 'Picco previsto oggi', 'Previsione del', 'Previsione già caricata.', 'Ultimo dato disponibile', 'la previsione non è aggiornata'],
    ['fur', 'Pic previodût par vuê', 'Prevision dal', 'Prevision za cjariade.', 'Ultin dât disponibil', 'la prevision no je inzornade'],
  ])(
    "renders a saved daily forecast immediately in %s and retains it honestly after expiry",
    (language, title, dateLabel, cachedLabel, retainedLabel, retainedNote) => {
      const run = Date.parse('2026-09-06T00:00:00Z');
      const document = { schema: 'pilot-uv-v1', unit: '1', run_at: new Date(run).toISOString(), grid: [[46, 13]],
        hours: Array.from({ length: 72 }, (_, i) => ({ time: new Date(run + i * 3600000).toISOString(), values: [i % 24 === 11 ? 5.9 : 0] })) };
      const cached = JSON.stringify({ version: 1, url: UV_FORECAST_URL, savedAt: run + 36 * 3600000, document });
      vi.useFakeTimers();
      vi.setSystemTime(run + 36 * 3600000);
      vi.stubGlobal('localStorage', { getItem: key => key === UV_CACHE_KEY ? cached : null });
      try {
        const html = renderToStaticMarkup(<WeatherUvCard language={language} point={{ latitude: 46, longitude: 13 }} />);
        expect(html.replace(/<[^>]*>/g, '')).toContain(title);
        expect(html).toContain('5,9');
        expect(html).toContain(`${dateLabel} 07/09/2026`);
        expect(html).toContain(cachedLabel);
        expect(html).toContain('<details class="mf-weather-uv-source">');
        expect(html).not.toContain('<details open');
        expect(html).toContain('Copernicus CAMS');
        expect(html).toContain('data-uv-current');
        expect(html).toContain('data-uv-peak');
        expect(html).toMatch(/<footer[^>]*mf-weather-uv-footer[^>]*>[\s\S]*mf-weather-uv-advice[\s\S]*mf-weather-uv-source/);
        expect(html).not.toContain('mf-weather-uv-scale');
        expect(html).not.toContain('<figcaption');
        expect(html).not.toContain('Dato valido');
        vi.setSystemTime(run + 49 * 3600000);
        const retained = renderToStaticMarkup(<WeatherUvCard language={language} point={{ latitude: 46, longitude: 13 }} />);
        expect(retained).toContain(retainedLabel);
        expect(retained).toContain(retainedNote);
        expect(retained).not.toContain(title);
        expect(retained).not.toContain('mf-weather-uv-curve');
        expect(retained).not.toContain('mf-weather-uv-advice');
      } finally {
        vi.unstubAllGlobals();
        vi.useRealTimers();
      }
    },
  );

  it.each(['it', 'fur'])('plots only the supplied hourly values with accessible text in %s', language => {
    const start = Date.parse('2026-09-07T04:00:00Z');
    const today = [0, 2, 1, 0].map((value, index) => ({ time: start + index * 3600000, value }));
    const model = { today, current: today[2], maximum: 2, peakTime: today[1].time };
    const html = renderToStaticMarkup(<UvValues model={model} language={language} />);
    expect(html).toContain('points="12,64 124,22 236,43 348,64"');
    expect(html).toContain(`data-uv-current="${today[2].time}"`);
    expect(html).toContain(`data-uv-peak="${today[1].time}"`);
    expect(html).toContain('06:00: 0; 07:00: 2; 08:00: 1; 09:00: 0');
    expect(html).toContain(language === 'fur' ? 'Andament UV previodût' : 'Andamento UV previsto');
    expect(html).toContain('aria-labelledby=');
    expect(html).not.toContain('12:00');
  });

  it('renders a flat zero series and no peak for a partial day', () => {
    const today = [0, 1, 2].map(index => ({ time: index * 3600000, value: 0 }));
    const html = renderToStaticMarkup(<UvValues model={{ today, current: today[1], maximum: null, peakTime: null }} />);
    expect(html).toContain('points="12,64 180,64 348,64"');
    expect(html).toContain('Giornata incompleta');
    expect(html).not.toContain('data-uv-peak');
    expect(html).not.toMatch(/NaN|Infinity/);
  });

  it('preserves an extreme forecast and its advice without the duplicate scale', () => {
    const model = { current: { time: 0, value: 20 }, maximum: 20, peakTime: 0 };
    const html = renderToStaticMarkup(<UvValues model={model} />);
    expect(html).toContain('>20</span>');
    expect(html).toContain('Estremo');
    expect(html).not.toContain('mf-weather-uv-scale');
    expect(renderToStaticMarkup(<UvAdvice model={model} />)).toContain('Evita il sole nelle ore centrali');
  });

  it('keeps the nightly current value in the header without stretching the daylight curve', () => {
    const start = Date.parse('2026-09-10T00:00:00+02:00');
    const today = Array.from({ length: 24 }, (_, i) => ({ time: start + i * 3600000, value: i === 12 ? 1.4 : 0 }));
    const html = renderToStaticMarkup(<UvValues point={{ latitude: 45.9567, longitude: 12.6605 }}
      model={{ today, now: today[23].time, current: today[23], maximum: 1.4, peakTime: today[12].time }} />);
    expect(html).toContain('ore 23:00');
    expect(html).toContain('>06:00</text>');
    expect(html).toContain('>20:00</text>');
    expect(html).not.toContain('data-uv-current');
    expect(html).toContain('data-uv-peak');
    expect(html).toContain('viewBox="0 0 360 82"');
  });

  it('shows one timestamp at a coincident peak/current point', () => {
    const start = Date.parse('2026-09-10T10:00:00Z');
    const today = [0, 2, 0].map((value, i) => ({ time: start + i * 3600000, value }));
    const html = renderToStaticMarkup(<UvValues model={{ today, current: today[1], maximum: 2, peakTime: today[1].time }} />);
    expect(html).toContain('data-uv-current');
    expect(html).toContain('data-uv-peak');
    expect(html.match(/>13:00<\/text>/g)).toHaveLength(1);
    expect(html).not.toContain('Ora corrente');
  });
});
