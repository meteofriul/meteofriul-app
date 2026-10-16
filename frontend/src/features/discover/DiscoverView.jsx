import { useEffect, useId, useState } from "react";
import { BookOpen, Brain, CalendarDays, ChevronDown, History, Library, MapPin, Sparkles, Speech, Sprout } from "lucide-react";

import { getLocationDisplayName } from "../../domain/geo/locationDisplayName";
import { LocationContext } from "../../ui/components/LocationContext";
import { TabPage } from "../../ui/layout/TabPage";
import { buildDiscoverViewModel } from "./discoverViewModel";
import { subscribeToDiscoverDayClock } from "./discoverDayClock";
import { getDiscoverCardAnchor } from "./discoverCardAnchor";
import { getMunicipalityVisual } from "./municipalityVisuals";
import { buildAlmanacViewModel } from "../almanac/almanacViewModel";
import { isDefinitiveAppExperience } from "../../services/localWeatherPilot";
import { buildPilotDiscoverCulture } from "./pilotDiscoverSections";
import { PilotDiscoverCard } from "./PilotDiscoverCard";
import { PilotWhyCard } from "./PilotWhyCard";
import { buildPilotCalendarSummary } from "./pilotCalendarSummary";
import { createPilotWhyVisit, getPilotWhyContentForVisit } from "./pilotWhyVisit";
import { getPilotMunicipalityContext } from "./pilotMunicipalityContext";
import { PromotionPlacementCard } from "../promotions/PromotionPlacementCard";

export function OtherSaints({ saint, language }) {
  const [expanded, setExpanded] = useState(false);
  const id = useId();
  return <section className="mf-discover-other-saints">
    <h3>{saint.otherSaintsLabel}</h3>
    <p id={id} className={expanded ? "" : "is-clamped"}>{saint.otherSaints.join(" · ")}</p>
    <button type="button" aria-expanded={expanded} aria-controls={id} onClick={() => setExpanded(value => !value)}>
      {language === "fur" ? (expanded ? "Mostre di mancul" : "Mostre altris…") : (expanded ? "Mostra meno" : "Mostra altri…")}
    </button>
  </section>;
}

export function AlmanacCulture({ calendar, sections, language, copy, excludedCards }) {
  const { sayings, traditions, earth } = buildPilotDiscoverCulture({
    calendar, sections, language, copy, excludedCards,
  });
  return <>
    {sayings.cards.length ? <DiscoverSection section={sayings} language={language} furPendingLabel={copy.furPending} /> : null}
    {traditions.cards.length || earth.items.length ? (
      <section className="mf-discover-section mf-discover-traditions" aria-labelledby="discover-traditions">
        <h2 id="discover-traditions">{traditions.title}</h2>
        {traditions.cards.length ? <div className="mf-discover-grid">
          {traditions.cards.map(card => <DiscoverCard key={card.id} card={card} sectionId="traditions" language={language} furPendingLabel={copy.furPending} />)}
        </div> : null}
        {earth.items.length ? <aside className="mf-discover-earth-tip" aria-labelledby="discover-earth-tip-title">
          <h3 id="discover-earth-tip-title"><Sprout size={18} aria-hidden="true" />{earth.title}</h3>
          <ul role="list">{earth.items.map(text => <li key={text}>{text}</li>)}</ul>
        </aside> : null}
      </section>
    ) : null}
  </>;
}

const LOCATION_COPY = {
  fur: { change: "Cambie", prefix: "A" },
  it: { change: "Cambia", prefix: "A" },
};

function DiscoverCardMeta({ seasonLabel, typeLabel }) {
  const values = [typeLabel, seasonLabel].filter(Boolean);
  if (!values.length) return null;

  return (
    <div className="mf-discover-card__meta">
      {values.map((value) => <span key={value}>{value}</span>)}
    </div>
  );
}

