"""Read-only verification through the HTTPS reader for this deployment.

Storage validation remains the publisher's responsibility (all 215 towns).
This additional gate checks the family pointer, both manifests and a real town
through HTTP, plus the entire regional UV document. No source-provider requests.
"""
import hashlib
import json
import os
import re
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

FAMILY = 'weather/v1/families/cams/latest.json'
UV = 'weather/v1/uv/latest.json'
_KEY = re.compile(r'weather/v1/(?:uv/latest\.json|families/cams/(?:latest\.json|runs/\d{8}T\d{6}Z/release\.json)|cams_europe(?:_pollen)?/runs/\d{8}T\d{6}Z/(?:manifest\.json|municipalities/\d{6}\.json))\Z')
_RUN_APP_HOST = re.compile(r'[a-z][a-z0-9-]*\.europe-west1\.run\.app\Z')


class ReadbackPending(RuntimeError):
    retryable = True


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def public_base():
    """Return the explicitly configured reader for this deployment.

    A worker must verify the same environment it writes. There is deliberately
    no pilot fallback: a missing value is a deployment error, not permission to
    read another project's public service.
    """
    value = os.environ.get('WEATHER_PUBLIC_BASE_URL', '').rstrip('/')
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname
            or not _RUN_APP_HOST.fullmatch(parsed.hostname)
            or parsed.username is not None or parsed.password is not None
            or parsed.port is not None or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('valid WEATHER_PUBLIC_BASE_URL is required')
    return value


def fetch_public(key):
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError('Invalid weather readback path')
    request = Request(public_base() + '/' + key, headers={
        'Accept': 'application/json', 'Accept-Encoding': 'identity',
        'Origin': 'https://localhost', 'Cache-Control': 'no-cache',
    })
    with build_opener(NoRedirects()).open(request, timeout=30) as response:
        if (response.status != 200 or response.headers.get_content_type() != 'application/json'
                or response.headers.get('Access-Control-Allow-Origin') != 'https://localhost'):
            raise ReadbackPending('public_reader_unavailable')
        raw = response.read(2 * 1024**2 + 1)
        if not 0 < len(raw) <= 2 * 1024**2:
            raise ReadbackPending('public_reader_invalid_size')
    return raw


def _same(data, key, fetch):
    stored = data.get(key).body
    observed = fetch(key)
    if stored != observed:
        raise ReadbackPending('public_reader_not_current')
    return json.loads(stored)


def verify_uv(data, expected_run, fetch=fetch_public):
    from uv_cloud import validate_document
    before = data.get(UV).body
    doc = _same(data, UV, fetch)
    validate_document(doc)
    if doc.get('run_at', '').replace('-', '').replace(':', '') != expected_run:
        raise ReadbackPending('public_uv_run_mismatch')
    if data.get(UV).body != before or fetch(UV) != before:
        raise ReadbackPending('public_uv_pointer_changed')
    return {'readback_sha256': hashlib.sha256(before).hexdigest()}


def verify_cams(data, expected_run, fetch=fetch_public):
    before = data.get(FAMILY).body
    pointer = _same(data, FAMILY, fetch)
    latest = pointer['latest']
    if latest['source_run_id'] != expected_run:
        raise ReadbackPending('public_cams_run_mismatch')
    release = _same(data, 'weather/v1/families/cams/' + latest['release_path'], fetch)
    if release['source_run_id'] != expected_run:
        raise ReadbackPending('public_cams_release_mismatch')
    for role, provider in [('core', 'cams_europe'), ('pollen', 'cams_europe_pollen')]:
        component = release['components'][role]
        # Family releases carry a full manifest_key; manifest_path belongs to
        # the separate per-provider latest contract, not the atomic family.
        manifest_key = f'weather/v1/{provider}/runs/{expected_run}/manifest.json'
        if component.get('manifest_key') != manifest_key:
            raise ReadbackPending('public_cams_manifest_mismatch')
        manifest = _same(data, manifest_key, fetch)
        if manifest['source_run_id'] != expected_run or len(manifest['objects']) != 215:
            raise ReadbackPending('public_cams_manifest_mismatch')
        town = manifest['objects']['093033']  # Pordenone, real pilot client path.
        _same(data, 'weather/v1/' + provider + '/' + town['path'], fetch)
    if data.get(FAMILY).body != before or fetch(FAMILY) != before:
        raise ReadbackPending('public_cams_pointer_changed')
    return {'readback_sha256': hashlib.sha256(before).hexdigest(),
            'manifest_municipality_count': 215, 'http_sample_istat': '093033'}
