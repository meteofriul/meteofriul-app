import { describe, expect, it } from "vitest";

import { selectHomeDiscoverPreview } from "./homeDiscoverPreview";

describe("Home Scopri preview selection", () => {
  it("uses the approved daily-memory rubric instead of the municipality focus", () => {
    const preview = selectHomeDiscoverPreview({
      focus: { id: "municipality-profile-pordenone", title: "Pordenone, città del Noncello" },
      sections: [
        {
          id: "today-memory",
          role: "exact-date-memory",
          title: "Memoria del giorno",
          cards: [{ id: "memory-0906", title: "Una storia del 6 settembre" }],
        },
        {
          id: "archive",
          role: "archive-rotation",
          title: "Archivio e tradizioni",
          cards: [{ id: "archive-1", title: "Una storia d'archivio" }],
        },
      ],
    });

    expect(preview).toEqual({
      heading: "Memoria del giorno",
      id: "memory-0906",
      title: "Una storia del 6 settembre",
    });
  });

  it("falls back to the archive without ever promoting the municipality focus", () => {
    expect(selectHomeDiscoverPreview({
      focus: { id: "municipality-profile-udine", title: "Udine" },
      sections: [
        {
          id: "today-memory",
          role: "exact-date-memory",
          title: "Memoria del giorno",
          cards: [],
        },
        {
          id: "archive",
          title: "Archivio e tradizioni",
          cards: [{ id: "archive-2", title: "Storia d'archivio" }],
        },
      ],
    })).toMatchObject({
      heading: "Archivio e tradizioni",
      id: "archive-2",
    });
  });

  it("returns no placeholder card when Scopri has no editorial sections", () => {
    expect(selectHomeDiscoverPreview({
      focus: { id: "municipality-profile-gorizia", title: "Gorizia" },
      sections: [],
    })).toBeNull();
  });
});
