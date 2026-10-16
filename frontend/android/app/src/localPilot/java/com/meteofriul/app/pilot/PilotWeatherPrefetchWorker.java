package com.meteofriul.app.pilot;

import android.content.Context;
import android.util.Log;
import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import java.util.Map;

/** Best-effort silent warming; no location, push, notification or foreground service. */
public final class PilotWeatherPrefetchWorker extends Worker {
    static final int MAX_ATTEMPTS = 4;
    public PilotWeatherPrefetchWorker(@NonNull Context context, @NonNull WorkerParameters parameters) { super(context, parameters); }
    @NonNull @Override public Result doWork() {
        PilotWeatherPrefetchStore store = new PilotWeatherPrefetchStore(getApplicationContext());
        PilotWeatherPrefetchCore.Selection selection = store.selection();
        if (selection == null || isStopped()) return Result.success();
        PilotWeatherPrefetchCore core = new PilotWeatherPrefetchCore(new PilotWeatherPrefetchHttp(this::isStopped),
            PilotWeatherPrefetchStore::decode, store);
        PilotWeatherPrefetchCore.Outcome outcome = core.refresh(selection);
        for (Map.Entry<String, String> entry : outcome.statuses.entrySet()) {
            Log.i("PilotWeatherPrefetch", "family=" + entry.getKey() + " result=" + entry.getValue()
                + " attempt=" + (getRunAttemptCount() + 1));
        }
        if (isStopped() || !store.isCurrent(selection)) return Result.success();
        if (outcome.retryable && getRunAttemptCount() + 1 < MAX_ATTEMPTS) return Result.retry();
        // A bounded failed attempt never erases the previously completed staging.
        return outcome.retryable ? Result.failure() : Result.success();
    }
}
