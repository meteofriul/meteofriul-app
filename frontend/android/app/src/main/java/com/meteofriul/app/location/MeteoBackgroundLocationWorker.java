package com.meteofriul.app.location;

import android.content.Context;
import android.location.Location;
import android.os.SystemClock;

import androidx.annotation.NonNull;
import androidx.core.location.LocationCompat;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import com.google.android.gms.location.CurrentLocationRequest;
import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationServices;
import com.google.android.gms.location.Priority;
import com.google.android.gms.tasks.CancellationTokenSource;
import com.google.android.gms.tasks.Tasks;
import com.google.firebase.FirebaseApp;
import com.google.firebase.appcheck.FirebaseAppCheck;
import com.meteofriul.app.BuildConfig;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;
import java.util.concurrent.TimeUnit;

import javax.net.ssl.HttpsURLConnection;

public final class MeteoBackgroundLocationWorker extends Worker {
    private static final long LOCATION_MAX_AGE_MS = 30 * 1000L;
    private static final long LOCATION_FUTURE_SKEW_MS = 2 * 60 * 1000L;
    private static final float MAX_ACCURACY_M = 250f;
    private static final long FAST_TIMEOUT_SECONDS = 2L;
    private static final long BALANCED_DURATION_MS = 5_000L;
    private static final long BALANCED_TIMEOUT_SECONDS = 7L;
    private static final long PRECISE_DURATION_MS = 18_500L;
    private static final long PRECISE_TIMEOUT_SECONDS = 21L;
    private static final int NETWORK_TIMEOUT_MS = 12_000;

    public MeteoBackgroundLocationWorker(
        @NonNull Context context,
        @NonNull WorkerParameters parameters
    ) {
        super(context, parameters);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context context = getApplicationContext();
        String trigger = normalizeTrigger(
            getInputData().getString(MeteoBackgroundLocationScheduler.INPUT_TRIGGER)
        );

        MeteoBackgroundLocationStore.disableIfDisclosureConsentMissing(context);
        if (!MeteoBackgroundLocationStore.isCollectionAllowed(context)) {
            MeteoBackgroundLocationScheduler.disable(context);
            return Result.success();
        }
        String installationId = MeteoBackgroundLocationStore.installationId(context);
        if (!MeteoBackgroundLocationStore.isValidInstallationId(installationId)) {
            MeteoBackgroundLocationStore.recordAttempt(context, trigger, "not_configured");
            return Result.failure();
        }
        if (!MeteoBackgroundLocationPermissions.hasBackground(context)) {
            MeteoBackgroundLocationStore.recordAttempt(context, trigger, "background_permission_required");
            MeteoBackgroundLocationScheduler.disable(context);
            return Result.success();
        }

        Location location;
        try {
            location = acquireLocation(context);
        } catch (SecurityException error) {
            MeteoBackgroundLocationStore.recordAttempt(context, trigger, "background_permission_required");
            return Result.success();
        } catch (Exception error) {
            MeteoBackgroundLocationStore.recordAttempt(context, trigger, "location_unavailable");
            return Result.retry();
        }
        if (!isReliable(location, LOCATION_MAX_AGE_MS)) {
            MeteoBackgroundLocationStore.recordAttempt(context, trigger, "location_unavailable");
            return Result.retry();
        }

        try {
            UploadResponse response = uploadLocation(
                context,
                installationId,
                location,
                trigger
            );
            if (response.retryable) {
                MeteoBackgroundLocationStore.recordAttempt(context, trigger, response.status);
                return Result.retry();
            }
            if (!response.success) {
                MeteoBackgroundLocationStore.recordAttempt(context, trigger, response.status);
                return Result.success();
            }

            MeteoBackgroundLocationStore.recordSuccess(
                context,
                trigger,
                response.status,
                response.displayName,
                response.localTargetEligible
            );
            MeteoBackgroundLocationScheduler.registerExitGeofence(context, location);
            if (response.hasCanonicalWeatherPoint()) {
                try {
                    MeteoBackgroundWeatherScheduler.enqueue(
                        context,
                        trigger,
                        response.canonicalLatitude,
                        response.canonicalLongitude,
                        response.displayName
                    );
                } catch (RuntimeException ignored) {
                    // Weather prefetch is optional and must never fail location targeting.
                }
            }
            return Result.success();
        } catch (Exception error) {
            MeteoBackgroundLocationStore.recordAttempt(context, trigger, "network_unavailable");
            return Result.retry();
        }
    }

