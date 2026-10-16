import { MapPin } from "lucide-react";
import { usePilotBackHandler } from "../../app/usePilotBackHandler";

export function BackgroundLocationDisclosure({ context = "settings", copy, onCancel, onContinue }) {
  usePilotBackHandler(onCancel);
  const isStartup = context === "startup";
  return (
    <div className={`mf-settings-disclosure${isStartup ? " mf-settings-disclosure--startup" : ""}`} role="presentation">
      <section
        aria-describedby="background-location-disclosure-body"
        aria-labelledby="background-location-disclosure-title"
        aria-modal="true"
        className="mf-settings-disclosure__card"
        role="dialog"
      >
        {isStartup ? (
          <div className="mf-settings-disclosure__heading">
            <span className="mf-settings-disclosure__icon">
              <MapPin aria-hidden="true" size={25} strokeWidth={2.2} />
            </span>
            <div className="mf-settings-disclosure__heading-copy">
              <span className="mf-settings-disclosure__eyebrow">{copy.eyebrow}</span>
              <h2 id="background-location-disclosure-title">{copy.title}</h2>
            </div>
          </div>
        ) : (
          <>
            <span className="mf-settings-disclosure__eyebrow">{copy.eyebrow}</span>
            <h2 id="background-location-disclosure-title">{copy.title}</h2>
          </>
        )}
        <p id="background-location-disclosure-body">{copy.body}</p>
        <div className="mf-settings-disclosure__actions">
          <button
            className="mf-settings-disclosure__cancel"
            onClick={onCancel}
            type="button"
          >
            {copy.cancel}
          </button>
          <button
            autoFocus
            className="mf-settings-disclosure__continue"
            onClick={onContinue}
            type="button"
          >
            {copy.continue}
          </button>
        </div>
      </section>
    </div>
  );
}
