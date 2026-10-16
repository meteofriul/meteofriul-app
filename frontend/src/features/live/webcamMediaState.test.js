import { describe, expect, it } from "vitest";

import {
  canAutoRetryWebcamMedia,
  createWebcamMediaState,
  failWebcamMedia,
  getNextWebcamId,
  retryWebcamMedia,
} from "./webcamMediaState";

describe("webcam media state", () => {
  it("treats an external-only record as a labelled static photo from the start", () => {
    const camera = {
      fallbackImageUrl: "/municipalities/photos/032006-photo.webp",
      id: "trieste-miramare",
    };

    expect(createWebcamMediaState(camera)).toEqual({
      liveUnavailable: false,
      mediaState: "loading",
      retryToken: 0,
      sourceKind: "static",
    });
  });

  it("keeps a failed external-only camera selected until the user asks for the next one", () => {
    const camera = {
      fallbackImageUrl: "/municipalities/photos/032006-photo.webp",
      id: "trieste-miramare",
    };
    const failedState = failWebcamMedia(camera, createWebcamMediaState(camera));

    expect(failedState).toMatchObject({ mediaState: "error", sourceKind: "static" });
    expect(failedState).not.toHaveProperty("selectedCameraId");
    expect(getNextWebcamId([{ id: camera.id }], camera.id)).toBe("");
    expect(getNextWebcamId([
      { id: camera.id },
      { id: "trieste-piazza-borsa" },
    ], camera.id)).toBe("trieste-piazza-borsa");
  });

  it("uses a territorial photo on live-frame failure and prepares one automatic retry", () => {
    const camera = {
      fallbackImageUrl: "/municipalities/photos/093037-photo.webp",
      imageUrl: "https://images.example.test/sacile.jpg",
    };
    const fallbackState = failWebcamMedia(camera, createWebcamMediaState(camera));

    expect(fallbackState).toMatchObject({
      liveUnavailable: true,
      mediaState: "loading",
      sourceKind: "static",
    });
    expect(canAutoRetryWebcamMedia(camera, fallbackState)).toBe(true);
    expect(retryWebcamMedia(camera, fallbackState)).toEqual({
      liveUnavailable: false,
      mediaState: "loading",
      retryToken: 1,
      sourceKind: "live",
    });
    expect(canAutoRetryWebcamMedia(camera, retryWebcamMedia(camera, fallbackState))).toBe(false);
  });

  it("does not schedule recovery when a webcam has no image source", () => {
    const camera = { id: "external-only" };

    expect(canAutoRetryWebcamMedia(camera, createWebcamMediaState(camera))).toBe(false);
  });
});
