package com.meteofriul.app.pilot;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Transport/reference-graph checks only. Weather schemas remain owned by weatherV1Client.js. */
public final class PilotWeatherPrefetchCore {
    public static final String BASE_URL = "https://meteofriul-weather-49007668366.europe-west1.run.app";
    public static final int MAX_METADATA_BYTES = 128 * 1024;
    public static final int MAX_MANIFEST_BYTES = 2 * 1024 * 1024;
    public static final int MAX_PAYLOAD_BYTES = 512 * 1024;
    public static final int MAX_FAMILY_BYTES = 6 * 1024 * 1024;
    public static final String ICON = "icon2i";
    public static final String CAMS = "families/cams";
    private static final String RUN = "[0-9]{8}T[0-9]{6}Z";

    public interface Transport {
        Response get(String provider, String path, String etag, int maxBytes) throws IOException;
    }
    public interface Decoder { Map<String, Object> decode(String body) throws IOException; }
    public interface Repository {
        boolean isCurrent(Selection selection);
        Snapshot read(String family, Selection selection);
        boolean write(String family, Selection selection, Snapshot snapshot) throws IOException;
    }
    public static final class Selection {
        public final String istatCode;
        public final long generation;
        public Selection(String istatCode, long generation) {
            this.istatCode = istatCode;
            this.generation = generation;
        }
    }
    public static final class Response {
        public final int status;
        public final String etag;
        public final byte[] body;
        public Response(int status, String etag, byte[] body) {
            this.status = status; this.etag = etag; this.body = body;
        }
    }
    public static final class RawObject {
        public final String provider, path, body, etag, sha256;
        public final int bodyBytes;
        public RawObject(String provider, String path, String body, String etag) throws Failure {
            if (!allowedPath(provider, path, null, true) || !validEtag(etag) || body == null) {
                throw new Failure("invalid_object", false);
            }
            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            if (bytes.length < 2 || bytes.length > maximumBytes(path)) throw new Failure("body_limit", false);
            this.provider = provider; this.path = path; this.body = body; this.etag = etag;
            this.bodyBytes = bytes.length; this.sha256 = sha256(bytes);
        }
        public String key() { return provider + "/" + path; }
    }
    public static final class Snapshot {
        public final RawObject pointer;
        public final Map<String, RawObject> objects;
        public Snapshot(RawObject pointer, Map<String, RawObject> objects) throws Failure {
            long bytes = pointer.bodyBytes;
            for (RawObject object : objects.values()) bytes += object.bodyBytes;
            if (bytes > MAX_FAMILY_BYTES || objects.size() > 5) throw new Failure("snapshot_limit", false);
            this.pointer = pointer;
            this.objects = Collections.unmodifiableMap(new LinkedHashMap<>(objects));
        }
    }
    public static final class Failure extends IOException {
        public final String code;
        public final boolean retryable;
        public Failure(String code, boolean retryable) { super(code); this.code = code; this.retryable = retryable; }
    }
    public static final class Outcome {
        public final Map<String, String> statuses = new LinkedHashMap<>();
        public boolean retryable;
    }

    private final Transport transport;
    private final Decoder decoder;
    private final Repository repository;
    public PilotWeatherPrefetchCore(Transport transport, Decoder decoder, Repository repository) {
        this.transport = transport; this.decoder = decoder; this.repository = repository;
    }

    public Outcome refresh(Selection selection) {
        Outcome outcome = new Outcome();
        for (String family : new String[] { ICON, CAMS }) {
            try {
                requireCurrent(selection);
                Snapshot previous = repository.read(family, selection);
                RawObject pointer = pointer(family, previous == null ? null : previous.pointer);
                requireCurrent(selection);
                Map<String, Object> latest = decoder.decode(pointer.body);
                Map<String, RawObject> objects = new LinkedHashMap<>();
                if (ICON.equals(family)) {
                    stageIconRun(selection, latest, map(latest.get("latest")), previous, objects);
                    if (latest.get("previous") != null) {
                        try {
                            stageIconRun(selection, latest, map(latest.get("previous")), previous, objects);
                        } catch (Failure error) {
                            if ("selection_changed".equals(error.code)) throw error;
                            // Missing historical enrichment must not discard a complete active ICON run.
                            outcome.retryable |= error.retryable;
                            outcome.statuses.put("icon_previous", error.code);
                        } catch (IOException error) {
                            outcome.retryable = true;
                            outcome.statuses.put("icon_previous", "transport_failure");
                        }
                    }
                } else stageCams(selection, latest, previous, objects);
                requireCurrent(selection);
                if (!repository.write(family, selection, new Snapshot(pointer, objects))) {
                    throw new Failure("selection_changed", false);
                }
                outcome.statuses.put(family, "staged");
            } catch (Failure error) {
                outcome.statuses.put(family, error.code);
                outcome.retryable |= error.retryable;
                if ("selection_changed".equals(error.code)) break;
            } catch (IOException error) {
                outcome.statuses.put(family, "transport_failure");
                outcome.retryable = true;
            } catch (RuntimeException error) {
                outcome.statuses.put(family, "invalid_metadata");
            }
        }
        return outcome;
    }

