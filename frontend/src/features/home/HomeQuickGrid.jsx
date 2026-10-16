import {
  ArrowRight,
  BookOpenText,
  CalendarDays,
  ChevronRight,
  CloudSun,
  Landmark,
  MapPinned,
  Moon,
  Music,
  ShoppingBag,
  Sprout,
  Ticket,
  Trophy,
  Utensils,
} from "lucide-react";
import { useState } from "react";

import { getHomeQuickGridCopy } from "./homeQuickGridCopy";
import { HomeMeteoconIcon } from "./HomeMeteoconIcon";
import { HomePromotionCard } from "./HomePromotionCard";
import { isDefinitiveAppExperience } from "../../services/localWeatherPilot";
import { getPilotWhyContentForDate } from "../discover/pilotWhyContent";

function selectForecastSamples(items) {
  if (!Array.isArray(items) || !items.length) return [];

  return items.slice(0, 3).filter(Boolean);
}

function EventBannerFallback({ category }) {
  const Icon = (() => {
    if (category === "convegni" || category === "cultura") return Landmark;
    if (category === "famiglia") return CalendarDays;
    if (category === "food_wine" || category === "sagra") return Utensils;
    if (category === "mercato") return ShoppingBag;
    if (category === "musica") return Music;
    if (category === "natura") return Sprout;
    if (category === "sport") return Trophy;
    return Ticket;
  })();

  return <Icon aria-hidden="true" size={30} strokeWidth={1.9} />;
}

function HomeQuickCard({
  children,
  className,
  decoratedHeader = true,
  heading,
  headingId,
  icon: Icon,
  iconNode,
  label,
  onOpen,
}) {
  return (
    <article className={`mf-home-quick-card ${className}${onOpen ? " is-interactive" : ""}`}>
      {onOpen ? (
        <button
          aria-label={label}
          className="mf-home-quick-card__action"
          onClick={onOpen}
          type="button"
        />
      ) : null}
      <header className="mf-home-quick-card__header">
        {decoratedHeader ? <span className="mf-home-quick-card__icon" aria-hidden="true">
          {iconNode || (Icon ? <Icon size={24} strokeWidth={2.1} /> : null)}
        </span> : null}
        <h2 id={headingId}>{heading}</h2>
        {onOpen && decoratedHeader ? <ChevronRight aria-hidden="true" className="mf-home-quick-card__chevron" size={18} strokeWidth={2.35} /> : null}
      </header>
      {children}
    </article>
  );
}

function ForecastQuickCard({ copy, hourly, onOpen }) {
  const samples = selectForecastSamples(hourly?.items);
  const heading = copy.forecastFallback;
  const actionLabel = `${copy.forecastAction}: ${heading}`;

  return (
    <HomeQuickCard
      className="mf-home-quick-card--forecast"
      heading={heading}
      headingId="home-quick-forecast-title"
      icon={CloudSun}
      label={actionLabel}
      onOpen={onOpen}
    >
      {samples.length ? (
        <div
          aria-label={hourly?.scrollLabel || heading}
          className="mf-home-quick-forecast"
          role="list"
        >
          {samples.map((slot, index) => (
            <div
              aria-label={slot.ariaLabel}
              className="mf-home-quick-forecast__slot"
              key={slot.timestamp || `${slot.time}-${index}`}
              role="listitem"
            >
              <span className="mf-home-quick-forecast__when">
                {slot.dayLabel ? <small>{slot.dayLabel}</small> : null}
                <time dateTime={slot.timestamp}>{slot.time}</time>
              </span>
              <span
                aria-hidden="true"
                className="mf-home-quick-forecast__icon-surface"
                data-phase={slot.icon?.night ? "night" : "day"}
              >
                {slot.icon?.night && slot.icon?.type !== "ClearNight" ? (
                  <Moon
                    className="mf-home-quick-forecast__night-crescent"
                    fill="currentColor"
                    size={15}
                  />
                ) : null}
                {slot.icon?.night && slot.icon?.type === "ClearNight" ? (
                  <Moon
                    className="mf-home-quick-forecast__moon"
                    fill="currentColor"
                    size={28}
                  />
                ) : <HomeMeteoconIcon icon={slot.icon} size={46} />}
              </span>
              <strong>{slot.temperature}</strong>
            </div>
          ))}
        </div>
      ) : (
        <p className="mf-home-quick-card__empty">{copy.forecastUnavailable}</p>
      )}
    </HomeQuickCard>
  );
}

function EventsQuickCard({ copy, events, onOpen }) {
  const featuredEvent = events?.items?.[0] || null;
  const [brokenImage, setBrokenImage] = useState("");
  const image = String(featuredEvent?.image || "").trim();
  const hasImage = Boolean(image && image !== brokenImage);
  const category = featuredEvent?.category || "other";
  const heading = featuredEvent?.featured
    ? copy.eventsFeaturedHeading
    : events?.title || copy.eventsFallback;
  const actionLabel = featuredEvent
    ? `${copy.eventsAction}: ${featuredEvent.title}`
    : copy.eventsAction;

  return (
    <HomeQuickCard
      className="mf-home-quick-card--events"
      heading={heading}
      headingId="home-quick-events-title"
      icon={CalendarDays}
      label={actionLabel}
      onOpen={onOpen}
    >
      <div className="mf-home-quick-events">
        {events?.available === false ? null : featuredEvent ? (
          <>
            <div
              className={`mf-home-quick-events__banner${hasImage ? " mf-home-quick-events__banner--image" : " mf-home-quick-events__banner--fallback"}`}
              data-category={category}
            >
              {hasImage ? (
                <img
                  alt=""
                  decoding="async"
                  loading="lazy"
                  onError={() => setBrokenImage(image)}
                  onLoad={(event) => {
                    const preview = event.currentTarget;
                    if (preview.naturalWidth < 96 || preview.naturalHeight < 96) {
                      setBrokenImage(image);
                    }
                  }}
                  src={image}
                />
              ) : (
                <span className="mf-home-quick-events__fallback" aria-hidden="true">
                  <EventBannerFallback category={category} />
                </span>
              )}
            </div>
            <p>{featuredEvent.title}</p>
            <small>{[featuredEvent.dateLabel, featuredEvent.location].filter(Boolean).join(" · ")}</small>
          </>
        ) : events?.isUnavailable ? null : (
          <div className="mf-home-quick-events__count">
            <strong>{events?.countValue ?? "0"}</strong>
            <span>{events?.countCaption || copy.eventsCountCaption}</span>
          </div>
        )}
        {events?.message ? (
          <div className="mf-home-quick-events__status" role="status">{events.message}</div>
        ) : null}
      </div>
    </HomeQuickCard>
  );
}

