import { describe, expect, it } from "vitest";

import {
  getApprovedWebcamPlayer,
  hasApprovedWebcamPlayer,
} from "./webcamPlayer";

describe("webcam player approval", () => {
  it("keeps development-only Panomax players closed in production", () => {
    const camera = {
      mediaType: "iframe",
      playerUrl: "https://fornidisopra.panomax.com/",
    };

    expect(getApprovedWebcamPlayer(camera, { dev: false })).toBeNull();
    expect(hasApprovedWebcamPlayer(camera, { dev: false })).toBe(false);
  });

  it("accepts the exact reviewed Gemona player in production", () => {
    const playerUrl = "https://stream-meteoproject.eu/weathercam-player.php?code=18";
    const camera = { mediaType: "iframe", playerUrl };

    expect(getApprovedWebcamPlayer(camera, { dev: false })).toEqual({
      mediaType: "iframe",
      playerUrl,
    });
    expect(hasApprovedWebcamPlayer(camera, { dev: false })).toBe(true);
  });

  it.each([
    "https://fornidisopra.panomax.com/",
    "https://sandanieledelfriuli.panomax.com/",
  ])("accepts the reviewed Panomax player %s only in DEV", (playerUrl) => {
    expect(getApprovedWebcamPlayer(
      { mediaType: "iframe", playerUrl },
      { dev: true },
    )).toEqual({
      mediaType: "iframe",
      playerUrl,
    });
    expect(hasApprovedWebcamPlayer(
      { mediaType: "iframe", playerUrl },
      { dev: true },
    )).toBe(true);
  });

  it("supports snake-case runtime aliases", () => {
    expect(getApprovedWebcamPlayer(
      {
        media_type: "iframe",
        player_url: "https://fornidisopra.panomax.com/",
      },
      { dev: true },
    )).toEqual({
      mediaType: "iframe",
      playerUrl: "https://fornidisopra.panomax.com/",
    });
  });

  it.each([
    { mediaType: "video", playerUrl: "https://fornidisopra.panomax.com/" },
    { mediaType: "iframe", playerUrl: "http://fornidisopra.panomax.com/" },
    { mediaType: "iframe", playerUrl: "https://fornidisopra.panomax.com.evil.test/" },
    { mediaType: "iframe", playerUrl: "https://fornidisopra.panomax.com:444/" },
    { mediaType: "iframe", playerUrl: "https://fornidisopra.panomax.com/?view=live" },
    { mediaType: "iframe", playerUrl: "https://fornidisopra.panomax.com/archive" },
    { mediaType: "iframe", playerUrl: "https://example.test/player" },
    { mediaType: "iframe", playerUrl: "https://stream-meteoproject.eu/weathercam-player.php?code=19" },
    { mediaType: "iframe", playerUrl: "https://stream-meteoproject.eu/weathercam-player.php?code=18&next=1" },
    { mediaType: "iframe", playerUrl: "https://stream-meteoproject.eu/weathercam-player.php?code=18#player" },
    { mediaType: "iframe", playerUrl: "not-a-url" },
    { mediaType: "iframe" },
  ])("rejects an unapproved or malformed player", (camera) => {
    expect(getApprovedWebcamPlayer(camera, { dev: true })).toBeNull();
    expect(hasApprovedWebcamPlayer(camera, { dev: true })).toBe(false);
  });
});
