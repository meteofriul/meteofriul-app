import { useEffect, useState } from "react";
import {
  BookOpenText,
  CalendarDays,
  ChevronDown,
  Church,
  Compass,
  Info,
  MoonStar,
  Sparkles,
  Sprout,
  SunMedium,
} from "lucide-react";

import { TabPage } from "../../ui/layout/TabPage";
import { buildAlmanacViewModel } from "./almanacViewModel";
import { MoonPhaseIcon } from "./MoonPhaseIcon";
import { isDefinitiveAppExperience } from "../../services/localWeatherPilot";

function SunVisual({ sun }) {

  return (
    <div
      className="mf-almanac-sun-summary"
      aria-label={`${sun.daylightSummaryLabel}: ${sun.daylight}`}
    >
      <div className="mf-almanac-sun-phase">
        <div>
          <strong>{sun.daylight}</strong>
          <small>{sun.daylightSummaryLabel}</small>
        </div>
      </div>
      {!sun.cycle ? <div className="mf-almanac-sun-grid">
        <span>
          <strong>{sun.sunrise}</strong>
          <small>{sun.sunriseLabel}</small>
        </span>
        <span>
          <strong>{sun.sunset}</strong>
          <small>{sun.sunsetLabel}</small>
        </span>
      </div> : null}
      {sun.eventNotice ? (
        <p className="mf-almanac-solar-event">
          <Info aria-hidden="true" size={15} strokeWidth={2.25} />
          <span>{sun.eventNotice}</span>
        </p>
      ) : null}
    </div>
  );
}

function MoonVisual({ moon }) {

  return (
    <div className="mf-almanac-sun-phase">
      <div>
        <strong>{moon.nightDuration || "—"}</strong>
        <small>{moon.nightLabel}</small>
        <small>{moon.phase}</small>
      </div>
    </div>
  );
}

