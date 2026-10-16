export function LocationChangeButton({
  className = "",
  disabled = false,
  label = "Cambia",
  onClick,
  tone = "surface",
}) {
  const classNames = [
    "mf-location-change",
    `mf-location-change--${tone}`,
    className,
  ].filter(Boolean).join(" ");

  return (
    <button
      aria-haspopup="dialog"
      className={classNames}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <span>{label}</span>
    </button>
  );
}
