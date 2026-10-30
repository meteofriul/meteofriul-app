import {
  CalendarDays,
  ChevronRight,
  Clock,
  ExternalLink,
  Frown,
  Landmark,
  MapPin,
  Music,
  Navigation,
  ShoppingBag,
  Sprout,
  Store,
  Ticket,
  Trophy,
  Utensils,
  X,
} from "lucide-react";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { usePilotBackHandler } from "../../app/usePilotBackHandler";
import { useBrowserDialogBack } from "../../app/useBrowserDialogBack";

import { TabPage } from "../../ui/layout/TabPage";
import { LocationContext } from "../../ui/components/LocationContext";
import { fetchLocalEventDetail } from "../../services/eventsApi";
import { isDefinitiveAppExperience } from "../../services/localWeatherPilot";
import { PromotionPlacementCard } from "../promotions/PromotionPlacementCard";

import { buildEventPreviewModel } from "./eventPreview";
import { groupEventOccurrences, sortEventsForTimeTab } from "./eventsViewModel";
import { EventsRadiusSelect } from "./EventsRadiusSelect";
import { findRequestedMarketEvent, MARKET_CATALOGUE, marketDirectionsUrl, matchMarket } from "../markets/marketsCatalog";
import { getMarketsCopy } from "../markets/marketsCopy";

const INITIAL_VISIBLE_EVENTS = 16;
const VISIBLE_EVENTS_STEP = 16;
const EVENTS_PROMOTION_AFTER_COUNT = 3;

function formatTabCount(count) {
  if (!count) return "";
  return count > 9 ? "9+" : String(count);
}

function FallbackIcon({ category }) {
  if (category === "convegni" || category === "cultura") return <Landmark size={27} strokeWidth={1.9} />;
  if (category === "famiglia") return <CalendarDays size={27} strokeWidth={1.9} />;
  if (category === "food_wine" || category === "sagra") return <Utensils size={27} strokeWidth={1.9} />;
  if (category === "mercato") return <ShoppingBag size={27} strokeWidth={1.9} />;
  if (category === "musica") return <Music size={27} strokeWidth={1.9} />;
  if (category === "natura") return <Sprout size={27} strokeWidth={1.9} />;
  if (category === "sport") return <Trophy size={27} strokeWidth={1.9} />;
  return <Ticket size={27} strokeWidth={1.9} />;
}

function EventDateChip({ chip }) {
  if (!chip?.start) {
    return (
      <span
        aria-label={chip?.accessibleLabel || chip?.label}
        className="mf-events-date-chip mf-events-date-chip--text"
        title={chip?.accessibleLabel || chip?.label}
      >
        <CalendarDays aria-hidden="true" size={13} strokeWidth={2.35} />
        <span>{chip?.compact || chip?.label}</span>
      </span>
    );
  }

  return (
    <span
      aria-label={chip.accessibleLabel || chip.label}
      className={`mf-events-date-chip${chip.isRange ? " mf-events-date-chip--range" : ""}`}
      title={chip.accessibleLabel || chip.label}
    >
      <span>
        <strong>{chip.start.day}</strong>
        <small>{chip.start.month}</small>
      </span>
      {chip.isRange ? (
        <>
          <i aria-hidden="true" />
          <span>
            <strong>{chip.end.day}</strong>
            <small>{chip.end.month}</small>
          </span>
        </>
      ) : null}
    </span>
  );
}

function EventFallbackVisual({ category }) {
  return (
    <div className="mf-events-card__fallback" aria-hidden="true">
      <span />
      <FallbackIcon category={category} />
    </div>
  );
}

