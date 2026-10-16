import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

function readAndroidSource(relativePath) {
  return readFileSync(new URL(
    `../../android/app/src/main/${relativePath}`,
    import.meta.url,
  ), "utf8");
}

function expectBefore(source, gate, protectedOperation) {
  const gateIndex = source.indexOf(gate);
  const operationIndex = source.indexOf(protectedOperation);

  expect(gateIndex).toBeGreaterThanOrEqual(0);
  expect(operationIndex).toBeGreaterThan(gateIndex);
}

const pluginSource = readAndroidSource(
  "java/com/meteofriul/app/MeteoBackgroundLocationPlugin.java",
);
const storeSource = readAndroidSource(
  "java/com/meteofriul/app/location/MeteoBackgroundLocationStore.java",
);
const schedulerSource = readAndroidSource(
  "java/com/meteofriul/app/location/MeteoBackgroundLocationScheduler.java",
);
const bootReceiverSource = readAndroidSource(
  "java/com/meteofriul/app/location/MeteoBootReceiver.java",
);
const geofenceReceiverSource = readAndroidSource(
  "java/com/meteofriul/app/location/MeteoGeofenceReceiver.java",
);
const workerSource = readAndroidSource(
  "java/com/meteofriul/app/location/MeteoBackgroundLocationWorker.java",
);
const manifestSource = readAndroidSource("AndroidManifest.xml");

describe("native background-location disclosure gate", () => {
  it("persists consent separately and defaults upgrades to no consent", () => {
    expect(storeSource).toContain('private static final String DISCLOSURE_ACCEPTED = "disclosure_accepted"');
    expect(storeSource).toContain("getBoolean(DISCLOSURE_ACCEPTED, false)");
    expect(storeSource).toContain("return hasDisclosureConsent(context) && isEnabled(context)");
    expect(storeSource).toMatch(
      /disableIfDisclosureConsentMissing[\s\S]*configure\(context, false, "", false\)/,
    );
  });

  it("accepts the explicit JS consent flag and cannot enable without it", () => {
    expect(pluginSource).toContain('call.getBoolean("disclosureAccepted", false)');
    expect(pluginSource).toContain("boolean enabled = requestedEnabled && disclosureAccepted");
    expect(pluginSource).toMatch(
      /MeteoBackgroundLocationStore\.configure\([\s\S]*disclosureAccepted[\s\S]*\)/,
    );
    expect(pluginSource).toContain(
      "boolean configured = MeteoBackgroundLocationStore.isCollectionAllowed(getContext())",
    );
  });

  it("gates package-replaced, geofence, and worker entry points before collection", () => {
    expect(manifestSource).toContain("android.intent.action.MY_PACKAGE_REPLACED");
    expectBefore(
      bootReceiverSource,
      "disableIfDisclosureConsentMissing(context)",
      "schedulePeriodic(context)",
    );
    expectBefore(
      geofenceReceiverSource,
      "isCollectionAllowed(context)",
      "GeofencingEvent.fromIntent(intent)",
    );
    expectBefore(
      workerSource,
      "isCollectionAllowed(context)",
      "acquireLocation(context)",
    );
  });

  it("gates every scheduler entry point before enqueuing work or a geofence", () => {
    const periodicSource = schedulerSource.slice(
      schedulerSource.indexOf("public static void schedulePeriodic"),
      schedulerSource.indexOf("public static void enqueueImmediate"),
    );
    const immediateSource = schedulerSource.slice(
      schedulerSource.indexOf("public static void enqueueImmediate"),
      schedulerSource.indexOf("public static void disable"),
    );
    const geofenceSource = schedulerSource.slice(
      schedulerSource.indexOf("public static boolean registerExitGeofence"),
      schedulerSource.indexOf("private static PendingIntent geofenceIntent"),
    );

    expectBefore(periodicSource, "isCollectionAllowed(context)", "enqueueUniquePeriodicWork");
    expectBefore(immediateSource, "isCollectionAllowed(context)", "enqueueUniqueWork");
    expectBefore(geofenceSource, "isCollectionAllowed(context)", "addGeofences");
  });
});
