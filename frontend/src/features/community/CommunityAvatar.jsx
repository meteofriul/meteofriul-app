import { useId } from "react";

import {
  buildCommunityIdentity,
  buildPublicCommunityIdentitySnapshot,
  getCommunityIdentityPalette,
  getCommunityIdentitySubject,
  normalizePublicCommunityIdentitySnapshot,
} from "./communityIdentity";
import "./communityAvatar.css";

const GRADIENT_COORDINATES = {
  45: { x1: "0%", x2: "100%", y1: "100%", y2: "0%" },
  90: { x1: "0%", x2: "100%", y1: "50%", y2: "50%" },
  135: { x1: "0%", x2: "100%", y1: "0%", y2: "100%" },
};

const VARIANT_ROTATIONS = [-4, 0, 4, -2];

function AvatarPattern({ patternId }) {
  if (patternId === "halo") {
    return (
      <>
        <circle className="mf-community-avatar__pattern" cx="24" cy="24" r="15" />
        <circle className="mf-community-avatar__pattern" cx="24" cy="24" r="9" />
      </>
    );
  }

  if (patternId === "split") {
    return <path className="mf-community-avatar__pattern-fill" d="M2 35 35 2h15v48H2Z" />;
  }

  if (patternId === "orbit") {
    return (
      <>
        <ellipse
          className="mf-community-avatar__pattern"
          cx="24"
          cy="24"
          rx="20"
          ry="9"
          transform="rotate(-28 24 24)"
        />
        <circle className="mf-community-avatar__pattern-dot" cx="39" cy="12" r="2" />
      </>
    );
  }

  return <path className="mf-community-avatar__pattern-fill" d="M-2 40 40-2h13L9 52H-2Z" />;
}

