export function AppBadge({ children, tone = "neutral" }) {
  return <span className={`mf-badge mf-badge--${tone}`}>{children}</span>;
}
