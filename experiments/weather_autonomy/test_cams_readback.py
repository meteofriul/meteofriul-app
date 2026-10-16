import json
import os
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch
from types import SimpleNamespace
from cams_readback import public_base, verify_cams, verify_uv, ReadbackPending, FAMILY, UV
from local_pipeline.contract_publisher import ContractV1Publisher

RUN = '20260909T000000Z'


class ReadbackTests(TestCase):
    def setUp(self):
        self.objects = {}
        self.store = SimpleNamespace(get=lambda key: SimpleNamespace(body=self.objects[key]))
        self.add(FAMILY, {'latest': {'source_run_id': RUN, 'release_path': f'runs/{RUN}/release.json'}})
        components = {}
        for role, provider in [('core', 'cams_europe'), ('pollen', 'cams_europe_pollen')]:
            towns = {f'{i:06d}': {} for i in range(214)}
            towns['093033'] = {'path': f'runs/{RUN}/municipalities/093033.json'}
            manifest_key = f'weather/v1/{provider}/runs/{RUN}/manifest.json'
            self.add(manifest_key, {'source_run_id': RUN, 'objects': towns})
            # Use the production family descriptor builder, not a hand-written
            # provider-latest-shaped mock. These are different contracts.
            components[role] = ContractV1Publisher._cams_component_descriptor(
                SimpleNamespace(provider=provider, source_run_id=RUN, manifest_key=manifest_key),
                self.objects[manifest_key])
            self.add(f'weather/v1/{provider}/runs/{RUN}/municipalities/093033.json', {'run': RUN})
        self.add(f'weather/v1/families/cams/runs/{RUN}/release.json', {'source_run_id': RUN, 'components': components})
        run = datetime(2026, 9, 9, tzinfo=timezone.utc)
        self.add(UV, {'schema': 'pilot-uv-v1', 'source': 'CAMS / Copernicus', 'unit': '1',
            'run_at': '2026-09-09T00:00:00Z', 'grid': [[46.0, 13.0]],
            'hours': [{'time': (run + timedelta(hours=i)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                       'values': [1.0]} for i in range(72)]})

    def add(self, key, doc):
        self.objects[key] = json.dumps(doc).encode()

    def test_both_components_and_real_town_are_read_through_public_endpoint(self):
        calls = []
        def fetch(key):
            calls.append(key)
            return self.objects[key]
        result = verify_cams(self.store, RUN, fetch)
        self.assertEqual(result['manifest_municipality_count'], 215)
        self.assertEqual(len(calls), 7)
        self.assertTrue(any('cams_europe_pollen/runs/' in key for key in calls))

    def test_provider_latest_descriptor_is_not_a_family_descriptor(self):
        key = f'weather/v1/families/cams/runs/{RUN}/release.json'
        release = json.loads(self.objects[key])
        release['components']['core'] = {'manifest_path': f'runs/{RUN}/manifest.json'}
        self.add(key, release)
        with self.assertRaises(ReadbackPending):
            verify_cams(self.store, RUN, self.objects.__getitem__)

    def test_storage_success_is_not_public_success(self):
        for check in (verify_cams, verify_uv):
            with self.subTest(check=check.__name__), self.assertRaises(ReadbackPending):
                check(self.store, RUN, lambda key: b'{"old":true}')

    def test_old_run_is_never_verified(self):
        with self.assertRaises(ReadbackPending):
            verify_uv(self.store, '20260910T000000Z', self.objects.__getitem__)

    def test_uv_entire_document_is_verified(self):
        self.assertIn('readback_sha256', verify_uv(self.store, RUN, self.objects.__getitem__))

    def test_changed_pointer_at_end_requires_new_readback(self):
        count = 0
        def fetch(key):
            nonlocal count
            if key == FAMILY:
                count += 1
                if count == 2:
                    return b'{}'
            return self.objects[key]
        with self.assertRaises(ReadbackPending):
            verify_cams(self.store, RUN, fetch)

    def test_official_reader_is_selected_explicitly(self):
        official = 'https://meteofriul-weather-49007668366.europe-west1.run.app'
        with patch.dict(os.environ, {'WEATHER_PUBLIC_BASE_URL': official}, clear=True):
            self.assertEqual(public_base(), official)

    def test_reader_has_no_implicit_pilot_fallback(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            public_base()

    def test_reader_rejects_non_run_app_or_path(self):
        invalid = (
            'http://meteofriul-weather-49007668366.europe-west1.run.app',
            'https://example.com',
            'https://meteofriul-weather-49007668366.europe-west1.run.app/weather',
        )
        for value in invalid:
            with self.subTest(value=value), patch.dict(
                    os.environ, {'WEATHER_PUBLIC_BASE_URL': value}, clear=True), self.assertRaises(ValueError):
                public_base()
