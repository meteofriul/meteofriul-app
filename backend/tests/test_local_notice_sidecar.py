"""The producer sidecar reaches real detectors without changing public nulls."""
import copy
from datetime import timedelta
import json
from pathlib import Path
import sys
import unittest

import requests
EXPERIMENT = Path(__file__).resolve().parents[2] / 'experiments/weather_autonomy'
sys.path.insert(0, str(EXPERIMENT))
from test_icon_accumulation_sidecar import bundle, RUN, TARGET
from local_pipeline.contract_publisher import ContractV1Publisher
from local_pipeline.published_runs_reader import PublishedRunsObjectReader
from test_contract_publisher import MemoryObjectStore
from local_pipeline.contract_v1 import canonical_json_bytes
from app.weather.local_notice_source import IconLocalNoticeSource
from app.weather.local_notice_sidecar import attach_evidence
from app.weather.local_notice_quality import QualityCounter
from app.services.location import LocationCatalog
import test_local_notice_source as source
import test_local_notice_shadow as detector


class NoticeSidecarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog, cls.docs, cls.manifest = bundle()
        cls.store = MemoryObjectStore()
        publisher = ContractV1Publisher(cls.store, cls.catalog)
        publisher.publish_run('icon2i', cls.docs, cls.manifest, published_at='2026-10-19T06:00:00Z')
        cls.reader = PublishedRunsObjectReader(cls.store, cls.catalog)
        cls.root = 'weather/v1/icon2i/'
        cls.latest = cls.reader.get(cls.root + 'latest.json').body
        cls.public_manifest = cls.reader.get(cls.root + f"runs/{cls.manifest['source_run_id']}/manifest.json").body
        cls.path = json.loads(cls.public_manifest)['objects'][TARGET]['path']
        cls.public = cls.reader.get(cls.root + cls.path).body
        cls.evidence = cls.reader.get(cls.root + cls.path.replace('/municipalities/', '/accumulation-quality/')).body

    def fetch(self, evidence=None, *, enabled=True):
        responses = [source.FakeResponse(json.loads(body), raw=body)
                     for body in (self.latest, self.public_manifest, self.public)]
        if enabled:
            responses.append(evidence or source.FakeResponse(json.loads(self.evidence), raw=self.evidence))
        session = source.FakeSession(responses)
        adapter = IconLocalNoticeSource(session=session, now=lambda: RUN + timedelta(hours=6), accumulation_sidecar=enabled)
        return adapter.fetch(LocationCatalog().match_istat(TARGET)), session

    def test_end_to_end_verified_tolerance_and_public_null_preserved(self):
        snapshot, session = self.fetch()
        self.assertEqual(snapshot['accumulation_evidence_status'], 'verified')
        self.assertTrue(all(x is None for x in snapshot['hourly']['snowfall']))
        result = detector.evaluate(snapshot, now=RUN + timedelta(hours=6))
        self.assertEqual(result['data_quality']['phenomena']['snow']['state'], 'evaluated_no_candidate')
        self.assertEqual(result['data_quality']['evaluations_with_tolerance'], 1)
        counter = QualityCounter(); counter.add((TARGET, None), result['data_quality'])
        self.assertEqual(counter.summary()['by_source_run'][0]['accumulation_evidence']['verified'], 1)
        self.assertEqual(len(session.calls), 4)

    def test_absent_or_failed_sidecar_preserves_other_phenomena(self):
        for response in (source.FakeResponse(http_error=requests.HTTPError('503')),
                         source.FakeResponse(http_error=requests.HTTPError('404'))):
            snapshot, _ = self.fetch(response)
            self.assertEqual(snapshot['accumulation_evidence_status'], 'unavailable')
            result = detector.evaluate(snapshot, now=RUN + timedelta(hours=6))
            self.assertEqual(result['data_quality']['phenomena']['snow']['state'], 'not_evaluable')
            self.assertEqual(result['data_quality']['phenomena']['wind']['state'], 'evaluated_no_candidate')
            self.assertEqual(result['data_quality']['evaluations_with_tolerance'], 0)

    def test_invalid_hash_run_city_hour_or_proof_never_authorizes_tolerance(self):
        variants = []
        for field, value in (('weather_sha256', '0'*64), ('source_run_id', '20261018T000000Z'), ('istat_code', '030129')):
            altered = json.loads(self.evidence); altered[field] = value; variants.append(altered)
        altered = json.loads(self.evidence); altered['hourly'][1]['valid_at'] = '20261019'; variants.append(altered)
        altered = json.loads(self.evidence)
        altered['hourly'][6]['accumulation_quality']['fields']['snow_water_equivalent_mm']['resolution_budget_mm'] = 1
        variants.append(altered)
        for value in variants:
            snapshot, _ = self.fetch(source.FakeResponse(value))
            self.assertEqual(snapshot['accumulation_evidence_status'], 'invalid')
            self.assertTrue(all(x is None for x in snapshot['hourly']['snowfall']))
            self.assertEqual(detector.evaluate(snapshot, now=RUN + timedelta(hours=6))['data_quality']['evaluations_with_tolerance'], 0)

    def test_disabled_uses_three_requests_and_no_tolerance(self):
        snapshot, session = self.fetch(enabled=False)
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(snapshot['accumulation_evidence_status'], 'disabled')
        self.assertEqual(detector.evaluate(snapshot, now=RUN + timedelta(hours=6))['data_quality']['evaluations_with_tolerance'], 0)

    def test_disabled_flag_cannot_use_unexpected_inline_evidence(self):
        from unittest.mock import patch
        with patch.object(self, 'public', self.docs[TARGET]):
            snapshot, session = self.fetch(enabled=False)
        self.assertEqual(snapshot['accumulation_evidence_status'], 'disabled')
        self.assertTrue(all(x is None for x in snapshot['hourly']['accumulation_quality']))
        self.assertEqual(detector.evaluate(snapshot, now=RUN + timedelta(hours=6))['data_quality']['evaluations_with_tolerance'], 0)

    def test_weather_hash_must_match_manifest_and_input_not_mutated(self):
        public, evidence = json.loads(self.public), json.loads(self.evidence)
        descriptor = json.loads(self.public_manifest)['objects'][TARGET]
        before = copy.deepcopy(public)
        enriched = attach_evidence(public, self.public, descriptor, evidence)
        self.assertEqual(public, before)
        self.assertIn('accumulation_quality', enriched['hourly'][1])
        with self.assertRaises(ValueError): attach_evidence(public, self.public, {**descriptor, 'sha256':'0'*64}, evidence)
