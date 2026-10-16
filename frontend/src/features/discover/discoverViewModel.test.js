import { describe, expect, it } from "vitest";

import { buildDiscoverViewModel } from "./discoverViewModel";

describe("separate detected municipality from the editorial location", () => {
  const editorialLocation = { city: "Pordenone", istatCode: "093033" };

  it("does not fall back to the editorial municipality when the detected one is explicitly absent", () => {
    const model = buildDiscoverViewModel({
      location: editorialLocation, municipalityLocation: null, today: "2026-09-20",
    });
    expect(model.focus?.visualKind).not.toBe("municipality");
    expect(model.location).toBe(editorialLocation);
    expect(model.sections.length).toBeGreaterThan(0);
  });

  it("uses the detected municipality without moving the editorial context", () => {
    const model = buildDiscoverViewModel({
      location: editorialLocation,
      municipalityLocation: { city: "Udine", istatCode: "030129" },
      today: "2026-09-20",
    });
    expect(model.focus).toMatchObject({ id: "municipality-profile-udine", visualKind: "municipality" });
    expect(model.location).toBe(editorialLocation);
  });

  it("retains the existing municipality selection for callers that do not opt in", () => {
    const model = buildDiscoverViewModel({ location: editorialLocation, today: "2026-09-20" });
    expect(model.focus).toMatchObject({ id: "municipality-profile-pordenone", visualKind: "municipality" });
    expect(model.focusTitle).toBe("Comune del giorno");
  });
});

const readyRecords = [
  {
    id: "ready-2",
    section: "almanacco",
    type: "vento",
    seasons: ["estate"],
    priority: 2,
    editorialStatus: "ready_it",
    languageStatus: { fur: "approved" },
    title: { it: "Vento", fur: "Vint" },
    text: { it: "Testo vento.", fur: "Test dal vint." },
    source: { label: "Ostermann 1894" },
  },
  {
    id: "ready-1",
    section: "riti_credenze_popolari",
    type: "rito",
    seasons: ["all"],
    priority: 1,
    editorialStatus: "ready_it",
    languageStatus: { fur: "approved" },
    title: { it: "Fuochi", fur: "Fucs" },
    text: { it: "Testo fuochi.", fur: "Test dai fucs." },
    source: { label: "Ostermann 1894" },
  },
  {
    id: "backlog",
    section: "archivio",
    type: "contesto",
    priority: 0,
    editorialStatus: "backlog_extracted",
    languageStatus: { fur: "pending_review" },
    title: { it: "Non pronto", fur: "pending_review" },
    text: { it: "Non deve comparire.", fur: "pending_review" },
  },
];

const readyLocalMemory = {
  categories: {
    storia: { it: "Storia locale", fur: "Storie locâl" },
  },
  records: [
    {
      id: "memory-ready",
      primaryUse: "discover",
      category: "storia",
      dateAnchors: ["07-03"],
      priority: 1,
      title: { it: "Accadde oggi", fur: "Al è sucedût vuê" },
      summary: { it: "Una pillola locale verificata.", fur: "Une pilule locâl verificade." },
      source: { label: "Fonte verificata", type: "verified_source" },
      editorialStatus: "ready_for_discover",
      languageStatus: { it: "approved", fur: "approved" },
      readyForUi: true,
    },
  ],
};

