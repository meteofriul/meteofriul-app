import { useEffect, useRef } from "react";
import { Languages } from "lucide-react";

const FOCUSABLE_SELECTOR = "button:not([disabled])";

export function PilotLanguageOnboarding({
  language = "it",
  onLanguageSelect,
}) {
  const dialogRef = useRef(null);
  const initialActionRef = useRef(null);
  const previousFocusRef = useRef(null);

  useEffect(() => {
    previousFocusRef.current = globalThis.document?.activeElement || null;
    const frameId = globalThis.requestAnimationFrame?.(() => {
      initialActionRef.current?.focus?.();
    });

    return () => {
      if (frameId != null) globalThis.cancelAnimationFrame?.(frameId);
      if (previousFocusRef.current?.isConnected) previousFocusRef.current.focus?.();
    };
  }, []);

  const handleDialogKeyDown = (event) => {
    if (event.key !== "Tab") return;

    const focusable = Array.from(dialogRef.current?.querySelectorAll?.(FOCUSABLE_SELECTOR) || []);
    if (!focusable.length) {
      event.preventDefault();
      dialogRef.current?.focus?.();
      return;
    }

    const first = focusable[0];
    const last = focusable.at(-1);
    const activeElement = globalThis.document?.activeElement;
    if (event.shiftKey && (activeElement === first || !dialogRef.current?.contains(activeElement))) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <div className="mf-web-onboarding mf-web-onboarding--language" role="presentation">
      <section
        aria-labelledby="mf-pilot-language-onboarding-title"
        aria-modal="true"
        className="mf-web-onboarding__card mf-pilot-language-onboarding"
        onKeyDown={handleDialogKeyDown}
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <div className="mf-pilot-language-onboarding__heading">
          <span className="mf-web-onboarding__icon">
            <Languages aria-hidden="true" size={26} strokeWidth={2.2} />
          </span>
          <div className="mf-pilot-language-onboarding__heading-copy">
            <p className="mf-web-onboarding__eyebrow">Benvenuto · Benvignût</p>
            <h2 id="mf-pilot-language-onboarding-title">Scegli la lingua</h2>
          </div>
        </div>
        <p className="mf-pilot-language-onboarding__description">
          Potrai cambiarla in qualsiasi momento dalle Impostazioni.
        </p>
        <div
          aria-label="Scegli la lingua dell’app"
          className="mf-pilot-language-onboarding__choices"
          role="group"
        >
          <button
            aria-pressed={language !== "fur"}
            className={`mf-pilot-language-onboarding__choice${language !== "fur" ? " is-active" : ""}`}
            onClick={() => onLanguageSelect?.("it")}
            ref={initialActionRef}
            type="button"
          >
            Italiano
          </button>
          <button
            aria-pressed={language === "fur"}
            className={`mf-pilot-language-onboarding__choice${language === "fur" ? " is-active" : ""}`}
            onClick={() => onLanguageSelect?.("fur")}
            type="button"
          >
            Furlan
          </button>
        </div>
      </section>
    </div>
  );
}
