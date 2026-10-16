package com.meteofriul.app.location;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONException;
import org.json.JSONObject;

public final class MeteoBackgroundWeatherStore {
    private static final String PREFERENCES = "meteofriul_background_weather_v1";
    private static final long RECHECK_INTERVAL_MS = 30 * 60 * 1000L;
    private static final double LOCATION_REFRESH_DISTANCE_M = 2_000d;

    private MeteoBackgroundWeatherStore() {}

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
    }

    public static boolean shouldRefresh(
        Context context,
        String city,
        double lat,
        double lon,
        long now
    ) {
        SharedPreferences stored = preferences(context);
        long savedAt = stored.getLong("saved_at", 0L);
        if (savedAt <= 0L || now < savedAt || now - savedAt >= RECHECK_INTERVAL_MS) return true;

        String previousCity = safe(stored.getString("city", ""), 160);
        if (!previousCity.equalsIgnoreCase(safe(city, 160))) return true;

        double previousLat = Double.longBitsToDouble(stored.getLong("lat_bits", 0L));
        double previousLon = Double.longBitsToDouble(stored.getLong("lon_bits", 0L));
        return distanceMeters(previousLat, previousLon, lat, lon) >= LOCATION_REFRESH_DISTANCE_M;
    }

    public static void write(
        Context context,
        String city,
        double lat,
        double lon,
        String trigger,
        JSONObject payload,
        long savedAt
    ) {
        preferences(context).edit()
            .putString("city", safe(city, 160))
            .putLong("lat_bits", Double.doubleToRawLongBits(lat))
            .putLong("lon_bits", Double.doubleToRawLongBits(lon))
            .putString("payload", payload.toString())
            .putLong("saved_at", savedAt)
            .putString("trigger", safe(trigger, 40))
            .apply();
    }

    public static JSONObject readPayload(Context context) {
        String raw = preferences(context).getString("payload", "");
        if (raw == null || raw.trim().isEmpty()) return null;

        try {
            JSONObject payload = new JSONObject(raw);
            return payload.optJSONObject("current") != null && payload.optJSONObject("forecast") != null
                ? payload
                : null;
        } catch (JSONException ignored) {
            return null;
        }
    }

    public static long savedAt(Context context) {
        return preferences(context).getLong("saved_at", 0L);
    }

    public static String city(Context context) {
        return preferences(context).getString("city", "");
    }

    public static double lat(Context context) {
        return Double.longBitsToDouble(preferences(context).getLong("lat_bits", 0L));
    }

    public static double lon(Context context) {
        return Double.longBitsToDouble(preferences(context).getLong("lon_bits", 0L));
    }

    public static String trigger(Context context) {
        return preferences(context).getString("trigger", "");
    }

    private static double distanceMeters(double lat1, double lon1, double lat2, double lon2) {
        if (!isCoordinateValid(lat1, lon1) || !isCoordinateValid(lat2, lon2)) {
            return Double.POSITIVE_INFINITY;
        }

        double deltaLat = Math.toRadians(lat2 - lat1);
        double deltaLon = Math.toRadians(lon2 - lon1);
        double firstLat = Math.toRadians(lat1);
        double secondLat = Math.toRadians(lat2);
        double haversine = Math.pow(Math.sin(deltaLat / 2d), 2d)
            + Math.cos(firstLat) * Math.cos(secondLat) * Math.pow(Math.sin(deltaLon / 2d), 2d);
        return 2d * 6_371_000d * Math.asin(Math.min(1d, Math.sqrt(haversine)));
    }

    private static boolean isCoordinateValid(double lat, double lon) {
        return Double.isFinite(lat)
            && Double.isFinite(lon)
            && lat >= -90d
            && lat <= 90d
            && lon >= -180d
            && lon <= 180d;
    }

    private static String safe(String value, int maxLength) {
        String normalized = value == null ? "" : value.trim();
        return normalized.length() <= maxLength ? normalized : normalized.substring(0, maxLength);
    }
}
