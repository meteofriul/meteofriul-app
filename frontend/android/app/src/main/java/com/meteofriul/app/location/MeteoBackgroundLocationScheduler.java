package com.meteofriul.app.location;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.location.Location;

import androidx.work.Constraints;
import androidx.work.Data;
import androidx.work.BackoffPolicy;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;

import com.google.android.gms.location.Geofence;
import com.google.android.gms.location.GeofencingRequest;
import com.google.android.gms.location.LocationServices;
import com.google.android.gms.tasks.Tasks;

import java.util.concurrent.TimeUnit;

public final class MeteoBackgroundLocationScheduler {
    public static final String INPUT_TRIGGER = "trigger";
    private static final String PERIODIC_WORK = "meteofriul-background-location-periodic-v1";
    private static final String IMMEDIATE_WORK = "meteofriul-background-location-immediate-v1";
    private static final String GEOFENCE_ID = "meteofriul-current-position-v1";

    private MeteoBackgroundLocationScheduler() {}

    public static void schedulePeriodic(Context context) {
        if (!MeteoBackgroundLocationStore.isCollectionAllowed(context)) {
            disable(context);
            return;
        }

        Constraints constraints = new Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build();
        Data input = new Data.Builder().putString(INPUT_TRIGGER, "periodic").build();
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
            MeteoBackgroundLocationWorker.class,
            15,
            TimeUnit.MINUTES
        )
            .setConstraints(constraints)
            .setInputData(input)
            .build();
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            PERIODIC_WORK,
            ExistingPeriodicWorkPolicy.UPDATE,
            request
        );
    }

    public static void enqueueImmediate(Context context, String trigger) {
        if (!MeteoBackgroundLocationStore.isCollectionAllowed(context)) {
            disable(context);
            return;
        }

        Constraints constraints = new Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build();
        Data input = new Data.Builder()
            .putString(INPUT_TRIGGER, normalizeTrigger(trigger))
            .build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(
            MeteoBackgroundLocationWorker.class
        )
            .setConstraints(constraints)
            .setInputData(input)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build();
        WorkManager.getInstance(context).enqueueUniqueWork(
            IMMEDIATE_WORK,
            ExistingWorkPolicy.REPLACE,
            request
        );
    }

    public static void disable(Context context) {
        WorkManager manager = WorkManager.getInstance(context);
        manager.cancelUniqueWork(PERIODIC_WORK);
        manager.cancelUniqueWork(IMMEDIATE_WORK);
        LocationServices.getGeofencingClient(context).removeGeofences(geofenceIntent(context));
    }

    public static boolean registerExitGeofence(Context context, Location location) {
        if (!MeteoBackgroundLocationStore.isCollectionAllowed(context)) return false;
        if (!MeteoBackgroundLocationPermissions.hasBackground(context)) return false;
        float radius = Math.max(200f, Math.min(500f, location.getAccuracy() * 2f + 100f));
        Geofence geofence = new Geofence.Builder()
            .setRequestId(GEOFENCE_ID)
            .setCircularRegion(location.getLatitude(), location.getLongitude(), radius)
            .setExpirationDuration(Geofence.NEVER_EXPIRE)
            .setNotificationResponsiveness(120_000)
            .setTransitionTypes(Geofence.GEOFENCE_TRANSITION_EXIT)
            .build();
        GeofencingRequest request = new GeofencingRequest.Builder()
            .setInitialTrigger(GeofencingRequest.INITIAL_TRIGGER_ENTER)
            .addGeofence(geofence)
            .build();
        try {
            Tasks.await(
                LocationServices.getGeofencingClient(context).addGeofences(
                    request,
                    geofenceIntent(context)
                ),
                15,
                TimeUnit.SECONDS
            );
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }

    private static PendingIntent geofenceIntent(Context context) {
        Intent intent = new Intent(context, MeteoGeofenceReceiver.class);
        return PendingIntent.getBroadcast(
            context,
            4107,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_MUTABLE
        );
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
}
