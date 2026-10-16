import { ChevronRight, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { registerPilotBackHandler } from "../../services/pilotBackNavigation";

const COPY = {
  it: {
    close: "Chiudi",
    details: "Dettagli",
    label: "Dati ambientali",
    open: "Apri i dettagli",
  },
  fur: {
    close: "Siere",
    details: "Detais",
    label: "Dâts ambientâi",
    open: "Vierç i detais",
  },
};

function EnvironmentTile({ active, controls, item, onOpen, openLabel }) {
  const Icon = item.icon;

  return (
    <button
      aria-label={`${openLabel}: ${item.title}`}
      aria-controls={controls}
      aria-expanded={active}
      aria-haspopup="dialog"
      className={`mf-weather-environment-tile mf-weather-environment-tile--${item.tone}`}
      data-status={item.status || undefined}
      data-uv-level={item.tone === "uv" ? item.visualTone : undefined}
      onClick={(event) => onOpen(item.id, event.currentTarget)}
      type="button"
    >
      <div className="mf-weather-environment-tile__header">
        <span className="mf-weather-environment-tile__icon"><Icon aria-hidden="true" size={20} /></span>
        <strong>{item.title}</strong>
        <ChevronRight aria-hidden="true" size={17} />
      </div>
      <div className="mf-weather-environment-tile__body">{item.summary}</div>
    </button>
  );
}

export function WeatherEnvironmentGrid({ items, language = "it" }) {
  const copy = COPY[language === "fur" ? "fur" : "it"];
  const [selectedId, setSelectedId] = useState(null);
  const dialogRef = useRef(null);
  const openerRef = useRef(null);
  const titleId = `${useId().replace(/:/gu, "")}-environment-title`;
  const dialogId = `${titleId}-dialog`;
  const selected = items.find((item) => item.id === selectedId) || null;

  useEffect(() => {
    if (!selectedId) return undefined;

    const dialog = dialogRef.current;
    if (!dialog) return undefined;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const unregisterBack = registerPilotBackHandler(() => setSelectedId(null), {
      isActive: () => dialog.open === true || dialog.hasAttribute("open"),
    });

    return () => {
      unregisterBack();
      document.body.style.overflow = previousOverflow;
      if (dialog.open && typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
      openerRef.current?.focus();
    };
  }, [selectedId]);

  const close = () => setSelectedId(null);
  const open = (id, opener) => {
    openerRef.current = opener;
    setSelectedId(id);
  };
  const SelectedIcon = selected?.icon;

  return (
    <section aria-label={copy.label} className="mf-weather-environment mf-weather-environment-grid">
      {items.map((item) => (
        <EnvironmentTile
          active={selectedId === item.id}
          controls={dialogId}
          item={item}
          key={item.id}
          onOpen={open}
          openLabel={copy.open}
        />
      ))}
      {selected ? (
        <dialog
          aria-labelledby={titleId}
          className={`mf-weather-environment-sheet mf-weather-environment-sheet--${selected.tone}`}
          id={dialogId}
          onCancel={(event) => {
            event.preventDefault();
            close();
          }}
          onClick={(event) => {
            if (event.target === event.currentTarget) close();
          }}
          onClose={close}
          ref={dialogRef}
        >
          <div aria-hidden="true" className="mf-weather-environment-sheet__handle" />
          <header className="mf-weather-environment-sheet__header">
            <span className="mf-weather-environment-tile__icon"><SelectedIcon aria-hidden="true" size={21} /></span>
            <div>
              <small>{copy.details}</small>
              <h2 id={titleId}>{selected.title}</h2>
            </div>
            <button aria-label={copy.close} autoFocus className="mf-weather-environment-sheet__close" onClick={close} type="button">
              <X aria-hidden="true" size={20} />
            </button>
          </header>
          <div className="mf-weather-environment-sheet__body">{selected.detail}</div>
        </dialog>
      ) : null}
    </section>
  );
}
