package com.meteofriul.app.pilot;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.cert.Certificate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import javax.net.ssl.HttpsURLConnection;

/** Same executable tests can run with plain javac/java or the JUnit wrapper. No Android mocks or JSON dependency. */
public final class PilotWeatherPrefetchCoreTest {
    private static final String A = "20260908T000000Z", B = "20260908T120000Z";
    private static final String ISTAT = "093033";
    private static int tests;
    interface Check { void run() throws Exception; }
    public static void main(String[] args) throws Exception {
        tests = 0;
        test("fixed origin and municipality arguments", () -> {
            PilotWeatherPrefetchCore.validateConfiguration(PilotWeatherPrefetchCore.BASE_URL, ISTAT);
            fails("invalid_configuration", () -> PilotWeatherPrefetchCore.validateConfiguration("https://example.com", ISTAT));
            fails("invalid_configuration", () -> PilotWeatherPrefetchCore.validateConfiguration(PilotWeatherPrefetchCore.BASE_URL + "/", ISTAT));
            fails("invalid_configuration", () -> PilotWeatherPrefetchCore.validateConfiguration(PilotWeatherPrefetchCore.BASE_URL, "../foo"));
        });
        test("only whitelisted provider immutable paths", () -> {
            yes(PilotWeatherPrefetchCore.allowedPath("icon2i", "runs/" + A + "/municipalities/" + ISTAT + ".json", ISTAT, false));
            for (String path : new String[] { "latest.json", "../latest.json", "runs/" + A + "/municipalities/030129.json", "runs/" + A + "/manifest.json?token=1", "https://example.com/a" }) {
                no(PilotWeatherPrefetchCore.allowedPath("icon2i", path, ISTAT, false));
            }
            no(PilotWeatherPrefetchCore.allowedPath("../icon2i", "latest.json", ISTAT, true));
            no(PilotWeatherPrefetchCore.allowedPath("cams_europe", "latest.json", ISTAT, true));
        });
        test("ETag and strict UTF8 bounded bodies", () -> {
            no(PilotWeatherPrefetchCore.validEtag("x\r\nInjected: 1"));
            no(PilotWeatherPrefetchCore.validEtag(""));
            fails("invalid_utf8", () -> PilotWeatherPrefetchCore.utf8(new byte[] { (byte) 0xc3, 0x28 }));
            fails("body_limit", () -> new PilotWeatherPrefetchCore.RawObject("icon2i", "latest.json", "x", "etag"));
        });
        test("active and previous ICON plus atomic CAMS pair", () -> {
            Fixture f = new Fixture(); f.icon(B, A); f.cams(A);
            PilotWeatherPrefetchCore.Outcome outcome = f.refresh();
            equals("staged", outcome.statuses.get("icon2i"));
            equals("staged", outcome.statuses.get("families/cams"));
            equals(4, f.repo.saved.get("icon2i").objects.size());
            equals(5, f.repo.saved.get("families/cams").objects.size());
            equals(11, f.requests.size());
        });
        test("unchanged pointers issue only two conditional metadata requests", () -> {
            Fixture f = new Fixture(); f.icon(B, A); f.cams(A); f.refresh();
            f.requests.clear(); f.refresh();
            equals(2, f.requests.size());
            yes(f.requests.stream().allMatch(value -> value.contains("latest.json")));
            equals(2, f.conditionalRequests);
        });
        test("failed B keeps complete A and still refreshes CAMS", () -> {
            Fixture f = new Fixture(); f.icon(A, null); f.cams(A); f.refresh();
            PilotWeatherPrefetchCore.Snapshot oldIcon = f.repo.saved.get("icon2i");
            f.icon(B, A); f.responses.put("icon2i/runs/" + B + "/manifest.json", new PilotWeatherPrefetchCore.Response(503, null, null));
            PilotWeatherPrefetchCore.Outcome result = f.refresh();
            yes(result.retryable); yes(oldIcon == f.repo.saved.get("icon2i"));
            equals("staged", result.statuses.get("families/cams"));
        });
        test("failed optional ICON history does not suppress active ICON", () -> {
            Fixture f = new Fixture(); f.icon(B, A); f.cams(A);
            f.responses.put("icon2i/runs/" + A + "/manifest.json", new PilotWeatherPrefetchCore.Response(503, null, null));
            PilotWeatherPrefetchCore.Outcome result = f.refresh();
            yes(result.retryable); equals("staged", result.statuses.get("icon2i"));
            equals(2, f.repo.saved.get("icon2i").objects.size());
        });
        test("CAMS pollen failure never stages only core and never removes ICON", () -> {
            Fixture f = new Fixture(); f.icon(A, null); f.cams(A); f.refresh();
            PilotWeatherPrefetchCore.Snapshot oldCams = f.repo.saved.get("families/cams");
            f.cams(B);
            f.responses.put("cams_europe_pollen/runs/" + B + "/municipalities/" + ISTAT + ".json", new PilotWeatherPrefetchCore.Response(429, null, null));
            PilotWeatherPrefetchCore.Outcome result = f.refresh();
            yes(result.retryable); yes(oldCams == f.repo.saved.get("families/cams"));
            equals("staged", result.statuses.get("icon2i"));
        });
        test("hash mismatch fails the graph without replacing a good family", () -> {
            Fixture f = new Fixture(); f.icon(A, null); f.cams(A); f.refresh();
            PilotWeatherPrefetchCore.Snapshot oldIcon = f.repo.saved.get("icon2i");
            f.icon(B, A);
            String key = "icon2i/runs/" + B + "/municipalities/" + ISTAT + ".json";
            f.responses.put(key, new PilotWeatherPrefetchCore.Response(200, "etag", "{}".getBytes(StandardCharsets.UTF_8)));
            PilotWeatherPrefetchCore.Outcome result = f.refresh();
            equals("integrity_mismatch", result.statuses.get("icon2i"));
            no(result.retryable); yes(oldIcon == f.repo.saved.get("icon2i"));
        });
        test("changing municipality during fetch vetoes publication", () -> {
            Fixture f = new Fixture(); f.icon(A, null); f.cams(A);
            f.onRequest = () -> f.repo.current = new PilotWeatherPrefetchCore.Selection("030129", 2);
            PilotWeatherPrefetchCore.Outcome result = f.refresh();
            equals("selection_changed", result.statuses.get("icon2i")); equals(0, f.repo.saved.size());
        });
        test("clear during fetch cannot recreate the staging", () -> {
            Fixture f = new Fixture(); f.icon(A, null); f.cams(A);
            f.onRequest = () -> f.repo.current = null;
            PilotWeatherPrefetchCore.Outcome result = f.refresh();
            equals("selection_changed", result.statuses.get("icon2i")); equals(0, f.repo.saved.size());
        });
        test("revoked active descriptor is not downloaded", () -> {
            Fixture f = new Fixture(); f.icon(A, null); f.cams(A);
            f.documents.get(new String(f.responses.get("icon2i/latest.json").body, StandardCharsets.UTF_8))
                .put("disabled_run_ids", Collections.singletonList(A));
            PilotWeatherPrefetchCore.Outcome result = f.refresh();
            equals("run_disabled", result.statuses.get("icon2i")); no(f.repo.saved.containsKey("icon2i"));
            no(f.requests.stream().anyMatch(value -> value.startsWith("icon2i/runs/")));
        });
        test("HTTPS exact origin, no redirects, ETag and byte preservation", () -> {
            FakeConnection connection = new FakeConnection(200, "{}".getBytes(StandardCharsets.UTF_8));
            PilotWeatherPrefetchHttp http = new PilotWeatherPrefetchHttp(url -> {
                equals(PilotWeatherPrefetchCore.BASE_URL + "/weather/v1/icon2i/latest.json", url.toString()); return connection;
            }, () -> false);
            PilotWeatherPrefetchCore.Response response = http.get("icon2i", "latest.json", "\"previous\"", 128);
            no(connection.getInstanceFollowRedirects()); yes(connection.disconnected);
            equals("\"previous\"", connection.getRequestProperty("If-None-Match"));
            equals("GET", connection.getRequestMethod()); equals("{}", PilotWeatherPrefetchCore.utf8(response.body));
        });
        test("redirects and HTTP errors never read redirected/error bodies", () -> {
            for (int status : new int[] { 302, 401, 403, 404, 503 }) {
                FakeConnection connection = new FakeConnection(status, new byte[100]);
                PilotWeatherPrefetchCore.Response response = new PilotWeatherPrefetchHttp(url -> connection, () -> false)
                    .get("icon2i", "latest.json", null, 128);
                equals(status, response.status); no(connection.bodyOpened); yes(connection.disconnected);
            }
        });
        test("stream bound applies even without content length", () -> {
            FakeConnection connection = new FakeConnection(200, new byte[129]);
            fails("body_limit", () -> new PilotWeatherPrefetchHttp(url -> connection, () -> false)
                .get("icon2i", "latest.json", null, 128));
            yes(connection.disconnected);
        });
        test("transport rejects invalid MIME and cancellation", () -> {
            FakeConnection connection = new FakeConnection(200, new byte[2]); connection.mime = "text/html";
            fails("invalid_content_type", () -> new PilotWeatherPrefetchHttp(url -> connection, () -> false)
                .get("icon2i", "latest.json", null, 128));
            fails("cancelled", () -> new PilotWeatherPrefetchHttp(url -> { throw new AssertionError("network started"); }, () -> true)
                .get("icon2i", "latest.json", null, 128));
        });
        System.out.println("PilotWeatherPrefetch native core/HTTP: " + tests + " tests passed");
    }
    private static void test(String name, Check check) throws Exception {
        try { check.run(); tests++; } catch (Throwable error) { throw new AssertionError(name, error); }
    }
    private static void yes(boolean value) { if (!value) throw new AssertionError("expected true"); }
    private static void no(boolean value) { yes(!value); }
    private static void equals(Object expected, Object actual) { if (!java.util.Objects.equals(expected, actual)) throw new AssertionError("expected " + expected + "; actual " + actual); }
    private static void fails(String code, Check check) throws Exception {
        try { check.run(); } catch (PilotWeatherPrefetchCore.Failure error) { equals(code, error.code); return; }
        throw new AssertionError("expected failure " + code);
    }
    private static Map<String, Object> map(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) result.put((String) pairs[i], pairs[i + 1]);
        return result;
    }
    private static final class Repo implements PilotWeatherPrefetchCore.Repository {
        PilotWeatherPrefetchCore.Selection current = new PilotWeatherPrefetchCore.Selection(ISTAT, 1);
        final Map<String, PilotWeatherPrefetchCore.Snapshot> saved = new LinkedHashMap<>();
        public boolean isCurrent(PilotWeatherPrefetchCore.Selection value) { return current != null && current.generation == value.generation && current.istatCode.equals(value.istatCode); }
        public PilotWeatherPrefetchCore.Snapshot read(String family, PilotWeatherPrefetchCore.Selection value) { return isCurrent(value) ? saved.get(family) : null; }
        public boolean write(String family, PilotWeatherPrefetchCore.Selection value, PilotWeatherPrefetchCore.Snapshot snapshot) {
            if (!isCurrent(value)) return false; saved.put(family, snapshot); return true;
        }
    }
    private static final class Fixture {
        final Repo repo = new Repo();
        final Map<String, PilotWeatherPrefetchCore.Response> responses = new LinkedHashMap<>();
        final Map<String, Map<String, Object>> documents = new LinkedHashMap<>();
        final List<String> requests = new ArrayList<>();
        int conditionalRequests;
        Runnable onRequest;
        PilotWeatherPrefetchCore.Outcome refresh() {
            PilotWeatherPrefetchCore.Selection captured = repo.current;
            return new PilotWeatherPrefetchCore((provider, path, etag, max) -> {
                String key = provider + "/" + path; requests.add(key);
                if (onRequest != null) { Runnable action = onRequest; onRequest = null; action.run(); }
                PilotWeatherPrefetchCore.Response response = responses.get(key);
                if (response == null) return new PilotWeatherPrefetchCore.Response(404, null, null);
                if (etag != null && etag.equals(response.etag)) { conditionalRequests++; return new PilotWeatherPrefetchCore.Response(304, etag, null); }
                return response;
            }, body -> { Map<String, Object> value = documents.get(body); if (value == null) throw new IOException("invalid fixture"); return value; }, repo).refresh(captured);
        }
        PilotWeatherPrefetchCore.RawObject put(String provider, String path, Map<String, Object> document) throws Exception {
            String body = "{\"fixture\":\"" + provider + "/" + path + "\",\"revision\":" + documents.size() + "}";
            PilotWeatherPrefetchCore.RawObject value = new PilotWeatherPrefetchCore.RawObject(provider, path, body, "\"" + documents.size() + "\"");
            documents.put(body, document); responses.put(value.key(), new PilotWeatherPrefetchCore.Response(200, value.etag, body.getBytes(StandardCharsets.UTF_8)));
            return value;
        }
        Map<String, Object> run(String provider, String run) throws Exception {
            String prefix = "runs/" + run + "/";
            PilotWeatherPrefetchCore.RawObject town = put(provider, prefix + "municipalities/" + ISTAT + ".json", map());
            PilotWeatherPrefetchCore.RawObject manifest = put(provider, prefix + "manifest.json", map("source_run_id", run,
                "objects", map(ISTAT, map("path", town.path, "sha256", town.sha256, "json_bytes", town.bodyBytes))));
            return map("source_run_id", run, "manifest_path", manifest.path, "manifest_sha256", manifest.sha256, "manifest_json_bytes", manifest.bodyBytes);
        }
        void icon(String active, String previous) throws Exception {
            Map<String, Object> current = run("icon2i", active);
            Map<String, Object> old = previous == null ? null : run("icon2i", previous);
            put("icon2i", "latest.json", map("latest", current, "previous", old, "disabled_run_ids", Collections.emptyList()));
        }
        void cams(String run) throws Exception {
            Map<String, Object> components = new LinkedHashMap<>();
            for (String role : Arrays.asList("core", "pollen")) {
                String provider = "core".equals(role) ? "cams_europe" : "cams_europe_pollen";
                Map<String, Object> manifest = run(provider, run);
                components.put(role, map("provider", provider, "source_run_id", run,
                    "manifest_key", "weather/v1/" + provider + "/" + manifest.get("manifest_path"),
                    "manifest_sha256", manifest.get("manifest_sha256"), "manifest_json_bytes", manifest.get("manifest_json_bytes")));
            }
            PilotWeatherPrefetchCore.RawObject release = put("families/cams", "runs/" + run + "/release.json", map("source_run_id", run, "components", components));
            put("families/cams", "latest.json", map("latest", map("source_run_id", run, "release_path", release.path,
                "release_sha256", release.sha256, "release_json_bytes", release.bodyBytes), "disabled_run_ids", Collections.emptyList()));
        }
    }
    private static final class FakeConnection extends HttpsURLConnection {
        final int status;
        final byte[] bytes;
        boolean disconnected, bodyOpened;
        String mime = "application/json; charset=utf-8";
        FakeConnection(int status, byte[] bytes) throws Exception { super(new URL(PilotWeatherPrefetchCore.BASE_URL)); this.status = status; this.bytes = bytes; }
        public int getResponseCode() { return status; }
        public String getHeaderField(String name) { return "ETag".equalsIgnoreCase(name) ? "\"response\"" : null; }
        public String getContentType() { return mime; }
        public long getContentLengthLong() { return -1; }
        public InputStream getInputStream() { bodyOpened = true; return new ByteArrayInputStream(bytes); }
        public void disconnect() { disconnected = true; }
        public boolean usingProxy() { return false; }
        public void connect() {}
        public String getCipherSuite() { return "TLS_FAKE"; }
        public Certificate[] getLocalCertificates() { return null; }
        public Certificate[] getServerCertificates() { return null; }
    }
}
