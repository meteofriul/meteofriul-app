import { BellRing, X } from "lucide-react";

const COPY = {
  it: {
    close: "Chiudi notifica",
    defaultBody: "È disponibile un nuovo aggiornamento meteo.",
    defaultTitle: "Meteo Friûl",
    open: "Apri Bollettino",
  },
  fur: {
    close: "Siere la notifiche",
    defaultBody: "Al è disponibil un gnûf inzornament meteo.",
    defaultTitle: "Meteo Friûl",
    open: "Vierç il Boletin",
  },
};

export function WebPushForegroundBanner({
  language = "it",
  message,
  onClose,
  onOpenBulletin,
}) {
  if (!message) return null;

  const copy = COPY[language === "fur" ? "fur" : "it"];
  const title = String(message.title || "").trim() || copy.defaultTitle;
  const body = String(message.body || "").trim() || copy.defaultBody;

  return (
    <section
      aria-describedby="mf-web-push-banner-body"
      aria-labelledby="mf-web-push-banner-title"
      aria-live="polite"
      className="mf-web-push-banner"
      role="region"
    >
      <span aria-hidden="true" className="mf-web-push-banner__icon">
        <BellRing size={20} strokeWidth={2.3} />
      </span>
      <div className="mf-web-push-banner__content">
        <strong id="mf-web-push-banner-title">{title}</strong>
        <p id="mf-web-push-banner-body">{body}</p>
        <button
          className="mf-web-push-banner__open"
          onClick={onOpenBulletin}
          type="button"
        >
          {copy.open}
        </button>
      </div>
      <button
        aria-label={copy.close}
        className="mf-web-push-banner__close"
        onClick={onClose}
        type="button"
      >
        <X aria-hidden="true" size={18} strokeWidth={2.4} />
      </button>
    </section>
  );
}