    private static Location acquireLocation(Context context) throws Exception {
        FusedLocationProviderClient client = LocationServices.getFusedLocationProviderClient(context);
        try {
            Location last = Tasks.await(
                client.getLastLocation(),
                FAST_TIMEOUT_SECONDS,
                TimeUnit.SECONDS
            );
            if (isReliable(last, LOCATION_MAX_AGE_MS)) return last;
        } catch (Exception ignored) {
            // A cached fix is only an optimization; continue with a fresh request.
        }

        Location balanced = currentLocation(
            client,
            Priority.PRIORITY_BALANCED_POWER_ACCURACY,
            BALANCED_DURATION_MS,
            BALANCED_TIMEOUT_SECONDS
        );
        if (isReliable(balanced, LOCATION_MAX_AGE_MS)) return balanced;

        Location precise = currentLocation(
            client,
            Priority.PRIORITY_HIGH_ACCURACY,
            PRECISE_DURATION_MS,
            PRECISE_TIMEOUT_SECONDS
        );
        return isReliable(precise, LOCATION_MAX_AGE_MS) ? precise : null;
    }

    private static Location currentLocation(
        FusedLocationProviderClient client,
        int priority,
        long durationMs,
        long timeoutSeconds
    ) throws Exception {
        CancellationTokenSource cancellation = new CancellationTokenSource();
        CurrentLocationRequest request = new CurrentLocationRequest.Builder()
            .setPriority(priority)
            .setDurationMillis(durationMs)
            .setMaxUpdateAgeMillis(0L)
            .build();
        try {
            return Tasks.await(
                client.getCurrentLocation(request, cancellation.getToken()),
                timeoutSeconds,
                TimeUnit.SECONDS
            );
        } finally {
            cancellation.cancel();
        }
    }

    private static boolean isReliable(Location location, long maxAgeMs) {
        if (
            location == null
            || !location.hasAccuracy()
            || location.getAccuracy() < 0f
            || location.getAccuracy() > MAX_ACCURACY_M
            || LocationCompat.isMock(location)
        ) return false;

        long ageFromElapsedMs = Long.MAX_VALUE;
        if (location.getElapsedRealtimeNanos() > 0L) {
            ageFromElapsedMs = TimeUnit.NANOSECONDS.toMillis(
                SystemClock.elapsedRealtimeNanos() - location.getElapsedRealtimeNanos()
            );
        }
        long ageFromWallMs = System.currentTimeMillis() - location.getTime();
        boolean elapsedValid = ageFromElapsedMs >= 0L && ageFromElapsedMs <= maxAgeMs;
        boolean wallValid = ageFromWallMs >= -LOCATION_FUTURE_SKEW_MS && ageFromWallMs <= maxAgeMs;
        return elapsedValid && wallValid;
    }

    private static UploadResponse uploadLocation(
        Context context,
        String installationId,
        Location location,
        String trigger
    ) throws Exception {
        if (FirebaseApp.getApps(context).isEmpty()) {
            return UploadResponse.terminal("app_check_not_configured");
        }

        for (int attempt = 0; attempt < 2; attempt += 1) {
            String token;
            try {
                token = Tasks.await(
                    FirebaseAppCheck.getInstance().getAppCheckToken(attempt > 0),
                    15,
                    TimeUnit.SECONDS
                ).getToken();
            } catch (Exception error) {
                return UploadResponse.retryable("app_check_unavailable");
            }
            if (token == null || token.trim().isEmpty()) {
                return UploadResponse.retryable("app_check_unavailable");
            }

            JSONObject body = new JSONObject();
            body.put("installation_id", installationId);
            body.put("lat", location.getLatitude());
            body.put("lon", location.getLongitude());
            body.put("accuracy_m", location.getAccuracy());
            body.put("captured_at", formatUtc(location.getTime()));
            body.put("trigger", trigger);

            HttpResult result = postJson(
                BuildConfig.METEO_API_BASE + "/push/devices/location",
                token,
                body.toString()
            );
            if ((result.statusCode == 401 || result.statusCode == 403) && attempt == 0) {
                continue;
            }
            if (result.statusCode >= 500 || result.statusCode == 408 || result.statusCode == 429) {
                return UploadResponse.retryable("backend_unavailable");
            }
            if (result.statusCode < 200 || result.statusCode >= 300) {
                if (result.statusCode == 404) return UploadResponse.terminal("device_not_registered");
                if (result.statusCode == 401 || result.statusCode == 403) {
                    return UploadResponse.terminal("app_check_rejected");
                }
                return UploadResponse.terminal("location_rejected");
            }

            JSONObject payload = new JSONObject(result.body == null ? "{}" : result.body);
            String status = safeStatus(payload.optString("status", ""));
            JSONObject dataPoint = payload.optJSONObject("data_point");
            double canonicalLatitude = Double.NaN;
            double canonicalLongitude = Double.NaN;
            if (
                ("resolved".equals(status) || "external_place".equals(status))
                && dataPoint != null
                && isCanonicalDataPointSource(
                    status,
                    dataPoint.optString("source", "")
                )
            ) {
                canonicalLatitude = dataPoint.optDouble("lat", Double.NaN);
                canonicalLongitude = dataPoint.optDouble("lon", Double.NaN);
            }
            return UploadResponse.success(
                status,
                payload.optString("display_name", ""),
                payload.optBoolean("local_target_eligible", false),
                canonicalLatitude,
                canonicalLongitude
            );
        }

        return UploadResponse.terminal("app_check_rejected");
    }