export function SkyCard({ model, separateNight = false }) {
  return (
    <section className="mf-almanac-sky-card" aria-label={`${model.sun.title} · ${model.moon.title}`}>
      <article>
        <div className="mf-almanac-panel-title"><span className="mf-almanac-sun-orb" aria-hidden="true" /><h2>{model.sun.title}</h2></div>
        <SunVisual sun={model.sun} />
      </article>
      <article>
        <div className="mf-almanac-panel-title"><span className="mf-almanac-moon-orb" aria-hidden="true"><MoonPhaseIcon cycleProgress={model.moon.cycleProgress} label={model.moon.phase} /></span><h2>{model.moon.title}</h2></div>
        {separateNight ? <div className="mf-sky-moon-summary"><p><strong>{model.moon.phase}</strong></p><small>{model.moon.next}</small></div> : <MoonVisual moon={model.moon} />}
      </article>
      {model.sun.cycle ? <div className={`mf-almanac-cycle${model.sun.cycle.isDay ? "" : " mf-almanac-cycle--night"}`}>
        <div className="mf-almanac-cycle__labels"><span>{model.sun.cycle.startLabel} {model.sun.cycle.start}</span><strong>{model.sun.cycle.label}</strong><span>{model.sun.cycle.endLabel} {model.sun.cycle.end}</span></div>
        <div className="mf-almanac-cycle__track" role="progressbar" aria-label={model.sun.cycle.label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={model.sun.cycle.progress} style={{ "--cycle-progress": `${model.sun.cycle.progress}%` }}>
          <span className="mf-almanac-cycle__fill" />
          <span className="mf-almanac-cycle__marker">{model.sun.cycle.isDay ? <SunMedium size={18} aria-hidden="true" /> : <MoonStar size={18} aria-hidden="true" />}</span>
        </div>
      </div> : null}
      <div className="mf-almanac-sky-details">
        <dl className="mf-almanac-sky-facts">
          {model.skyFacts.map((fact) => <div key={fact.label}>
            <dt>{separateNight ? fact.shortLabel || fact.label : fact.label}</dt>
            <dd>{fact.value}<small>{fact.note}</small></dd>
          </div>)}
        </dl>
        {!separateNight ? <p className="mf-almanac-sky-next"><MoonStar size={20} aria-hidden="true" /><strong>{model.moon.next}</strong></p> : null}
      </div>
    </section>
  );
}

function AlmanacSectionKicker({ children, icon: Icon }) {
  return (
    <div className="mf-almanac-section-kicker">
      <Icon aria-hidden="true" size={17} strokeWidth={2.35} />
      <span>{children}</span>
    </div>
  );
}

function OtherSaintsLine({ saint }) {
  const [expanded, setExpanded] = useState(false);
  const names = expanded ? saint.otherSaints : saint.otherSaintsPreview;
  const actionLabel = expanded ? saint.otherSaintsCollapseLabel : saint.otherSaintsRemainder;

  if (!names.length) return null;

  return (
    <p className="mf-almanac-other-saints-line" aria-label={saint.otherSaintsLabel}>
      <span>{names.join(" · ")}</span>
      {actionLabel ? (
        <>
          <span aria-hidden="true"> · </span>
          <button
            aria-expanded={expanded}
            className="mf-almanac-other-saints-toggle"
            onClick={() => setExpanded((value) => !value)}
            type="button"
          >
            <span>{actionLabel}</span>
            <ChevronDown aria-hidden="true" size={13} strokeWidth={2.5} />
          </button>
        </>
      ) : null}
    </p>
  );
}

export function AlmanacView({ copy, date, language = "it", location, now, onNavigate, solarEvent, weather }) {
  const [clock, setClock] = useState(() => new Date());
  useEffect(() => {
    if (now != null) return undefined;
    const timer = setInterval(() => setClock(new Date()), 60_000);
    return () => clearInterval(timer);
  }, [now]);
  const model = buildAlmanacViewModel({ date: date ?? now ?? clock, language, location, now: now ?? clock, solarEvent, weather });
  const title = copy.placeholders.almanacTitle;

  if (isDefinitiveAppExperience()) return (
    <TabPage className="mf-tab-page--almanac" language={language} title={title}>
      <div className="mf-almanac-view">
        <p>{language === "fur" ? "Lis rubrichis dal Almanac a son in Meteo e Scuvierç." : "Le rubriche dell’Almanacco sono ora in Meteo e Scopri."}</p>
        <button className="mf-almanac-discover-link" type="button" onClick={() => onNavigate?.("weather")}><SunMedium aria-hidden="true" size={18} />{language === "fur" ? "Soreli e Lune" : "Sole e Luna"}</button>
        <button className="mf-almanac-discover-link" type="button" onClick={() => onNavigate?.("discover")}><Compass aria-hidden="true" size={18} />{language === "fur" ? "Calendari, proverbis, tradizions e tiere" : "Calendario, proverbi, tradizioni e terra"}</button>
      </div>
    </TabPage>
  );

  return (
    <TabPage className="mf-tab-page--almanac" language={language} title={title}>
      <div className="mf-almanac-view">
        <section className="mf-almanac-date-strip" aria-label="Data Almanacco">
          <span className="mf-almanac-date-strip__date">
            <CalendarDays aria-hidden="true" size={16} strokeWidth={2.25} />
            {model.dayLabel}
          </span>
          <span>{model.seasonLabel}</span>
          <span>{model.dayProgressLabel}</span>
        </section>

        {isDefinitiveAppExperience()
          ? <button className="mf-almanac-discover-link" onClick={() => onNavigate?.("weather")} type="button">
            <SunMedium aria-hidden="true" size={18} />{language === "fur" ? "Soreli e Lune in Meteo" : "Sole e Luna in Meteo"}
          </button>
          : <SkyCard model={model} />}

        <section className="mf-almanac-saint" aria-label={model.saint.title}>
          <AlmanacSectionKicker icon={Church}>{model.saint.title}</AlmanacSectionKicker>
          <div className="mf-almanac-saint__body">
            <strong>{model.saint.label}</strong>
            {model.saint.body ? <p>{model.saint.body}</p> : null}
          </div>
          {model.saint.nameDays.length ? (
            <div className="mf-almanac-name-day">
              <span className="mf-almanac-name-day__label">{model.saint.nameDayLabel}</span>
              <span className="mf-almanac-name-day__names">{model.saint.nameDays.join(" · ")}</span>
            </div>
          ) : null}
          <OtherSaintsLine key={`${language}-${model.dayLabel}`} saint={model.saint} />
        </section>

        <section className="mf-almanac-culture" aria-label={model.tradition.title}>
          <AlmanacSectionKicker icon={BookOpenText}>{model.tradition.title}</AlmanacSectionKicker>
          <article className="mf-almanac-culture__entry">
            <span>{model.tradition.label}</span>
            <p>{model.tradition.body}</p>
          </article>
          <article className="mf-almanac-culture__entry mf-almanac-culture__entry--proverb">
            <span>
              <Sparkles aria-hidden="true" size={16} strokeWidth={2.25} />
              {model.proverb.title}
            </span>
            <p>{model.proverb.body}</p>
          </article>
        </section>

        {model.earth.items.length ? (
          <section className="mf-almanac-earth" aria-labelledby="almanac-earth-title">
            <div className="mf-almanac-panel-title">
              <Sprout aria-hidden="true" size={22} strokeWidth={2.25} />
              <h2 id="almanac-earth-title">{model.earth.title}</h2>
            </div>
            <p className="mf-almanac-earth__tip">{model.earth.items[0]}</p>
          </section>
        ) : null}

        <button
          className="mf-almanac-discover-link"
          onClick={() => onNavigate?.("discover")}
          type="button"
        >
          <Compass aria-hidden="true" size={18} strokeWidth={2.25} />
          <span>{model.discoverCta}</span>
        </button>
      </div>
    </TabPage>
  );
}
