import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ImageCreditsView } from "./ImageCreditsView";

const REQUIRED_SOURCE_URLS = [
  "https://www.meteo.fvg.it/",
  "https://www.protezionecivile.fvg.it/it/allerte",
  "https://meteohub.agenziaitaliameteo.it/",
  "https://meteohub.agenziaitaliameteo.it/app/license",
  "https://atmosphere.copernicus.eu/",
  "https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts",
  "https://doi.org/10.24381/a4005cee",
  "https://mappe.protezionecivile.gov.it/it/mappe-e-dashboard-rischi/piattaforma-radar/",
  "https://www.openstreetmap.org/copyright",
  "https://www.istat.it/notizia/confini-delle-unita-amministrative-a-fini-statistici-al-1-gennaio-2018-2/",
  "https://irdat.regione.fvg.it/consultatore-dati-ambientali-territoriali/home?language=it",
  "https://svs.gsfc.nasa.gov/5587/",
  "https://www.techeudine.it/biblioteche-digital-furlane/proverbi-friulani-raccolti-dalla-viva-voce-del-popolo",
];

describe("ImageCreditsView", () => {
  it("links every principal source and license in Italian", () => {
    const html = renderToStaticMarkup(<ImageCreditsView language="it" />);

    expect(html).toContain("Informazioni e crediti");
    expect(html).toContain("Fonti e attribuzioni");
    expect(html).toContain("Ideazione, sviluppo e direzione editoriale: Riccardo Rosset");
    expect(html).toContain("progetto indipendente");
    expect(html).toContain("non rappresenta ARPA FVG");
    expect(html).toContain("CC BY-SA 4.0");
    expect(html).toContain("ODbL");
    expect(html).toContain("CC BY 4.0");
    expect(html).toContain("Agenzia ItaliaMeteo · ICON-2I");
    expect(html).not.toContain("Open-Meteo");
    expect(html).toContain("nessuna classificazione sanitaria");
    expect(html).toContain("IODL 2.0");
    expect(html).toContain("NASA/GSFC");
    expect(html).toContain("React e React DOM");
    expect(html).toContain("Licenza BSD-2-Clause");
    expect(html).toContain("Licenza ISC");

    REQUIRED_SOURCE_URLS.forEach((url) => {
      expect(html).toContain(`href="${url}"`);
    });

    expect(html).toContain("target=\"_blank\"");
    expect(html).toContain("rel=\"noreferrer\"");
  });

  it("does not invent a public photo catalog or correction contact", () => {
    const html = renderToStaticMarkup(<ImageCreditsView language="it" />);

    expect(html).toContain("non è ancora disponibile in una pagina pubblica");
    expect(html).not.toContain("mailto:");
    expect(html).not.toContain("meteofriul.it/credit");
    expect(html).not.toContain("meteofriul.it/contatt");
  });

  it("renders the same source coverage with coherent Friulian copy", () => {
    const html = renderToStaticMarkup(<ImageCreditsView language="fur" />);

    expect(html).toContain("Informazions e credits");
    expect(html).toContain("Fonts e atribuzions");
    expect(html).toContain("Ideazion, disvilup e direzion editoriâl: Riccardo Rosset");
    expect(html).toContain("progjet indipendent");
    expect(html).toContain("nol rapresente ARPA FVG");
    expect(html).toContain("Meteo, alertis e ambient");
    expect(html).toContain("Agjenzie ItaliaMeteo · ICON-2I");
    expect(html).not.toContain("Open-Meteo");
    expect(html).toContain("Fotografiis comunâls");

    REQUIRED_SOURCE_URLS.forEach((url) => {
      expect(html).toContain(`href="${url}"`);
    });
  });

});
