"""Offline raw evidence, bounded sampling and checkpoint compatibility."""
import copy
import gzip
import hashlib
import json
import unittest
from unittest.mock import patch

import run_pilot as pilot
from test_run_pilot import snapshot_fixture
from local_pipeline.icon_quality import build_source_quality, quality_log_summary, validate_source_quality
from local_pipeline.contract_v1 import canonical_json_bytes
from local_pipeline.icon_checkpoint import encode_checkpoint, decode_checkpoint
from local_pipeline.publication_intent import PublicationIntentCorruption
import test_icon_checkpoint as checkpoints


class SourceQualityTests(unittest.TestCase):
    def test_raw_thermal_evidence_and_saturated_controls_do_not_change_public_values(self):
        snapshot = snapshot_fixture()
        snapshot['raw']['TD_2M']['values'][4][0] = 293.1502
        snapshot['raw']['TD_2M']['values'][4][1] = 293.1498
        snapshot['raw']['T_2M']['metadata'][4]['packingError'] = 0.0005
        payload = pilot.derive(snapshot)
        before = canonical_json_bytes(payload)
        quality = build_source_quality(snapshot, payload, source_sha256='d'*64)
        self.assertEqual(canonical_json_bytes(payload), before)
        self.assertEqual(quality['counts']['humidity_anomaly_rows'], 1)
        sample = quality['anomaly_samples'][0]
        self.assertEqual(sample['temperature_kelvin'], 293.15)
        self.assertEqual(sample['dewpoint_kelvin'], 293.1502)
        self.assertIn('dewpoint_above_temperature', sample['reasons'])
        self.assertIn('relative_humidity_outside_range', sample['reasons'])
        self.assertGreater(sample['rh_unclipped_pct'], 100)
        self.assertEqual(quality['near_saturation_controls'][0]['grid_index'], 1)
        self.assertEqual(quality['packing_by_field_and_lead']['T_2M'][4]['packingError'], 0.0005)
        self.assertIsNone(payload['municipalities'][0]['hourly'][4]['relative_humidity_pct'])
        log = quality_log_summary(quality)
        self.assertEqual(log['quality_municipality_hours'], 15695)
        self.assertNotIn('anomaly_samples', log)

    def test_sample_cap_does_not_truncate_counts_and_resolution_is_retained(self):
        snapshot = snapshot_fixture()
        for lead in range(73):
            snapshot['raw']['TD_2M']['values'][lead] = [293.1502]*215
        payload = pilot.derive(snapshot)
        with patch('local_pipeline.icon_quality.MAX_ANOMALY_SAMPLES', 3):
            quality = build_source_quality(snapshot, payload, source_sha256='d'*64)
        self.assertEqual(quality['counts']['humidity_anomaly_rows'], 15695)
        self.assertEqual(len(quality['anomaly_samples']), 3)
        self.assertTrue(quality['sampling']['anomaly_samples_truncated'])
        self.assertEqual(quality['counts']['null_rows']['precipitation_previous_hour_mm'], 215)
        self.assertGreater(quality['accumulation_resolution_ranges']['TOT_PREC']['maximum_mm'], 0)
        self.assertEqual(quality['field_sha256']['TD_2M'], 'c'*64)

    def test_distinct_towns_on_same_grid_are_counted_but_not_sampled_twice(self):
        snapshot = snapshot_fixture()
        snapshot['grid_points'][1]['index'] = 0
        for index in (0, 1):
            snapshot['raw']['TD_2M']['values'][4][index] = 293.1502
        quality = build_source_quality(snapshot, pilot.derive(snapshot), source_sha256='d'*64)
        self.assertEqual(quality['counts']['humidity_anomaly_rows'], 2)
        self.assertEqual(quality['counts']['humidity_anomaly_grid_hours'], 1)
        self.assertEqual(len(quality['anomaly_samples']), 1)

    def test_legacy_checkpoint_quality_is_unavailable_not_zero(self):
        self.assertEqual(quality_log_summary(None), {'quality_available':False, 'quality_reason':'legacy_checkpoint_without_quality'})


class QualityCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        checkpoints.IconCheckpointTests.setUpClass()
        cls.fixture = checkpoints.IconCheckpointTests
        snap = snapshot_fixture()
        cls.quality = build_source_quality(snap, pilot.derive(snap), source_sha256='d'*64)
        # The independently generated checkpoint fixture has a different date.
        cls.quality['source_run_id'] = cls.fixture.prepared.source_run_id

    def encoded(self, quality):
        return encode_checkpoint(slot=checkpoints.SLOT, prepared=self.fixture.prepared,
            intent=self.fixture.intent, catalog=self.fixture.catalog, source_quality=quality)

    def test_v2_round_trip_keeps_public_bytes_and_v1_remains_readable(self):
        restored = decode_checkpoint(self.encoded(self.quality), slot=checkpoints.SLOT, catalog=self.fixture.catalog)
        self.assertEqual(restored.source_quality, self.quality)
        self.assertEqual(restored.prepared.documents, self.fixture.prepared.documents)
        self.assertEqual(restored.prepared.manifest_bytes, self.fixture.prepared.manifest_bytes)
        legacy = decode_checkpoint(self.fixture.body, slot=checkpoints.SLOT, catalog=self.fixture.catalog)
        self.assertIsNone(legacy.source_quality)

    def test_tampered_diagnostics_are_rejected(self):
        envelope = json.loads(gzip.decompress(self.encoded(self.quality)))
        envelope['source_quality']['counts']['humidity_anomaly_rows'] = 1
        with self.assertRaises(PublicationIntentCorruption):
            decode_checkpoint(gzip.compress(canonical_json_bytes(envelope)), slot=checkpoints.SLOT, catalog=self.fixture.catalog)

    def test_wrong_run_identity_and_oversized_diagnostics_are_rejected(self):
        quality = copy.deepcopy(self.quality)
        quality['source_run_id'] = '20260101T000000Z'
        with self.assertRaises(ValueError):
            self.encoded(quality)
        with patch('local_pipeline.icon_quality.MAX_DIAGNOSTIC_BYTES', 10), self.assertRaises(ValueError):
            self.encoded(self.quality)