describe("buildDiscoverViewModel", () => {
  it("uses only curated UI-ready records and orders them by priority", () => {
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: { records: [] },
      sourceRecords: readyRecords,
      traditionalSayingsSource: { records: [] },
    });

    expect(model.count).toBe(2);
    expect(model.focus.title).toBe("Fuochi");
    expect(model.sections.flatMap((section) => section.cards).some((card) => card.id === "backlog")).toBe(false);
  });

  it("keeps an explicitly blocked curated record outside the UI", () => {
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: { records: [] },
      sourceRecords: [{
        ...readyRecords[0],
        id: "blocked-ready-record",
        recurrence: "always",
        readyForUi: false,
      }],
      traditionalSayingsSource: { records: [] },
      today: "2028-08-10",
    });

    expect(model.count).toBe(0);
    expect(model.sections).toEqual([]);
  });

  it("uses approved FUR copy when available", () => {
    const model = buildDiscoverViewModel({
      language: "fur",
      localMemorySource: { records: [] },
      sourceRecords: readyRecords,
      traditionalSayingsSource: { records: [] },
    });

    expect(model.title).toBe("Scuvierç");
    expect(model.focus.title).toBe("Fucs");
    expect(model.focus.text).toBe("Test dai fucs.");
  });

  it("never promotes archive context to the page focus", () => {
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: { records: [] },
      sourceRecords: [
        {
          ...readyRecords[0],
          id: "archive-context",
          recurrence: "always",
          editorialStatus: "archive_context",
          priority: 1,
        },
        {
          ...readyRecords[1],
          id: "ready-focus",
          recurrence: "always",
          priority: 2,
        },
      ],
      traditionalSayingsSource: { records: [] },
      today: "2026-07-11",
    });

    expect(model.focus.id).toBe("ready-focus");
    expect(model.sections.flatMap((section) => section.cards).map((card) => card.id))
      .toContain("archive-context");
  });

  it("hides records from the FUR view when FUR is not approved", () => {
    const sourceRecords = [
      {
        ...readyRecords[0],
        languageStatus: { fur: "short_ready" },
        title: { it: "Titolo italiano" },
        text: { it: "Testo italiano." },
      },
    ];
    const model = buildDiscoverViewModel({
      language: "fur",
      localMemorySource: { records: [] },
      sourceRecords,
      traditionalSayingsSource: { records: [] },
    });

    expect(model.count).toBe(0);
    expect(model.focus).toBeNull();
    expect(model.sections).toEqual([]);
  });

  it("adds local memory only when a record is ready for Scopri", () => {
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: readyLocalMemory,
      sourceRecords: readyRecords,
      traditionalSayingsSource: { records: [] },
      today: "2026-07-03",
    });

    expect(model.sections[0]).toMatchObject({
      id: "today-memory",
      title: "Memoria del giorno",
      role: "exact-date-memory",
      cards: [{ id: "memory-ready", title: "Accadde oggi" }],
    });
    expect(model.sourceLine).toBe("Selezione editoriale Meteo Friul.");
  });

  it("uses a non-duplicated locality card as the first Scopri focus", () => {
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: {
        categories: readyLocalMemory.categories,
        records: [
          readyLocalMemory.records[0],
          {
            ...readyLocalMemory.records[0],
            id: "memory-pordenone-focus",
            areas: ["pordenone", "friuli_venezia_giulia"],
            dateAnchors: ["08-01"],
            localityFocus: {
              temporal: "evergreen",
              targets: [{ scope: "municipality", istatCode: "093033" }],
            },
            title: { it: "Una storia di Pordenone", fur: "Une storie di Pordenon" },
          },
        ],
      },
      location: { city: "Pordenone", region: "Friuli Venezia Giulia" },
      municipalityProfileSource: { profiles: [] },
      sourceRecords: readyRecords,
      traditionalSayingsSource: { records: [] },
      today: "2026-07-03",
    });

    expect(model.focusTitle).toBe("Dal territorio");
    expect(model.focus).toMatchObject({
      id: "memory-pordenone-focus",
      locationLabel: "Pordenone",
      locationScope: "city",
      visualKind: "location",
    });
    expect(model.sections[0]).toMatchObject({
      id: "today-memory",
      cards: [{ id: "memory-ready" }],
    });
    expect(model.sections.flatMap((section) => section.cards).map((card) => card.id))
      .not.toContain(model.focus.id);
  });

  it("uses the approved municipality profile before other territorial focus cards", () => {
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: {
        categories: readyLocalMemory.categories,
        records: [{
          ...readyLocalMemory.records[0],
          id: "older-pordenone-focus",
          localityFocus: {
            temporal: "evergreen",
            targets: [{ scope: "municipality", istatCode: "093033" }],
          },
        }],
      },
      location: { city: "Pordenone", istatCode: "093033" },
      sourceRecords: readyRecords,
      traditionalSayingsSource: { records: [] },
      today: "2026-07-03",
    });

    expect(model.focusTitle).toBe("Comune del giorno");
    expect(model.focus).toMatchObject({
      id: "municipality-profile-pordenone",
      locationLabel: "Pordenone",
      selectionKind: "municipality_profile",
      sourceLabel: "Comune di Pordenone - Storia di Pordenone",
      visualKind: "municipality",
    });
  });

  it("uses the reviewed municipality profile in Scopri FUR", () => {
    const model = buildDiscoverViewModel({
      language: "fur",
      localMemorySource: { records: [] },
      location: { city: "Pordenone", istatCode: "093033" },
      sourceRecords: readyRecords,
      traditionalSayingsSource: { records: [] },
      today: "2026-07-03",
    });

    expect(model.focusTitle).toBe("Comun dal dì");
    expect(model.focus).toMatchObject({
      id: "municipality-profile-pordenone",
      title: "Pordenon, citât dal Noncel",
      selectionKind: "municipality_profile",
      typeLabel: "Il comun",
    });
  });

  it("deduplicates the same editorial candidate across memory and archive pools", () => {
    const duplicateCandidateId = "shared-ostermann-candidate";
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: {
        categories: readyLocalMemory.categories,
        records: [{
          ...readyLocalMemory.records[0],
          candidateId: duplicateCandidateId,
        }],
      },
      location: { city: "Localita senza focus" },
      sourceRecords: [
        {
          ...readyRecords[0],
          candidateId: duplicateCandidateId,
          id: "archive-duplicate",
          priority: 1,
        },
        {
          ...readyRecords[1],
          id: "independent-focus",
          priority: 2,
        },
      ],
      traditionalSayingsSource: { records: [] },
      today: "2026-07-03",
    });
    const visibleCards = [model.focus, ...model.sections.flatMap((section) => section.cards)].filter(Boolean);

    expect(model.focus.id).toBe("independent-focus");
    expect(model.sections.find((section) => section.id === "today-memory")).toMatchObject({
      cards: [{ id: "memory-ready", contentKey: duplicateCandidateId }],
    });
    expect(new Set(visibleCards.map((card) => card.contentKey)).size).toBe(visibleCards.length);
  });

  it("uses the next archive candidate when the preferred one duplicates memory", () => {
    const duplicateCandidateId = "shared-candidate";
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: {
        categories: readyLocalMemory.categories,
        records: [{
          ...readyLocalMemory.records[0],
          candidateId: duplicateCandidateId,
        }],
      },
      location: { city: "Localita senza focus" },
      sourceRecords: [
        {
          ...readyRecords[1],
          id: "evergreen-focus",
          recurrence: "always",
        },
        {
          ...readyRecords[0],
          id: "duplicate-archive",
          candidateId: duplicateCandidateId,
          dateAnchors: ["07-03"],
        },
        {
          ...readyRecords[0],
          id: "archive-fallback",
          recurrence: "always",
          editorialStatus: "archive_context",
        },
      ],
      traditionalSayingsSource: { records: [] },
      today: "2026-07-03",
    });

    expect(model.sections.find((section) => section.id === "archive")).toMatchObject({
      cards: [{ id: "archive-fallback" }],
    });
  });

  it("adds secondary local memories in a separate section", () => {
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: {
        categories: {
          storia: { it: "Storia locale", fur: "Storie local" },
        },
        records: [
          {
            id: "memory-primary",
            primaryUse: "discover",
            category: "storia",
            dailyRole: "primary",
            dateAnchors: ["07-03"],
            priority: 1,
            title: { it: "Memoria principale", fur: "Memorie principâl" },
            summary: { it: "La voce principale del giorno.", fur: "La vôs principâl dal dì." },
            source: { label: "Fonte verificata", type: "verified_source" },
            editorialStatus: "ready_for_discover",
            languageStatus: { it: "approved", fur: "approved" },
            readyForUi: true,
          },
          {
            id: "memory-secondary",
            primaryUse: "discover",
            category: "storia",
            dailyRole: "secondary",
            dateAnchors: ["07-03"],
            priority: 2,
            title: { it: "Voce collegata", fur: "Vôs colegade" },
            summary: { it: "Una seconda memoria da non confondere con la principale.", fur: "Une seconde memorie di no confondi cu la principâl." },
            source: { label: "Fonte verificata", type: "verified_source" },
            editorialStatus: "ready_for_discover",
            languageStatus: { it: "approved", fur: "approved" },
            readyForUi: true,
          },
        ],
      },
      sourceRecords: readyRecords,
      traditionalSayingsSource: { records: [] },
      today: "2026-07-03",
    });

    expect(model.sections[0]).toEqual(expect.objectContaining({
      id: "today-memory",
      title: "Memoria del giorno",
      role: "exact-date-memory",
      cards: [expect.objectContaining({ id: "memory-primary" })],
    }));
    expect(model.sections.find((section) => section.id === "local-memory-secondary"))
      .toEqual(expect.objectContaining({
        title: "Altre memorie",
        role: "exact-date-secondary-memory",
        cards: [expect.objectContaining({ id: "memory-secondary" })],
      }));
    expect(model.sections.findIndex((section) => section.id === "local-memory-secondary"))
      .toBeGreaterThan(model.sections.findIndex((section) => section.id === "archive"));
  });

  it("keeps secondary local memories tied to the active location", () => {
    const localMemorySource = {
      categories: {
        storia: { it: "Storia locale", fur: "Storie local" },
      },
      records: [
        {
          id: "memory-primary",
          primaryUse: "discover",
          category: "storia",
          dailyRole: "primary",
          dateAnchors: ["07-03"],
          priority: 1,
          title: { it: "Memoria principale", fur: "Memorie principal" },
          summary: { it: "La voce principale del giorno.", fur: "La vos principal dal di." },
          source: { label: "Fonte verificata", type: "verified_source" },
          editorialStatus: "ready_for_discover",
          languageStatus: { it: "approved", fur: "approved" },
          readyForUi: true,
        },
        {
          id: "memory-secondary-pn",
          primaryUse: "discover",
          category: "storia",
          dailyRole: "secondary",
          dateAnchors: ["07-03"],
          areas: ["pordenone"],
          priority: 2,
          title: { it: "Voce Pordenone", fur: "Vos Pordenon" },
          summary: { it: "Una memoria locale di Pordenone.", fur: "Une memorie local di Pordenon." },
          source: { label: "Fonte verificata", type: "verified_source" },
          editorialStatus: "ready_for_discover",
          languageStatus: { it: "approved", fur: "approved" },
          readyForUi: true,
        },
        {
          id: "memory-secondary-ts",
          primaryUse: "discover",
          category: "storia",
          dailyRole: "secondary",
          dateAnchors: ["07-03"],
          areas: ["trieste"],
          priority: 3,
          title: { it: "Voce Trieste", fur: "Vos Triest" },
          summary: { it: "Una memoria locale di Trieste.", fur: "Une memorie local di Triest." },
          source: { label: "Fonte verificata", type: "verified_source" },
          editorialStatus: "ready_for_discover",
          languageStatus: { it: "approved", fur: "approved" },
          readyForUi: true,
        },
      ],
    };
    const pordenoneModel = buildDiscoverViewModel({
      language: "it",
      localMemorySource,
      location: { city: "Pordenone", region: "Friuli Venezia Giulia" },
      sourceRecords: readyRecords,
      traditionalSayingsSource: { records: [] },
      today: "2026-07-03",
    });
    const goriziaModel = buildDiscoverViewModel({
      language: "it",
      localMemorySource,
      location: { city: "Gorizia", region: "Friuli Venezia Giulia" },
      sourceRecords: readyRecords,
      traditionalSayingsSource: { records: [] },
      today: "2026-07-03",
    });

    expect(pordenoneModel.sections.find((section) => section.id === "local-memory-secondary")).toMatchObject({
      cards: [{ id: "memory-secondary-pn" }],
    });
    expect(goriziaModel.sections.some((section) => section.id === "local-memory-secondary")).toBe(false);
  });

  it("shows all approved secondary memories for the active location ordered by priority", () => {
    const secondaryRecord = {
      ...readyLocalMemory.records[0],
      dailyRole: "secondary",
      areas: ["pordenone"],
      dateAnchors: ["07-03"],
    };
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: {
        categories: readyLocalMemory.categories,
        records: [
          readyLocalMemory.records[0],
          { ...secondaryRecord, id: "secondary-first", priority: 1 },
          { ...secondaryRecord, id: "secondary-second", priority: 2 },
        ],
      },
      location: { city: "Pordenone", region: "Friuli Venezia Giulia" },
      sourceRecords: readyRecords,
      traditionalSayingsSource: { records: [] },
      today: "2026-07-03",
    });

    expect(model.sections.find((section) => section.id === "local-memory-secondary")?.cards)
      .toEqual([
        expect.objectContaining({ id: "secondary-first" }),
        expect.objectContaining({ id: "secondary-second" }),
      ]);
  });

  it("labels rotating local memory as Storie del territorio", () => {
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: {
        categories: {
          storia: { it: "Storia locale", fur: "Storie local" },
        },
        records: [
          {
            id: "memory-rotation",
            primaryUse: "discover",
            category: "storia",
            dateAnchors: [],
            priority: 1,
            title: { it: "Storia del territorio", fur: "Storie dal teritori" },
            summary: { it: "Una scheda non legata alla data.", fur: "Une schede no leade ae date." },
            source: { label: "Fonte editoriale", type: "editorial_note" },
            editorialStatus: "ready_for_discover",
            languageStatus: { it: "approved", fur: "approved" },
            readyForUi: true,
          },
        ],
      },
      sourceRecords: readyRecords,
      traditionalSayingsSource: { records: [] },
      today: "2026-07-04",
    });

    expect(model.sections[0]).toMatchObject({
      id: "territory-stories",
      title: "Storie del territorio",
      role: "rotation-memory",
      cards: [{ id: "memory-rotation", title: "Storia del territorio" }],
    });
  });

  it("never labels a rotating memory as Memoria del giorno", () => {
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: {
        categories: {
          storia: { it: "Storia locale", fur: "Storie local" },
        },
        records: [
          {
            id: "memory-rotation",
            primaryUse: "discover",
            category: "storia",
            dateAnchors: [],
            priority: 1,
            title: { it: "Rotazione territoriale", fur: "Rotazion teritoriâl" },
            summary: { it: "Scheda editoriale non datata.", fur: "Schede editoriâl no datade." },
            source: { label: "Fonte editoriale", type: "editorial_note" },
            editorialStatus: "ready_for_discover",
            languageStatus: { it: "approved", fur: "approved" },
            readyForUi: true,
          },
        ],
      },
      sourceRecords: [],
      traditionalSayingsSource: { records: [] },
      today: "2026-02-10",
    });

    expect(model.sections).toEqual([
      expect.objectContaining({
        id: "territory-stories",
        title: "Storie del territorio",
        role: "rotation-memory",
        cards: [expect.objectContaining({ selectionKind: "rotation" })],
      }),
    ]);
    expect(model.sections[0].title).not.toBe("Memoria del giorno");
  });

  it("keeps one focus plus selective daily sections instead of publishing archive lists", () => {
    const sourceRecords = [
      ...readyRecords,
      {
        id: "ready-3",
        section: "riti_credenze_popolari",
        type: "rito",
        dateAnchors: ["07-04"],
        seasons: ["estate"],
        priority: 3,
        editorialStatus: "ready_it",
        languageStatus: { fur: "approved" },
        title: { it: "Rito del giorno", fur: "Rit dal di" },
        text: { it: "Un solo rito per la pagina.", fur: "Un sol rit pe pagjine." },
        source: { label: "Ostermann 1894" },
      },
      {
        id: "ready-4",
        section: "almanacco",
        type: "calendario",
        seasons: ["estate"],
        priority: 4,
        editorialStatus: "ready_it",
        languageStatus: { fur: "approved" },
        title: { it: "Calendario", fur: "Calendari" },
        text: { it: "Un solo contesto per la pagina.", fur: "Un sol contest pe pagjine." },
        source: { label: "Ostermann 1894" },
      },
    ];
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: { records: [] },
      sourceRecords,
      traditionalSayingsSource: { records: [] },
      today: "2026-07-04",
    });

    expect(model.focus).toMatchObject({ id: "ready-1", title: "Fuochi" });
    expect(model.sections.map((section) => ({
      id: section.id,
      count: section.cards.length,
    }))).toEqual([
      { id: "rituals", count: 1 },
      { id: "archive", count: 1 },
    ]);
    expect(new Set(model.sections.map((section) => section.id)).size).toBe(model.sections.length);
    expect(new Set(model.sections.flatMap((section) => section.cards.map((card) => card.id))).size)
      .toBe(model.sections.flatMap((section) => section.cards).length);
    expect(model.sourceLine).toBe("Da Ostermann 1894, con selezione editoriale Meteo Friul.");
  });

  it("prefers dated curated Scopri records on their exact day", () => {
    const sourceRecords = [
      ...readyRecords,
      {
        id: "dated-archive",
        section: "archivio_tradizioni",
        type: "calendario",
        seasons: ["estate"],
        priority: 3,
        editorialStatus: "ready_it",
        languageStatus: { fur: "approved" },
        dateAnchors: ["07-12"],
        title: { it: "Sant'Ermacora", fur: "Sant Ermacore" },
        text: { it: "Scheda datata.", fur: "Schede datade." },
        source: { label: "Ostermann 1894" },
      },
      {
        id: "rotation-archive",
        section: "archivio_tradizioni",
        type: "calendario",
        seasons: ["estate"],
        priority: 4,
        editorialStatus: "ready_it",
        languageStatus: { fur: "approved" },
        title: { it: "Archivio generico", fur: "Archivi gjeneric" },
        text: { it: "Scheda di rotazione.", fur: "Schede di rotazion." },
        source: { label: "Ostermann 1894" },
      },
    ];
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: { records: [] },
      sourceRecords,
      traditionalSayingsSource: { records: [] },
      today: "2026-07-12",
    });

    expect(model.sections.find((section) => section.id === "archive")).toMatchObject({
      cards: [{ id: "dated-archive", title: "Sant'Ermacora" }],
    });
  });

  it("handles curated date ranges that cross the end of the year", () => {
    const sourceRecords = [
      ...readyRecords,
      {
        id: "year-crossing-archive",
        section: "archivio_tradizioni",
        type: "calendario",
        seasons: ["inverno"],
        priority: 3,
        editorialStatus: "ready_it",
        languageStatus: { fur: "approved" },
        dateRanges: ["12-26..01-06"],
        title: { it: "Le dodici notti", fur: "Lis dodis gnots" },
        text: { it: "Scheda dell'inverno.", fur: "Schede dal invier." },
        source: { label: "Ostermann 1894" },
      },
    ];
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: { records: [] },
      sourceRecords,
      traditionalSayingsSource: { records: [] },
      today: "2026-01-02",
    });

    expect(model.sections.find((section) => section.id === "archive")).toMatchObject({
      cards: [{ id: "year-crossing-archive", title: "Le dodici notti" }],
    });
  });

  it("adds one Si diceva che card without publishing the full sayings archive", () => {
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: { records: [] },
      sourceRecords: readyRecords,
      traditionalSayingsSource: {
        records: [
          {
            id: "saying-a",
            primaryUse: "discover",
            recommendedSurface: "discover",
            category: "detto_meteo",
            dateAnchors: ["01-02"],
            priority: 1,
            title: { it: "Detto A", fur: "Dit A" },
            summary: { it: "Voce di tradizione.", fur: "Vos di tradizion." },
            dateLabel: { it: "2 gennaio", fur: "2 di Zenar" },
            source: { label: "Ostermann 1894", type: "verified_source" },
            editorialStatus: "ready_for_discover",
            languageStatus: { it: "approved", fur: "approved" },
            readyForUi: true,
          },
          {
            id: "saying-b",
            primaryUse: "discover",
            recommendedSurface: "discover",
            category: "detto_meteo",
            dateAnchors: [],
            priority: 2,
            title: { it: "Detto B", fur: "Dit B" },
            summary: { it: "Non deve apparire insieme.", fur: "No al a di compari insiemi." },
            dateLabel: { it: "rotazione", fur: "rotazion" },
            source: { label: "Ostermann 1894", type: "verified_source" },
            editorialStatus: "ready_for_discover",
            languageStatus: { it: "approved", fur: "approved" },
            readyForUi: true,
          },
        ],
      },
      today: "2026-01-02",
    });

    expect(model.sections.find((section) => section.id === "traditional-sayings")).toMatchObject({
      title: "Si diceva che...",
      cards: [{ id: "saying-a", title: "Detto A" }],
    });
  });

  it("does not rotate dated sayings outside their date", () => {
    const model = buildDiscoverViewModel({
      language: "it",
      localMemorySource: { records: [] },
      sourceRecords: readyRecords,
      traditionalSayingsSource: {
        records: [
          {
            id: "dated-saying",
            primaryUse: "discover",
            recommendedSurface: "discover",
            category: "detto_meteo",
            dateAnchors: ["01-02"],
            priority: 1,
            title: { it: "Detto datato", fur: "Dit datat" },
            summary: { it: "Non deve ruotare fuori data.", fur: "No al a di zirâ fûr date." },
            dateLabel: { it: "2 gennaio", fur: "2 di Zenar" },
            source: { label: "Ostermann 1894", type: "verified_source" },
            editorialStatus: "ready_for_discover",
            languageStatus: { it: "approved", fur: "approved" },
            readyForUi: true,
          },
          {
            id: "undated-saying",
            primaryUse: "discover",
            recommendedSurface: "discover",
            category: "detto_meteo",
            dateAnchors: [],
            priority: 2,
            title: { it: "Detto senza data", fur: "Dit cence date" },
            summary: { it: "Puo ruotare come detto generico.", fur: "Al pues zirâ come dit gjeneric." },
            dateLabel: { it: "rotazione", fur: "rotazion" },
            source: { label: "Ostermann 1894", type: "verified_source" },
            editorialStatus: "ready_for_discover",
            languageStatus: { it: "approved", fur: "approved" },
            readyForUi: true,
          },
        ],
      },
      today: "2026-01-05",
    });

    expect(model.sections.find((section) => section.id === "traditional-sayings")).toMatchObject({
      cards: [{ id: "undated-saying", title: "Detto senza data" }],
    });
  });
});
