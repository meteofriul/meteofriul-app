export function AppButton({
  children,
  className = "",
  disabled = false,
  icon: Icon,
  isLoading = false,
  type = "button",
  variant = "primary",
  ...buttonProps
}) {
  return (
    <button
      className={`mf-button mf-button--${variant} ${className}`.trim()}
      disabled={disabled || isLoading}
      type={type}
      {...buttonProps}
    >
      {Icon ? <Icon aria-hidden="true" size={18} strokeWidth={2.25} /> : null}
      <span>{isLoading ? "..." : children}</span>
    </button>
  );
}
