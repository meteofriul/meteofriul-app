import { describe, expect, it } from "vitest";

import { buildAlmanacViewModel } from "./almanacViewModel";

describe("buildAlmanacViewModel", () => {
  it("shows the verified Regina name day without treating it as another saint", () => {
    const model = buildAlmanacViewModel({ date: new Date("2026-09-07T12:00:00+02:00"), language: "it" });
    expect(model.saint.nameDays).toContain("Regina");
    expect(model.saint.otherSaints).not.toContain("Regina");
    expect(model.saint.label).toBe("Santa Regina, martire");
  });
  it("adapts real almanac data to the current Almanacco UI contract", () => {
    const model = buildAlmanacViewModel({
      date: new Date("2026-06-24T12:00:00+02:00"),
      now: new Date("2026-06-24T12:00:00+02:00"),
      language: "it",
    });

    expect(model.dayLabel).toBe("Mercoledì 24 giugno");
    expect(model.discoverCta).toBe("Continua in Scopri");
    expect(model.seasonLabel).toBe("Estate");
    expect(model.dayProgressLabel).toBe("Giorno 175");
    expect(model.saint.label).toBe("Natività di san Giovanni Battista");
    expect(model.tradition).toMatchObject({
      label: "Il tempo di San Giovanni",
      source: "Da Ostermann 1894, con selezione editoriale Meteo Friul.",
    });
    expect(model.proverb.body).toBeTruthy();
    expect(model.sun.eventNotice).toBe("");
    expect(model.sun.solarSummary).toBe("Sole alto · 67° sopra l'orizzonte");
    expect(model.moon.phase).toBe("Primo quarto");
    expect(model.moon).not.toHaveProperty("tradition");
    expect(model.earth.items).toHaveLength(1);
  });

  it("keeps Friulian labels visible without falling back to Italian primary saint names", () => {
    const model = buildAlmanacViewModel({
      date: new Date("2026-06-24T12:00:00+02:00"),
      language: "fur",
      now: new Date("2026-06-24T12:00:00+02:00"),
    });

    expect(model.dayLabel).toBe("Miercus 24 Jugn");
    expect(model.discoverCta).toBe("Va a Scuvierç");
    expect(model.seasonLabel).toBe("Istat");
    expect(model.saint.label).toBe("Nativitât di Sant Zuan Batiste");
    expect(model.tradition.label).toBe("Il timp di San Zuan");
    expect(model.moon.phase).toBe("Prin cuart");
  });

  it("shows a solar eclipse notice only when the event is verified, local, and current", () => {
    const solarEvent = {
      date: "2026-08-12",
      notice: {
        fur: "Eclissi parziâl · massim aes 19:18 · cuvierture 12%",
        it: "Eclissi parziale · massimo alle 19:18 · copertura 12%",
      },
      type: "solar_eclipse",
      verified: true,
      visibleFromLocation: true,
    };
    const options = {
      date: new Date("2026-08-12T12:00:00+02:00"),
      now: new Date("2026-08-12T12:00:00+02:00"),
      solarEvent,
    };

    expect(buildAlmanacViewModel({ ...options, language: "it" }).sun.eventNotice).toBe(
      "Eclissi parziale · massimo alle 19:18 · copertura 12%",
    );
    expect(buildAlmanacViewModel({ ...options, language: "fur" }).sun.eventNotice).toBe(
      "Eclissi parziâl · massim aes 19:18 · cuvierture 12%",
    );
    expect(buildAlmanacViewModel({
      ...options,
      date: new Date("2026-08-13T12:00:00+02:00"),
    }).sun.eventNotice).toBe("");
    expect(buildAlmanacViewModel({
      ...options,
      solarEvent: { ...solarEvent, verified: false },
    }).sun.eventNotice).toBe("");
    expect(buildAlmanacViewModel({
      ...options,
      solarEvent: { ...solarEvent, visibleFromLocation: false },
    }).sun.eventNotice).toBe("");
  });

  it("shows the verified profile in both supported languages", () => {
    const model = buildAlmanacViewModel({
      date: new Date("2026-07-22T12:00:00+02:00"),
      language: "it",
    });
    const friulianModel = buildAlmanacViewModel({
      date: new Date("2026-07-22T12:00:00+02:00"),
      language: "fur",
    });

    expect(model.saint.label).toBe("Santa Maria Maddalena");
    expect(model.saint.body).toBe(
      "Discepola di Gesù, lo accompagnò fino alla crocifissione. La mattina di Pasqua fu la prima a incontrare il Risorto e ne annunciò la risurrezione agli altri discepoli.",
    );
    expect(friulianModel.saint.label).toBe("Sante Maria Maddalena");
    expect(friulianModel.saint.body).toBeTruthy();
    expect(friulianModel.saint.body).not.toBe(model.saint.body);
  });

  it("exposes the name day and a normalized secondary saint list", () => {
    const model = buildAlmanacViewModel({
      date: new Date("2026-08-02T12:00:00+02:00"),
      language: "it",
    });

    expect(model.saint.nameDayLabel).toBe("Onomastico");
    expect(model.saint.nameDays).toEqual(["Eusebio", "Gustavo"]);
    expect(model.saint.otherSaints).toHaveLength(14);
    expect(model.saint.otherSaints).toContain("San Giustino Russolillo");
    expect(model.saint.otherSaints.join(" ")).not.toContain("Santissima Trinità");
    expect(model.saint.otherSaintsCollapseLabel).toBe("Mostra meno");
    expect(model.saint.otherSaintsLabel).toBe("Altri santi del giorno");
    expect(model.saint.otherSaintsPreview).toEqual([
      "San Pietro Giuliano Eymard",
      "San Rutilio",
      "Santo Stefano I",
    ]);
    expect(model.saint.otherSaintsRemainder).toBe("e altri 11");
  });

  it("keeps other saints visible in Friulian while preferring reviewed names", () => {
    const pendingModel = buildAlmanacViewModel({
      date: new Date("2026-08-02T12:00:00+02:00"),
      language: "fur",
    });
    const curatedModel = buildAlmanacViewModel({
      date: new Date("2026-02-13T12:00:00+01:00"),
      language: "fur",
    });

    expect(pendingModel.saint.nameDayLabel).toBe("Nons dal dì");
    expect(pendingModel.saint.nameDays).toEqual(["Eusebio", "Gustavo"]);
    expect(pendingModel.saint.otherSaints).toHaveLength(14);
    expect(pendingModel.saint.otherSaintsPreview).toEqual([
      "San Pietro Giuliano Eymard",
      "San Rutilio",
      "Santo Stefano I",
    ]);
    expect(pendingModel.saint.otherSaintsRemainder).toBe("e altris 11");
    expect(pendingModel.saint.otherSaintsCollapseLabel).toBe("Mostre mancul");
    expect(curatedModel.saint.otherSaints).toContain("Sant Martiniano di Atene");
    expect(curatedModel.saint.otherSaintsCollapseLabel).toBe("Mostre mancul");
    expect(curatedModel.saint.otherSaintsLabel).toBe("Altris sants dal dì");
    expect(curatedModel.saint.otherSaintsRemainder).toBe("e altris 11");
  });

  it("does not invent a description when the official page has no profile copy", () => {
    const modelWithoutSourceCopy = buildAlmanacViewModel({
      date: new Date("2026-03-30T12:00:00+02:00"),
      language: "it",
    });

    expect(modelWithoutSourceCopy.saint.body).toBe("");
  });

  it("uses the verified leap-day entry instead of rolling into March", () => {
    const leapDayModel = buildAlmanacViewModel({
      date: new Date("2028-02-29T12:00:00+01:00"),
      language: "it",
    });

    expect(leapDayModel.saint.label).toBe("Sant'Ilario, papa");
    expect(leapDayModel.saint.body).toContain("concili di Nicea, Efeso e Calcedonia");

    const leapDayFurModel = buildAlmanacViewModel({
      date: new Date("2028-02-29T12:00:00+01:00"),
      language: "fur",
    });

    expect(leapDayFurModel.saint.label).toBe("Sant Ilario, pape");
    expect(leapDayFurModel.saint.body).toBeTruthy();
  });
});
