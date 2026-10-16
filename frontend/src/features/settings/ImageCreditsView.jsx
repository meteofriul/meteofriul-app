import { ChevronLeft, ExternalLink } from "lucide-react";

import { TabPage } from "../../ui/layout/TabPage";

const URLS = {
  cams: "https://atmosphere.copernicus.eu/",
  camsDataset: "https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts",
  camsDoi: "https://doi.org/10.24381/a4005cee",
  leafletLicense: "https://github.com/Leaflet/Leaflet/blob/main/LICENSE",
  lucideLicense: "https://github.com/lucide-icons/lucide/blob/main/LICENSE",
  meteoconsLicense: "https://github.com/basmilius/meteocons/blob/main/LICENSE",
  nasaMoon: "https://svs.gsfc.nasa.gov/5587/",
  openStreetMap: "https://www.openstreetmap.org/copyright",
  istatBoundaries: "https://www.istat.it/notizia/confini-delle-unita-amministrative-a-fini-statistici-al-1-gennaio-2018-2/",
  italiaMeteoHub: "https://meteohub.agenziaitaliameteo.it/",
  italiaMeteoLicense: "https://meteohub.agenziaitaliameteo.it/app/license",
  ccBy40: "https://creativecommons.org/licenses/by/4.0/",
  irdatCatalog: "https://irdat.regione.fvg.it/consultatore-dati-ambientali-territoriali/home?language=it",
  osmer: "https://www.meteo.fvg.it/",
  osmerLegal: "https://www.meteo.fvg.it/note-legali.php",
  ostermannCatalogue: "https://www.techeudine.it/biblioteche-digital-furlane/proverbi-friulani-raccolti-dalla-viva-voce-del-popolo",
  ostermannFacsimile: "https://manoscrittisbhu.comune.udine.it/uploads/BDF/LO11116556.pdf",
  protectionCivil: "https://www.protezionecivile.fvg.it/it/allerte",
  radarDpc: "https://mappe.protezionecivile.gov.it/it/mappe-e-dashboard-rischi/piattaforma-radar/",
  radarDpcLicense: "https://creativecommons.org/licenses/by-sa/4.0/",
  reactLicense: "https://github.com/facebook/react/blob/main/LICENSE",
};