    private void stageIconRun(Selection selection, Map<String, Object> latest, Map<String, Object> descriptor,
        Snapshot previous, Map<String, RawObject> objects) throws IOException {
        String run = enabledRun(latest, descriptor);
        String path = "runs/" + run + "/manifest.json";
        requireEqual(path, descriptor.get("manifest_path"));
        RawObject manifest = immutable(selection, ICON, path, descriptor.get("manifest_sha256"),
            descriptor.get("manifest_json_bytes"), previous);
        Map<String, Object> document = decoder.decode(manifest.body);
        requireEqual(run, document.get("source_run_id"));
        RawObject municipality = municipality(selection, ICON, run, document, previous);
        objects.put(manifest.key(), manifest);
        objects.put(municipality.key(), municipality);
    }

    private void stageCams(Selection selection, Map<String, Object> latest, Snapshot previous,
        Map<String, RawObject> objects) throws IOException {
        Map<String, Object> descriptor = map(latest.get("latest"));
        String run = enabledRun(latest, descriptor);
        String path = "runs/" + run + "/release.json";
        requireEqual(path, descriptor.get("release_path"));
        RawObject release = immutable(selection, CAMS, path, descriptor.get("release_sha256"),
            descriptor.get("release_json_bytes"), previous);
        Map<String, Object> document = decoder.decode(release.body);
        requireEqual(run, document.get("source_run_id"));
        Map<String, Object> components = map(document.get("components"));
        objects.put(release.key(), release);
        for (String role : new String[] { "core", "pollen" }) {
            String provider = "core".equals(role) ? "cams_europe" : "cams_europe_pollen";
            Map<String, Object> component = map(components.get(role));
            requireEqual(provider, component.get("provider"));
            requireEqual(run, component.get("source_run_id"));
            String manifestPath = "runs/" + run + "/manifest.json";
            requireEqual("weather/v1/" + provider + "/" + manifestPath, component.get("manifest_key"));
            RawObject manifest = immutable(selection, provider, manifestPath, component.get("manifest_sha256"),
                component.get("manifest_json_bytes"), previous);
            Map<String, Object> manifestDocument = decoder.decode(manifest.body);
            requireEqual(run, manifestDocument.get("source_run_id"));
            RawObject municipality = municipality(selection, provider, run, manifestDocument, previous);
            objects.put(manifest.key(), manifest);
            objects.put(municipality.key(), municipality);
        }
    }

    private RawObject municipality(Selection selection, String provider, String run,
        Map<String, Object> manifest, Snapshot previous) throws IOException {
        Map<String, Object> descriptor = map(map(manifest.get("objects")).get(selection.istatCode));
        String path = "runs/" + run + "/municipalities/" + selection.istatCode + ".json";
        requireEqual(path, descriptor.get("path"));
        return immutable(selection, provider, path, descriptor.get("sha256"), descriptor.get("json_bytes"), previous);
    }

    private RawObject pointer(String provider, RawObject previous) throws IOException {
        Response response = transport.get(provider, "latest.json", previous == null ? null : previous.etag, MAX_METADATA_BYTES);
        if (response.status == 304) {
            if (previous == null || (response.etag != null && !previous.etag.equals(response.etag))) {
                throw new Failure("invalid_304", false);
            }
            return previous;
        }
        return responseObject(provider, "latest.json", response);
    }

    private RawObject immutable(Selection selection, String provider, String path, Object hashValue,
        Object sizeValue, Snapshot previous) throws IOException {
        requireCurrent(selection);
        String hash = hashValue instanceof String ? (String) hashValue : "";
        int size = integer(sizeValue);
        if (!allowedPath(provider, path, selection.istatCode, false) || !validHash(hash)
            || size < 2 || size > maximumBytes(path)) throw new Failure("invalid_reference", false);
        RawObject cached = previous == null ? null : previous.objects.get(provider + "/" + path);
        if (cached != null && cached.sha256.equals(hash) && cached.bodyBytes == size) return cached;
        RawObject downloaded = responseObject(provider, path, transport.get(provider, path, null, size));
        if (downloaded.bodyBytes != size || !downloaded.sha256.equals(hash)) throw new Failure("integrity_mismatch", false);
        requireCurrent(selection);
        return downloaded;
    }

