import { useCallback, useEffect, useId, useRef, useState } from "react";
import { ChevronDown, MapPin } from "lucide-react";
import { DEFAULT_EVENTS_RADIUS_KM, normalizeEventsRadius } from "../../app/eventsRadiusPreference";
import { useBrowserDialogBack } from "../../app/useBrowserDialogBack";
import { usePilotBackHandler } from "../../app/usePilotBackHandler";
import { EVENT_RADII } from "../events/eventsRadius";

function RadiusPickerDialog({ language, initialValue, title, onCancel, onConfirm, triggerRef }) {
  const id = useId();
  const dialogRef = useRef(null);
  const wheelRef = useRef(null);
  const settleTimerRef = useRef(null);
  const touchingRef = useRef(false);
  const [value, setValue] = useState(initialValue);

  useEffect(() => {
    const dialog = dialogRef.current;
    const trigger = triggerRef.current;
    const previousOverflow = document.body.style.overflow;
    if (!dialog.open) dialog.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
      if (trigger?.isConnected) trigger.focus({ preventScroll: true });
    };
  }, [triggerRef]);

  useEffect(() => {
    const wheel = wheelRef.current;
    window.clearTimeout(settleTimerRef.current);
    touchingRef.current = false;
    if (wheel) {
      const stepHeight = wheel.firstElementChild?.offsetHeight || 24;
      wheel.scrollTop = EVENT_RADII.indexOf(value) * stepHeight;
    }
    return () => window.clearTimeout(settleTimerRef.current);
  }, [value]);

  const nearestIndex = () => {
    const wheel = wheelRef.current;
    const stepHeight = wheel?.firstElementChild?.offsetHeight || 24;
    return Math.max(0, Math.min(EVENT_RADII.length - 1, Math.round((wheel?.scrollTop || 0) / stepHeight)));
  };

  const selectIndex = (index) => {
    window.clearTimeout(settleTimerRef.current);
    const boundedIndex = Math.max(0, Math.min(EVENT_RADII.length - 1, index));
    const wheel = wheelRef.current;
    if (wheel) {
      const stepHeight = wheel.firstElementChild?.offsetHeight || 24;
      wheel.scrollTop = boundedIndex * stepHeight;
    }
    const nextValue = EVENT_RADII[boundedIndex];
    setValue(nextValue);
  };

  const scheduleSelection = () => {
    window.clearTimeout(settleTimerRef.current);
    if (touchingRef.current) return;
    settleTimerRef.current = window.setTimeout(() => selectIndex(nearestIndex()), 160);
  };

  const handleKeyDown = (event) => {
    const current = nearestIndex();
    const next = {
      ArrowUp: current + 1,
      ArrowDown: current - 1,
      Home: 0,
      End: EVENT_RADII.length - 1,
    }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    selectIndex(next);
  };

  return <dialog
    aria-labelledby={`${id}-label`}
    className="mf-radius-dialog"
    onCancel={(event) => { event.preventDefault(); onCancel(); }}
    onClick={(event) => {
      if (event.target !== event.currentTarget) return;
      const bounds = event.currentTarget.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right ||
          event.clientY < bounds.top || event.clientY > bounds.bottom) onCancel();
    }}
    ref={dialogRef}
  >
    <h2 id={`${id}-label`}>{title}</h2>
    <div className="mf-radius-wheel">
      <div
        aria-labelledby={`${id}-label`}
        aria-valuemax={EVENT_RADII[EVENT_RADII.length - 1]}
        aria-valuemin={EVENT_RADII[0]}
        aria-valuenow={value}
        aria-valuetext={`${value} km`}
        className="mf-radius-wheel__scroll"
        onClick={(event) => {
          const item = event.target.closest("[data-radius-index]");
          if (item && event.currentTarget.contains(item)) selectIndex(Number(item.dataset.radiusIndex));
        }}
        onKeyDown={handleKeyDown}
        onScroll={scheduleSelection}
        onTouchStart={() => {
          touchingRef.current = true;
          window.clearTimeout(settleTimerRef.current);
        }}
        onTouchEnd={() => {
          touchingRef.current = false;
          scheduleSelection();
        }}
        onTouchCancel={() => {
          touchingRef.current = false;
          scheduleSelection();
        }}
        ref={wheelRef}
        role="spinbutton"
        tabIndex={0}
      >
        {EVENT_RADII.map((distance, index) => <span
          aria-hidden="true"
          className="mf-radius-wheel__number"
          data-radius-index={index}
          key={distance}
        >{distance}</span>)}
      </div>
      <span aria-hidden="true" className="mf-radius-wheel__unit">km</span>
    </div>
    <div className="mf-radius-dialog__actions">
      <button className="mf-button mf-button--secondary" onClick={onCancel} type="button">
        {language === "fur" ? "Anule" : "Annulla"}
      </button>
      <button className="mf-button mf-button--primary" onClick={() => {
        window.clearTimeout(settleTimerRef.current);
        onConfirm(EVENT_RADII[nearestIndex()]);
      }} type="button">
        {language === "fur" ? "Conferme" : "Conferma"}
      </button>
    </div>
  </dialog>;
}

export function SearchRadiusSetting({ language = "it", radius = DEFAULT_EVENTS_RADIUS_KM, onChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const triggerRef = useRef(null);
  const value = normalizeEventsRadius(radius) ?? DEFAULT_EVENTS_RADIUS_KM;
  const title = language === "fur" ? "Rai di ricercje" : "Raggio di ricerca";
  const close = useCallback(() => setIsOpen(false), []);
  useBrowserDialogBack(close, isOpen);
  usePilotBackHandler(close, isOpen);

  return <div className="mf-settings-search-radius">
    <span className="mf-settings-row__icon"><MapPin size={20} aria-hidden="true" /></span>
    <span className="mf-settings-search-radius__label">{title}</span>
    <button
      aria-expanded={isOpen}
      aria-haspopup="dialog"
      aria-label={`${title}: ${value} km`}
      className="mf-settings-search-radius__trigger"
      onClick={() => setIsOpen(true)}
      ref={triggerRef}
      type="button"
    >
      <span>{value} km</span><ChevronDown aria-hidden="true" size={16} />
    </button>
    {isOpen && <RadiusPickerDialog
      initialValue={value}
      key={value}
      language={language}
      onCancel={close}
      onConfirm={(nextValue) => {
        close();
        if (nextValue !== value) onChange?.(nextValue);
      }}
      title={language === "fur" ? "Rai di ricercje dai events" : "Raggio di ricerca eventi"}
      triggerRef={triggerRef}
    />}
  </div>;
}
