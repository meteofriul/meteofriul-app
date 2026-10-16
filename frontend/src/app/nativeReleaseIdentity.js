export const UNKNOWN_NATIVE_RELEASE_IDENTITY = "unknown";

function normalizeIdentityPart(value) {
  return String(value || "").trim();
}

export function getNativeReleaseIdentity(info = {}) {
  const version = normalizeIdentityPart(info?.version);
  const build = normalizeIdentityPart(info?.build);

  if (version && build) return `${version}+${build}`;
  return version || UNKNOWN_NATIVE_RELEASE_IDENTITY;
}

export function isNativeReleaseIdentityKnown(value) {
  const normalized = normalizeIdentityPart(value);
  return Boolean(
    normalized
    && normalized.toLowerCase() !== UNKNOWN_NATIVE_RELEASE_IDENTITY,
  );
}