    private RawObject responseObject(String provider, String path, Response response) throws IOException {
        if (response.status != 200) throw new Failure("http_" + response.status,
            response.status == 408 || response.status == 429 || (response.status >= 500 && response.status <= 599));
        if (response.body == null || response.body.length > maximumBytes(path)) throw new Failure("body_limit", false);
        return new RawObject(provider, path, utf8(response.body), response.etag);
    }
    private void requireCurrent(Selection selection) throws Failure {
        if (!repository.isCurrent(selection)) throw new Failure("selection_changed", false);
    }
    private static String enabledRun(Map<String, Object> latest, Map<String, Object> descriptor) throws Failure {
        Object value = descriptor.get("source_run_id");
        if (!(value instanceof String) || !((String) value).matches(RUN)) throw new Failure("invalid_run", false);
        Object disabled = latest.get("disabled_run_ids");
        if (!(disabled instanceof List)) throw new Failure("invalid_revocations", false);
        for (Object run : (List<?>) disabled) {
            if (!(run instanceof String) || !((String) run).matches(RUN)) throw new Failure("invalid_revocations", false);
            if (value.equals(run)) throw new Failure("run_disabled", false);
        }
        return (String) value;
    }
    @SuppressWarnings("unchecked")
    private static Map<String, Object> map(Object value) throws Failure {
        if (!(value instanceof Map)) throw new Failure("invalid_metadata", false);
        return (Map<String, Object>) value;
    }
    private static int integer(Object value) throws Failure {
        if (!(value instanceof Number)) throw new Failure("invalid_size", false);
        double number = ((Number) value).doubleValue();
        if (!Double.isFinite(number) || number != Math.floor(number) || number > Integer.MAX_VALUE) {
            throw new Failure("invalid_size", false);
        }
        return (int) number;
    }
    private static void requireEqual(String expected, Object actual) throws Failure {
        if (!expected.equals(actual)) throw new Failure("reference_mismatch", false);
    }
    public static void validateConfiguration(String baseUrl, String istatCode) throws Failure {
        if (!BASE_URL.equals(baseUrl) || istatCode == null || !istatCode.matches("[0-9]{6}")) {
            throw new Failure("invalid_configuration", false);
        }
    }
    public static boolean allowedPath(String provider, String path, String istatCode, boolean allowLatest) {
        if (path == null || provider == null) return false;
        if (CAMS.equals(provider)) return (allowLatest && "latest.json".equals(path))
            || path.matches("runs/" + RUN + "/release\\.json");
        if (!ICON.equals(provider) && !"cams_europe".equals(provider) && !"cams_europe_pollen".equals(provider)) return false;
        if (allowLatest && ICON.equals(provider) && "latest.json".equals(path)) return true;
        if (path.matches("runs/" + RUN + "/manifest\\.json")) return true;
        String code = istatCode == null ? "[0-9]{6}" : istatCode;
        return (istatCode == null || istatCode.matches("[0-9]{6}"))
            && path.matches("runs/" + RUN + "/municipalities/" + code + "\\.json");
    }
    public static boolean validHash(String hash) { return hash != null && hash.matches("[0-9a-f]{64}"); }
    public static boolean validEtag(String etag) {
        return etag != null && !etag.isEmpty() && etag.length() <= 256 && etag.equals(etag.trim())
            && etag.indexOf('\r') < 0 && etag.indexOf('\n') < 0;
    }
    public static int maximumBytes(String path) {
        if (path.endsWith("manifest.json")) return MAX_MANIFEST_BYTES;
        return path.contains("/municipalities/") ? MAX_PAYLOAD_BYTES : MAX_METADATA_BYTES;
    }
    public static String utf8(byte[] bytes) throws Failure {
        try { return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
            .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString(); }
        catch (CharacterCodingException error) { throw new Failure("invalid_utf8", false); }
    }
    public static String sha256(byte[] bytes) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
            StringBuilder result = new StringBuilder(64);
            for (byte value : digest) result.append(String.format(java.util.Locale.ROOT, "%02x", value & 255));
            return result.toString();
        } catch (java.security.NoSuchAlgorithmException error) { throw new IllegalStateException(error); }
    }
}
