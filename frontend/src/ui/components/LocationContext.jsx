import { MapPin } from "lucide-react";

import { LocationChangeButton } from "./LocationChangeButton";

export function LocationContext({
  changeLabel = "Cambia",
  city,
  className = "",
  disabled = false,
  onChange,
  prefix = "",
}) {
  const label = city || "Udine";
  const classNames = ["mf-location-context", className].filter(Boolean).join(" ");

  return (
    <div className={classNames}>
      <MapPin aria-hidden="true" size={14} strokeWidth={2.35} />
      <span className="mf-location-context__text">
        {prefix ? <span>{prefix} </span> : null}
        <strong>{label}</strong>
      </span>
      {onChange ? (
        <LocationChangeButton
          className="mf-location-context__action"
          disabled={disabled}
          label={changeLabel}
          onClick={onChange}
        />
      ) : null}
    </div>
  );
}
