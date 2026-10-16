package com.meteofriul.app.pilot;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.IOException;

/** Registered only by src/localPilot/assets/capacitor.plugins.json. */
@CapacitorPlugin(name = "PilotWeatherPrefetch")
public final class PilotWeatherPrefetchPlugin extends Plugin {
    @PluginMethod public void configure(PluginCall call) {
        try {
            synchronized (PilotWeatherPrefetchStore.LOCK) {
                new PilotWeatherPrefetchStore(getContext()).configure(call.getString("baseUrl", ""), call.getString("istatCode", ""));
                PilotWeatherPrefetchScheduler.configure(getContext());
            }
            call.resolve(new JSObject().put("available", true));
        } catch (IOException | RuntimeException error) { call.reject("pilot_prefetch_configuration_failed"); }
    }
    @PluginMethod public void readObject(PluginCall call) {
        try {
            String istatCode = call.getString("istatCode", "");
            PilotWeatherPrefetchCore.RawObject object = new PilotWeatherPrefetchStore(getContext()).readObject(
                call.getString("baseUrl", ""), istatCode, call.getString("provider", ""),
                call.getString("path", ""), call.getString("sha256", ""));
            if (object == null) { call.resolve(new JSObject().put("available", false)); return; }
            call.resolve(new JSObject().put("available", true).put("baseUrl", PilotWeatherPrefetchCore.BASE_URL)
                .put("istatCode", istatCode).put("provider", object.provider).put("path", object.path)
                .put("sha256", object.sha256).put("bodyBytes", object.bodyBytes).put("body", object.body).put("etag", object.etag));
        } catch (IOException | RuntimeException error) { call.resolve(new JSObject().put("available", false)); }
    }
    @PluginMethod public void clear(PluginCall call) {
        try {
            synchronized (PilotWeatherPrefetchStore.LOCK) {
                // Advance the generation before cancelling: an in-flight old worker cannot republish.
                new PilotWeatherPrefetchStore(getContext()).clear();
                PilotWeatherPrefetchScheduler.clear(getContext());
            }
            call.resolve(new JSObject().put("available", true));
        } catch (IOException | RuntimeException error) { call.reject("pilot_prefetch_clear_failed"); }
    }
}
