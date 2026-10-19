import gzip
import hashlib
import json
import unittest
from datetime import timedelta

from local_pipeline.accumulation_tolerance import build_accumulation_quality, validate_accumulation_quality
from local_pipeline.contract_v1 import canonical_json_bytes, load_catalog, _validate_icon_hour
from local_pipeline.icon_checkpoint import encode_checkpoint, decode_checkpoint
from local_pipeline.job_entrypoints import PreparedIconPublication
from local_pipeline.job_outcomes import JobKind
from local_pipeline.publication_intent import PublicationIntent
from local_pipeline.snapshot_materializer import materialize_icon_documents
from local_pipeline.icon_quality import build_source_quality, quality_log_summary
from test_run_pilot import snapshot_fixture, RUN_TIME
from test_contract_v1 import icon_hourly, RUN
from run_pilot import derive


def known(value=0):
    return dict(value_mm=value, status="valid", uncertainty_mm=0)


def unresolved(budget=0.001):
    return dict(value_mm=None, status="positive_within_encoding_resolution", uncertainty_mm=budget)


def intervals():
    return {f: known() for f in ("TOT_PREC", "RAIN_CON", "RAIN_GSP", "SNOW_CON", "SNOW_GSP")}


class AccumulationToleranceTests(unittest.TestCase):
    def test_sum_of_components_not_a_budget_per_component(self):
        data = intervals()
        data.update(SNOW_CON=unresolved(0.012), SNOW_GSP=unresolved(0.012))
        q = build_accumulation_quality(data, {"SNOW_CON": [0.001, 0.001], "SNOW_GSP": [0.001, 0.001]})
        self.assertEqual(q['fields']['snow_water_equivalent_mm']['reason'], 'resolution_budget_exceeded')
        data['SNOW_CON'] = known(0.7)
        q = build_accumulation_quality(data, {"SNOW_GSP": [0.001, 0.001]})
        self.assertEqual(q['fields']['snow_water_equivalent_mm']['state'], 'resolution_tolerance_verified')
        self.assertEqual(q['fields']['snow_water_equivalent_mm']['known_component_sum_mm'], 0.7)

    def test_missing_packing_and_genuine_missing_are_distinct(self):
        data = intervals(); data['TOT_PREC'] = unresolved()
        self.assertEqual(build_accumulation_quality(data, {})['fields']['precipitation_mm']['reason'], 'resolution_metadata_missing')
        data['TOT_PREC'] = dict(value_mm=None, status='invalid')
        self.assertEqual(build_accumulation_quality(data, {})['fields']['precipitation_mm']['reason'], 'missing_or_invalid_accumulation')

    def test_legacy_rows_and_verified_extension_validate_but_forged_proof_does_not(self):
        row = icon_hourly()[1]
        _validate_icon_hour(row, RUN + timedelta(hours=1), RUN)
        row['accumulation_quality'] = build_accumulation_quality(intervals(), {})
        _validate_icon_hour(row, RUN + timedelta(hours=1), RUN)
        row['accumulation_quality']['fields']['precipitation_mm']['known_component_sum_mm'] = 1
        with self.assertRaises(ValueError):
            _validate_icon_hour(row, RUN + timedelta(hours=1), RUN)

    def test_negative_resolution_is_explicit_and_missing_never_verified(self):
        data = intervals(); data['SNOW_GSP'] = unresolved()
        data['SNOW_GSP']['status'] = 'negative_within_encoding_resolution'
        q = build_accumulation_quality(data, {'SNOW_GSP': [0.001, 0.001]})
        self.assertEqual(q['fields']['snow_water_equivalent_mm']['state'], 'resolution_tolerance_verified')
        row = dict(precipitation_mm=0, liquid_rain_mm=0, snow_water_equivalent_mm=None)
        validate_accumulation_quality(q, row)
        row['snow_water_equivalent_mm'] = 0
        with self.assertRaises(ValueError): validate_accumulation_quality(q, row)

    def test_full_producer_materializer_and_quality_counts(self):
        source = snapshot_fixture(); catalog = load_catalog()
        source['catalog_sha256'] = catalog.sha256
        source['points'] = [dict(slug=t.slug, name=t.name, latitude=t.latitude, longitude=t.longitude,
                                 istatCode=t.istat_code) for t in catalog.municipalities]
        source['grid_points'] = [dict(lat=t.latitude, lon=t.longitude, distance=0, index=i)
                                 for i, t in enumerate(catalog.municipalities)]
        for field in ('TOT_PREC', 'SNOW_GSP'):
            source['raw'][field]['values'][1][0] = 0.0001
            for meta in source['raw'][field]['metadata']:
                meta['packingError'] = 0.0005
        # One missing metadata guard, distinct from genuine lead-zero missing intervals.
        source['raw']['RAIN_GSP']['values'][1][0] = 0.0001
        payload = derive(source, now=RUN_TIME + timedelta(hours=1))
        payload['catalog_sha256'] = catalog.sha256
        docs, manifest = materialize_icon_documents(payload, catalog)
        public = json.loads(docs[catalog.municipalities[0].istat_code])
        self.assertIsNone(public['hourly'][1]['snow_water_equivalent_mm'])
        self.assertEqual(public['hourly'][1]['accumulation_quality']['fields']['snow_water_equivalent_mm']['state'], 'resolution_tolerance_verified')
        self.assertEqual(public['hourly'][1]['accumulation_quality']['fields']['liquid_rain_mm']['reason'], 'resolution_metadata_missing')
        quality = build_source_quality(source, payload, source_sha256='d'*64)
        log = quality_log_summary(quality)
        self.assertEqual(log['quality_tolerance_expected_snow'], 215*73)
        self.assertEqual(log['quality_tolerance_verified_snow'], 1)
        self.assertEqual(log['quality_guard_rain_resolution_metadata_missing'], 1)
        self.assertEqual(log['quality_guard_snow_missing_or_invalid_accumulation'], 215)
        self.assertEqual(len(docs), 215)
        manifest_bytes = canonical_json_bytes(manifest)
        prepared = PreparedIconPublication(manifest['source_run_id'], hashlib.sha256(manifest_bytes).hexdigest(), docs, manifest_bytes)
        intent = PublicationIntent(JobKind.ICON, prepared.source_run_id, '2026-09-03T06:00:00Z', prepared.input_fingerprint_sha256)
        body = encode_checkpoint(slot='20260903-am', prepared=prepared, intent=intent, catalog=catalog, source_quality=quality)
        restored = decode_checkpoint(body, slot='20260903-am', catalog=catalog)
        self.assertEqual(restored.prepared.documents, docs)
        self.assertEqual(restored.source_quality, quality)
        self.assertLess(len(body), 16*1024**2)
        self.assertLess(len(gzip.decompress(body)), 64*1024**2)


if __name__ == '__main__': unittest.main()
