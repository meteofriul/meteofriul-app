package com.meteofriul.app;

import android.content.Intent;
import android.net.Uri;
import android.provider.Settings;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.meteofriul.app.location.MeteoBackgroundLocationPermissions;
import com.meteofriul.app.location.MeteoBackgroundLocationScheduler;
import com.meteofriul.app.location.MeteoBackgroundLocationStore;
import com.meteofriul.app.location.MeteoBackgroundWeatherStore;

import org.json.JSONObject;

@CapacitorPlugin(name = "MeteoBackgroundLocation")
public final class MeteoBackgroundLocationPlugin extends Plugin {
    @PluginMethod
    public void configure(PluginCall call) {
        boolean disclosureAccepted = Boolean.TRUE.equals(
            call.getBoolean("disclosureAccepted", false)
        );
        boolean requestedEnabled = Boolean.TRUE.equals(call.getBoolean("enabled", false));
        boolean enabled = requestedEnabled && disclosureAccepted;
        String installationId = call.getString("installationId", "");
        if (enabled && !MeteoBackgroundLocationStore.isValidInstallationId(installationId)) {
            call.reject("background_location_installation_id_invalid");
            return;
        }

        MeteoBackgroundLocationStore.configure(
            getContext(),
            enabled,
            installationId,
            disclosureAccepted
        );
        if (!enabled) {
            MeteoBackgroundLocationScheduler.disable(getContext());
        } else if (MeteoBackgroundLocationPermissions.hasBackground(getContext())) {
            MeteoBackgroundLocationScheduler.schedulePeriodic(getContext());
            MeteoBackgroundLocationScheduler.enqueueImmediate(getContext(), "configure");
        } else {
            MeteoBackgroundLocationScheduler.disable(getContext());
        }
        call.resolve(statusPayload());
    }

    @PluginMethod
    public void getStatus(PluginCall call) {
        if (MeteoBackgroundLocationStore.disableIfDisclosureConsentMissing(getContext())) {
            MeteoBackgroundLocationScheduler.disable(getContext());
            call.resolve(statusPayload());
            return;
        }

        boolean enabled = MeteoBackgroundLocationStore.isCollectionAllowed(getContext());
        if (enabled && MeteoBackgroundLocationPermissions.hasBackground(getContext())) {
            MeteoBackgroundLocationScheduler.schedulePeriodic(getContext());
        } else {
            MeteoBackgroundLocationScheduler.disable(getContext());
        }
        call.resolve(statusPayload());
    }

    @PluginMethod
    public void getWeatherPrefetch(PluginCall call) {
        JSONObject weatherPayload = MeteoBackgroundWeatherStore.readPayload(getContext());
        JSObject payload = new JSObject();
        payload.put("available", weatherPayload != null);
        payload.put("city", MeteoBackgroundWeatherStore.city(getContext()));
        payload.put("lat", MeteoBackgroundWeatherStore.lat(getContext()));
        payload.put("lon", MeteoBackgroundWeatherStore.lon(getContext()));
        payload.put("payload", weatherPayload);
        payload.put("savedAt", MeteoBackgroundWeatherStore.savedAt(getContext()));
        payload.put("trigger", MeteoBackgroundWeatherStore.trigger(getContext()));
        call.resolve(payload);
    }

    @PluginMethod
    public void refreshNow(PluginCall call) {
        if (
            !MeteoBackgroundLocationStore.isCollectionAllowed(getContext())
            || !MeteoBackgroundLocationPermissions.hasBackground(getContext())
        ) {
            call.reject("background_location_not_active");
            return;
        }
        MeteoBackgroundLocationScheduler.schedulePeriodic(getContext());
        MeteoBackgroundLocationScheduler.enqueueImmediate(getContext(), "manual_refresh");
        call.resolve(statusPayload());
    }

    @PluginMethod
    public void openSettings(PluginCall call) {
        Intent intent = new Intent(
            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
            Uri.parse("package:" + getContext().getPackageName())
        );
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        getContext().startActivity(intent);
        call.resolve();
    }

    private JSObject statusPayload() {
        boolean configured = MeteoBackgroundLocationStore.isCollectionAllowed(getContext());
        boolean precise = MeteoBackgroundLocationPermissions.hasPrecise(getContext());
        boolean background = MeteoBackgroundLocationPermissions.hasBackground(getContext());
        JSObject payload = new JSObject();
        payload.put("available", true);
        payload.put("configured", configured);
        payload.put("precisePermission", precise);
        payload.put("backgroundPermission", background);
        payload.put("trackingActive", configured && precise && background);
        payload.put("lastAttemptAt", MeteoBackgroundLocationStore.lastAttemptAt(getContext()));
        payload.put("lastSuccessAt", MeteoBackgroundLocationStore.lastSuccessAt(getContext()));
        payload.put("lastStatus", MeteoBackgroundLocationStore.lastStatus(getContext()));
        payload.put("lastTrigger", MeteoBackgroundLocationStore.lastTrigger(getContext()));
        payload.put("lastDisplayName", MeteoBackgroundLocationStore.lastDisplayName(getContext()));
        payload.put(
            "localTargetEligible",
            MeteoBackgroundLocationStore.localTargetEligible(getContext())
        );
        return payload;
    }
}
