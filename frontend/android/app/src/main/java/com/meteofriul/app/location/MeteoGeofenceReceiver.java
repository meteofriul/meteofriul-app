package com.meteofriul.app.location;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import com.google.android.gms.location.Geofence;
import com.google.android.gms.location.GeofencingEvent;

public final class MeteoGeofenceReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        MeteoBackgroundLocationStore.disableIfDisclosureConsentMissing(context);
        if (!MeteoBackgroundLocationStore.isCollectionAllowed(context)) {
            MeteoBackgroundLocationScheduler.disable(context);
            return;
        }
        GeofencingEvent event = GeofencingEvent.fromIntent(intent);
        if (
            event == null
            || event.hasError()
            || event.getGeofenceTransition() != Geofence.GEOFENCE_TRANSITION_EXIT
        ) return;
        MeteoBackgroundLocationScheduler.enqueueImmediate(context, "geofence_exit");
    }
}
