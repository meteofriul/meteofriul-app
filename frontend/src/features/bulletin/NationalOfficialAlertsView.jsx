import { AlertTriangle, CheckCircle2, ExternalLink, MapPinned } from "lucide-react";

import { EmptyState } from "../../ui/components/EmptyState";
import { TabPage } from "../../ui/layout/TabPage";
import { buildNationalOfficialAlertsViewModel } from "./nationalOfficialAlertsViewModel";

const STATUS_COPY = {
  it: {
    loadingBody: "Stiamo verificando il bollettino nazionale per il Comune selezionato.",
    loadingTitle: "Verifica delle allerte in corso",
    stale: "Dati salvati sul dispositivo; aggiornamento in attesa.",
    unavailableBody: "Il dato ufficiale verificato non è disponibile. Riprova tra poco.",
    unavailableTitle: "Allerte temporaneamente non disponibili",
    missingMunicipalityBody: "Scegli di nuovo il Comune dalla ricerca: il codice ISTAT della località salvata non è verificato.",
    missingMunicipalityTitle: "Comune per le allerte non verificato",
  },
  fur: {
    loadingBody: "O sin daûr a verificâ il boletin nazionâl pal Comun selezionât.",
    loadingTitle: "Verifiche des alertis in cors",
    stale: "Dâts salvâts sul dispositîf; inzornament in spiete.",
    unavailableBody: "Il dât uficiâl verificât nol è disponibil. Torne prove fra pôc.",
    unavailableTitle: "Alertis pal moment no disponibilis",
    missingMunicipalityBody: "Sielç di gnûf il Comun de ricercje: il codiç ISTAT de localitat salvade nol è verificât.",
    missingMunicipalityTitle: "Comun pes alertis no verificât",
  },
};

export function NationalOfficialAlertsView({ copy, language = "it", state }) {
  const statusCopy = STATUS_COPY[language === "fur" ? "fur" : "it"];
  const model = buildNationalOfficialAlertsViewModel(state?.data, { language });
  const missingMunicipality = state?.error === "Codice ISTAT del Comune mancante";

  return (
    <TabPage className="mf-tab-page--bulletin" language={language} title={copy.placeholders.bulletinTitle} titleMode="hidden">
      {!model ? (
        <EmptyState
          body={missingMunicipality
            ? statusCopy.missingMunicipalityBody
            : state?.error ? statusCopy.unavailableBody : statusCopy.loadingBody}
          title={missingMunicipality
            ? statusCopy.missingMunicipalityTitle
            : state?.error ? statusCopy.unavailableTitle : statusCopy.loadingTitle}
        />
      ) : (
        <div className="mf-national-alerts" data-alert-tone={model.highestLevel}>
          <header className="mf-national-alerts__header">
            <span className="mf-national-alerts__icon">
              {model.active
                ? <AlertTriangle aria-hidden="true" size={26} strokeWidth={2.25} />
                : <CheckCircle2 aria-hidden="true" size={26} strokeWidth={2.25} />}
            </span>
            <div>
              <span>{model.authority}</span>
              <h2>{model.title}</h2>
              <strong>{model.municipality}</strong>
            </div>
          </header>

          <section className="mf-national-alerts__zones">
            <h3><MapPinned aria-hidden="true" size={18} />{model.zonesLabel}</h3>
            <p>{model.zoneNames.join(" · ")}</p>
            {model.cautiousMessage ? <small>{model.cautiousMessage}</small> : null}
          </section>

          <div className="mf-national-alerts__days">
            {model.days.map(day => (
              <article data-alert-tone={day.level} key={day.date}>
                <span>{day.dateLabel}</span>
                <strong>{day.levelLabel}</strong>
                <p>{day.activeRisks.length ? day.activeRisks.join(" · ") : model.greenLabel}</p>
              </article>
            ))}
          </div>

          {model.noTransmissionMessage ? (
            <p className="mf-national-alerts__notice">{model.noTransmissionMessage}</p>
          ) : null}
          {state?.isStale ? (
            <p className="mf-national-alerts__notice">{statusCopy.stale}</p>
          ) : null}
          <footer>
            <span>{model.completenessLabel}</span>
            <a href={model.sourceUrl} rel="noreferrer" target="_blank">
              {model.sourceLink}<ExternalLink aria-hidden="true" size={15} />
            </a>
          </footer>
        </div>
      )}
    </TabPage>
  );
}
