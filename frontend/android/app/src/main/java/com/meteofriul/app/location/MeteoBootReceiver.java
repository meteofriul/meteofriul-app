package com.meteofriul.app.location;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public final class MeteoBootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        MeteoBackgroundLocationStore.disableIfDisclosureConsentMissing(context);
        if (!MeteoBackgroundLocationStore.isCollectionAllowed(context)) {
            MeteoBackgroundLocationScheduler.disable(context);
            return;
        }
        if (!MeteoBackgroundLocationPermissions.hasBackground(context)) {
            MeteoBackgroundLocationScheduler.disable(context);
            return;
        }
        MeteoBackgroundLocationScheduler.schedulePeriodic(context);
        MeteoBackgroundLocationScheduler.enqueueImmediate(context, "boot");
    }
}
