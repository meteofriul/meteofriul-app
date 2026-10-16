import { useEffect, useRef } from "react";
import { BellRing, LocateFixed, MapPin, X } from "lucide-react";

const FOCUSABLE_SELECTOR = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

const COPY = {
  it: {
    close: "Chiudi configurazione iniziale",
    later: "Non ora",
    working: "Richiesta in corso…",
    location: {
      action: "Usa la mia posizione",
      body: "Usiamo la posizione solo durante questa richiesta per individuare la località e il Comune e mostrare dati più pertinenti. Non conserviamo una cronologia delle coordinate GPS. Puoi disattivare la posizione automatica in qualsiasi momento.",
      eyebrow: "1 di 2 · Posizione",
      failures: {
        permission_denied: "La posizione è bloccata. Apri i permessi del sito dal lucchetto del browser, consentila e riprova; in alternativa scegli il Comune.",
        stale_or_imprecise: "Il browser ha fornito una posizione troppo vecchia o imprecisa. Attiva la posizione precisa e riprova; in alternativa scegli il Comune.",
        timeout: "La posizione non ha risposto in tempo. Controlla che la localizzazione del telefono sia attiva e riprova; in alternativa scegli il Comune.",
        unavailable: "La posizione non è disponibile in questo momento. Puoi riprovare oppure scegliere il Comune.",
        unsupported: "Questo browser non mette a disposizione la posizione. Apri Meteo Friûl in Chrome o Safari oppure scegli il Comune.",
      },
      retry: "Riprova posizione",
      title: "Meteo vicino a te",
    },
    notifications: {
      action: "Autorizza notifiche",
      body: "Ricevi Allerte ufficiali e Avvisi meteo anche quando la Web App non è aperta. Puoi cambiare scelta in qualsiasi momento dalle Impostazioni.",
      checking: "Stiamo verificando se questo browser può ricevere le notifiche.",
      checkingAction: "Controllo in corso…",
      denied: "Le notifiche sono bloccate dal browser. Puoi riabilitarle dalle impostazioni del sito.",
      done: "Chiudi",
      error: "Non siamo riusciti a inizializzare le notifiche. Chiudi e controlla lo stato dettagliato in Impostazioni.",
      eyebrow: "2 di 2 · Notifiche",
      locationFallback: "Non siamo riusciti a rilevare la posizione. Puoi scegliere il Comune manualmente.",
      manualLocation: "Scegli il Comune",
      notConfigured: "Le notifiche Web non sono attive in questa fase. Per ricevere allerte e avvisi usa l'app Android Meteo Friûl.",
      serviceWorkerError: "Il componente notifiche del browser non si è attivato. Aggiorna la pagina e riprova.",
      title: "Ricevi le notifiche",
      unsupported: "Questo browser non supporta le notifiche web. Puoi continuare a consultare tutte le informazioni nell’app.",
      webEnrollmentBody: "Nel browser puoi consultare tutte le informazioni. Le notifiche sono disponibili nell'app Android Meteo Friûl.",
      webEnrollmentTitle: "Notifiche nell'app Android",
    },
  },
  fur: {
    close: "Siere la configurazion iniziâl",
    later: "No cumò",
    working: "Operazion in cors…",
    location: {
      action: "Dopre la mê posizion",
      body: "O doprìn la posizion dome dilunc di cheste richieste par individuâ la localitât e il Comun e mostrâ dâts plui pertinents. No conservìn une cronologjie des coordenadis GPS. Tu puedis disativâ la posizion automatiche cuant che tu vuelis.",
      eyebrow: "1 di 2 · Posizion",
      failures: {
        permission_denied: "La posizion e je blocade. Vierç i permès dal sît dal cjadenaç dal navigadôr, permetile e torne prove; in alternative sielç il Comun.",
        stale_or_imprecise: "Il navigadôr al à dât une posizion masse vecje o imprecise. Ative la posizion precise e torne prove; in alternative sielç il Comun.",
        timeout: "La posizion no à rispuindût in timp. Controle che la localizazion dal telefon e sedi ative e torne prove; in alternative sielç il Comun.",
        unavailable: "La posizion no je disponibile in chest moment. Tu puedis tornâ a provâ o sielzi il Comun.",
        unsupported: "Chest navigadôr nol met a disposizion la posizion. Vierç Meteo Friûl in Chrome o Safari, o sielç il Comun.",
      },
      retry: "Torne prove la posizion",
      title: "Meteo dongje di te",
    },
    notifications: {
      action: "Autorize lis notifichis",
      body: "Ricêf Alertis uficiâls e Avîs meteo ancje cuant che la Web App no je vierte. Tu puedis cambiâ sielte cuant che tu vuelis tes Impostazions.",
      checking: "O sin daûr a verificâ se chest navigadôr al pues ricevi lis notifichis.",
      checkingAction: "Control in cors…",
      denied: "Lis notifichis a son blocadis dal navigadôr. Tu puedis tornâ a ativâlis tes impostazions dal sît.",
      done: "Siere",
      error: "No sin rivâts a inizializâ lis notifichis. Siere e controle il stât in detai tes Impostazions.",
      eyebrow: "2 di 2 · Notifichis",
      locationFallback: "No sin rivâts a rilevâ la posizion. Tu puedis sielzi il Comun a man.",
      manualLocation: "Sielç il Comun",
      notConfigured: "Lis notifichis Web no son ativis in cheste fase. Par ricevi lis alertis e i avîs dopre la app Android Meteo Friûl.",
      serviceWorkerError: "Il component notifichis dal navigadôr no si è ativât. Inzorne la pagjine e torne prove.",
      title: "Ricêf lis notifichis",
      unsupported: "Chest navigadôr nol supuarte lis notifichis web. Tu puedis continuâ a consultâ dutis lis informazions te app.",
      webEnrollmentBody: "Tal navigadôr tu puedis consultâ dutis lis informazions. Lis notifichis a son disponibilis te app Android Meteo Friûl.",
      webEnrollmentTitle: "Notifichis te app Android",
    },
  },
};

