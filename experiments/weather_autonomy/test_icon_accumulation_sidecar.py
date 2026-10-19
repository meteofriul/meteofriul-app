"""Offline publication/rollback and old-document compatibility regressions."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import unittest
from unittest.mock import patch

from local_pipeline.accumulation_tolerance import build_accumulation_quality
from local_pipeline.icon_accumulation_sidecar import split_document, validate_sidecar
from local_pipeline.contract_v1 import build_icon_payload, build_run_manifest, canonical_json_bytes, ContractError
from local_pipeline.contract_publisher import ContractV1Publisher, ImmutableContractConflict
from local_pipeline.published_runs_reader import PublishedRunsObjectReader, PublishedRunsReaderError
from local_pipeline.sqlite_object_store import ObjectNotFound
from local_pipeline.http_data_plane import _request_object_key
import test_contract_publisher as fixtures

RUN = datetime(2026, 10, 19, tzinfo=timezone.utc)
TARGET = '093033'


def bundle(run=RUN):
    fixtures.ContractPublisherTests.setUpClass()
    catalog = fixtures.ContractPublisherTests.catalog
    docs, manifest = fixtures.ContractPublisherTests.icon_bundle(run)
    docs, manifest = dict(docs), copy.deepcopy(manifest)
    item = json.loads(docs[TARGET])
    for row in item['hourly'][1:]:
        inputs = {f: dict(value_mm=0, status='valid', uncertainty_mm=0)
                  for f in ('TOT_PREC', 'RAIN_CON', 'RAIN_GSP', 'SNOW_CON', 'SNOW_GSP')}
        for f in ('TOT_PREC', 'RAIN_GSP', 'SNOW_GSP'):
            inputs[f] = dict(value_mm=None, status='positive_within_encoding_resolution', uncertainty_mm=0.001)
        for name in ('precipitation_mm', 'liquid_rain_mm', 'snow_water_equivalent_mm'):
            row[name] = None
        row['accumulation_quality'] = build_accumulation_quality(inputs, {f: [0.0005, 0.0005] for f in inputs})
    enriched = build_icon_payload(catalog=catalog, istat_code=TARGET, run_at=item['run_at'],
        generated_at=item['generated_at'], model_point=item['municipality']['model_point'], hourly=item['hourly'])
    docs[TARGET] = canonical_json_bytes(enriched)
    manifest = build_run_manifest(provider='icon2i', catalog=catalog, run_at=item['run_at'],
                                  generated_at=item['generated_at'], objects=docs)
    return catalog, docs, manifest


class IconSidecarTests(unittest.TestCase):
    def setUp(self):
        self.catalog, self.docs, self.manifest = bundle()
        self.store = fixtures.MemoryObjectStore()
        self.publisher = ContractV1Publisher(self.store, self.catalog)
        self.run = self.manifest['source_run_id']
        self.weather_key = f'weather/v1/icon2i/runs/{self.run}/municipalities/{TARGET}.json'
        self.quality_key = self.weather_key.replace('/municipalities/', '/accumulation-quality/')
        self.latest_key = 'weather/v1/icon2i/latest.json'

    def publish(self):
        return self.publisher.publish_run('icon2i', self.docs, self.manifest, published_at='2026-10-19T06:00:00Z')

    def test_public_documents_have_only_original_fields_and_nulls(self):
        self.publish()
        reader = PublishedRunsObjectReader(self.store, self.catalog)
        for code in self.catalog.istat_codes:
            original = json.loads(self.docs[code])
            expected = copy.deepcopy(original)
            for row in expected['hourly']:
                row.pop('accumulation_quality', None)
            body = reader.get(self.publisher.payload_key('icon2i', self.run, code)).body
            self.assertEqual(json.loads(body), expected)
        public = reader.get(self.weather_key).body
        evidence = reader.get(self.quality_key)
        self.assertEqual(reader.head(self.quality_key).sha256, evidence.sha256)
        self.assertEqual(validate_sidecar(evidence.body, public)['source_run_id'], self.run)
        from cloud_reader import PilotApplication
        response = []
        served = b''.join(PilotApplication(lambda: reader)(
            {'REQUEST_METHOD': 'GET', 'PATH_INFO': '/' + self.quality_key},
            lambda status, headers: response.append(status)))
        self.assertEqual(response, ['200 OK'])
        self.assertEqual(served, evidence.body)
        self.assertIsNone(json.loads(public)['hourly'][1]['snow_water_equivalent_mm'])
        self.assertEqual(self.publish().latest_updated, False)

    def test_staged_or_revoked_evidence_is_not_exposed(self):
        self.publisher.stage_run('icon2i', self.docs, self.manifest)
        with self.assertRaises(PublishedRunsReaderError):
            PublishedRunsObjectReader(self.store, self.catalog)
        self.publish()
        reader = PublishedRunsObjectReader(self.store, self.catalog)
        reader.get(self.quality_key)
        _, docs, manifest = bundle(RUN + timedelta(hours=12))
        self.publisher.publish_run('icon2i', docs, manifest, published_at='2026-10-19T18:00:00Z')
        self.publisher.revoke_run('icon2i', self.run, published_at='2026-10-19T19:00:00Z')
        with self.assertRaises(ObjectNotFound): reader.get(self.quality_key)

    def test_sidecar_failure_never_advances_latest(self):
        put = self.store.put
        def fail(key, *args, **kwargs):
            if '/accumulation-quality/' in key: raise OSError('simulated storage failure')
            return put(key, *args, **kwargs)
        with patch.object(self.store, 'put', side_effect=fail), self.assertRaises(OSError): self.publish()
        self.assertFalse(self.store.exists(self.latest_key))

    def test_recovery_authenticates_enriched_fingerprint_after_manifest_crash(self):
        self.publisher.stage_run('icon2i', self.docs, self.manifest)
        fingerprint = hashlib.sha256(canonical_json_bytes(self.manifest)).hexdigest()
        result = self.publisher.publish_existing_run('icon2i', self.run,
            expected_manifest_sha256=fingerprint, published_at='2026-10-19T06:00:00Z')
        self.assertTrue(result.latest_updated)
        self.assertFalse(self.publisher.publish_existing_run('icon2i', self.run,
            expected_manifest_sha256=fingerprint, published_at='2026-10-19T06:00:00Z').latest_updated)

    def test_recovery_rejects_missing_or_changed_evidence(self):
        self.publisher.stage_run('icon2i', self.docs, self.manifest)
        self.store.objects.pop(self.quality_key)
        with self.assertRaises(ImmutableContractConflict):
            self.publisher.publish_existing_run('icon2i', self.run,
                expected_manifest_sha256=hashlib.sha256(canonical_json_bytes(self.manifest)).hexdigest(),
                published_at='2026-10-19T06:00:00Z')
        self.assertFalse(self.store.exists(self.latest_key))

    def test_evidence_cannot_cross_weather_bytes_run_city_or_hour(self):
        public, body = split_document(self.docs[TARGET])
        for field, value in (('weather_sha256', '0'*64), ('source_run_id', '20261018T000000Z'), ('istat_code', '030129')):
            altered = json.loads(body); altered[field] = value
            with self.assertRaises(ContractError): validate_sidecar(canonical_json_bytes(altered), public)
        altered = json.loads(body); altered['hourly'][1]['valid_at'] = altered['hourly'][2]['valid_at']
        with self.assertRaises(ContractError): validate_sidecar(canonical_json_bytes(altered), public)
        altered = json.loads(public); altered['hourly'][1]['temperature_c'] += 1
        with self.assertRaises(ContractError): validate_sidecar(body, canonical_json_bytes(altered))

    def test_reader_rejects_corrupted_evidence_but_keeps_public_weather(self):
        self.publish()
        stored = self.store.get(self.quality_key)
        value = json.loads(stored.body); value['weather_sha256'] = '0'*64
        self.store.compare_and_swap(self.quality_key, canonical_json_bytes(value),
                                    expected_etag=stored.etag, content_type='application/json')
        reader = PublishedRunsObjectReader(self.store, self.catalog)
        with self.assertRaises(PublishedRunsReaderError): reader.get(self.quality_key)
        self.assertEqual(reader.get(self.weather_key).body, split_document(self.docs[TARGET])[0])

    def test_route_is_scoped_to_icon_and_rejects_path_traversal(self):
        self.assertEqual(_request_object_key('/' + self.quality_key), self.quality_key)
        for path in (self.quality_key.replace('icon2i', 'cams_europe'),
                     self.quality_key.replace(TARGET, '..'), self.quality_key + '?x=1'):
            with self.assertRaises(ValueError): _request_object_key('/' + path)


if __name__ == '__main__': unittest.main()