function TerritoryQuickCard({ copy, editorial = false, language, onOpen, territory }) {
  const title = territory?.title || copy.territoryInvitation;
  const actionLabel = `${editorial ? copy.territoryRead : copy.territoryAction}: ${title}`;
  const category = territory?.type === "musica"
    ? (language === "fur" ? "Musiche" : "Musica") : territory?.typeLabel;
  const metadata = editorial
    ? [territory?.seasonLabel, category].filter(Boolean).join(" · ") || territory?.metaLabel
    : territory?.metaLabel;
  return (
    <HomeQuickCard
      className={`mf-home-quick-card--territory${editorial ? " mf-home-quick-card--memory" : ""}`}
      decoratedHeader={!editorial}
      heading={territory?.heading || copy.territoryHeading}
      headingId="home-quick-territory-title"
      icon={MapPinned}
      label={actionLabel}
      onOpen={onOpen}
    >
      <div className="mf-home-quick-territory">
        {metadata ? <small>{metadata}</small> : null}
        <strong>{title}</strong>
        <p>{territory?.text || copy.territoryInvitation}</p>
      </div>
      {editorial && onOpen ? <span className="mf-home-quick-memory__cta" aria-hidden="true">{copy.territoryRead}<ArrowRight size={16} strokeWidth={2} /></span> : null}
    </HomeQuickCard>
  );
}

function WhyQuickCard({ content, onOpen }) {
  return (
    <HomeQuickCard
      className="mf-home-quick-card--why"
      decoratedHeader={false}
      heading={content.rubric}
      headingId="home-quick-why-title"
      label={content.actionLabel}
      onOpen={onOpen}
    >
      <div className="mf-home-quick-why">
        {content.category ? <small className="mf-home-quick-why__meta">{content.category}</small> : null}
        <p className="mf-home-quick-why__question">{content.question}</p>
      </div>
      {onOpen ? <span className="mf-home-quick-why__cta" aria-hidden="true">{content.cta}<ArrowRight size={16} strokeWidth={2} /></span> : null}
    </HomeQuickCard>
  );
}

function AlmanacQuickCard({ almanac, copy, onOpen }) {
  const heading = almanac?.title || copy.almanacFallback;
  const saint = String(almanac?.saintLabel || almanac?.body || "").trim();

  return (
    <HomeQuickCard
      className="mf-home-quick-card--almanac"
      heading={heading}
      headingId="home-quick-almanac-title"
      icon={BookOpenText}
      label={`${almanac?.actionLabel || copy.almanacAction}: ${almanac?.dateLabel || heading}`}
      onOpen={onOpen}
    >
      <div className="mf-home-quick-almanac">
        {almanac?.dateLabel ? <small>{almanac.dateLabel}</small> : null}
        {almanac?.saintLabel ? (
          <span className="mf-home-quick-almanac__label">{copy.almanacSaintLabel}</span>
        ) : null}
        {saint ? <p>{saint}</p> : null}
      </div>
    </HomeQuickCard>
  );
}

export function HomeQuickGrid({
  almanac,
  events,
  hourly,
  language = "it",
  now,
  onNavigate,
  territory,
}) {
  const copy = getHomeQuickGridCopy(language);
  const pilot = isDefinitiveAppExperience();
  const why = pilot ? getPilotWhyContentForDate(language, now) : null;

  return (
    <section aria-label={copy.sectionLabel} className="mf-home-quick-grid">
      <ForecastQuickCard
        copy={copy}
        hourly={hourly}
        onOpen={onNavigate ? () => onNavigate("weather") : undefined}
      />
      <EventsQuickCard
        copy={copy}
        events={events}
        onOpen={onNavigate ? () => onNavigate("events") : undefined}
      />
      {pilot ? <HomePromotionCard language={language} /> : null}
      <TerritoryQuickCard
        copy={copy}
        editorial={pilot}
        language={language}
        onOpen={onNavigate ? () => onNavigate(
          "discover",
          territory?.anchor ? { anchor: territory.anchor } : undefined,
        ) : undefined}
        territory={territory}
      />
      {why ? <WhyQuickCard
        content={why}
        onOpen={onNavigate ? () => onNavigate("discover", { anchor: why.anchor, whyId: why.id }) : undefined}
      /> : <AlmanacQuickCard
        almanac={pilot ? { ...almanac, title: language === "fur" ? "Calendari" : "Calendario", actionLabel: language === "fur" ? "Calendari" : "Calendario" } : almanac}
        copy={copy}
        onOpen={onNavigate ? () => onNavigate(pilot ? "discover" : "almanac") : undefined}
      />}
    </section>
  );
}
