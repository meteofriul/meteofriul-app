const WIDTH = 640;
const HEIGHT = 184;
const PLOT = Object.freeze({ left: 42, right: 12, top: 18, bottom: 30 });
const WINDOW_SIZE = 24;

const COPY = {
  it: {
    apparent: "Percepita",
    chartWindow: "Finestra di 24 ore",
    gusts: "Raffiche",
    heading: "Andamento",
    precipitation: "Precipitazioni",
    temperature: "Temperatura",
    unavailable: "Dati insufficienti per il grafico",
    wind: "Vento",
  },
  fur: {
    apparent: "Percepide",
    chartWindow: "Barcon di 24 oris",
    gusts: "Rafichis",
    heading: "Andament",
    precipitation: "Precipitazions",
    temperature: "Temperadure",
    unavailable: "Dâts insuficients pal grafic",
    wind: "Vint",
  },
};

function numeric(value) {
  if (
    value === null
    || value === undefined
    || typeof value === "boolean"
    || (typeof value === "string" && !value.trim())
  ) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function getForecastChartWindow(items, selectedKey, windowSize = WINDOW_SIZE) {
  if (!Array.isArray(items) || !items.length) return { items: [], start: 0 };
  const selectedIndex = Math.max(0, items.findIndex((item) => item.timestamp === selectedKey));
  const start = Math.floor(selectedIndex / windowSize) * windowSize;
  return { items: items.slice(start, start + windowSize), start };
}

function getExtent(items, keys, { floorZero = false } = {}) {
  const values = items.flatMap((item) => keys
    .map((key) => numeric(item.values?.[key]))
    .filter((value) => value !== null));
  if (!values.length) return null;
  let min = floorZero ? 0 : Math.min(...values);
  let max = Math.max(...values);
  if (min === max) {
    const padding = Math.max(1, Math.abs(min) * 0.1);
    min = floorZero ? 0 : min - padding;
    max += padding;
  }
  return { min, max };
}

function pointX(index, count) {
  const width = WIDTH - PLOT.left - PLOT.right;
  return PLOT.left + (count <= 1 ? width / 2 : index * width / (count - 1));
}

function pointY(value, extent) {
  const height = HEIGHT - PLOT.top - PLOT.bottom;
  return PLOT.top + (extent.max - value) * height / (extent.max - extent.min);
}

function linePath(items, key, extent) {
  let drawing = false;
  return items.map((item, index) => {
    const value = numeric(item.values?.[key]);
    if (value === null) {
      drawing = false;
      return "";
    }
    const command = drawing ? "L" : "M";
    drawing = true;
    return `${command}${pointX(index, items.length).toFixed(1)},${pointY(value, extent).toFixed(1)}`;
  }).filter(Boolean).join(" ");
}

function tickIndexes(count) {
  if (count <= 1) return [0];
  const last = count - 1;
  return [...new Set([0, Math.round(last / 4), Math.round(last / 2), Math.round(3 * last / 4), last])];
}

function AxisLayer({ extent, items, unit }) {
  const ticks = [extent.max, (extent.max + extent.min) / 2, extent.min];
  return (
    <g aria-hidden="true" className="mf-weather-chart__axes">
      {ticks.map((value, index) => {
        const y = PLOT.top + index * (HEIGHT - PLOT.top - PLOT.bottom) / 2;
        return (
          <g key={`${value}-${index}`}>
            <line x1={PLOT.left} x2={WIDTH - PLOT.right} y1={y} y2={y} />
            <text x={PLOT.left - 7} y={y + 4}>{Math.round(value)}{unit}</text>
          </g>
        );
      })}
      {tickIndexes(items.length).map((index) => (
        <text
          className="mf-weather-chart__time"
          key={`${items[index]?.timestamp}-${index}`}
          textAnchor={index === 0 ? "start" : index === items.length - 1 ? "end" : "middle"}
          x={pointX(index, items.length)}
          y={HEIGHT - 8}
        >
          {items[index]?.time}
        </text>
      ))}
    </g>
  );
}

function SelectionCursor({ items, selectedKey }) {
  const index = items.findIndex((item) => item.timestamp === selectedKey);
  if (index < 0) return null;
  const x = pointX(index, items.length);
  return (
    <line
      aria-hidden="true"
      className="mf-weather-chart__cursor"
      data-testid="forecast-chart-cursor"
      x1={x}
      x2={x}
      y1={PLOT.top}
      y2={HEIGHT - PLOT.bottom}
    />
  );
}

function ChartFrame({ children, description, id, items, legend, selectedKey, title, unavailable, unit }) {
  const extent = getExtent(items, legend.map(({ key }) => key), { floorZero: unit === " mm" });
  return (
    <figure className="mf-weather-chart">
      <figcaption>
        <strong>{title}</strong>
        <span className="mf-weather-chart__legend">
          {legend.map((entry) => (
            <span data-style={entry.style || "solid"} key={entry.key}>
              <i aria-hidden="true" data-color={entry.color} />
              {entry.label}
            </span>
          ))}
        </span>
      </figcaption>
      {extent ? (
        <svg aria-labelledby={`${id}-title ${id}-desc`} role="img" viewBox={`0 0 ${WIDTH} ${HEIGHT}`}>
          <title id={`${id}-title`}>{title}</title>
          <desc id={`${id}-desc`}>{description}</desc>
          <AxisLayer extent={extent} items={items} unit={unit} />
          {children(extent)}
          <SelectionCursor items={items} selectedKey={selectedKey} />
        </svg>
      ) : (
        <p>{unavailable}</p>
      )}
    </figure>
  );
}

function LineChart({ copy, id, items, keys, selectedKey, title, unit }) {
  const description = `${copy.chartWindow}: ${items[0]?.time || ""}–${items.at(-1)?.time || ""}`;
  return (
    <ChartFrame
      description={description}
      id={id}
      items={items}
      legend={keys}
      selectedKey={selectedKey}
      title={title}
      unavailable={copy.unavailable}
      unit={unit}
    >
      {(extent) => keys.map((entry) => {
        const path = linePath(items, entry.key, extent);
        return path ? (
          <path
            aria-hidden="true"
            className="mf-weather-chart__line"
            d={path}
            data-color={entry.color}
            data-style={entry.style || "solid"}
            key={entry.key}
          />
        ) : null;
      })}
    </ChartFrame>
  );
}

function PrecipitationChart({ copy, items, selectedKey }) {
  const description = `${copy.chartWindow}: ${items[0]?.time || ""}–${items.at(-1)?.time || ""}`;
  return (
    <ChartFrame
      description={description}
      id="forecast-precipitation-chart"
      items={items}
      legend={[{ color: "rain", key: "precipitation", label: copy.precipitation }]}
      selectedKey={selectedKey}
      title={copy.precipitation}
      unavailable={copy.unavailable}
      unit=" mm"
    >
      {(extent) => {
        const plotBottom = HEIGHT - PLOT.bottom;
        const width = (WIDTH - PLOT.left - PLOT.right) / Math.max(1, items.length);
        return items.map((item, index) => {
          const value = numeric(item.values?.precipitation);
          if (value === null) return null;
          const y = pointY(value, extent);
          return (
            <rect
              aria-hidden="true"
              className="mf-weather-chart__bar"
              height={Math.max(1, plotBottom - y)}
              key={item.timestamp}
              width={Math.max(3, width * 0.58)}
              x={pointX(index, items.length) - Math.max(3, width * 0.58) / 2}
              y={Math.min(plotBottom - 1, y)}
            />
          );
        });
      }}
    </ChartFrame>
  );
}

export function WeatherForecastCharts({ items, language = "it", selectedKey }) {
  const copy = COPY[language === "fur" ? "fur" : "it"];
  const window = getForecastChartWindow(items, selectedKey);
  if (!window.items.length) return null;

  return (
    <section aria-labelledby="weather-forecast-charts-title" className="mf-weather-charts">
      <header>
        <h4 id="weather-forecast-charts-title">{copy.heading}</h4>
        <span>{copy.chartWindow}</span>
      </header>
      <div className="mf-weather-charts__grid">
        <LineChart
          copy={copy}
          id="forecast-temperature-chart"
          items={window.items}
          keys={[
            { color: "temperature", key: "temperature", label: copy.temperature },
            { color: "apparent", key: "apparentTemperature", label: copy.apparent, style: "dashed" },
          ]}
          selectedKey={selectedKey}
          title={copy.temperature}
          unit="°"
        />
        <PrecipitationChart copy={copy} items={window.items} selectedKey={selectedKey} />
        <LineChart
          copy={copy}
          id="forecast-wind-chart"
          items={window.items}
          keys={[
            { color: "wind", key: "windSpeed", label: copy.wind },
            { color: "gust", key: "windGusts", label: copy.gusts, style: "dashed" },
          ]}
          selectedKey={selectedKey}
          title={`${copy.wind} · ${copy.gusts}`}
          unit=" km/h"
        />
      </div>
    </section>
  );
}
