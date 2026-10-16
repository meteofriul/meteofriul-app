export function AppCard({ as: Component = "section", children, className = "", variant = "default", ...props }) {
  return (
    <Component className={`mf-card mf-card--${variant} ${className}`.trim()} {...props}>
      {children}
    </Component>
  );
}
