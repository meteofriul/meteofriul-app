// @vitest-environment jsdom

import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SettingsView } from "./SettingsView";

function SettingsHarness({
  backgroundPermission = false,
  onAutomaticLocationChange,
}) {
  const [autoLocationEnabled, setAutoLocationEnabled] = useState(true);
  const [notificationPreferences, setNotificationPreferences] = useState({
    officialAlerts: true,
    weatherNotices: true,
  });

  return (
    <SettingsView
      activeLocation={{ city: "Pordenone", source: "capacitor_geolocation" }}
      autoLocationEnabled={autoLocationEnabled}
      backgroundLocationRuntime={{
        available: true,
        backgroundPermission,
        configured: backgroundPermission,
        trackingActive: backgroundPermission,
      }}
      deviceLocationStatus={{ city: "Pordenone", status: "success" }}
      language="it"
      notificationPreferences={notificationPreferences}
      notificationRuntime={{
        connected: true,
        permission: "granted",
        platform: "android",
        readOnly: false,
        status: "connected",
      }}
      onAutomaticLocationChange={(enabled) => {
        onAutomaticLocationChange(enabled);
        setAutoLocationEnabled(enabled);
      }}
      onNotificationPreferenceChange={(preference, enabled) => {
        setNotificationPreferences((current) => ({
          ...current,
          [preference]: enabled,
        }));
      }}
    />
  );
}

function NationalSettingsHarness({ location, onPreferenceChange, weatherNotices = false }) {
  const [notificationPreferences, setNotificationPreferences] = useState({
    nationalOfficialAlerts: false,
    officialAlerts: true,
    weatherNotices,
  });

  return (
    <SettingsView
      activeLocation={location}
      notificationPreferences={notificationPreferences}
      notificationRuntime={{ permission: "granted", platform: "android", readOnly: false }}
      onNotificationPreferenceChange={(preference, enabled) => {
        onPreferenceChange(preference, enabled);
        setNotificationPreferences((current) => ({ ...current, [preference]: enabled }));
      }}
      productScope={{ sources: {
        nationalAlerts: { status: location.regionCode === "IT-36" ? "unsupported" : "enabled" },
        osmer: { status: location.regionCode === "IT-36" ? "enabled" : "unsupported" },
      } }}
    />
  );
}

describe("SettingsView notification and location independence", () => {
  let container;
  let root;

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    globalThis.IS_REACT_ACT_ENVIRONMENT = false;
  });

  it("does not disable automatic location when weather notices are turned off or on", async () => {
    const onAutomaticLocationChange = vi.fn();

    await act(async () => {
      root.render(
        <SettingsHarness onAutomaticLocationChange={onAutomaticLocationChange} />,
      );
    });

    const positionToggle = () => container.querySelector('[aria-label="Disattiva Posizione"]');
    const noticesToggle = () => container.querySelector('[aria-label$="Avvisi"]');

    expect(positionToggle()?.getAttribute("aria-checked")).toBe("true");
    expect(container.querySelector('[data-background-location-status="permission_required"]'))
      .not.toBeNull();
    expect(noticesToggle()?.getAttribute("aria-checked")).toBe("true");

    await act(async () => noticesToggle().click());

    expect(container.querySelector('[aria-label="Attiva Avvisi"]')?.getAttribute("aria-checked")).toBe("false");
    expect(positionToggle()?.getAttribute("aria-checked")).toBe("true");
    expect(container.querySelector('[data-background-location-status="permission_required"]'))
      .toBeNull();
    expect(onAutomaticLocationChange).not.toHaveBeenCalled();

    await act(async () => container.querySelector('[aria-label="Attiva Avvisi"]').click());

    expect(noticesToggle()?.getAttribute("aria-checked")).toBe("true");
    expect(positionToggle()?.getAttribute("aria-checked")).toBe("true");
    expect(container.querySelector('[data-background-location-status="permission_required"]'))
      .not.toBeNull();
    expect(onAutomaticLocationChange).not.toHaveBeenCalled();
  });

  it("does not change automatic location when official alerts are toggled", async () => {
    const onAutomaticLocationChange = vi.fn();

    await act(async () => {
      root.render(
        <SettingsHarness onAutomaticLocationChange={onAutomaticLocationChange} />,
      );
    });

    const positionToggle = () => container.querySelector('[aria-label="Disattiva Posizione"]');
    const alertsToggle = () => container.querySelector('[aria-label$="Allerte"]');

    expect(positionToggle()?.getAttribute("aria-checked")).toBe("true");
    expect(alertsToggle()?.getAttribute("aria-checked")).toBe("true");

    await act(async () => alertsToggle().click());

    expect(container.querySelector('[aria-label="Attiva Allerte"]')?.getAttribute("aria-checked"))
      .toBe("false");
    expect(positionToggle()?.getAttribute("aria-checked")).toBe("true");
    expect(onAutomaticLocationChange).not.toHaveBeenCalled();
  });

  it("keeps Avvisi enabled and unchanged when moving between FVG and a manually selected national locality", async () => {
    const onPreferenceChange = vi.fn();
    const roma = {
      city: "Roma",
      countryCode: "IT",
      municipality: { istatCode: "058091", name: "Roma" },
      regionCode: "IT-62",
      source: "manual",
    };
    const pordenone = {
      city: "Pordenone",
      countryCode: "IT",
      municipality: { istatCode: "093033", name: "Pordenone" },
      regionCode: "IT-36",
      source: "manual",
    };

    for (const location of [pordenone, roma, pordenone, roma]) {
      await act(async () => root.render(
        <NationalSettingsHarness
          location={location}
          onPreferenceChange={onPreferenceChange}
          weatherNotices
        />,
      ));
      const noticesToggle = container.querySelector('[aria-label="Disattiva Avvisi"]');
      expect(noticesToggle?.getAttribute("aria-checked")).toBe("true");
      expect(noticesToggle?.hasAttribute("disabled")).toBe(false);
    }
    expect(onPreferenceChange).not.toHaveBeenCalled();
  });

  it("does not turn on national alerts from the old FVG consent or change it when returning to FVG", async () => {
    const onPreferenceChange = vi.fn();
    const roma = {
      city: "Roma",
      countryCode: "IT",
      municipality: { istatCode: "058091", name: "Roma" },
      regionCode: "IT-62",
      source: "manual",
    };
    const pordenone = {
      city: "Pordenone",
      countryCode: "IT",
      municipality: { istatCode: "093033", name: "Pordenone" },
      regionCode: "IT-36",
      source: "manual",
    };

    await act(async () => root.render(
      <NationalSettingsHarness location={roma} onPreferenceChange={onPreferenceChange} />,
    ));
    expect(container.querySelector('[aria-label="Attiva Allerte per Roma"]')?.getAttribute("aria-checked"))
      .toBe("false");

    await act(async () => container.querySelector('[aria-label="Attiva Allerte per Roma"]').click());
    expect(onPreferenceChange).toHaveBeenCalledWith("nationalOfficialAlerts", true);
    expect(container.querySelector('[aria-label="Disattiva Allerte per Roma"]')?.getAttribute("aria-checked"))
      .toBe("true");

    await act(async () => root.render(
      <NationalSettingsHarness location={pordenone} onPreferenceChange={onPreferenceChange} />,
    ));
    expect(container.querySelector('[aria-label="Disattiva Allerte"]')?.getAttribute("aria-checked"))
      .toBe("true");
    expect(onPreferenceChange).toHaveBeenCalledTimes(1);
  });
});
