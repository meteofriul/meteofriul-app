package com.meteofriul.app.location;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.regex.Pattern;

public final class MeteoBackgroundLocationStore {
    private static final String PREFERENCES = "meteofriul_background_location_v1";
    private static final String DISCLOSURE_ACCEPTED = "disclosure_accepted";
    private static final String ENABLED = "enabled";
    private static final String INSTALLATION_ID_KEY = "installation_id";
    private static final Pattern INSTALLATION_ID = Pattern.compile("^[a-f0-9]{32}$");

    private MeteoBackgroundLocationStore() {}

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
    }

    public static boolean isValidInstallationId(String value) {
        return value != null && INSTALLATION_ID.matcher(value.trim().toLowerCase()).matches();
    }

    public static void configure(
        Context context,
        boolean enabled,
        String installationId,
        boolean disclosureAccepted
    ) {
        boolean collectionEnabled = enabled && disclosureAccepted;
        SharedPreferences.Editor editor = preferences(context).edit()
            .putBoolean(DISCLOSURE_ACCEPTED, disclosureAccepted)
            .putBoolean(ENABLED, collectionEnabled);
        if (collectionEnabled && isValidInstallationId(installationId)) {
            editor.putString(INSTALLATION_ID_KEY, installationId.trim().toLowerCase());
        } else if (!collectionEnabled) {
            editor.remove(INSTALLATION_ID_KEY);
        }
        editor.apply();
    }

    public static boolean isEnabled(Context context) {
        return preferences(context).getBoolean(ENABLED, false);
    }

    public static boolean hasDisclosureConsent(Context context) {
        return preferences(context).getBoolean(DISCLOSURE_ACCEPTED, false);
    }

    public static boolean isCollectionAllowed(Context context) {
        return hasDisclosureConsent(context) && isEnabled(context);
    }

    public static boolean disableIfDisclosureConsentMissing(Context context) {
        if (hasDisclosureConsent(context)) return false;

        configure(context, false, "", false);
        return true;
    }

    public static String installationId(Context context) {
        return preferences(context).getString(INSTALLATION_ID_KEY, "");
    }

    public static void recordAttempt(Context context, String trigger, String status) {
        preferences(context).edit()
            .putLong("last_attempt_at", System.currentTimeMillis())
            .putString("last_trigger", safe(trigger, 40))
            .putString("last_status", safe(status, 80))
            .apply();
    }

    public static void recordSuccess(
        Context context,
        String trigger,
        String status,
        String displayName,
        boolean localTargetEligible
    ) {
        preferences(context).edit()
            .putLong("last_attempt_at", System.currentTimeMillis())
            .putLong("last_success_at", System.currentTimeMillis())
            .putString("last_trigger", safe(trigger, 40))
            .putString("last_status", safe(status, 80))
            .putString("last_display_name", safe(displayName, 160))
            .putBoolean("local_target_eligible", localTargetEligible)
            .apply();
    }

    public static long lastAttemptAt(Context context) {
        return preferences(context).getLong("last_attempt_at", 0L);
    }

    public static long lastSuccessAt(Context context) {
        return preferences(context).getLong("last_success_at", 0L);
    }

    public static String lastTrigger(Context context) {
        return preferences(context).getString("last_trigger", "");
    }

    public static String lastStatus(Context context) {
        return preferences(context).getString("last_status", "");
    }

    public static String lastDisplayName(Context context) {
        return preferences(context).getString("last_display_name", "");
    }

    public static boolean localTargetEligible(Context context) {
        return preferences(context).getBoolean("local_target_eligible", false);
    }

    private static String safe(String value, int maxLength) {
        String normalized = value == null ? "" : value.trim();
        return normalized.length() <= maxLength ? normalized : normalized.substring(0, maxLength);
    }
}
