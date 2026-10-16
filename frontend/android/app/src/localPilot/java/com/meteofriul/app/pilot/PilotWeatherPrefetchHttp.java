package com.meteofriul.app.pilot;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URL;
import java.util.Locale;
import javax.net.ssl.HttpsURLConnection;

/** Exact-origin, bounded HTTPS transport; no redirects, credentials or legacy API. */
public final class PilotWeatherPrefetchHttp implements PilotWeatherPrefetchCore.Transport {
    interface Connections { HttpsURLConnection open(URL url) throws IOException; }
    interface Cancellation { boolean stopped(); }
    private final Connections connections;
    private final Cancellation cancellation;
    public PilotWeatherPrefetchHttp(Cancellation cancellation) {
        this(url -> (HttpsURLConnection) url.openConnection(), cancellation);
    }
    PilotWeatherPrefetchHttp(Connections connections, Cancellation cancellation) {
        this.connections = connections; this.cancellation = cancellation;
    }
    @Override
    public PilotWeatherPrefetchCore.Response get(String provider, String path, String etag, int maxBytes) throws IOException {
        if (!PilotWeatherPrefetchCore.allowedPath(provider, path, null, true)
            || maxBytes < 2 || maxBytes > PilotWeatherPrefetchCore.maximumBytes(path)
            || (etag != null && !PilotWeatherPrefetchCore.validEtag(etag))) {
            throw new PilotWeatherPrefetchCore.Failure("invalid_request", false);
        }
        checkStopped();
        URL url = new URL(PilotWeatherPrefetchCore.BASE_URL + "/weather/v1/" + provider + "/" + path);
        HttpsURLConnection connection = connections.open(url);
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(12_000);
        connection.setReadTimeout(12_000);
        connection.setRequestMethod("GET");
        connection.setRequestProperty("Accept", "application/json");
        connection.setUseCaches(false);
        if (etag != null) connection.setRequestProperty("If-None-Match", etag);
        try {
            int status = connection.getResponseCode();
            checkStopped();
            if (status != 200) return new PilotWeatherPrefetchCore.Response(status,
                status == 304 ? connection.getHeaderField("ETag") : null, null);
            String type = connection.getContentType();
            if (type == null || !type.toLowerCase(Locale.ROOT).matches("application/json(?:\\s*;.*)?")) {
                throw new PilotWeatherPrefetchCore.Failure("invalid_content_type", false);
            }
            String responseEtag = connection.getHeaderField("ETag");
            if (!PilotWeatherPrefetchCore.validEtag(responseEtag)) {
                throw new PilotWeatherPrefetchCore.Failure("invalid_etag", false);
            }
            long length = connection.getContentLengthLong();
            if (length > maxBytes) throw new PilotWeatherPrefetchCore.Failure("body_limit", false);
            try (InputStream stream = connection.getInputStream()) {
                ByteArrayOutputStream body = new ByteArrayOutputStream(Math.min(maxBytes, 8192));
                byte[] buffer = new byte[8192];
                int count;
                while ((count = stream.read(buffer)) != -1) {
                    checkStopped();
                    if (body.size() + count > maxBytes) throw new PilotWeatherPrefetchCore.Failure("body_limit", false);
                    body.write(buffer, 0, count);
                }
                return new PilotWeatherPrefetchCore.Response(status, responseEtag, body.toByteArray());
            }
        } finally { connection.disconnect(); }
    }
    private void checkStopped() throws PilotWeatherPrefetchCore.Failure {
        if (Thread.currentThread().isInterrupted() || cancellation.stopped()) {
            throw new PilotWeatherPrefetchCore.Failure("cancelled", false);
        }
    }
}
