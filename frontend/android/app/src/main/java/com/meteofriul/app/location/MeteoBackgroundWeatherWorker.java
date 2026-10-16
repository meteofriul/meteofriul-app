package com.meteofriul.app.location;

import android.content.Context;

import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import com.meteofriul.app.BuildConfig;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

import javax.net.ssl.HttpsURLConnection;

public final class MeteoBackgroundWeatherWorker extends Worker {
    private static final int NETWORK_TIMEOUT_MS = 12_000;
    private static final int MAX_RESPONSE_CHARS = 1_000_000;

    public MeteoBackgroundWeatherWorker(
        @NonNull Context context,
        @NonNull WorkerParameters parameters
    ) {
        super(context, parameters);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context context = getApplicationContext();
        String city = safe(getInputData().getString(MeteoBackgroundWeatherScheduler.INPUT_CITY), 160);
        String trigger = safe(getInputData().getString(MeteoBackgroundWeatherScheduler.INPUT_TRIGGER), 40);
        double lat = getInputData().getDouble(MeteoBackgroundWeatherScheduler.INPUT_LAT, Double.NaN);
        double lon = getInputData().getDouble(MeteoBackgroundWeatherScheduler.INPUT_LON, Double.NaN);
        long now = System.currentTimeMillis();

        if (city.isEmpty() || !isCoordinateValid(lat, lon)) return Result.failure();
        if (!MeteoBackgroundWeatherStore.shouldRefresh(context, city, lat, lon, now)) {
            return Result.success();
        }

        try {
            HttpResult result = getWeather(city, lat, lon);
            if (result.statusCode >= 500 || result.statusCode == 408 || result.statusCode == 429) {
                return Result.retry();
            }
            if (result.statusCode < 200 || result.statusCode >= 300) return Result.failure();

            JSONObject payload = new JSONObject(result.body == null ? "{}" : result.body);
            if (payload.optJSONObject("current") == null || payload.optJSONObject("forecast") == null) {
                return Result.failure();
            }

            MeteoBackgroundWeatherStore.write(context, city, lat, lon, trigger, payload, now);
            return Result.success();
        } catch (Exception ignored) {
            return Result.retry();
        }
    }

    private static HttpResult getWeather(String city, double lat, double lon) throws IOException {
        String query = "city=" + URLEncoder.encode(city, StandardCharsets.UTF_8.name())
            + "&lat=" + String.format(Locale.US, "%.6f", lat)
            + "&lon=" + String.format(Locale.US, "%.6f", lon);
        URL url = new URL(BuildConfig.METEO_API_BASE + "/weather/bootstrap?" + query);
        if (!"https".equalsIgnoreCase(url.getProtocol())) throw new IOException("https_required");

        HttpsURLConnection connection = (HttpsURLConnection) url.openConnection();
        connection.setConnectTimeout(NETWORK_TIMEOUT_MS);
        connection.setReadTimeout(NETWORK_TIMEOUT_MS);
        connection.setRequestMethod("GET");
        connection.setRequestProperty("Accept", "application/json");

        try {
            int statusCode = connection.getResponseCode();
            InputStream stream = statusCode >= 200 && statusCode < 400
                ? connection.getInputStream()
                : connection.getErrorStream();
            return new HttpResult(statusCode, readStream(stream));
        } finally {
            connection.disconnect();
        }
    }

    private static String readStream(InputStream stream) throws IOException {
        if (stream == null) return "";

        StringBuilder body = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
            new InputStreamReader(stream, StandardCharsets.UTF_8)
        )) {
            char[] buffer = new char[4_096];
            int count;
            while ((count = reader.read(buffer)) >= 0) {
                if (body.length() + count > MAX_RESPONSE_CHARS) {
                    throw new IOException("weather_payload_too_large");
                }
                body.append(buffer, 0, count);
            }
        }
        return body.toString();
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

    private static final class HttpResult {
        final int statusCode;
        final String body;

        HttpResult(int statusCode, String body) {
            this.statusCode = statusCode;
            this.body = body;
        }
    }
}