function getNotificationFallback(copy, runtime) {
  if (runtime?.permission === "denied") return copy.denied;
  if (runtime?.reason === "web_enrollment_disabled") return copy.notConfigured;
  if (runtime?.reason === "not_configured") return copy.notConfigured;
  if (runtime?.status === "error") {
    return runtime?.errorCategory === "service_worker"
      ? copy.serviceWorkerError
      : copy.error;
  }
  return copy.unsupported;
}

function getLocationFallback(copy, result) {
  const reason = String(result?.reason || "").trim();
  const message = copy.failures?.[reason] || copy.failures?.unavailable;
  return {
    message,
    retryable: reason !== "unsupported",
  };
}

export function WebStartupOnboarding({
  busy = false,
  language = "it",
  locationResult,
  notificationRuntime,
  onClose,
  onLocationRequest,
  onLocationSkip,
  onManualLocation,
  onNotificationRequest,
  step = "location",
}) {
  const dialogRef = useRef(null);
  const closeButtonRef = useRef(null);
  const initialActionRef = useRef(null);
  const previousFocusRef = useRef(null);
  const copy = COPY[language === "fur" ? "fur" : "it"];
  const notificationRuntimeChecking = notificationRuntime?.status === "checking";
  const webEnrollmentDisabled = notificationRuntime?.reason === "web_enrollment_disabled";
  const notificationsAvailable = !notificationRuntimeChecking &&
    notificationRuntime?.readOnly !== true &&
    notificationRuntime?.permission !== "denied";
  const notificationCopy = copy.notifications;
  const locationFallback = locationResult?.ok === false
    ? getLocationFallback(copy.location, locationResult)
    : null;

  useEffect(() => {
    previousFocusRef.current = globalThis.document?.activeElement || null;
    const frameId = globalThis.requestAnimationFrame?.(() => {
      const focusTarget = initialActionRef.current?.disabled
        ? closeButtonRef.current
        : initialActionRef.current;
      focusTarget?.focus?.();
    });

    return () => {
      if (frameId != null) globalThis.cancelAnimationFrame?.(frameId);
      if (previousFocusRef.current?.isConnected) previousFocusRef.current.focus?.();
    };
  }, []);

  useEffect(() => {
    if (!busy) {
      const focusTarget = initialActionRef.current?.disabled
        ? closeButtonRef.current
        : initialActionRef.current;
      focusTarget?.focus?.();
    }
  }, [busy, notificationRuntimeChecking, step]);

  const handleDialogKeyDown = (event) => {
    if (event.key === "Escape" && !busy) {
      event.preventDefault();
      onClose?.("dismissed");
      return;
    }
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
    <div className="mf-web-onboarding" role="presentation">
      <section
        aria-labelledby="mf-web-onboarding-title"
        aria-modal="true"
        aria-busy={busy || notificationRuntimeChecking}
        className="mf-web-onboarding__card"
        onKeyDown={handleDialogKeyDown}
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <button
          aria-label={copy.close}
          className="mf-web-onboarding__close"
          disabled={busy}
          onClick={() => onClose?.("dismissed")}
          ref={closeButtonRef}
          type="button"
        >
          <X aria-hidden="true" size={19} strokeWidth={2.4} />
        </button>

        {step === "location" ? (
          <>
            <span className="mf-web-onboarding__icon">
              <LocateFixed aria-hidden="true" size={25} strokeWidth={2.2} />
            </span>
            <p className="mf-web-onboarding__eyebrow">{copy.location.eyebrow}</p>
            <h2 id="mf-web-onboarding-title">{copy.location.title}</h2>
            <p>{copy.location.body}</p>
            <div className="mf-web-onboarding__actions">
              <button
                className="mf-button mf-button--primary"
                data-initial-focus="true"
                disabled={busy}
                onClick={onLocationRequest}
                ref={initialActionRef}
                type="button"
              >
                <LocateFixed aria-hidden="true" size={17} />
                {copy.location.action}
              </button>
              <button
                className="mf-button mf-button--ghost"
                disabled={busy}
                onClick={onLocationSkip}
                type="button"
              >
                {copy.later}
              </button>
            </div>
          </>
        ) : (
          <>
            <span className="mf-web-onboarding__icon">
              <BellRing aria-hidden="true" size={25} strokeWidth={2.2} />
            </span>
            <p className="mf-web-onboarding__eyebrow">{notificationCopy.eyebrow}</p>
            <h2 id="mf-web-onboarding-title">
              {webEnrollmentDisabled
                ? notificationCopy.webEnrollmentTitle
                : notificationCopy.title}
            </h2>
            <p>
              {webEnrollmentDisabled
                ? notificationCopy.webEnrollmentBody
                : notificationCopy.body}
            </p>
            {locationFallback ? (
              <div className="mf-web-onboarding__fallback">
                <p>{locationFallback.message}</p>
                <div className="mf-web-onboarding__location-actions">
                  {locationFallback.retryable ? (
                    <button
                      className="mf-web-onboarding__manual"
                      disabled={busy}
                      onClick={onLocationRequest}
                      type="button"
                    >
                      <LocateFixed aria-hidden="true" size={16} />
                      {copy.location.retry}
                    </button>
                  ) : null}
                  <button
                    className="mf-web-onboarding__manual"
                    disabled={busy}
                    onClick={onManualLocation}
                    type="button"
                  >
                    <MapPin aria-hidden="true" size={16} />
                    {notificationCopy.manualLocation}
                  </button>
                </div>
              </div>
            ) : null}
            {notificationRuntimeChecking ? (
              <p aria-live="polite" className="mf-web-onboarding__notice" role="status">
                {notificationCopy.checking}
              </p>
            ) : !notificationsAvailable ? (
              <p className="mf-web-onboarding__notice">
                {getNotificationFallback(notificationCopy, notificationRuntime)}
              </p>
            ) : null}
            <div
              className={`mf-web-onboarding__actions${
                !notificationRuntimeChecking && !notificationsAvailable
                  ? " mf-web-onboarding__actions--centered"
                  : ""
              }`}
            >
              {notificationRuntimeChecking ? (
                <button
                  aria-busy="true"
                  className="mf-button mf-button--primary"
                  disabled
                  ref={initialActionRef}
                  type="button"
                >
                  {notificationCopy.checkingAction}
                </button>
              ) : notificationsAvailable ? (
                <button
                  className="mf-button mf-button--primary"
                  data-initial-focus="true"
                  disabled={busy}
                  onClick={onNotificationRequest}
                  ref={initialActionRef}
                  type="button"
                >
                  <BellRing aria-hidden="true" size={17} />
                  {notificationCopy.action}
                </button>
              ) : (
                <button
                  className="mf-button mf-button--primary"
                  data-initial-focus="true"
                  disabled={busy}
                  onClick={() => onClose?.("completed")}
                  ref={initialActionRef}
                  type="button"
                >
                  {notificationCopy.done}
                </button>
              )}
              {!notificationRuntimeChecking && notificationsAvailable ? (
                <button
                  className="mf-button mf-button--ghost"
                  disabled={busy}
                  onClick={() => onClose?.("dismissed")}
                  type="button"
                >
                  {copy.later}
                </button>
              ) : null}
            </div>
          </>
        )}
        {busy ? (
          <p aria-live="polite" className="mf-web-onboarding__progress" role="status">
            {copy.working}
          </p>
        ) : null}
      </section>
    </div>
  );
}