const COPY = {
  it: {
    title: "Informazioni e crediti",
    back: "Indietro",
    sourcesTitle: "Fonti e attribuzioni",
    editorialCredit: "Ideazione, sviluppo e direzione editoriale: Riccardo Rosset",
    independence: "Meteo Friûl è un progetto indipendente: non è un servizio ufficiale e non rappresenta ARPA FVG, OSMER, Protezione Civile, Regione FVG o gli altri enti citati. Per allerte e decisioni di sicurezza consulta sempre le fonti ufficiali.",
    sourceGroups: [
      {
        id: "weather",
        title: "Meteo, allerte e ambiente",
        sources: [
          {
            label: "ARPA FVG – OSMER e GRN",
            detail: "Bollettini e osservazioni meteorologiche regionali.",
            href: URLS.osmer,
            relatedLinks: [{ label: "Note legali", href: URLS.osmerLegal }],
          },
          {
            label: "Protezione Civile FVG",
            detail: "Allerte ufficiali per il Friuli Venezia Giulia.",
            href: URLS.protectionCivil,
          },
          {
            label: "Agenzia ItaliaMeteo · ICON-2I",
            detail: "Previsioni numeriche locali elaborate da Meteo Friûl; dati distribuiti in cooperazione con Arpae Emilia-Romagna Idro-Meteo-Clima.",
            href: URLS.italiaMeteoHub,
            relatedLinks: [{ label: "Licenza e attribuzione · CC BY 4.0", href: URLS.italiaMeteoLicense }],
          },
          {
            label: "CAMS · Copernicus",
            detail: "Previsioni europee elaborate da Meteo Friûl per pollini e composizione atmosferica; nessuna classificazione sanitaria aggiunta.",
            href: URLS.cams,
            relatedLinks: [
              { label: "Dataset", href: URLS.camsDataset },
              { label: "DOI 10.24381/a4005cee", href: URLS.camsDoi },
              { label: "CC BY 4.0", href: URLS.ccBy40 },
            ],
          },
          {
            label: "Radar-DPC",
            detail: "Piattaforma radar del Dipartimento della Protezione Civile.",
            href: URLS.radarDpc,
            relatedLinks: [{ label: "CC BY-SA 4.0", href: URLS.radarDpcLicense }],
          },
        ],
      },
      {
        id: "maps-astronomy",
        title: "Mappe e astronomia",
        sources: [
          {
            label: "OpenStreetMap",
            detail: "© contributori OpenStreetMap · dati cartografici ODbL.",
            href: URLS.openStreetMap,
          },
          {
            label: "ISTAT · Confini amministrativi 2026",
            detail: "Confini comunali usati per determinare il Comune dalle coordinate.",
            href: URLS.istatBoundaries,
            relatedLinks: [{ label: "CC BY 4.0", href: URLS.ccBy40 }],
          },
          {
            label: "Regione FVG · IRDAT",
            detail: "Toponimi territoriali usati per riconoscere località e frazioni.",
            href: URLS.irdatCatalog,
            relatedLinks: [{ label: "IODL 2.0", href: URLS.irdatCatalog }],
          },
          {
            label: "NASA Scientific Visualization Studio",
            detail: "Texture lunare 2026 adattata localmente per dimensione e formato; crediti Ernie Wright (USRA) e Noah Petro (NASA/GSFC).",
            href: URLS.nasaMoon,
          },
        ],
      },
      {
        id: "culture-images",
        title: "Cultura e immagini",
        sources: [
          {
            label: "Valentino Ostermann · Biblioteca Digitale Friulana",
            detail: "Proverbi friulani raccolti dalla viva voce del popolo, edizione 1876.",
            href: URLS.ostermannCatalogue,
            relatedLinks: [{ label: "Facsimile", href: URLS.ostermannFacsimile }],
          },
          {
            label: "Fotografie comunali",
            detail: "Il catalogo dettagliato con autore, fonte e licenza è presente nel progetto, ma non è ancora disponibile in una pagina pubblica.",
            pending: true,
          },
        ],
      },
      {
        id: "open-source",
        title: "Software open source",
        sources: [
          {
            label: "React e React DOM",
            detail: "Licenza MIT.",
            href: URLS.reactLicense,
          },
          {
            label: "Leaflet",
            detail: "Licenza BSD-2-Clause.",
            href: URLS.leafletLicense,
          },
          {
            label: "Lucide",
            detail: "Licenza ISC.",
            href: URLS.lucideLicense,
          },
          {
            label: "Meteocons",
            detail: "Icone meteo di Bas Milius · licenza MIT.",
            href: URLS.meteoconsLicense,
          },
        ],
      },
    ],
  },
  fur: {
    title: "Informazions e credits",
    back: "Indaûr",
    sourcesTitle: "Fonts e atribuzions",
    editorialCredit: "Ideazion, disvilup e direzion editoriâl: Riccardo Rosset",
    independence: "Meteo Friûl al è un progjet indipendent: nol è un servizi uficiâl e nol rapresente ARPA FVG, OSMER, Protezion Civîl, Regjon FVG o chei altris ents nomenâts. Pes alertis e pes decisions di sigurece, consulte simpri lis fonts uficiâls.",
    sourceGroups: [
      {
        id: "weather",
        title: "Meteo, alertis e ambient",
        sources: [
          {
            label: "ARPA FVG – OSMER e GRN",
            detail: "Boletins e osservazions meteorologjichis regjonâls.",
            href: URLS.osmer,
            relatedLinks: [{ label: "Notis legâls", href: URLS.osmerLegal }],
          },
          {
            label: "Protezion Civîl FVG",
            detail: "Alertis uficiâls pal Friûl-Vignesie Julie.",
            href: URLS.protectionCivil,
          },
          {
            label: "Agjenzie ItaliaMeteo · ICON-2I",
            detail: "Previsions numerichis locâls elaboradis di Meteo Friûl; dâts distribuîts in cooperazion cun Arpae Emilia-Romagna Idro-Meteo-Clima.",
            href: URLS.italiaMeteoHub,
            relatedLinks: [{ label: "Licence e atribuzion · CC BY 4.0", href: URLS.italiaMeteoLicense }],
          },
          {
            label: "CAMS · Copernicus",
            detail: "Previsions europeanis elaboradis di Meteo Friûl pai polins e pe composizion atmosferiche; nissune classificazion sanitarie zontade.",
            href: URLS.cams,
            relatedLinks: [
              { label: "Dataset", href: URLS.camsDataset },
              { label: "DOI 10.24381/a4005cee", href: URLS.camsDoi },
              { label: "CC BY 4.0", href: URLS.ccBy40 },
            ],
          },
          {
            label: "Radar-DPC",
            detail: "Plateforme radar dal Dipartiment de Protezion Civîl.",
            href: URLS.radarDpc,
            relatedLinks: [{ label: "CC BY-SA 4.0", href: URLS.radarDpcLicense }],
          },
        ],
      },
      {
        id: "maps-astronomy",
        title: "Mapis e astronomie",
        sources: [
          {
            label: "OpenStreetMap",
            detail: "© colaboradôrs di OpenStreetMap · dâts cartografics ODbL.",
            href: URLS.openStreetMap,
          },
          {
            label: "ISTAT · Confins aministratîfs 2026",
            detail: "Confins comunâi doprâts par determinâ il Comun des coordenadis.",
            href: URLS.istatBoundaries,
            relatedLinks: [{ label: "CC BY 4.0", href: URLS.ccBy40 }],
          },
          {
            label: "Regjon FVG · IRDAT",
            detail: "Toponims teritoriâi doprâts par ricognossi localitâts e frazions.",
            href: URLS.irdatCatalog,
            relatedLinks: [{ label: "IODL 2.0", href: URLS.irdatCatalog }],
          },
          {
            label: "NASA Scientific Visualization Studio",
            detail: "Texture lunâr 2026 adatade in locâl par dimension e formât; credits Ernie Wright (USRA) e Noah Petro (NASA/GSFC).",
            href: URLS.nasaMoon,
          },
        ],
      },
      {
        id: "culture-images",
        title: "Culture e imagjins",
        sources: [
          {
            label: "Valentino Ostermann · Biblioteche Digjitâl Furlane",
            detail: "Proverbis furlans racolts de vive vôs dal popul, edizion 1876.",
            href: URLS.ostermannCatalogue,
            relatedLinks: [{ label: "Facsimil", href: URLS.ostermannFacsimile }],
          },
          {
            label: "Fotografiis comunâls",
            detail: "Il catalic detaiât cun autôr, font e licence al è tal progjet, ma nol è ancjemò disponibil intune pagjine publiche.",
            pending: true,
          },
        ],
      },
      {
        id: "open-source",
        title: "Software open source",
        sources: [
          {
            label: "React e React DOM",
            detail: "Licence MIT.",
            href: URLS.reactLicense,
          },
          {
            label: "Leaflet",
            detail: "Licence BSD-2-Clause.",
            href: URLS.leafletLicense,
          },
          {
            label: "Lucide",
            detail: "Licence ISC.",
            href: URLS.lucideLicense,
          },
          {
            label: "Meteocons",
            detail: "Iconis meteo di Bas Milius · licence MIT.",
            href: URLS.meteoconsLicense,
          },
        ],
      },
    ],
  },
};

