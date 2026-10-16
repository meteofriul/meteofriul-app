import {
  AlertTriangle,
  ExternalLink,
  MapPinned,
} from "lucide-react";
import { useMemo, useState } from "react";

import { AppTabs } from "../../ui/components/AppTabs";
import { TabPage } from "../../ui/layout/TabPage";
import { BulletinMap } from "./BulletinMap";
import { buildBulletinViewModel } from "./bulletinViewModel";

const COPY = {
  it: {
    alertMeta: "Protezione Civile FVG",
    forecastTitle: "Previsione regionale",
    linkLabel: "www.meteo.fvg.it",
    mapCaption: "Mappa Meteo Friul",
    mapLayerUnavailableText: "La base cartografica resta disponibile. Consulta la fonte OSMER dal link sopra.",
    mapLayerUnavailableStoryText: "La base cartografica resta disponibile. Consulta la fonte OSMER dal link in fondo alla pagina.",
    mapLayerUnavailableTitle: "Dati previsionali non disponibili",
    mapTitle: "Mappa FVG",
    reliabilityLabel: "Attendibilità stimata",
    source: "OSMER ARPA FVG",
    tabsLabel: "Giorni del bollettino",
  },
  fur: {
    alertMeta: "Protezion Civîl FVG",
    forecastTitle: "Prevision regjonâl",
    linkLabel: "www.meteo.fvg.it",
    mapCaption: "Mape Meteo Friul",
    mapLayerUnavailableText: "La base cartografiche e reste disponibile. Consulte la font OSMER dal leam parsore.",
    mapLayerUnavailableStoryText: "La base cartografiche e reste disponibile. Consulte la font OSMER.",
    mapLayerUnavailableTitle: "Dâts previsionâi no disponibii",
    mapTitle: "Mape FVG",
    reliabilityLabel: "Atendibilitât stimade",
    source: "OSMER ARPA FVG",
    tabsLabel: "Dîs dal boletin",
  },
};

const LAB_ALERT_TONES = new Set(["yellow", "orange", "red"]);
const BULLETIN_DAY_PANEL_ID = "bulletin-day-panel";

function getLabAlertPreview(language) {
  if (!import.meta.env.DEV) return null;

  const tone = new URLSearchParams(globalThis.window?.location?.search || "").get("alertTone");
  if (!LAB_ALERT_TONES.has(tone)) return null;

  const labels = language === "fur"
    ? { orange: "Alerte narant", red: "Alerte rosse", yellow: "Alerte zale" }
    : { orange: "Allerta arancione", red: "Allerta rossa", yellow: "Allerta gialla" };
  const level = labels[tone];

  return {
    label: level,
    meta: language === "fur" ? "Protezion Civîl FVG" : "Protezione Civile FVG",
    paragraphs: language === "fur"
      ? [
        "Alerte regjonâl 24 dal 2026 des 18:00 di joibe ai 20/08/26 aes 24:00 di vinars ai 21/08/26: alerte naranç par temporâi fuarts e criticitât idrogjologjiche su dute la regjon.",
        "La fase acute e je previodude des 18:00 aes 24:00 dai 20 di Avost e des 12:00 aes 24:00 dai 21 di Avost 2026.",
      ]
      : [
        "Allerta regionale 24 del 2026 dalle ore 18:00 di giovedì 20/08/26 alle ore 24:00 di venerdì 21/08/26: allerta arancione per temporali forti e criticità idrogeologica su tutta la regione.",
        "La fase acuta dell’evento è prevista dalle ore 18:00 alle ore 24:00 del 20 agosto e dalle ore 12:00 alle 24:00 del 21 agosto 2026.",
      ],
    text: language === "fur"
      ? "Temporâi fuarts e criticitât idrogjologjiche su dute la regjon."
      : "Temporali forti e criticità idrogeologica su tutta la regione.",
    tone,
    validityLabel: "",
  };
}

function getCopy(language) {
  return COPY[language === "fur" ? "fur" : "it"];
}

function shouldPreviewMissingLayer() {
  if (!import.meta.env.DEV) return false;

  return new URLSearchParams(globalThis.window?.location?.search || "").get("bulletinMask") === "missing";
}

