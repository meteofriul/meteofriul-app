import { describe, expect, it, vi } from "vitest";

import { createLocationSelectionController } from "./locationSelectionController";

describe("location selection controller", () => {
  it("waits for the selected location to be prepared", async () => {
    let resolveSelection;
    const onSelect = vi.fn(() => new Promise((resolve) => {
      resolveSelection = resolve;
    }));
    const controller = createLocationSelectionController();
    const pending = controller.select({ city: "Udine" }, onSelect);

    expect(controller.pending).toBe(true);
    expect(onSelect).toHaveBeenCalledWith({ city: "Udine" });

    resolveSelection({ city: "Udine" });

    await expect(pending).resolves.toEqual({
      status: "success",
      value: { city: "Udine" },
    });
    expect(controller.pending).toBe(false);
  });

  it("reports a failed preparation without committing a selection", async () => {
    const error = new Error("ICON non disponibile");
    const controller = createLocationSelectionController();

    await expect(controller.select(
      { city: "Udine" },
      vi.fn().mockRejectedValue(error),
    )).resolves.toEqual({ status: "error", error });
    expect(controller.pending).toBe(false);
  });

  it("blocks a second selection while the first one is pending", async () => {
    let resolveSelection;
    const onSelect = vi.fn(() => new Promise((resolve) => {
      resolveSelection = resolve;
    }));
    const controller = createLocationSelectionController();
    const first = controller.select({ city: "Udine" }, onSelect);

    await expect(controller.select({ city: "Trieste" }, onSelect))
      .resolves.toEqual({ status: "busy" });
    expect(onSelect).toHaveBeenCalledTimes(1);

    resolveSelection({ city: "Udine" });
    await first;
  });

  it("allows a retry after a failed selection", async () => {
    const controller = createLocationSelectionController();
    const onSelect = vi.fn()
      .mockRejectedValueOnce(new Error("ICON non disponibile"))
      .mockResolvedValueOnce({ city: "Udine" });

    await expect(controller.select({ city: "Udine" }, onSelect))
      .resolves.toMatchObject({ status: "error" });
    await expect(controller.select({ city: "Udine" }, onSelect))
      .resolves.toEqual({
        status: "success",
        value: { city: "Udine" },
      });
    expect(onSelect).toHaveBeenCalledTimes(2);
  });
});
