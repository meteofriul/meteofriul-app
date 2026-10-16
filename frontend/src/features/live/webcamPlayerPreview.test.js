import { describe, expect, it } from "vitest";

import {
  createWebcamPlayerPreviewState,
  getLocalWebcamPlayerPreviewMode,
  WEBCAM_PLAYER_PREVIEW_MODE_PANOMAX,
} from "./webcamPlayerPreview";

describe("webcam player local preview", () => {
  it("requires a development build and the exact Panomax query flag", () => {
    expect(getLocalWebcamPlayerPreviewMode({
      dev: true,
      search: "?tab=live&webcamPlayerQa=panomax",
    })).toBe(WEBCAM_PLAYER_PREVIEW_MODE_PANOMAX);
    expect(getLocalWebcamPlayerPreviewMode({
      dev: false,
      search: "?tab=live&webcamPlayerQa=panomax",
    })).toBe("");
    expect(getLocalWebcamPlayerPreviewMode({
      dev: true,
      search: "?tab=live&webcamPlayerQa=unknown",
    })).toBe("");
  });

  it("adds players only to the reviewed records without mutating input", () => {
    const original = {
      community: { payload: { reports: [] } },
      webcams: {
        payload: {
          webcams: [
            { id: "forni-varmost", name: "Forni di Sopra - Malga Varmost" },
            { id: "san-daniele-centro", name: "San Daniele" },
            { id: "trieste-san-giusto", name: "Trieste - San Giusto" },
            { id: "sacile", name: "Sacile" },
          ],
        },
        status: "fresh",
      },
    };
    const preview = createWebcamPlayerPreviewState(original, { dev: true });

    expect(preview).not.toBe(original);
    expect(preview.community).toBe(original.community);
    expect(preview.webcams.payload.webcams).toEqual([
      {
        id: "forni-varmost",
        mediaType: "iframe",
        name: "Forni di Sopra - Malga Varmost",
        playerUrl: "https://fornidisopra.panomax.com/",
      },
      {
        id: "san-daniele-centro",
        mediaType: "iframe",
        name: "San Daniele",
        playerUrl: "https://sandanieledelfriuli.panomax.com/",
      },
      {
        id: "trieste-san-giusto",
        mediaType: "iframe",
        name: "Trieste - San Giusto",
        playerUrl: "https://trieste.panomax.com/",
      },
      { id: "sacile", name: "Sacile" },
    ]);
    expect(original.webcams.payload.webcams[0]).not.toHaveProperty("playerUrl");
  });

  it("cannot inject preview players when the production gate is active", () => {
    const state = {
      webcams: {
        payload: { webcams: [{ id: "forni-varmost", name: "Forni" }] },
        status: "fresh",
      },
    };

    expect(createWebcamPlayerPreviewState(state, { dev: false })).toBe(state);
    expect(state.webcams.payload.webcams[0]).not.toHaveProperty("playerUrl");
  });

  it("keeps an unresolved state unchanged", () => {
    const state = { webcams: { payload: null, status: "loading" } };
    expect(createWebcamPlayerPreviewState(state, { dev: true })).toBe(state);
  });

  it("does not attach the Malga Varmost panorama to the different Chianeit webcam", () => {
    const state = {
      webcams: { payload: { webcams: [{ id: "forni-chianeit", name: "Forni - Chianeit" }] } },
    };
    const preview = createWebcamPlayerPreviewState(state, { dev: true });

    expect(preview.webcams.payload.webcams[0]).not.toHaveProperty("playerUrl");
    expect(preview.webcams.payload.webcams[0].name).toBe("Forni - Chianeit");
  });
});
