package com.meteofriul.app.location;

import android.content.Context;

import androidx.work.BackoffPolicy;
import androidx.work.Constraints;
import androidx.work.Data;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;

import com.meteofriul.app.BuildConfig;

import java.util.concurrent.TimeUnit;

public final class MeteoBackgroundWeatherScheduler {
    public static final String INPUT_CITY = "city";
    public static final String INPUT_LAT = "lat";
    public static final String INPUT_LON = "lon";
    public static final String INPUT_TRIGGER = "trigger";
    private static final String PREFETCH_WORK = "meteofriul-background-weather-prefetch-v1";

    private MeteoBackgroundWeatherScheduler() {}

    public static void enqueue(
        Context context,
        String trigger,
        double latitude,
        double longitude,
        String city
    ) {
        if (BuildConfig.LOCAL_WEATHER_PILOT) {
            // ICON-2I is deterministic and this pilot has no calibrated
            // precipitation probability. Never run the legacy predictive
            // prefetch/notification path in the side-by-side test package.
            WorkManager.getInstance(context).cancelUniqueWork(PREFETCH_WORK);
            return;
        }
        if (
            city == null
            || city.trim().isEmpty()
            || !Double.isFinite(latitude)
            || !Double.isFinite(longitude)
            || latitude < -90d
            || latitude > 90d
            || longitude < -180d
            || longitude > 180d
        ) return;

        Constraints constraints = new Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build();
        Data input = new Data.Builder()
            .putString(INPUT_CITY, city.trim())
            .putDouble(INPUT_LAT, latitude)
            .putDouble(INPUT_LON, longitude)
            .putString(INPUT_TRIGGER, trigger == null ? "periodic" : trigger)
            .build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(
            MeteoBackgroundWeatherWorker.class
        )
            .setConstraints(constraints)
            .setInputData(input)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build();

        WorkManager.getInstance(context).enqueueUniqueWork(
            PREFETCH_WORK,
            ExistingWorkPolicy.REPLACE,
            request
        );
    }
}
