import { describe, expect, it } from "vitest";

import {
  getSelectedWebcamId,
  rememberWebcamSelection,
} from "./webcamSelectionState";

const GROUP = {
  cameras: [{ id: "first" }, { id: "second" }],
  id: "plain",
};

describe("webcam selection state", () => {
  it("keeps the remembered camera when returning to a category", () => {
    const selections = rememberWebcamSelection({}, GROUP.id, "second");

    expect(getSelectedWebcamId(GROUP, selections[GROUP.id])).toBe("second");
  });

  it("falls back safely when a refreshed catalog removes the remembered camera", () => {
    expect(getSelectedWebcamId(GROUP, "removed-camera")).toBe("first");
  });

  it("does not create a new state object for an unchanged selection", () => {
    const selections = { plain: "second" };

    expect(rememberWebcamSelection(selections, "plain", "second")).toBe(selections);
  });

  it("remembers independent selections for different categories", () => {
    const withPlain = rememberWebcamSelection({}, "plain", "cividale");
    const withMountain = rememberWebcamSelection(withPlain, "mountain", "tarvisio");

    expect(withMountain).toEqual({
      mountain: "tarvisio",
      plain: "cividale",
    });
  });
});
