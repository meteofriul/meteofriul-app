import { AlertTriangle } from "lucide-react";

import { FVG_PROVINCE_PATHS, FVG_REGION_PATH } from "./fvgMapGeometry";

const MAP_SIZE = 346;

function toMapUnit(value) {
  return (value / 100) * MAP_SIZE;
}

function WeatherGlyph({ type, x, y }) {
  const cx = toMapUnit(x);
  const cy = toMapUnit(y);
  const showSun = type !== "fog" && type !== "snow";
  const showCloud = type === "partly" || type === "storm" || type === "rain" || type === "snow";

  return (
    <g className={`mf-bulletin-weather-glyph mf-bulletin-weather-glyph--${type}`} transform={`translate(${cx} ${cy}) scale(0.9)`}>
      {showSun ? <circle className="mf-bulletin-weather-glyph__glow" cx="0" cy="0" r="22" /> : null}
      {showSun ? <circle className="mf-bulletin-weather-glyph__sun" cx="-3" cy="-4" r="13" /> : null}
      {showCloud ? (
        <g className="mf-bulletin-weather-glyph__cloud" transform="translate(-11 1)">
          <ellipse cx="6" cy="9" rx="11" ry="7" />
          <ellipse cx="18" cy="8" rx="13" ry="8" />
          <ellipse cx="29" cy="11" rx="10" ry="6" />
          <rect height="10" rx="5" width="32" x="4" y="8" />
        </g>
      ) : null}
      {type === "storm" ? (
        <path className="mf-bulletin-weather-glyph__storm" d="M 9 18 L 2 34 L 12 27 L 7 42 L 21 22 L 12 26 Z" />
      ) : null}
      {type === "rain" ? (
        <g className="mf-bulletin-weather-glyph__rain">
          <path d="M -6 26 C -10 33 -5 37 0 33 C 3 30 0 26 -3 22 Z" />
          <path d="M 12 27 C 8 34 13 38 18 34 C 21 31 18 27 15 23 Z" />
        </g>
      ) : null}
      {type === "snow" ? (
        <g className="mf-bulletin-weather-glyph__snow">
          <path d="M -8 -8 L 8 8 M 8 -8 L -8 8 M 0 -12 L 0 12 M -12 0 L 12 0" />
          <circle cx="0" cy="0" r="13" />
        </g>
      ) : null}
      {type === "fog" ? (
        <g className="mf-bulletin-weather-glyph__fog">
          <path d="M -24 -7 H 24 M -18 3 H 20 M -24 13 H 16" />
        </g>
      ) : null}
    </g>
  );
}

function MapBadge({ id, tone = "cool", x, y, value }) {
  const visualPosition = {
    "quota-1000": { x: 28, y: 28 },
    "quota-2000": { x: 34, y: 8 },
  }[id] || { x, y };
  const cx = toMapUnit(visualPosition.x);
  const cy = toMapUnit(visualPosition.y);
  const width = Math.max(60, value.length * 8.4);

  return (
    <g className={`mf-bulletin-map-badge mf-bulletin-map-badge--${tone}`} transform={`translate(${cx} ${cy})`}>
      <rect height="20" rx="5" width={width} x={-width / 2} y="-10" />
      <text dominantBaseline="central" textAnchor="middle">
        {value}
      </text>
    </g>
  );
}

