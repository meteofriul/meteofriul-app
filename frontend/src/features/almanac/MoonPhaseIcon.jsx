import { useId } from "react";

const MOON_RADIUS = 45;
const MOON_CENTER = 50;
const TERMINATOR_STEPS = 24;
const MOON_TEXTURE_PATH = "/astronomy/moon-surface-nasa.webp";

function clampCycleProgress(value) {
  if (value === null || value === undefined || value === "") return null;
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return null;
  return Math.min(100, Math.max(0, numericValue));
}

function formatCoordinate(value) {
  return Number(value.toFixed(3));
}

function getMoonEdgeX(y) {
  return Math.sqrt(Math.max(0, (MOON_RADIUS ** 2) - (y ** 2)));
}

function buildIlluminatedPath(cycleProgress) {
  const phase = cycleProgress / 100;
  const waxing = phase <= 0.5;
  const phaseCosine = Math.cos(phase * Math.PI * 2);
  const points = [];

  for (let step = 0; step <= TERMINATOR_STEPS; step += 1) {
    const y = -MOON_RADIUS + ((MOON_RADIUS * 2 * step) / TERMINATOR_STEPS);
    const edgeX = getMoonEdgeX(y);
    const x = waxing ? edgeX : -phaseCosine * edgeX;
    points.push([MOON_CENTER + x, MOON_CENTER + y]);
  }

  for (let step = TERMINATOR_STEPS; step >= 0; step -= 1) {
    const y = -MOON_RADIUS + ((MOON_RADIUS * 2 * step) / TERMINATOR_STEPS);
    const edgeX = getMoonEdgeX(y);
    const x = waxing ? phaseCosine * edgeX : -edgeX;
    points.push([MOON_CENTER + x, MOON_CENTER + y]);
  }

  return points
    .map(([x, y], index) => `${index === 0 ? "M" : "L"} ${formatCoordinate(x)} ${formatCoordinate(y)}`)
    .join(" ") + " Z";
}

export function MoonPhaseIcon({ className = "", cycleProgress, decorative = false, label = "" }) {
  const generatedId = useId();
  const normalizedProgress = clampCycleProgress(cycleProgress);
  if (normalizedProgress === null) return null;

  const accessible = !decorative && Boolean(label);
  const classes = ["mf-moon-phase-icon", className].filter(Boolean).join(" ");
  const illuminatedPath = buildIlluminatedPath(normalizedProgress);
  const textureClipId = `mf-moon-texture-${generatedId.replaceAll(":", "")}`;

  return (
    <svg
      aria-hidden={accessible ? undefined : "true"}
      aria-label={accessible ? label : undefined}
      className={classes}
      data-cycle-progress={normalizedProgress}
      focusable="false"
      role={accessible ? "img" : undefined}
      viewBox="0 0 100 100"
    >
      <defs>
        <clipPath id={textureClipId}>
          <path d={illuminatedPath} />
        </clipPath>
      </defs>
      <circle className="mf-moon-phase-icon__shadow" cx="50" cy="50" r={MOON_RADIUS} />
      <path className="mf-moon-phase-icon__light" d={illuminatedPath} />
      <image
        className="mf-moon-phase-icon__surface"
        clipPath={`url(#${textureClipId})`}
        height="90"
        href={MOON_TEXTURE_PATH}
        preserveAspectRatio="xMidYMid slice"
        width="90"
        x="5"
        y="5"
      />
      <circle className="mf-moon-phase-icon__rim" cx="50" cy="50" r={MOON_RADIUS} />
    </svg>
  );
}
