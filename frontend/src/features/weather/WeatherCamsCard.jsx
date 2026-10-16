import { Flower2, Info, Wind } from "lucide-react";
import { CamsSpeciesIcon } from "./CamsSpeciesIcon";

const AIR_FIELDS = [
  ["particulate_matter_2.5um", "PM2.5"],
  ["particulate_matter_10um", "PM10"],
  ["ozone", "Ozono · O₃", "Ozon · O₃"],
  ["nitrogen_dioxide", "Biossido di azoto · NO₂", "Diossit di azot · NO₂"],
];

function formatTimestamp(value) {
  const date = value ? new Date(value) : null;
  return date && Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat("it-IT", {
      timeZone: "Europe/Rome",
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date)
    : "";
}

function formatTime(value) {
  const date = value ? new Date(value) : null;
  return date && Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat("it-IT", {
      timeZone: "Europe/Rome",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date)
    : "";
}

function localDateKey(value) {
  const date = value ? new Date(value) : null;
  return date && Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat("en-CA", {
      timeZone: "Europe/Rome",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(date)
    : "";
}

function DetailFooter({ language, methodology, runAt, sampleStatus, validAt }) {
  const fur = language === "fur";
  const validDateKey = localDateKey(validAt);
  const runDateKey = localDateKey(runAt);
  const includeDate = sampleStatus === "last_known"
    || Boolean(validDateKey && runDateKey && validDateKey !== runDateKey);
  const validLabel = includeDate ? formatTimestamp(validAt) : formatTime(validAt);
  const runLabel = includeDate ? formatTimestamp(runAt) : formatTime(runAt);
  const trace = [
    fur ? "Font: Copernicus CAMS" : "Fonte: Copernicus CAMS",
    validLabel
      ? `${fur ? (includeDate ? "Riferît al" : "Riferît aes") : (includeDate ? "Riferito al" : "Riferito alle")} ${validLabel}`
      : "",
  ].filter(Boolean).join(" · ");

  return <footer className="mf-weather-cams-card__footer mf-weather-cams-card__footer--detail">
    <small className="mf-weather-cams-card__trace">
      {trace}{runLabel ? ` (${fur ? "inz." : "agg."} ${runLabel})` : ""}
    </small>
    <small className="mf-weather-cams-card__method-note">
      <Info aria-hidden="true" size={13} strokeWidth={2.2} />
      <span>{methodology}</span>
    </small>
  </footer>;
}

function AirValues({ air, fields, language }) {
  return <dl className="mf-weather-cams-card__values">{fields.map(([id, it, fur]) => {
    const value = air?.values?.[id];
    return <div key={id}><dt><CamsSpeciesIcon species={id} />{language === "fur" ? fur || it : it}</dt><dd>
      {typeof value === "number" && Number.isFinite(value)
        ? <>{new Intl.NumberFormat("it-IT", { maximumFractionDigits: 1 }).format(value)} <span>µg/m³</span></>
        : "—"}
    </dd></div>;
  })}</dl>;
}

function AirCard({ air, detailMode = false, language, lastKnownLabel, runAt, sampleStatus }) {
  const fur = language === "fur";
  const validLabel = formatTimestamp(air?.valid_at);
  const resolvedRunAt = runAt || air?.run_at;
  return <section className="mf-weather-cams-card">
    <header className="mf-weather-cams-card__header"><Wind aria-hidden="true" size={22} /><div>
      <h2>{fur ? "Cualitât de arie" : "Qualità dell’aria"}</h2>
      <p>{fur ? "Concentrazions previodudis dal model" : "Concentrazioni previste da modello"}</p>
    </div></header>
    {air && sampleStatus === "last_known" ? (
      <p className="mf-weather-cams-card__status" role="status">{lastKnownLabel}</p>
    ) : null}
    {air ? <><AirValues air={air} fields={AIR_FIELDS} language={language} />
      </> : <p>{fur ? "Dâts de arie no disponibii" : "Dati dell’aria non disponibili"}</p>}
    {detailMode ? <DetailFooter
      language={language}
      methodology={fur
        ? "Stime modelistiche su gridele: no sostituìs lis rilevazions des centralinis a tiere."
        : "Stima modellistica su griglia: non sostituisce i rilievi delle centraline al suolo."}
      runAt={resolvedRunAt}
      sampleStatus={sampleStatus}
      validAt={air?.valid_at}
    /> : <footer className="mf-weather-cams-card__footer">
      <small>{fur ? "Font" : "Fonte"}: CAMS / Copernicus{validLabel ? ` · ${fur ? "Dât valit" : "Dato valido"} ${validLabel}` : ""}</small>
    </footer>}
  </section>;
}

const COPY = {
  it: {
    ariaLabel: "Previsione pollinica CAMS separata",
    experimental: "Previsione sperimentale · nessun livello sanitario",
    source: "Fonte: CAMS / Copernicus",
    modelRun: "Emissione del modello",
    validAt: "Valido",
    methodology: "Concentrazioni da simulazioni numeriche: non sostituiscono i bollettini dei campionatori aerobiologici locali delle ARPA.",
  },
  fur: {
    ariaLabel: "Prevision dai polins CAMS separade",
    experimental: "Prevision sperimentâl · nissun nivel sanitari",
    source: "Font: CAMS / Copernicus",
    modelRun: "Corse dal model",
    validAt: "Valit",
    methodology: "Concentrazions di simulazions numerichis: no sostituissin i boletins dai campionadôrs aerobiologjics locâi des ARPA.",
  },
};

function PollenCard({ copy, detailMode = false, language, model }) {
  return <section
    aria-label={copy.ariaLabel}
    className="mf-weather-cams-card"
    data-status={model.status}
  >
    <header className="mf-weather-cams-card__header">
      <span aria-hidden="true" className="mf-weather-cams-card__icon">
        <Flower2 size={22} strokeWidth={2.1} />
      </span>
      <div>
        <h2>{model.heading}</h2>
        <p>{copy.experimental}</p>
      </div>
    </header>

    <p className="mf-weather-cams-card__status" role={model.pollenSampleStatus === "last_known" ? "status" : undefined}>
      {model.pollenSampleStatus === "last_known" ? model.pollenLastKnownLabel : model.note}
    </p>

    {model.status === "available" && model.values.length ? (
      <dl className="mf-weather-cams-card__values">
        {model.values.map((entry) => (
          <div key={entry.id}>
            <dt><CamsSpeciesIcon species={entry.id} />{entry.label}</dt>
            <dd>{entry.displayValue} <span>{model.units}</span></dd>
          </div>
        ))}
      </dl>
    ) : null}

    {detailMode ? <DetailFooter
      language={language}
      methodology={language === "fur"
        ? "Model matematic su largje scjale: no sostituìs i campionadôrs aerobiologjics ARPA."
        : "Modello matematico a larga scala: non sostituisce i campionatori aerobiologici ARPA."}
      runAt={model.runAt}
      sampleStatus={model.pollenSampleStatus}
      validAt={model.validAt}
    /> : <footer className="mf-weather-cams-card__footer">
      <small>{copy.source}</small>
    </footer>}
  </section>;
}

export function WeatherCamsCard({ detailMode = false, language = "it", model, section = "all" }) {
  if (!model) return null;
  const copy = COPY[language === "fur" ? "fur" : "it"];
  const airCard = <AirCard air={model.air} detailMode={detailMode} language={language} lastKnownLabel={model.airLastKnownLabel}
    runAt={model.runAt} sampleStatus={model.airSampleStatus} />;
  const pollenCard = <PollenCard copy={copy} detailMode={detailMode} language={language} model={model} />;

  if (section === "air") return airCard;
  if (section === "pollen") return pollenCard;

  return (
    <section className="mf-weather-environment" aria-label={language === "fur" ? "Arie e polins" : "Aria e pollini"}>
      {airCard}
      {pollenCard}
    </section>
  );
}
