package com.meteofriul.app.pilot;

import android.content.Context;
import androidx.work.BackoffPolicy;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import java.util.concurrent.TimeUnit;

final class PilotWeatherPrefetchScheduler {
    static final String WORK_NAME = "meteofriul-pilot-weather-prefetch-v1";
    private PilotWeatherPrefetchScheduler() {}
    static void configure(Context context) {
        Constraints constraints = new Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED).setRequiresBatteryNotLow(true).build();
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(PilotWeatherPrefetchWorker.class, 60, TimeUnit.MINUTES)
            .setInitialDelay(30, TimeUnit.MINUTES)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 5, TimeUnit.MINUTES)
            .setConstraints(constraints).addTag(WORK_NAME).build();
        // KEEP neither multiplies work nor postpones the first run on every resume.
        // The worker reads the persisted selection at execution, not stale input data.
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(WORK_NAME, ExistingPeriodicWorkPolicy.KEEP, request);
    }
    static void clear(Context context) { WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME); }
}