export function BulletinView({ copy, language, model, storyLayout = false }) {
  const previewMissingLayer = shouldPreviewMissingLayer();
  const bulletinCopy = getCopy(language);
  const mapCopy = storyLayout
    ? { ...bulletinCopy, mapLayerUnavailableText: bulletinCopy.mapLayerUnavailableStoryText }
    : bulletinCopy;
  const bulletinModel = useMemo(() => {
    const resolvedModel = model || buildBulletinViewModel({}, { language });
    const alertPreview = getLabAlertPreview(language);

    return alertPreview ? { ...resolvedModel, alert: alertPreview } : resolvedModel;
  }, [language, model]);
  const [activeDayId, setActiveDayId] = useState(bulletinModel.activeDayId);
  const activeDay = bulletinModel.days.find((day) => day.id === activeDayId) || bulletinModel.days[0];
  const resolvedActiveDayId = activeDay?.id || bulletinModel.activeDayId;
  const focusItems = Array.isArray(activeDay?.focus) ? activeDay.focus : [];
  const tabItems = useMemo(
    () =>
      bulletinModel.days.map((day, index) => {
        const copyKey = language === "fur" ? "fur" : "it";

        return {
          controlsId: BULLETIN_DAY_PANEL_ID,
          id: day.id,
          label: day.tabLabel || (index === 0 ? day.labels[copyKey] : day.weekdayLabels?.[copyKey] || day.labels[copyKey]),
          meta: day.compactDateLabel,
          tabId: `bulletin-day-tab-${day.id}`,
        };
      }),
    [bulletinModel.days, language],
  );

  const handleDayChange = (dayId) => {
    setActiveDayId(dayId);
  };

  const summary = (
    <section aria-labelledby="bulletin-summary-title" className="mf-bulletin-summary">
      <div className="mf-bulletin-summary__title">
        <MapPinned aria-hidden="true" size={22} strokeWidth={2.25} />
        <span className="mf-bulletin-summary__date">{activeDay.date}</span>
        <h2 id="bulletin-summary-title">{activeDay.summary}</h2>
        {storyLayout && activeDay.reliability ? (
          <span
            aria-label={`${bulletinCopy.reliabilityLabel} ${activeDay.reliability}`}
            className="mf-bulletin-summary__reliability"
          >
            <span>{bulletinCopy.reliabilityLabel}</span>
            <strong>{activeDay.reliability}</strong>
          </span>
        ) : null}
        {!storyLayout ? (
          <a className="mf-bulletin-summary__link" href={bulletinModel.source.url} rel="noreferrer" target="_blank">
            <span>{bulletinModel.source.linkLabel}</span>
            <ExternalLink aria-hidden="true" size={15} strokeWidth={2.25} />
          </a>
        ) : null}
      </div>
      {!storyLayout ? (
        <div
          aria-label={`${bulletinModel.source.label}. ${bulletinModel.source.updatedLabel}`}
          className="mf-bulletin-summary__source"
        >
          <span>{bulletinModel.source.label}</span>
          <span>{bulletinModel.source.updatedLabel}</span>
        </div>
      ) : null}
      <p>{activeDay.text}</p>
      {focusItems.length ? (
        <div className="mf-bulletin-focus-grid">
          {focusItems.map((item) => (
            <article key={item.label}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );

  const sourceFooter = storyLayout ? (
    <footer
      aria-label={`${bulletinModel.source.label}. ${bulletinModel.source.updatedLabel}`}
      className="mf-bulletin-source-footer"
    >
      <div className="mf-bulletin-source-footer__meta">
        <span>{bulletinModel.source.label}</span>
        <span aria-hidden="true">·</span>
        <span>{bulletinModel.source.updatedLabel}</span>
      </div>
      <a href={bulletinModel.source.url} rel="noreferrer" target="_blank">
        <span>{bulletinModel.source.linkLabel}</span>
        <ExternalLink aria-hidden="true" size={13} strokeWidth={2.25} />
      </a>
    </footer>
  ) : null;

  return (
    <TabPage className="mf-tab-page--bulletin" language={language} title={copy.placeholders.bulletinTitle} titleMode="hidden">
      <div className={`mf-bulletin-view${storyLayout ? " mf-bulletin-view--story" : ""}`}>
        {bulletinModel.alert ? (
          <section
            aria-label={bulletinModel.alert.label}
            className="mf-bulletin-alert"
            data-alert-tone={bulletinModel.alert.tone}
            id="official-alerts"
            tabIndex={-1}
          >
            <span className="mf-bulletin-alert__icon">
              <AlertTriangle aria-hidden="true" size={22} strokeWidth={2.35} />
            </span>
            <div className="mf-bulletin-alert__body">
              <span className="mf-bulletin-alert__source">{bulletinModel.alert.meta}</span>
              <strong>{bulletinModel.alert.label}</strong>
            </div>
            <div className="mf-bulletin-alert__content">
              {(bulletinModel.alert.paragraphs?.length
                ? bulletinModel.alert.paragraphs
                : [bulletinModel.alert.text].filter(Boolean)
              ).map((paragraph, index) => (
                <p key={`${bulletinModel.alert.label}-${index}`}>{paragraph}</p>
              ))}
              {bulletinModel.alert.languageNotice ? (
                <span className="mf-bulletin-alert__language-note">
                  {bulletinModel.alert.languageNotice}
                </span>
              ) : null}
              {bulletinModel.alert.validityLabel
                && !bulletinModel.alert.validityIncludedInText ? (
                <span className="mf-bulletin-alert__validity">{bulletinModel.alert.validityLabel}</span>
              ) : null}
            </div>
          </section>
        ) : null}

        <section
          aria-label={storyLayout ? bulletinCopy.forecastTitle : bulletinCopy.mapTitle}
          className="mf-bulletin-map-card"
        >
          <div className="mf-bulletin-tabs">
            <AppTabs
              activeId={resolvedActiveDayId}
              ariaLabel={bulletinCopy.tabsLabel}
              items={tabItems}
              onChange={handleDayChange}
            />
          </div>
          <div
            aria-labelledby={`bulletin-day-tab-${resolvedActiveDayId}`}
            className="mf-bulletin-day-panel"
            id={BULLETIN_DAY_PANEL_ID}
            role="tabpanel"
            tabIndex={0}
          >
            {!storyLayout ? (
              <p
                aria-hidden={activeDay.reliability ? undefined : true}
                aria-label={activeDay.reliability ? `${bulletinCopy.reliabilityLabel} ${activeDay.reliability}` : undefined}
                className={`mf-bulletin-map-meta${activeDay.reliability ? "" : " mf-bulletin-map-meta--empty"}`}
              >
                {activeDay.reliability ? (
                  <>
                    <span>{bulletinCopy.reliabilityLabel}</span>
                    <strong>{activeDay.reliability}</strong>
                  </>
                ) : null}
              </p>
            ) : null}

            <BulletinMap
              copy={mapCopy}
              day={activeDay}
              showOverlay={!previewMissingLayer && activeDay.hasStructuredMap}
            />
            {storyLayout ? summary : null}
            {sourceFooter}
          </div>
        </section>

        {!storyLayout ? summary : null}
      </div>
    </TabPage>
  );
}