function AvatarGlyph({ glyph }) {
  switch (glyph) {
    case "frog":
      return (
        <>
          <circle cx="7" cy="7" r="2.2" /><circle cx="17" cy="7" r="2.2" />
          <path d="M5 10c0 6 2.5 9 7 9s7-3 7-9c-2.2 1.2-4.5 1.8-7 1.8S7.2 11.2 5 10Z" />
          <path className="mf-community-avatar__accent" d="M9 15c1.8 1.2 4.2 1.2 6 0" />
        </>
      );
    case "bear":
      return (
        <>
          <circle cx="6.2" cy="6.5" r="2.8" /><circle cx="17.8" cy="6.5" r="2.8" />
          <path d="M5 10c0-4 3-6 7-6s7 2 7 6v4c0 4-3 6-7 6s-7-2-7-6Z" />
          <path d="M9 14c1.5-1.3 4.5-1.3 6 0-1 2.4-5 2.4-6 0Z" />
          <circle className="mf-community-avatar__accent-fill" cx="15.8" cy="9.5" r="1" />
        </>
      );
    case "eagle":
      return (
        <>
          <path d="M3 15c4-1 5-5 7-9 1 3 4 4 8 4l3 2-4 2c-1 4-4 6-8 6 1.2-2 1.5-4 .8-6-2.2 1.4-4.5 1.7-6.8 1Z" />
          <path className="mf-community-avatar__accent" d="m18 10 3 2-4 2" />
          <circle className="mf-community-avatar__accent-fill" cx="16" cy="10.8" r=".8" />
        </>
      );
    case "owl":
      return (
        <>
          <path d="m5 5 4 2a8 8 0 0 1 6 0l4-2v9a7 7 0 0 1-14 0Z" />
          <circle cx="9" cy="12" r="2.3" /><circle cx="15" cy="12" r="2.3" />
          <path className="mf-community-avatar__accent" d="m10.5 16 1.5 1.5 1.5-1.5" />
        </>
      );
    case "fox":
    case "wolf":
      return (
        <>
          <path d="m4 5 5 3a9 9 0 0 1 6 0l5-3-2 10c-.8 3.2-3 5-6 5s-5.2-1.8-6-5Z" />
          <path d="m9 15 3 2 3-2" />
          <circle className="mf-community-avatar__accent-fill" cx="15.2" cy="11.5" r=".9" />
        </>
      );
    case "mouse":
      return (
        <>
          <circle cx="7" cy="8" r="3" /><circle cx="17" cy="8" r="3" />
          <path d="M6 11c0-3.5 2.5-6 6-6s6 2.5 6 6v3c0 3.5-2.5 6-6 6s-6-2.5-6-6Z" />
          <path className="mf-community-avatar__accent" d="M12 14v3m-2 0h4" />
        </>
      );
    case "squirrel":
      return (
        <>
          <path d="M8 18c-3-4-2-9 2-11 3-1.5 6 0 6.5 2.5C20 8 21 11 19 14c-1.5 2.3-4 2.5-6 1" />
          <path d="M8 18c1.5-4 4.5-6 8-6" />
          <circle className="mf-community-avatar__accent-fill" cx="12.5" cy="9" r=".9" />
        </>
      );
    case "snake":
      return (
        <>
          <path d="M6 6c8-3 13 0 11 4-2 4-10 1-10 6 0 3 5 3 9 1" />
          <path className="mf-community-avatar__accent" d="m16 17 4-1-2.5 3" />
        </>
      );
    case "star":
      return <path d="m12 3 2.7 5.7L21 9.5l-4.6 4.4 1.2 6.1-5.6-3-5.6 3 1.2-6.1L3 9.5l6.3-.8Z" />;
    case "dog":
      return (
        <>
          <path d="M6 7 3 5v8l3 2c1 4 3.5 5 6 5s5-1 6-5l3-2V5l-3 2c-3-2-9-2-12 0Z" />
          <path d="M9 15c2 1.5 4 1.5 6 0" />
          <circle className="mf-community-avatar__accent-fill" cx="15.5" cy="11" r=".9" />
        </>
      );
    case "cat":
      return (
        <>
          <path d="m5 4 5 3h4l5-3-1 11c-.4 3-2.7 5-6 5s-5.6-2-6-5Z" />
          <path d="M4 14h5m6 0h5M5 17l4-1m6 0 4 1" />
          <circle className="mf-community-avatar__accent-fill" cx="15" cy="11" r=".9" />
        </>
      );
    case "horse":
      return (
        <>
          <path d="m6 20 1-11 5-5 6 3-2 4 1 8h-5l-2-5-1 6Z" />
          <path className="mf-community-avatar__accent" d="m12 4 1 6 3 1" />
          <circle className="mf-community-avatar__accent-fill" cx="15" cy="8" r=".8" />
        </>
      );
    case "goat":
      return (
        <>
          <path d="M8 8C4 6 4 2 6 2c3 0 4 3 4 6m6 0c4-2 4-6 2-6-3 0-4 3-4 6" />
          <path d="M7 9c0 7 1.5 11 5 11s5-4 5-11c-3-2-7-2-10 0Z" />
          <path className="mf-community-avatar__accent" d="m10 14 2 2 2-2" />
        </>
      );
    case "flower":
      return (
        <>
          <circle cx="12" cy="7" r="3" /><circle cx="17" cy="11" r="3" />
          <circle cx="15" cy="17" r="3" /><circle cx="9" cy="17" r="3" />
          <circle cx="7" cy="11" r="3" /><circle className="mf-community-avatar__accent-fill" cx="12" cy="12" r="2.2" />
        </>
      );
    case "leaf":
      return (
        <>
          <path d="M4 18C4 9 10 4 20 4c0 10-5 16-14 16" />
          <path className="mf-community-avatar__accent" d="M6 18 17 7M10 14l-1-5m5 2 5-1" />
        </>
      );
    case "tree":
      return (
        <>
          <path d="M12 3 5 12h4l-4 5h14l-4-5h4Z" />
          <path className="mf-community-avatar__accent" d="M12 17v4" />
        </>
      );
    case "cherry":
      return (
        <>
          <path d="M12 6c1 4-1 7-4 9m4-9c2 2 4 5 4 9m-4-9c2-2 4-3 7-2" />
          <circle cx="7" cy="17" r="3" /><circle cx="17" cy="17" r="3" />
          <path className="mf-community-avatar__accent" d="M14 5c2-2 4-2 6-1" />
        </>
      );
    case "bell":
      return (
        <>
          <path d="M6 16h12l-2-3V9a4 4 0 0 0-8 0v4Z" />
          <path className="mf-community-avatar__accent" d="M10 19h4M12 3v2" />
        </>
      );
    case "stone":
      return <path d="m4 16 3-8 6-3 6 5 1 7-5 3H8Z" />;
    case "castle":
      return (
        <>
          <path d="M4 20V7h4v3h3V7h3v3h3V7h3v13Z" />
          <path className="mf-community-avatar__accent" d="M10 20v-5h4v5" />
        </>
      );
    case "hat":
      return (
        <>
          <path d="M6 15 9 6h6l3 9" /><path d="M3 16c5 3 13 3 18 0" />
          <path className="mf-community-avatar__accent" d="M7 13h10" />
        </>
      );
    case "cup":
      return (
        <>
          <path d="M5 6h12v12H5Z" /><path d="M17 9h2a3 3 0 0 1 0 6h-2" />
          <path className="mf-community-avatar__accent" d="M8 3v2m4-2v2" />
        </>
      );
    case "deer":
      return (
        <>
          <path d="M8 9 5 6V3m11 6 3-3V3M5 6H3m16 0h2" />
          <path d="M7 9c0 7 1.5 11 5 11s5-4 5-11c-3-2-7-2-10 0Z" />
          <circle className="mf-community-avatar__accent-fill" cx="15" cy="12" r=".8" />
        </>
      );
    case "badger":
      return (
        <>
          <path d="M5 11c1-5 4-7 7-7s6 2 7 7v4c-2 4-5 5-7 5s-5-1-7-5Z" />
          <path d="m8 7 2 9m6-9-2 9" />
          <path className="mf-community-avatar__accent" d="M10 16h4" />
        </>
      );
    case "rooster":
      return (
        <>
          <path d="M7 19c-2-6 0-11 5-12l-1-3 3 2 2-3 1 4c3 2 3 7 1 10-2 3-7 4-11 2Z" />
          <path className="mf-community-avatar__accent" d="m18 9 4 2-4 2M9 19l-1 3m5-3 1 3" />
        </>
      );
    case "shoe":
      return (
        <>
          <path d="M4 15c5 0 7-3 7-9h4c0 5 2 7 5 9v4H4Z" />
          <path className="mf-community-avatar__accent" d="M11 10h5m-6 3h7" />
        </>
      );
    case "cart":
      return (
        <>
          <path d="M4 6h14l-2 8H7Z" /><path d="m18 7 3-3" />
          <circle cx="8" cy="18" r="3" /><circle cx="17" cy="18" r="3" />
          <path className="mf-community-avatar__accent" d="M8 15v6m-3-3h6" />
        </>
      );
    case "spoon":
      return (
        <>
          <ellipse cx="9" cy="7" rx="4" ry="5" /><path d="m11 11 8 9" />
          <path className="mf-community-avatar__accent" d="m16 17 3 3" />
        </>
      );
    case "pan":
      return (
        <>
          <circle cx="9" cy="14" r="6" /><path d="m14 10 7-6" />
          <path className="mf-community-avatar__accent" d="m17 7 4-3" />
        </>
      );
    case "cork":
      return (
        <>
          <path d="M8 4h8l1 15H7Z" /><path d="M6 4h12" />
          <path className="mf-community-avatar__accent" d="M9 9h6m-6 5h6" />
        </>
      );
    case "key":
    default:
      return (
        <>
          <circle cx="8" cy="8" r="4" /><path d="m11 11 9 9m-5-5 3-3m-1 5 3-3" />
          <circle className="mf-community-avatar__accent" cx="8" cy="8" r="1.5" />
        </>
      );
  }
}

