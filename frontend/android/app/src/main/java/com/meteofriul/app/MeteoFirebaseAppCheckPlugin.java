package com.meteofriul.app;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.firebase.FirebaseApp;
import com.google.firebase.appcheck.FirebaseAppCheck;

@CapacitorPlugin(name = "MeteoFirebaseAppCheck")
public final class MeteoFirebaseAppCheckPlugin extends Plugin {
    @PluginMethod
    public void getToken(PluginCall call) {
        if (FirebaseApp.getApps(getContext()).isEmpty()) {
            call.reject("firebase_app_check_not_configured");
            return;
        }

        final boolean forceRefresh = Boolean.TRUE.equals(call.getBoolean("forceRefresh", false));

        FirebaseAppCheck.getInstance()
            .getAppCheckToken(forceRefresh)
            .addOnSuccessListener(result -> {
                final String token = result == null ? null : result.getToken();
                if (token == null || token.trim().isEmpty()) {
                    call.reject("firebase_app_check_token_missing");
                    return;
                }

                final JSObject response = new JSObject();
                response.put("token", token);
                call.resolve(response);
            })
            .addOnFailureListener(error -> call.reject(
                "firebase_app_check_token_failed",
                error
            ));
    }
}