function getImageCreditsCopy(language) {
  return COPY[language === "fur" ? "fur" : "it"];
}

function ExternalSourceLink({ children, className = "", href }) {
  return (
    <a className={className} href={href} rel="noreferrer" target="_blank">
      <span>{children}</span>
      <ExternalLink aria-hidden="true" size={13} strokeWidth={2.25} />
    </a>
  );
}

export function ImageCreditsView({
  language = "it",
  onBack,
}) {
  const copy = getImageCreditsCopy(language);

  return (
    <TabPage className="mf-tab-page--image-credits" language={language} title={copy.title}>
      <div className="mf-image-credits-view">
        <button className="mf-settings-back" onClick={onBack} type="button">
          <ChevronLeft aria-hidden="true" size={18} strokeWidth={2.35} />
          <span>{copy.back}</span>
        </button>

        <section className="mf-information-sources" aria-labelledby="app-sources-title">
          <div className="mf-information-sources__intro">
            <h2 id="app-sources-title">{copy.sourcesTitle}</h2>
            <p>{copy.editorialCredit}</p>
            <p>{copy.independence}</p>
          </div>

          {copy.sourceGroups.map((group) => (
            <div className="mf-information-sources__list" key={group.id}>
              <div className="mf-information-sources__heading">
                <h3>{group.title}</h3>
              </div>
              {group.sources.map((source) => (
                <div
                  className={`mf-information-source${source.pending ? " mf-information-source--pending" : ""}`}
                  key={source.label}
                >
                  {source.href ? (
                    <ExternalSourceLink className="mf-information-source__link" href={source.href}>
                      {source.label}
                    </ExternalSourceLink>
                  ) : (
                    <strong>{source.label}</strong>
                  )}
                  <span className="mf-information-source__detail">
                    {source.detail}
                  </span>
                  {source.relatedLinks?.length ? (
                    <div className="mf-information-source__related-links">
                      {source.relatedLinks.map((link) => (
                        <ExternalSourceLink
                          className="mf-information-source__related-link"
                          href={link.href}
                          key={link.href}
                        >
                          {link.label}
                        </ExternalSourceLink>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ))}
        </section>
      </div>
    </TabPage>
  );
}