    private static HttpResult postJson(String endpoint, String appCheckToken, String json)
        throws IOException {
        URL url = new URL(endpoint);
        if (!"https".equalsIgnoreCase(url.getProtocol())) {
            throw new IOException("https_required");
        }
        HttpsURLConnection connection = (HttpsURLConnection) url.openConnection();
        connection.setConnectTimeout(NETWORK_TIMEOUT_MS);
        connection.setReadTimeout(NETWORK_TIMEOUT_MS);
        connection.setRequestMethod("POST");
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("X-Firebase-AppCheck", appCheckToken);

        byte[] payload = json.getBytes(StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(payload.length);
        try (OutputStream output = connection.getOutputStream()) {
            output.write(payload);
        }

        int statusCode = connection.getResponseCode();
        InputStream stream = statusCode >= 200 && statusCode < 400
            ? connection.getInputStream()
            : connection.getErrorStream();
        String responseBody = readBody(stream);
        connection.disconnect();
        return new HttpResult(statusCode, responseBody);
    }

    private static String readBody(InputStream stream) throws IOException {
        if (stream == null) return "";
        StringBuilder body = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
            new InputStreamReader(stream, StandardCharsets.UTF_8)
        )) {
            String line;
            while ((line = reader.readLine()) != null) body.append(line);
        }
        return body.toString();
    }

    private static String formatUtc(long timestampMs) {
        SimpleDateFormat formatter = new SimpleDateFormat(
            "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
            Locale.US
        );
        formatter.setTimeZone(TimeZone.getTimeZone("UTC"));
        return formatter.format(new Date(timestampMs));
    }

    private static String normalizeTrigger(String value) {
        String trigger = value == null ? "periodic" : value.trim();
        if (
            "app_foreground".equals(trigger)
            || "boot".equals(trigger)
            || "configure".equals(trigger)
            || "geofence_exit".equals(trigger)
            || "manual_refresh".equals(trigger)
            || "periodic".equals(trigger)
        ) return trigger;
        return "periodic";
    }

    private static String safeStatus(String value) {
        if (
            "ambiguous_boundary".equals(value)
            || "external_place".equals(value)
            || "outside_fvg".equals(value)
            || "resolved".equals(value)
        ) return value;
        return "location_rejected";
    }

    private static boolean isCanonicalDataPointSource(String status, String source) {
        if ("external_place".equals(status)) {
            return "nominatim_place".equals(source);
        }
        return "resolved".equals(status)
            && (
                "rafvg_irdat_5000".equals(source)
                || "municipality_catalog".equals(source)
            );
    }

    private static final class HttpResult {
        final int statusCode;
        final String body;

        HttpResult(int statusCode, String body) {
            this.statusCode = statusCode;
            this.body = body;
        }
    }

    private static final class UploadResponse {
        final boolean success;
        final boolean retryable;
        final String status;
        final String displayName;
        final boolean localTargetEligible;
        final double canonicalLatitude;
        final double canonicalLongitude;

        private UploadResponse(
            boolean success,
            boolean retryable,
            String status,
            String displayName,
            boolean localTargetEligible,
            double canonicalLatitude,
            double canonicalLongitude
        ) {
            this.success = success;
            this.retryable = retryable;
            this.status = status;
            this.displayName = displayName == null ? "" : displayName;
            this.localTargetEligible = localTargetEligible;
            this.canonicalLatitude = canonicalLatitude;
            this.canonicalLongitude = canonicalLongitude;
        }

        boolean hasCanonicalWeatherPoint() {
            boolean eligibleStatus = (
                "resolved".equals(status) && localTargetEligible
            ) || (
                "external_place".equals(status) && !localTargetEligible
            );
            return eligibleStatus
                && !displayName.isEmpty()
                && Double.isFinite(canonicalLatitude)
                && Double.isFinite(canonicalLongitude)
                && canonicalLatitude >= -90d
                && canonicalLatitude <= 90d
                && canonicalLongitude >= -180d
                && canonicalLongitude <= 180d;
        }

        static UploadResponse success(
            String status,
            String displayName,
            boolean eligible,
            double canonicalLatitude,
            double canonicalLongitude
        ) {
            return new UploadResponse(
                true,
                false,
                status,
                displayName,
                eligible,
                canonicalLatitude,
                canonicalLongitude
            );
        }

        static UploadResponse retryable(String status) {
            return new UploadResponse(
                false,
                true,
                status,
                "",
                false,
                Double.NaN,
                Double.NaN
            );
        }

        static UploadResponse terminal(String status) {
            return new UploadResponse(
                false,
                false,
                status,
                "",
                false,
                Double.NaN,
                Double.NaN
            );
        }
    }
}
