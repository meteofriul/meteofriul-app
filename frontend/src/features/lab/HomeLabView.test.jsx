import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HomeLabView } from "./HomeLabView";

const copy = {
  placeholders: {
    homeTitle: "Home",
  },
};

describe("HomeLabView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-12T12:00:00+02:00"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps weather and day phase as independent visual controls", () => {
    const markup = renderToStaticMarkup(<HomeLabView copy={copy} language="it" />);

    expect(markup).toContain('aria-label="Variante meteo"');
    expect(markup).toContain('aria-label="Fase della giornata"');
    expect(markup).toContain('aria-label="Stile delle card informative"');
    expect(markup).toContain(">Sole</button>");
    expect(markup).toContain(">Neve</button>");
    expect(markup).toContain(">Alba</button>");
    expect(markup).toContain(">Tramonto</button>");
    expect(markup).toContain(">Originale</button>");
    expect(markup).toContain(">Linea</button>");
    expect(markup).toContain(">Texture</button>");
    expect(markup).not.toContain(">Nuvoloso notte</button>");
    expect(markup).toContain('data-day-phase="midday"');
    expect(markup).toContain('data-card-style="current"');
    expect(markup.match(/data-card-style="current"/g)).toHaveLength(1);
    expect(markup).toContain('class="mf-home-view mf-home-card-style"');
    expect(markup).toContain("Mercoledì 12 agosto");
    expect(markup).not.toContain("Sant&#x27;Ireneo");
    expect(markup).toContain("Santo del giorno");
    expect(markup).toContain("S. Giovanna Francesca Fremiot de Chantal, religiosa");
    expect(markup).toContain("lucide-book-open-text");
    expect(markup).not.toContain("mf-moon-phase-icon");
    expect(markup).not.toContain("Luna nuova");
    expect(markup).toContain("mf-home-quick-card--events");
    expect(markup).toContain("Notte di musica in centro");
    expect(markup).not.toContain("mf-home-events-card__icon--image");
  });
});