function BaseMap({ caption }) {
  return (
    <svg aria-hidden="true" className="mf-bulletin-native-map" viewBox="0 0 346 346">
      <defs>
        <linearGradient id="mf-bulletin-sea" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#bde7f4" />
          <stop offset="1" stopColor="#6abbd1" />
        </linearGradient>
        <linearGradient id="mf-bulletin-land" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#dcefd6" />
          <stop offset="0.58" stopColor="#eef5df" />
          <stop offset="1" stopColor="#d7eacb" />
        </linearGradient>
        <linearGradient id="mf-bulletin-mountains" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#9b9385" />
          <stop offset="1" stopColor="#d2cbb8" />
        </linearGradient>
        <filter id="mf-bulletin-map-shadow" x="-10%" y="-10%" width="120%" height="120%">
          <feDropShadow dx="0" dy="6" floodColor="#123a4f" floodOpacity="0.22" stdDeviation="5" />
        </filter>
        <clipPath id="mf-bulletin-region-clip">
          <path d={FVG_REGION_PATH} />
        </clipPath>
      </defs>

      <rect className="mf-bulletin-map-sea" height="346" width="346" />
      <path className="mf-bulletin-map-water" d="M 0 254 C 42 242 72 240 110 252 C 155 268 192 260 226 247 C 264 232 306 233 346 246 L 346 346 L 0 346 Z" />
      <path className="mf-bulletin-map-land-shadow" d={FVG_REGION_PATH} />

      <g clipPath="url(#mf-bulletin-region-clip)">
        <path className="mf-bulletin-map-land" d={FVG_REGION_PATH} />
        <path className="mf-bulletin-map-mountains" d="M 28 70 C 79 20 152 20 210 44 C 242 57 275 69 293 103 L 284 148 C 232 134 190 134 149 158 C 102 187 61 171 31 138 Z" />
        <path className="mf-bulletin-map-plain" d="M 35 154 C 86 174 129 171 171 154 C 218 136 251 147 286 178 L 282 257 C 240 276 196 286 146 273 C 92 259 54 233 35 199 Z" />
        <path className="mf-bulletin-map-lagoon" d="M 132 270 C 167 261 190 265 215 280 C 244 297 276 296 318 278 L 327 320 L 128 322 Z" />
        <g className="mf-bulletin-map-rivers">
          <path d="M 116 46 C 126 88 124 125 139 164 C 150 194 147 226 141 263" />
          <path d="M 187 44 C 177 83 181 121 198 154 C 215 188 218 228 210 277" />
          <path d="M 246 82 C 232 112 228 136 238 160 C 249 187 246 218 235 256" />
          <path d="M 62 110 C 88 132 112 149 136 176 C 157 200 185 215 219 222" />
        </g>
      </g>
      <g className="mf-bulletin-map-provinces">
        {FVG_PROVINCE_PATHS.map((province) => (
          <path key={province.id} aria-label={province.label} d={province.d} />
        ))}
      </g>
      <path className="mf-bulletin-map-border" d={FVG_REGION_PATH} />

      <g className="mf-bulletin-map-labels">
        <text className="mf-bulletin-map-label--area" x="55" y="68">Carnia</text>
        <text className="mf-bulletin-map-label--area" x="292" y="100">Tarvisiano</text>
        <text className="mf-bulletin-map-label--province" x="105" y="182">PN</text>
        <text className="mf-bulletin-map-label--province" x="183" y="168">UD</text>
        <text className="mf-bulletin-map-label--province" x="286" y="200">GO</text>
        <text className="mf-bulletin-map-label--province" x="312" y="307">TS</text>
        <text className="mf-bulletin-map-label--area" x="190" y="318">Laguna</text>
      </g>
      <text className="mf-bulletin-map-signature" x="18" y="328">
        {caption}
      </text>
    </svg>
  );
}

export function BulletinMap({ copy, day, showOverlay = true }) {
  const points = Array.isArray(day.mapPoints) ? day.mapPoints : [];
  const badges = Array.isArray(day.mapBadges) ? day.mapBadges : [];
  const hasOverlay = showOverlay && points.length > 0;
  const isPendingBulletin = day?.source === "pending_official";
  const shouldShowWarning = !hasOverlay && !isPendingBulletin;

  return (
    <figure className="mf-bulletin-map-frame">
      <div aria-label={day.mapAlt} className="mf-bulletin-native-map-shell" role="img">
        <BaseMap caption={copy.mapCaption} />
        {hasOverlay ? (
          <svg aria-hidden="true" className="mf-bulletin-native-overlay" viewBox="0 0 346 346">
            {badges.map((badge) => (
              <MapBadge key={badge.id} {...badge} />
            ))}
            {points.map((point) => (
              <WeatherGlyph key={point.id} {...point} />
            ))}
          </svg>
        ) : null}
        {shouldShowWarning ? (
          <div
            aria-live="polite"
            className="mf-bulletin-map-warning"
            role="status"
          >
            <AlertTriangle aria-hidden="true" size={18} strokeWidth={2.35} />
            <strong>{copy.mapLayerUnavailableTitle}</strong>
            {copy.mapLayerUnavailableText ? <span>{copy.mapLayerUnavailableText}</span> : null}
          </div>
        ) : null}
      </div>
    </figure>
  );
}
