export function AppIconButton({ ariaLabel, className = "", icon: Icon, title, variant = "ghost", ...buttonProps }) {
  return (
    <button
      aria-label={ariaLabel}
      className={`mf-icon-button mf-icon-button--${variant} ${className}`.trim()}
      title={title || ariaLabel}
      type="button"
      {...buttonProps}
    >
      <Icon aria-hidden="true" size={20} strokeWidth={2.25} />
    </button>
  );
}