function resolveSnapshot(identity, snapshot) {
  const normalizedSnapshot = normalizePublicCommunityIdentitySnapshot(snapshot);
  if (normalizedSnapshot) return normalizedSnapshot;

  const builtSnapshot = buildPublicCommunityIdentitySnapshot(identity);
  if (builtSnapshot) return builtSnapshot;

  return buildPublicCommunityIdentitySnapshot(buildCommunityIdentity());
}

export function CommunityAvatar({
  className = "",
  decorative = false,
  glyphScale = 1,
  identity,
  label,
  size = 40,
  snapshot,
}) {
  const avatarSnapshot = resolveSnapshot(identity, snapshot);
  const subject = getCommunityIdentitySubject(avatarSnapshot.subjectId);
  const palette = getCommunityIdentityPalette(avatarSnapshot.avatar.paletteId);
  const coordinates = GRADIENT_COORDINATES[avatarSnapshot.avatar.angle]
    ?? GRADIENT_COORDINATES[135];
  const generatedId = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const gradientId = `mf-community-avatar-gradient-${generatedId}`;
  const clipId = `mf-community-avatar-clip-${generatedId}`;
  const dimension = typeof size === "number" ? `${Math.max(20, size)}px` : size;
  const parsedGlyphScale = Number(glyphScale);
  const normalizedGlyphScale = Number.isFinite(parsedGlyphScale)
    ? Math.min(1.4, Math.max(0.8, parsedGlyphScale))
    : 1;
  const accessibleLabel = label
    || `Avatar community anonimo: ${avatarSnapshot.alias}`;
  const classes = ["mf-community-avatar", className].filter(Boolean).join(" ");

  return (
    <span
      aria-hidden={decorative || undefined}
      aria-label={decorative ? undefined : accessibleLabel}
      className={classes}
      data-kind={subject.kind}
      data-palette={palette.id}
      data-pattern={avatarSnapshot.avatar.patternId}
      data-subject={subject.id}
      role={decorative ? undefined : "img"}
      style={{
        "--mf-community-avatar-accent": palette.accent,
        "--mf-community-avatar-glow": `${palette.end}66`,
        height: dimension,
        width: dimension,
      }}
    >
      <svg aria-hidden="true" focusable="false" viewBox="0 0 48 48">
        <defs>
          <linearGradient id={gradientId} {...coordinates}>
            <stop offset="0%" stopColor={palette.start} />
            <stop offset="100%" stopColor={palette.end} />
          </linearGradient>
          <clipPath id={clipId}>
            <circle cx="24" cy="24" r="22" />
          </clipPath>
        </defs>
        <circle className="mf-community-avatar__background" cx="24" cy="24" r="22" fill={`url(#${gradientId})`} />
        <g clipPath={`url(#${clipId})`}>
          <AvatarPattern patternId={avatarSnapshot.avatar.patternId} />
        </g>
        <g
          className="mf-community-avatar__glyph"
          transform={`translate(12 12) rotate(${VARIANT_ROTATIONS[avatarSnapshot.avatar.variant]} 12 12)`}
        >
          {normalizedGlyphScale === 1 ? (
            <AvatarGlyph glyph={subject.glyph} />
          ) : (
            <g transform={`translate(12 12) scale(${normalizedGlyphScale}) translate(-12 -12)`}>
              <AvatarGlyph glyph={subject.glyph} />
            </g>
          )}
        </g>
        <circle className="mf-community-avatar__rim" cx="24" cy="24" r="21.25" />
      </svg>
    </span>
  );
}
