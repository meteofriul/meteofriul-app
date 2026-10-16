package com.meteofriul.app.pilot;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.AtomicFile;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Private untrusted raw staging. Never writes weather-v1 localStorage or a display bundle. */
final class PilotWeatherPrefetchStore implements PilotWeatherPrefetchCore.Repository {
    static final Object LOCK = new Object();
    private static final String NAMESPACE = "pilot_weather_prefetch_v1";
    private static final int MAX_STORED_BYTES = 16 * 1024 * 1024;
    private final Context context;
    PilotWeatherPrefetchStore(Context context) { this.context = context.getApplicationContext(); }
    private SharedPreferences preferences() { return context.getSharedPreferences(NAMESPACE, Context.MODE_PRIVATE); }
    private AtomicFile file(String family) {
        if (!PilotWeatherPrefetchCore.ICON.equals(family) && !PilotWeatherPrefetchCore.CAMS.equals(family)) {
            throw new IllegalArgumentException("unknown_family");
        }
        return new AtomicFile(new File(context.getFilesDir(), NAMESPACE + (PilotWeatherPrefetchCore.ICON.equals(family) ? "_icon.json" : "_cams.json")));
    }
    PilotWeatherPrefetchCore.Selection configure(String baseUrl, String istatCode) throws IOException {
        PilotWeatherPrefetchCore.validateConfiguration(baseUrl, istatCode);
        synchronized (LOCK) {
            PilotWeatherPrefetchCore.Selection existing = selection();
            if (existing != null && existing.istatCode.equals(istatCode)) return existing;
            long generation = nextGeneration();
            if (!preferences().edit().putBoolean("enabled", true).putString("istat_code", istatCode)
                .putLong("generation", generation).commit()) throw new IOException("configuration_not_saved");
            deleteFiles();
            return new PilotWeatherPrefetchCore.Selection(istatCode, generation);
        }
    }
    PilotWeatherPrefetchCore.Selection selection() {
        synchronized (LOCK) {
            SharedPreferences values = preferences();
            String istatCode = values.getString("istat_code", "");
            if (!values.getBoolean("enabled", false) || istatCode == null || !istatCode.matches("[0-9]{6}")) return null;
            return new PilotWeatherPrefetchCore.Selection(istatCode, values.getLong("generation", 0));
        }
    }
    private long nextGeneration() throws IOException {
        long previous = preferences().getLong("generation", 0);
        if (previous < 0 || previous == Long.MAX_VALUE) throw new IOException("generation_exhausted");
        return previous + 1;
    }
    void clear() throws IOException {
        synchronized (LOCK) {
            if (!preferences().edit().putBoolean("enabled", false).remove("istat_code")
                .putLong("generation", nextGeneration()).commit()) throw new IOException("clear_not_saved");
            deleteFiles();
        }
    }
    private void deleteFiles() { file(PilotWeatherPrefetchCore.ICON).delete(); file(PilotWeatherPrefetchCore.CAMS).delete(); }
    @Override public boolean isCurrent(PilotWeatherPrefetchCore.Selection selection) {
        synchronized (LOCK) {
            PilotWeatherPrefetchCore.Selection current = selection();
            return current != null && current.generation == selection.generation && current.istatCode.equals(selection.istatCode);
        }
    }
    @Override public PilotWeatherPrefetchCore.Snapshot read(String family, PilotWeatherPrefetchCore.Selection selection) {
        synchronized (LOCK) {
            if (!isCurrent(selection)) return null;
            try (FileInputStream input = file(family).openRead()) {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                byte[] buffer = new byte[8192];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    if (bytes.size() + count > MAX_STORED_BYTES) return null;
                    bytes.write(buffer, 0, count);
                }
                JSONObject value = new JSONObject(PilotWeatherPrefetchCore.utf8(bytes.toByteArray()));
                if (value.getInt("version") != 1 || value.getLong("generation") != selection.generation
                    || !value.getString("istat_code").equals(selection.istatCode)) return null;
                PilotWeatherPrefetchCore.RawObject pointer = raw(value.getJSONObject("pointer"));
                if (!family.equals(pointer.provider) || !"latest.json".equals(pointer.path)) return null;
                JSONArray rows = value.getJSONArray("objects");
                if (rows.length() > 5) return null;
                Map<String, PilotWeatherPrefetchCore.RawObject> objects = new LinkedHashMap<>();
                for (int index = 0; index < rows.length(); index++) {
                    PilotWeatherPrefetchCore.RawObject object = raw(rows.getJSONObject(index));
                    if (!PilotWeatherPrefetchCore.allowedPath(object.provider, object.path, selection.istatCode, false)
                        || objects.put(object.key(), object) != null) return null;
                }
                return new PilotWeatherPrefetchCore.Snapshot(pointer, objects);
            } catch (IOException | JSONException | RuntimeException error) { return null; }
        }
    }
    @Override public boolean write(String family, PilotWeatherPrefetchCore.Selection selection,
        PilotWeatherPrefetchCore.Snapshot snapshot) throws IOException {
        synchronized (LOCK) {
            // Compare the generation at publication, after every network operation.
            if (!isCurrent(selection)) return false;
            AtomicFile destination = file(family);
            FileOutputStream output = null;
            try {
                JSONArray rows = new JSONArray();
                for (PilotWeatherPrefetchCore.RawObject object : snapshot.objects.values()) rows.put(json(object));
                JSONObject value = new JSONObject().put("version", 1).put("generation", selection.generation)
                    .put("istat_code", selection.istatCode).put("pointer", json(snapshot.pointer)).put("objects", rows);
                byte[] bytes = value.toString().getBytes(StandardCharsets.UTF_8);
                if (bytes.length > MAX_STORED_BYTES) throw new IOException("staging_file_limit");
                output = destination.startWrite();
                output.write(bytes);
                destination.finishWrite(output);
                return true;
            } catch (IOException | JSONException | RuntimeException error) {
                if (output != null) destination.failWrite(output);
                throw new IOException("staging_not_saved", error);
            }
        }
    }
    PilotWeatherPrefetchCore.RawObject readObject(String baseUrl, String istatCode, String provider,
        String path, String sha256) throws IOException {
        PilotWeatherPrefetchCore.validateConfiguration(baseUrl, istatCode);
        if (!PilotWeatherPrefetchCore.allowedPath(provider, path, istatCode, false)
            || !PilotWeatherPrefetchCore.validHash(sha256)) return null;
        synchronized (LOCK) {
            PilotWeatherPrefetchCore.Selection selected = selection();
            if (selected == null || !selected.istatCode.equals(istatCode)) return null;
            String family = PilotWeatherPrefetchCore.ICON.equals(provider) ? PilotWeatherPrefetchCore.ICON : PilotWeatherPrefetchCore.CAMS;
            PilotWeatherPrefetchCore.Snapshot snapshot = read(family, selected);
            PilotWeatherPrefetchCore.RawObject object = snapshot == null ? null : snapshot.objects.get(provider + "/" + path);
            return isCurrent(selected) && object != null && object.sha256.equals(sha256) ? object : null;
        }
    }
    private static JSONObject json(PilotWeatherPrefetchCore.RawObject object) throws JSONException {
        return new JSONObject().put("provider", object.provider).put("path", object.path).put("body", object.body)
            .put("etag", object.etag).put("sha256", object.sha256).put("body_bytes", object.bodyBytes);
    }
    private static PilotWeatherPrefetchCore.RawObject raw(JSONObject value) throws JSONException, IOException {
        PilotWeatherPrefetchCore.RawObject object = new PilotWeatherPrefetchCore.RawObject(value.getString("provider"),
            value.getString("path"), value.getString("body"), value.getString("etag"));
        if (object.bodyBytes != value.getInt("body_bytes") || !object.sha256.equals(value.getString("sha256"))) {
            throw new IOException("staging_integrity_mismatch");
        }
        return object;
    }
    static Map<String, Object> decode(String body) throws IOException {
        try { return objectMap(new JSONObject(body)); }
        catch (JSONException error) { throw new PilotWeatherPrefetchCore.Failure("invalid_metadata", false); }
    }
    private static Map<String, Object> objectMap(JSONObject value) throws JSONException {
        Map<String, Object> result = new LinkedHashMap<>();
        Iterator<String> keys = value.keys();
        while (keys.hasNext()) { String key = keys.next(); result.put(key, decoded(value.get(key))); }
        return result;
    }
    private static Object decoded(Object value) throws JSONException {
        if (value == JSONObject.NULL) return null;
        if (value instanceof JSONObject) return objectMap((JSONObject) value);
        if (value instanceof JSONArray) {
            List<Object> result = new ArrayList<>();
            JSONArray array = (JSONArray) value;
            for (int index = 0; index < array.length(); index++) result.add(decoded(array.get(index)));
            return result;
        }
        return value;
    }
}