function ProgrammeSchedule({ copy, sessions }) {
  if (!Array.isArray(sessions) || sessions.length === 0) return null;
  const days = new Map();
  for (const session of sessions) {
    const day = session.start_date || "";
    if (!days.has(day)) days.set(day, []);
    days.get(day).push(session);
  }
  const formatDay = (day) => /^\d{4}-\d{2}-\d{2}$/.test(day)
    ? new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "long", weekday: "long", timeZone: "UTC" })
      .format(new Date(`${day}T12:00:00Z`)) : day;
  const safeUrl = (value) => {
    try {
      const url = new URL(value);
      return url.protocol === "https:" ? url.href : "";
    } catch { return ""; }
  };

  return (
    <section aria-label={copy.previewProgrammeLabel} className="mf-event-preview__programme">
      <div className="mf-event-preview__programme-heading">
        <h3>{copy.previewProgrammeLabel}</h3>
        <span>{sessions.length} {copy.previewProgrammeCountLabel}</span>
      </div>
      <div aria-label={copy.previewProgrammeScrollLabel} className="mf-event-preview__programme-scroll" role="region" tabIndex={0}>
        {[...days].map(([day, entries]) => (
          <div className="mf-event-preview__programme-day" key={day}>
            <h4>{formatDay(day)}</h4>
            <ol>
              {entries.map((session, index) => {
                const url = safeUrl(session.url);
                return (
                  <li className={session.time ? undefined : "is-untimed"} key={`${session.url || session.title}-${session.time}-${index}`}>
                    {session.time ? <time dateTime={`${day}T${session.time}`}>{session.time}</time> : null}
                    <div>
                      {url ? <a href={url} rel="noopener noreferrer" target="_blank">{session.title}</a>
                        : <strong>{session.title}</strong>}
                      {session.place ? <span>{session.place}</span> : null}
                      {session.access_notes ? <small>{session.access_notes}</small> : null}
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        ))}
      </div>
    </section>
  );
}

function mainFestivalDates(event) {
  const raw = event?.raw;
  if (raw?.source !== "Le Giornate del Cinema Muto") return "";
  const start = raw.programme_main_start_date;
  const end = raw.programme_main_end_date;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start || "")
    || !/^\d{4}-\d{2}-\d{2}$/.test(end || "")
    || (start === raw.programme_start_date && end === raw.programme_end_date)) return "";
  const first = new Date(`${start}T12:00:00Z`);
  const last = new Date(`${end}T12:00:00Z`);
  if (Number.isNaN(first.getTime()) || Number.isNaN(last.getTime()) || first > last) return "";
  if (first.getUTCFullYear() === last.getUTCFullYear()
    && first.getUTCMonth() === last.getUTCMonth()) {
    const monthYear = new Intl.DateTimeFormat("it-IT", {
      month: "long", year: "numeric", timeZone: "UTC",
    }).format(last);
    return `${first.getUTCDate()}–${last.getUTCDate()} ${monthYear}`;
  }
  return new Intl.DateTimeFormat("it-IT", {
    day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  }).formatRange(first, last);
}

export function EventPreviewPanel({
  closeButtonRef,
  copy,
  descriptionPending = false,
  event,
  imageBroken = false,
  onClose,
  onImageError,
  panelRef,
  onMarketOpen,
  language = 'it',
  catalogue = MARKET_CATALOGUE,
}) {
  const preview = buildEventPreviewModel(event);
  const festivalDates = mainFestivalDates(event);
  const market = matchMarket(event, catalogue);
  const edition = catalogue.dates.find(item => item.id && item.id === event.raw?.market_edition_id);
  const directionsUrl = event.raw?.market_catalogue ? marketDirectionsUrl(market, edition) : preview.directionsUrl;

  return (
    <section
      aria-label={copy.previewDialogLabel}
      aria-labelledby="mf-event-preview-title"
      aria-modal="true"
      className={`mf-event-preview__panel mf-events-card--${preview.category}`}
      ref={panelRef}
      role="dialog"
    >
      <div className={`mf-event-preview__media${preview.image && !imageBroken ? "" : " is-fallback"}`}>
        {preview.image && !imageBroken ? (
          <img
            alt=""
            decoding="async"
            onError={onImageError}
            src={preview.image}
          />
        ) : (
          <div className="mf-event-preview__fallback" aria-hidden="true">
            <span className="mf-event-preview__fallback-orbit" />
            <span className="mf-event-preview__monogram">{preview.monogram}</span>
            <span className="mf-event-preview__fallback-mark">
              <FallbackIcon category={preview.category} />
            </span>
          </div>
        )}

        <button
          aria-label={copy.previewCloseLabel}
          className="mf-event-preview__close"
          onClick={onClose}
          ref={closeButtonRef}
          type="button"
        >
          <X aria-hidden="true" size={19} strokeWidth={2.5} />
        </button>
      </div>

      <div className="mf-event-preview__body">
        <div className="mf-event-preview__meta">
          <span className="mf-event-preview__category">{preview.categoryLabel}</span>
          {preview.source && !preview.descriptionSourceName ? (
            <span className="mf-event-preview__source">{copy.previewSourceLabel}: {preview.source}</span>
          ) : null}
        </div>

        <h2 id="mf-event-preview-title">{preview.title}</h2>
        {event.scheduleLabel ? <p>{event.scheduleLabel}</p> : null}
        {event.occurrences?.length > 1 ? <div className="mf-event-preview__occurrences">
          {event.occurrences.map((occurrence, index) => <p key={`${occurrence.id}-${index}`}>
            <strong>{occurrence.date}</strong>
            {(occurrence.raw?.time || occurrence.raw?.start_time) ? ` · ${occurrence.raw.time || occurrence.raw.start_time}` : ""}
            {occurrence.raw?.description ? <span style={{ display: "block" }}>{occurrence.raw.description}</span> : null}
          </p>)}
        </div> : null}

        <div className="mf-event-preview__facts">
          {preview.dateLabel ? (
            <p>
              <CalendarDays aria-hidden="true" size={17} strokeWidth={2.15} />
              <span>{preview.dateLabel}</span>
            </p>
          ) : null}
          {preview.timeLabel && !(event.occurrences?.length > 1) ? (
            <p data-testid="event-preview-time">
              <Clock aria-hidden="true" size={17} strokeWidth={2.15} />
              <span>{preview.timeLabel}</span>
            </p>
          ) : null}
          {festivalDates ? (
            <p>
              <CalendarDays aria-hidden="true" size={17} strokeWidth={2.15} />
              <span>{copy.previewMainFestivalDatesLabel}: {festivalDates}</span>
            </p>
          ) : null}
          {preview.location ? (
            <p>
              <MapPin aria-hidden="true" size={17} strokeWidth={2.15} />
              <span>{preview.location}</span>
            </p>
          ) : null}
        </div>

        {preview.description || descriptionPending || !event.raw?.programme_sessions?.length ? (
          <p className={`mf-event-preview__description${preview.description ? "" : ` ${descriptionPending ? "is-loading" : "is-fallback"}`}`}>
            {preview.description || (descriptionPending
              ? copy.previewDescriptionLoading
              : copy.previewDescriptionFallback)}
          </p>
        ) : null}
        {preview.description && preview.descriptionSourceName ? (
          <p className="mf-event-preview__attribution">
            {copy.previewSourceLabel}:{" "}
            {preview.descriptionSourceUrl ? (
              <a href={preview.descriptionSourceUrl} rel="noopener noreferrer" target="_blank">
                {preview.descriptionSourceName}
              </a>
            ) : preview.descriptionSourceName}
          </p>
        ) : null}

        <ProgrammeSchedule copy={copy} sessions={event.raw?.programme_sessions} />

        {market && onMarketOpen ? <button type="button" className="mf-market-catalogue-link" onClick={() => onMarketOpen(market.id)}>
          <ShoppingBag size={18} aria-hidden="true" />{getMarketsCopy(language).details}
        </button> : null}
        <div className="mf-event-preview__actions">
          {preview.pageUrl ? (
            <a
              className="mf-event-preview__action is-primary"
              href={preview.pageUrl}
              rel="noopener noreferrer"
              target="_blank"
            >
              <ExternalLink aria-hidden="true" size={18} strokeWidth={2.25} />
              <span>{copy.previewPageLabel}</span>
            </a>
          ) : null}
          {directionsUrl ? (
            <a
              className="mf-event-preview__action"
              href={directionsUrl}
              rel="noopener noreferrer"
              target="_blank"
            >
              <Navigation aria-hidden="true" size={18} strokeWidth={2.25} />
              <span>{event.raw?.market_catalogue ? getMarketsCopy(language).directions : copy.previewDirectionsLabel}</span>
            </a>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function needsTurismoFvgDetail(event) {
  if (event?.raw?.market_managed) return false;
  const preview = buildEventPreviewModel(event);
  return preview.source.toLocaleLowerCase("it-IT") === "turismofvg"
    && Boolean(event?.url)
    && (!preview.description || !preview.directionsUrl);
}

function EventPreviewDialog({ copy, event, onClose, onMarketOpen, language, catalogue }) {
  usePilotBackHandler(onClose);
  useBrowserDialogBack(onClose);
  const closeButtonRef = useRef(null);
  const panelRef = useRef(null);
  const [imageBroken, setImageBroken] = useState(false);
  const [resolvedDetail, setResolvedDetail] = useState(null);
  // Linked editions follow source refreshes. Detail fields belong only to
  // the event object that requested them, never to a newer source snapshot.
  const detailFields = resolvedDetail?.event === event ? resolvedDetail.fields : null;
  const resolvedEvent = detailFields
    ? { ...event, raw: { ...event.raw, ...detailFields } } : event;
  const descriptionPending = needsTurismoFvgDetail(event) && resolvedDetail?.event !== event;

  useEffect(() => {
    if (!needsTurismoFvgDetail(event)) return undefined;

    let cancelled = false;

    fetchLocalEventDetail(event)
      .then((detail) => {
        if (cancelled) return;
        const detailRaw = detail.raw || {};
        const verifiedFields = Object.fromEntries(
          [
            "description",
            "description_excerpt",
            "description_source_name",
            "description_source_url",
            "description_checked_at",
            "event_city",
            "place",
            "venue",
            "address",
            "maps_url",
            "lat",
            "lon",
            "location_confidence",
          ]
            .filter((key) => detailRaw[key] !== null && detailRaw[key] !== undefined && detailRaw[key] !== "")
            .map((key) => [key, detailRaw[key]]),
        );
        setResolvedDetail({ event, fields: verifiedFields });
      })
      .catch(() => {
        if (!cancelled) setResolvedDetail({ event, fields: {} });
      });

    return () => {
      cancelled = true;
    };
  }, [event]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (keyboardEvent) => {
      if (keyboardEvent.key === "Escape") {
        keyboardEvent.preventDefault();
        onClose();
        return;
      }
      if (keyboardEvent.key !== "Tab" || !panelRef.current) return;

      const focusable = [...panelRef.current.querySelectorAll(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )];
      const first = focusable[0];
      const last = focusable.at(-1);
      if (!first || !last) return;

      if (keyboardEvent.shiftKey && document.activeElement === first) {
        keyboardEvent.preventDefault();
        last.focus();
      } else if (!keyboardEvent.shiftKey && document.activeElement === last) {
        keyboardEvent.preventDefault();
        first.focus();
      }
    };

    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);
    closeButtonRef.current?.focus();

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  if (typeof document === "undefined") return null;

  return createPortal(
    <div className="mf-event-preview">
      <button
        aria-label={copy.previewCloseLabel}
        className="mf-event-preview__backdrop"
        onClick={onClose}
        type="button"
      />
      <EventPreviewPanel
        closeButtonRef={closeButtonRef}
        copy={copy}
        descriptionPending={descriptionPending}
        event={resolvedEvent}
        imageBroken={imageBroken}
        onClose={onClose}
        onImageError={() => setImageBroken(true)}
        panelRef={panelRef}
        language={language}
        catalogue={catalogue}
        onMarketOpen={onMarketOpen ? (id) => { onClose(); onMarketOpen(id); } : undefined}
      />
    </div>,
    document.body,
  );
}

export function EventCard({ copy, event, imagePriority = false, onOpen, showCategoryLabel = true, showSource = true }) {
  const [imageBroken, setImageBroken] = useState(false);
  const hasImage = Boolean(event.image && !imageBroken);
  const programmeCount = Array.isArray(event.raw?.programme_sessions)
    ? event.raw.programme_sessions.length : 0;

  return (
    <article className={`mf-events-card mf-events-card--${event.category} is-clickable${programmeCount ? " is-programme" : ""}`}>
      <button
        aria-label={`${event.title} - ${copy.previewOpenLabel}`}
        className="mf-events-card__link"
        onClick={(clickEvent) => onOpen(event, clickEvent.currentTarget)}
        type="button"
      >
        <ChevronRight aria-hidden="true" size={14} strokeWidth={2.3} />
      </button>

      <div className={`mf-events-card__media${hasImage ? "" : " is-fallback"}`}>
        {hasImage ? (
          <img
            alt=""
            decoding="async"
            fetchPriority={imagePriority ? "high" : "auto"}
            loading={imagePriority ? "eager" : "lazy"}
            onError={() => setImageBroken(true)}
            onLoad={(eventLoad) => {
              const image = eventLoad.currentTarget;
              if (image.naturalWidth < 96 || image.naturalHeight < 96) {
                setImageBroken(true);
              }
            }}
            src={event.image}
          />
        ) : (
          <EventFallbackVisual category={event.category} />
        )}
      </div>

      <div className="mf-events-card__body">
        <div className="mf-events-card__main">
          <h2>{event.title}</h2>
          {event.location ? (
            <p>
              <MapPin aria-hidden="true" size={13} strokeWidth={2.35} />
              <span>{event.location}</span>
            </p>
          ) : null}
          {programmeCount ? (
            <p className="mf-events-card__programme-count">
              <CalendarDays aria-hidden="true" size={13} strokeWidth={2.35} />
              <span>{programmeCount} {copy.previewProgrammeCountLabel}</span>
            </p>
          ) : null}
        </div>

        <div className="mf-events-card__footer">
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {(event.visibleOccurrences || event.occurrences || [event]).filter((item, index, all) => all.findIndex((other) => other.date === item.date) === index).map((item, index) => <EventDateChip key={`${item.id}-${index}`} chip={item.dateChip} />)}
          </div>
          <div className="mf-events-card__badges">
            {showSource && event.source ? <span className="mf-events-card__source">{event.source}</span> : null}
            {showSource && event.source && showCategoryLabel ? (
              <span aria-hidden="true" className="mf-events-card__badge-separator">•</span>
            ) : null}
            {showCategoryLabel ? (
              <span className={`mf-events-category mf-events-category--${event.category}`}>
                {event.categoryLabel}
              </span>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  );
}

function EmptyEvents({ copy, isLoading, isDegraded, isUnavailable, tab }) {
  return (
    <div className="mf-events-empty" role={isLoading || isDegraded || isUnavailable ? "status" : undefined}>
      <span aria-hidden="true">
        <Frown size={34} strokeWidth={2.15} />
      </span>
      <strong>{isLoading ? copy.loadingTitle : isDegraded || isUnavailable ? copy.unavailableTitle : tab === "today" ? copy.emptyTodayTitle : copy.emptyTitle}</strong>
      <p>{isLoading ? copy.loadingBody : isDegraded || isUnavailable ? copy.unavailableBody : copy.emptyBody}</p>
    </div>
  );
}

export function EventsView({
  language = "it",
  model,
  promotionCampaigns,
  radius = 20,
  onRadiusChange,
  showCardSource = true,
  titleMode = "visible",
  onMarketsOpen,
  marketEventRequest,
  catalogue = MARKET_CATALOGUE,
}) {
  const requestedEvent = findRequestedMarketEvent(model.items, marketEventRequest, new Date(), catalogue);
  const [requestedTab, setRequestedTab] = useState(() => requestedEvent?.timeCategory || "today");
  const [activeCategory, setActiveCategory] = useState(() => marketEventRequest ? "mercato" : "all");
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [requestPreviewDismissed, setRequestPreviewDismissed] = useState(!marketEventRequest);
  // Follow source refreshes until the user closes the linked edition or opens another card.
  const currentSelectedEvent = selectedEvent?.raw?.market_id
    ? model.items.find(item => item.id === selectedEvent.id) || null : selectedEvent;
  const effectiveSelectedEvent = requestPreviewDismissed ? currentSelectedEvent : requestedEvent;
  const [visibleState, setVisibleState] = useState({ count: INITIAL_VISIBLE_EVENTS, key: "" });
  const previewTriggerRef = useRef(null);
  const copy = model.copy;
  const marketsCopy = getMarketsCopy(language);
  const handlePreviewOpen = useCallback((event, trigger) => {
    previewTriggerRef.current = trigger;
    setRequestPreviewDismissed(true);
    setSelectedEvent(event);
  }, []);
  const handlePreviewClose = useCallback(() => {
    const trigger = previewTriggerRef.current;
    previewTriggerRef.current = null;
    setRequestPreviewDismissed(true);
    setSelectedEvent(null);
    window.requestAnimationFrame(() => trigger?.focus());
  }, []);
  const categoriesWithEvents = useMemo(() => {
    const available = new Set(model.items.map((event) => event.category));
    return model.categories.filter((category) => category.id === "all" || available.has(category.id));
  }, [model.categories, model.items]);
  const effectiveCategory = categoriesWithEvents.some((category) => category.id === activeCategory)
    ? activeCategory
    : "all";
  const categoryFilteredEvents = useMemo(() => (
    model.items.filter((event) => effectiveCategory === "all" || event.category === effectiveCategory)
  ), [effectiveCategory, model.items]);
  const counts = useMemo(() => {
    const nextCounts = { next: 0, today: 0, weekend: 0 };

    nextCounts.today = groupEventOccurrences(categoryFilteredEvents.filter((event) => event.timeCategory === "today")).length;
    nextCounts.weekend = groupEventOccurrences(categoryFilteredEvents.filter((event) => event.timeCategory === "weekend")).length;
    nextCounts.next = groupEventOccurrences(categoryFilteredEvents.filter((event) => ["weekend", "next"].includes(event.timeCategory))).length;
    return nextCounts;
  }, [categoryFilteredEvents]);
  const effectiveTab = useMemo(() => {
    if (requestedTab === "next") return "next";
    if (counts[requestedTab] > 0) return requestedTab;
    return model.tabs.find((tab) => counts[tab.id] > 0)?.id || "next";
  }, [counts, model.tabs, requestedTab]);
  const filteredEvents = useMemo(() => {
    const matchingEvents = categoryFilteredEvents.filter((event) => {
      if (effectiveTab === "today") return event.timeCategory === "today";
      if (effectiveTab === "weekend") return event.timeCategory === "weekend";
      return event.timeCategory === "weekend" || event.timeCategory === "next";
    });

    return sortEventsForTimeTab(groupEventOccurrences(matchingEvents, categoryFilteredEvents).map((group) => ({ ...group, date: group.visibleOccurrences[0].date })), effectiveTab);
  }, [categoryFilteredEvents, effectiveTab]);
  const visibleKey = `${effectiveCategory}:${effectiveTab}:${model.locationLabel}:${radius}`;
  const visibleCount = visibleState.key === visibleKey ? visibleState.count : INITIAL_VISIBLE_EVENTS;
  const visibleEvents = filteredEvents.slice(0, visibleCount);
  const totalCount = String(filteredEvents.length);
  const filteredCountLabel = `${totalCount} ${copy.eventCountLabel}`;

  return (
    <TabPage
      className="mf-tab-page--events"
      language={language}
      title={copy.viewTitle}
      titleMeta={titleMode !== "hidden" && !model.isUnavailable && totalCount ? (
        <span aria-label={filteredCountLabel} className="mf-events-title-count" title={filteredCountLabel}>
          {totalCount}
        </span>
      ) : null}
      titleMode={titleMode}
    >
      <div className="mf-events-view">
        <div className={"mf-section-navigation" + (isDefinitiveAppExperience() ? " mf-section-navigation--sticky" : "")}>
          <section className="mf-events-hero" aria-label={copy.viewTitle}>
            <div className="mf-events-hero__context">
              <LocationContext
                city={model.locationLabel || "-----"}
                className="mf-route-location-context"
              />
              {onRadiusChange ? <EventsRadiusSelect radius={radius} onChange={onRadiusChange} language={language} /> : null}
            </div>
            {model.message ? (
              <div className="mf-events-hero__meta" role="status">
                <p>{model.message}</p>
              </div>
            ) : null}
          </section>

          <section className="mf-events-filters" aria-label="Filtri eventi">
            <div className="mf-events-time-tabs mf-weather-section-nav mf-weather-section-nav--compact">
              {model.tabs.map((tab) => {
                const count = counts[tab.id] || 0;
                const disabled = count === 0;

                return (
                  <button
                    aria-label={count ? `${tab.label} ${formatTabCount(count)}` : tab.label}
                    aria-pressed={effectiveTab === tab.id}
                    className={`mf-weather-section-nav__item${effectiveTab === tab.id ? " is-active" : ""}`}
                    disabled={disabled}
                    key={tab.id}
                    onClick={() => {
                      if (!disabled) setRequestedTab(tab.id);
                    }}
                    type="button"
                  >
                    <span>{tab.label}</span>
                    {count ? (
                      <strong className="mf-events-time-tabs__count">
                        {formatTabCount(count)}
                      </strong>
                    ) : null}
                  </button>
                );
              })}
            </div>

            {categoriesWithEvents.length > 1 ? (
              <div className="mf-events-category-scroll">
                {categoriesWithEvents.map((category) => (
                  <button
                    aria-pressed={effectiveCategory === category.id}
                    className={`mf-events-filter mf-events-filter--${category.id}${effectiveCategory === category.id ? " is-active" : ""}`}
                    key={category.id}
                    onClick={() => setActiveCategory(category.id)}
                    type="button"
                  >
                    {category.id !== "all" ? (
                      <span aria-hidden="true" className="mf-events-filter__dot" />
                    ) : null}
                    <span>{category.label}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </section>
        </div>

        {onMarketsOpen ? <button className="mf-market-catalogue-link mf-market-catalogue-link--banner" type="button" onClick={() => onMarketsOpen()}>
          <span className="mf-market-banner__icon" aria-hidden="true"><Store size={27} strokeWidth={1.8} /></span>
          <span className="mf-market-banner__copy">
            <strong>{marketsCopy.title}</strong>
            <span>{marketsCopy.explore}</span>
          </span>
          <span className="mf-market-banner__arrow" aria-hidden="true"><ChevronRight size={22} strokeWidth={2.2} /></span>
        </button> : null}
        {marketEventRequest && !requestedEvent && !model.isLoading ? <p role="status" className="mf-markets-note">
          {language === "fur" ? "L’apontament nol è disponibil tal calendari corint. Controle la font dal marcjât." : "L’appuntamento non è disponibile nel calendario corrente. Consulta la fonte del mercato."}
        </p> : null}
        <section className="mf-events-list" aria-label={copy.viewTitle}>
          {model.isLoading ? (
            <EmptyEvents copy={copy} isLoading tab={effectiveTab} />
          ) : visibleEvents.length ? (
            <>
              {visibleEvents.map((event, index) => (
                <Fragment key={`${event.id}-${index}`}>
                  <EventCard
                    copy={copy}
                    event={event}
                    imagePriority={index < 4}
                    onOpen={handlePreviewOpen}
                    showCategoryLabel={effectiveCategory === "all"}
                    showSource={showCardSource}
                  />
                  {isDefinitiveAppExperience()
                    && index === Math.min(EVENTS_PROMOTION_AFTER_COUNT, visibleEvents.length) - 1 ? (
                      <PromotionPlacementCard
                        campaigns={promotionCampaigns}
                        language={language}
                        placement="events"
                      />
                    ) : null}
                </Fragment>
              ))}
              {visibleEvents.length < filteredEvents.length ? (
                <button
                  className="mf-events-load-more"
                  onClick={() => setVisibleState({ count: visibleCount + VISIBLE_EVENTS_STEP, key: visibleKey })}
                  type="button"
                >
                  <span>{visibleEvents.length} / {filteredEvents.length}</span>
                  <strong>
                    {copy.loadMoreLabel}
                    <ChevronRight aria-hidden="true" size={16} strokeWidth={2.35} />
                  </strong>
                </button>
              ) : null}
            </>
          ) : (
            <EmptyEvents copy={copy} isDegraded={model.isDegraded} isUnavailable={model.isUnavailable} tab={effectiveTab} />
          )}
        </section>
      </div>
      {effectiveSelectedEvent ? (
        <EventPreviewDialog
          copy={copy}
          event={effectiveSelectedEvent}
          language={language}
          catalogue={catalogue}
          onMarketOpen={onMarketsOpen}
          key={`${effectiveSelectedEvent.source || "event"}:${effectiveSelectedEvent.url || effectiveSelectedEvent.title}`}
          onClose={handlePreviewClose}
        />
      ) : null}
    </TabPage>
  );
}
