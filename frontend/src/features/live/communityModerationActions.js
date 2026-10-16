export async function submitCommunityModerationFlag({
  onClose,
  onFlag,
  phenomenon,
  reason,
}) {
  const result = await onFlag(phenomenon, reason);
  if (result?.ok) onClose?.();
  return result;
}

export function hideCommunityModerationSources({
  onClose,
  onHideSources,
  phenomenon,
}) {
  onHideSources(phenomenon);
  onClose?.();
}
