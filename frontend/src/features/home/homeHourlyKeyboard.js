export function getHourlyScrollTarget(key, { scrollLeft, scrollWidth, clientWidth, slotWidth = 64 }) {
  const end = Math.max(0, scrollWidth - clientWidth);

  if (key === "Home") return 0;
  if (key === "End") return end;
  if (key === "ArrowLeft") return Math.max(0, scrollLeft - slotWidth);
  if (key === "ArrowRight") return Math.min(end, scrollLeft + slotWidth);

  return null;
}