function MunicipalityTimeline({ card, label }) {
  const milestones = Array.isArray(card.milestones) ? card.milestones : [];

  if (!milestones.length) return null;

  const titleId = `${card.id}-milestones-title`;

  return (
    <section className="mf-discover-card__timeline" aria-labelledby={titleId}>
      <h3 id={titleId}>
        <History aria-hidden="true" size={15} strokeWidth={2.4} />
        <span>{label}</span>
      </h3>
      <ol>
        {milestones.map((milestone) => (
          <li key={milestone.id}>
            <time>{milestone.period}</time>
            <span>{milestone.label}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function MunicipalityDiscoverCard({
  card,
  internalLabel,
  timelineLabel,
}) {
  const visual = getMunicipalityVisual(card);

  return (
    <article
      className={[
        "mf-discover-card",
        "mf-discover-card--featured",
        "mf-discover-card--location",
        "mf-discover-card--municipality",
        visual?.photoUrl ? "mf-discover-card--with-photo" : "",
      ].filter(Boolean).join(" ")}
      id={getDiscoverCardAnchor(card.id)}
      tabIndex={-1}
    >
      {visual?.photoUrl ? (
        <img
          alt={visual.photoAlt || ""}
          className="mf-discover-card__photo"
          decoding="async"
          src={visual.photoUrl}
          style={{ objectPosition: visual.photoPosition }}
        />
      ) : null}

      <div className="mf-discover-card__municipality-topline">
        <div className="mf-discover-card__kicker">
          <Library aria-hidden="true" size={15} strokeWidth={2.4} />
          <span>{internalLabel}</span>
        </div>

        <div className="mf-discover-card__crest" aria-hidden="true">
          {visual?.coatOfArmsUrl ? (
            <img alt="" src={visual.coatOfArmsUrl} />
          ) : (
            <MapPin size={22} strokeWidth={2.4} />
          )}
        </div>
      </div>

      <div className="mf-discover-card__body">
        <h2>{card.title}</h2>
        {card.text ? <p>{card.text}</p> : null}
        <MunicipalityTimeline card={card} label={timelineLabel} />
      </div>
    </article>
  );
}

export function DiscoverCard({
  card,
  language = "it",
  featured = false,
  sectionId = "",
  furPendingLabel = "",
  internalLabel = "",
  municipalityMilestonesTitle = "",
}) {
  const isMunicipalityCard = card.visualKind === "municipality";
  const isLocationCard = card.visualKind === "location" || card.visualKind === "municipality";
  const sourceLabel = card.isFurPending && furPendingLabel
    ? `${card.sourceLabel} - ${furPendingLabel}`
    : card.sourceLabel;

  if (isMunicipalityCard) {
    return (
      <MunicipalityDiscoverCard
        card={card}
        internalLabel={internalLabel}
        timelineLabel={municipalityMilestonesTitle}
      />
    );
  }

  if (isDefinitiveAppExperience()) {
    return <PilotDiscoverCard card={card} sectionId={sectionId} sourceLabel={sourceLabel} language={language} />;
  }

  const cardClassName = [
    "mf-discover-card",
    featured ? "mf-discover-card--featured" : "",
    isLocationCard ? "mf-discover-card--location" : "",
  ].filter(Boolean).join(" ");

  return (
    <article className={cardClassName} id={getDiscoverCardAnchor(card.id)} tabIndex={-1}>
      <div className="mf-discover-card__icon" aria-hidden="true">
        {isLocationCard
          ? <MapPin size={22} strokeWidth={2.4} />
          : ["today-memory", "territory-stories", "local-memory-secondary"].includes(sectionId)
            ? <Brain size={20} strokeWidth={2.3} />
          : sectionId === "traditional-sayings"
            ? <Speech size={20} strokeWidth={2.3} />
          : sectionId === "archive"
            ? <Library size={20} strokeWidth={2.3} />
          : featured
            ? <Sparkles size={22} strokeWidth={2.4} />
            : <BookOpen size={20} strokeWidth={2.3} />}
      </div>
      <div className="mf-discover-card__body">
        <DiscoverCardMeta seasonLabel={card.seasonLabel} typeLabel={card.typeLabel} />
        <h2>{card.title}</h2>
        {card.text ? <p>{card.text}</p> : null}
        <small>{sourceLabel}</small>
      </div>
    </article>
  );
}

function DiscoverSection({ furPendingLabel, municipalityMilestonesTitle, section, language }) {
  return (
    <section className="mf-discover-section" aria-labelledby={`discover-${section.id}`}>
      <h2 id={`discover-${section.id}`}>{section.title}</h2>
      <div className="mf-discover-grid">
        {section.cards.map((card) => (
          <DiscoverCard
            card={card}
            language={language}
            sectionId={section.id}
            furPendingLabel={furPendingLabel}
            key={card.id}
            municipalityMilestonesTitle={municipalityMilestonesTitle}
          />
        ))}
      </div>
    </section>
  );
}

function DiscoverFocus({ model, municipalityFocus, language, municipalityMode }) {
  if (!model.focus) return null;

  const title = municipalityFocus && municipalityMode
    ? municipalityMode === "detected"
      ? model.copy.detectedMunicipalitySectionTitle
      : model.copy.selectedMunicipalitySectionTitle
    : model.focusTitle;

  return (
    <section className="mf-discover-focus" aria-labelledby="discover-focus-title">
      <h2 className="mf-discover-focus__label" id="discover-focus-title">
        {!municipalityFocus ? <Library aria-hidden="true" size={16} strokeWidth={2.35} /> : null}
        <span>{title}</span>
      </h2>
      <DiscoverCard
        card={model.focus}
        language={language}
        featured
        furPendingLabel={model.copy.furPending}
        internalLabel={municipalityFocus ? model.copy.municipalityKicker : ""}
        municipalityMilestonesTitle={model.copy.municipalityMilestonesTitle}
      />
    </section>
  );
}

export function DiscoverView({
  activeLocation,
  autoLocationEnabled = false,
  copy,
  deviceLocationStatus,
  language,
  municipalityLocation = activeLocation,
  pilotWhyId,
  promotionCampaigns,
}) {
  const [today, setToday] = useState(() => new Date());
  const pilot = isDefinitiveAppExperience();
  const municipalityContext = pilot
    ? getPilotMunicipalityContext({
      activeLocation: municipalityLocation,
      autoLocationEnabled,
      deviceLocationStatus,
    })
    : null;
  const model = buildDiscoverViewModel({
    language,
    location: activeLocation,
    municipalityLocation: pilot ? municipalityContext?.location || null : activeLocation,
    today,
  });
  const locationCopy = LOCATION_COPY[language === "fur" ? "fur" : "it"];
  const municipalityFocus = model.focus?.visualKind === "municipality";
  const [whyVisit] = useState(() => createPilotWhyVisit(pilotWhyId));
  const why = pilot
    ? getPilotWhyContentForVisit({ date: today, language, visit: whyVisit })
    : null;
  const almanac = buildAlmanacViewModel({ date: today, now: today, language, location: activeLocation });
  // The pilot shows only the reviewed short description. Long biographies and
  // source references remain hidden; the shared legacy archive stays intact.
  const calendar = pilot ? buildPilotCalendarSummary(almanac) : almanac;
  const CalendarContainer = pilot ? "article" : "details";
  const CalendarHeader = pilot ? "header" : "summary";
  const orderedSections = [...model.sections].sort((a, b) => {
    const order = ["today-memory", "local-memory-secondary", "traditional-sayings", "rituals", "archive"];
    return order.indexOf(a.id) - order.indexOf(b.id);
  });

  useEffect(() => subscribeToDiscoverDayClock(setToday), []);

  return (
    <TabPage
      className="mf-tab-page--discover"
      language={language}
      title={copy.placeholders.discoverTitle}
      titleMode={pilot ? "hidden" : "visible"}
    >
      <div className={`mf-discover-view${pilot ? " mf-discover-view--editorial" : ""}`}>
        <section className="mf-discover-section" aria-labelledby="discover-calendar-title">
        <div className="mf-discover-calendar-heading">
          <h2 id="discover-calendar-title">{language === "fur" ? "Calendari" : "Calendario"}</h2>
          <p className="mf-discover-calendar-heading__meta">{calendar.seasonLabel} · {calendar.dayProgressLabel}</p>
        </div>
        <CalendarContainer className={`mf-discover-calendar${pilot ? " mf-discover-calendar--pilot" : ""}`}>
          <CalendarHeader className={pilot ? "mf-discover-calendar__static-heading" : undefined}>
            <CalendarDays aria-hidden="true" size={22} />
            <span>
              <span className="mf-discover-card__meta"><span>{calendar.saint.title}</span><span>{calendar.dayLabel}</span></span>
              <strong className="mf-discover-calendar__date mf-discover-calendar__saint">{calendar.saint.label}</strong>
              {calendar.saint.body ? <span className="mf-discover-calendar__brief">{calendar.saint.body}</span> : null}
              {calendar.saint.nameDays.length ? <span className="mf-discover-calendar__namedays">
                {language === "fur" ? calendar.saint.nameDayLabel : "Buon onomastico a"}: {calendar.saint.nameDays.join(" · ")}
              </span> : null}
            </span>
            {!pilot ? <ChevronDown className="mf-discover-calendar__chevron" aria-hidden="true" size={18} /> : null}
          </CalendarHeader>
          {!pilot || calendar.saint.biography.length || calendar.saint.otherSaints.length || calendar.saint.sourceLabel ? <div className="mf-discover-calendar__content">
            {calendar.saint.biography.length
              ? calendar.saint.biography.map((paragraph) => <p className="mf-discover-calendar__story" key={paragraph}>{paragraph}</p>)
              : null}
            {calendar.saint.otherSaints.length ? <OtherSaints key={calendar.dayLabel} saint={calendar.saint} language={language} /> : null}
            {calendar.saint.sourceLabel ? <small className="mf-discover-calendar__source">{language === "fur" ? "Font" : "Fonte"}: {calendar.saint.biographySource || calendar.saint.sourceLabel}</small> : null}
          </div> : null}
        </CalendarContainer>
        </section>
        {pilot ? <PilotWhyCard content={why} /> : null}
        {!pilot && !municipalityFocus ? (
          <LocationContext
            city={getLocationDisplayName(activeLocation, language)}
            prefix={locationCopy.prefix}
          />
        ) : null}

        <DiscoverFocus
          model={model}
          municipalityFocus={municipalityFocus}
          language={language}
          municipalityMode={pilot ? municipalityContext?.mode : undefined}
        />

        {pilot ? (
          <PromotionPlacementCard
            campaigns={promotionCampaigns}
            language={language}
            placement="discover"
          />
        ) : null}

        {orderedSections.filter(section => !pilot || !["traditional-sayings", "rituals", "archive"].includes(section.id)).map((section) => section.id === "local-memory-secondary" && !pilot ? (
          <details className="mf-discover-more-memories" key={section.id}>
            <summary>{section.title}</summary>
            <DiscoverSection section={section} language={language} furPendingLabel={model.copy.furPending} municipalityMilestonesTitle={model.copy.municipalityMilestonesTitle} />
          </details>
        ) : (
          <DiscoverSection
            language={language}
            furPendingLabel={model.copy.furPending}
            key={section.id}
            municipalityMilestonesTitle={model.copy.municipalityMilestonesTitle}
            section={section}
          />
        ))}

        {pilot ? <AlmanacCulture calendar={calendar} sections={orderedSections} language={language} copy={model.copy} excludedCards={[
          model.focus,
          ...orderedSections.filter(section => !["traditional-sayings", "rituals", "archive"].includes(section.id)).flatMap(section => section.cards),
        ].filter(Boolean)} /> : null}

        <p className="mf-discover-source">
          {!pilot ? <MapPin aria-hidden="true" size={14} strokeWidth={2.2} /> : null}
          {model.sourceLine}
        </p>
      </div>
    </TabPage>
  );
}
