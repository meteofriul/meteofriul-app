"""Behavioral regressions for independent availability and explicit degradation."""
import copy
import unittest

from app.weather.local_notice_source import _adapt_icon_row
from app.weather.local_notice_quality import QualityCounter, utc_stamp
from app.weather import local_notice_shadow as detector
from app.services.location import LocationCatalog
import test_local_notice_shadow as fixture
import test_local_notice_source as source_fixture
import test_local_notice_delivery_service as delivery
import test_local_notice_shadow_service as shadow_service
import test_send_local_weather_notices_job as job


def outcomes(snapshot):
    return fixture.evaluate(snapshot)['data_quality']['phenomena']


def native_snapshot(**overrides):
    snapshot = fixture.build_snapshot(**overrides)
    snapshot['hourly']['native_weather_code'] = [1] * 6
    snapshot['hourly_units']['native_weather_code'] = 'wmo code'
    return snapshot


class PerPhenomenonTests(unittest.TestCase):
    def test_missing_inputs_block_exact_dependencies(self):
        expected = {
            'wind_gusts_10m': {'wind'}, 'temperature_2m': {'heat'}, 'apparent_temperature': {'heat'},
            'precipitation': {'rain', 'snow'}, 'precipitation_probability': {'rain', 'snow'},
            'rain': {'rain'}, 'showers': {'rain'}, 'snowfall': {'snow'},
            'weather_code': {'snow'}, 'native_weather_code': {'storm', 'ice'},
        }
        for field, blocked in expected.items():
            with self.subTest(field=field):
                snap = native_snapshot()
                snap['hourly'][field][1] = None
                actual = outcomes(snap)
                self.assertEqual({k for k, v in actual.items() if v['state'] == 'not_evaluable'}, blocked)
                self.assertTrue(all(v['cause_class'] == 'other_or_mixed' for k, v in actual.items() if k in blocked))

    def test_adapter_separates_native_code_and_accumulation_derived_code(self):
        row = source_fixture.municipality_payload()['hourly'][0]
        row.update(precipitation_mm=None, liquid_rain_mm=None, snow_water_equivalent_mm=None)
        snap = native_snapshot(wind_gusts_10m=[80]*6, temperature_2m=[36]*6, apparent_temperature=[40]*6)
        row.update(temperature_c=36, apparent_temperature_c=40, wind_gust_max_m_s=80/3.6)
        adapted, issues = _adapt_icon_row(row, source_fixture.NOW)
        self.assertEqual(adapted['native_weather_code'], row['condition']['native_code'])
        self.assertIsNone(adapted['weather_code'])
        for field, value in adapted.items():
            if field != 'time':
                snap['hourly'][field] = [value]*6
        result = fixture.evaluate(snap)
        self.assertEqual(result['status'], 'partial_evaluation')
        states = result['data_quality']['phenomena']
        self.assertEqual({c['kind'] for c in result['candidates']}, {'wind', 'heat'})
        self.assertEqual(states['wind']['state'], 'evaluated_with_candidate')
        self.assertEqual(states['heat']['state'], 'evaluated_with_candidate')
        self.assertEqual(states['storm']['state'], 'evaluated_no_candidate')
        self.assertEqual(states['ice']['state'], 'evaluated_no_candidate')
        self.assertEqual(states['rain']['state'], 'not_evaluable')
        self.assertEqual(states['snow']['state'], 'not_evaluable')

    def test_invalid_native_code_never_becomes_clear_for_storm_or_ice(self):
        for value, status in ((None, 'valid'), (False, 'valid'), ('0', 'valid'), (2.5, 'valid'), (0, 'invalid')):
            row = source_fixture.municipality_payload()['hourly'][0]
            row['condition'] = dict(native_code=value, native_status=status)
            adapted, _ = _adapt_icon_row(row, source_fixture.NOW)
            self.assertIsNone(adapted['native_weather_code'])
        snap = native_snapshot()
        snap['hourly']['native_weather_code'][0] = None
        states = outcomes(snap)
        self.assertEqual(states['storm']['state'], 'not_evaluable')
        self.assertEqual(states['ice']['state'], 'not_evaluable')

    def test_storm_corroboration_missing_is_not_evaluable_known_zero_is_unconfirmed(self):
        snap = native_snapshot()
        snap['hourly']['native_weather_code'][0] = 95
        known = fixture.evaluate(snap)
        candidate = fixture.candidate_for(known, 'storm')
        self.assertFalse(candidate['confidence']['corroborated'])
        self.assertEqual(known['data_quality']['phenomena']['storm']['state'], 'evaluated_with_candidate')
        for field in ('precipitation', 'precipitation_probability', 'rain', 'showers'):
            bad = copy.deepcopy(snap)
            bad['hourly'][field][0] = None
            result = fixture.evaluate(bad)
            self.assertEqual(result['data_quality']['phenomena']['storm']['state'], 'not_evaluable')
            self.assertIsNone(fixture.candidate_for(result, 'storm'))
        snap['hourly']['native_weather_code'][0] = 66
        snap['hourly']['precipitation'][0] = None
        self.assertIsNotNone(fixture.candidate_for(fixture.evaluate(snap), 'ice'))

    def test_resolution_and_other_or_mixed_are_exclusive(self):
        snap = native_snapshot()
        snap['source_run_id'] = '20261019T000000Z'
        snap['hourly']['precipitation'][0] = None
        slots, _ = detector._build_slots(snap['hourly'], now=fixture.NOW)
        at = utc_stamp(slots[0]['event_at'])
        snap['source_quality_issues'] = [dict(at=at, field='precipitation', variable='precipitation_mm', reason='positive_within_encoding_resolution')]
        first = fixture.evaluate(snap)
        self.assertEqual(first['data_quality']['phenomena']['rain']['cause_class'], 'only_resolution')
        snap['hourly']['rain'][1] = None
        mixed = fixture.evaluate(snap)
        self.assertEqual(mixed['data_quality']['phenomena']['rain']['cause_class'], 'other_or_mixed')
        self.assertEqual(mixed['data_quality']['phenomena']['snow']['cause_class'], 'only_resolution')
        counter = QualityCounter()
        counter.add(('one', ''), first['data_quality'])
        counter.add(('one', ''), first['data_quality'])  # Another device does not multiply it.
        counter.add(('two', ''), mixed['data_quality'])
        totals = counter.summary()['by_source_run'][0]['phenomena']['rain']
        self.assertEqual(totals['expected'], 2)
        self.assertEqual(totals['not_evaluable'], 2)
        self.assertEqual(totals['only_resolution'], 1)
        self.assertEqual(totals['other_or_mixed'], 1)

    def test_fully_missing_and_contract_error_have_different_status(self):
        snap = native_snapshot()
        for field in snap['hourly']:
            if field != 'time':
                snap['hourly'][field] = [None]*6
        missing = fixture.evaluate(snap)
        self.assertEqual(missing['status'], 'not_evaluable')
        self.assertEqual(missing['validation_errors'], [])
        self.assertEqual(missing['data_quality']['evaluations_not_possible'], 1)
        del snap['hourly']['rain']
        contract = fixture.evaluate(snap)
        self.assertEqual(contract['status'], 'rejected')
        self.assertIn('missing_hourly_field:rain', contract['validation_errors'])
        self.assertEqual(contract['data_quality']['phenomena_not_possible'], 6)

    def test_time_gap_and_native_unit_error_reject_entire_snapshot(self):
        snap = native_snapshot()
        snap['hourly']['time'][2] = snap['hourly']['time'][1]
        self.assertEqual(fixture.evaluate(snap)['status'], 'rejected')
        snap = native_snapshot()
        snap['hourly_units']['native_weather_code'] = 'mm'
        self.assertEqual(fixture.evaluate(snap)['status'], 'rejected')

    def test_partial_without_candidate_is_visible_in_delivery_audit_and_exit(self):
        snap = delivery.snapshot()
        snap['hourly']['rain'][1] = None
        audit = delivery.FakeAuditRepository()
        sender = delivery.FakeSender()
        service = delivery.LocalNoticeDeliveryServiceTests.make_service(self, source=delivery.FakeSource(snap), audit=audit, sender=sender)
        result = service.run()
        self.assertEqual(result.status, 'data_degraded')
        self.assertEqual(result.data_degraded_groups, 1)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.source_failed, 0)
        self.assertEqual(result.attempted, 0)
        self.assertEqual(sender.payloads, [])
        self.assertEqual(audit.saved[-1]['delivery_status'], 'partial_evaluation')
        code, logged, _ = job.SendLocalWeatherNoticesJobTests.run_job(self, value=result)
        self.assertEqual(code, 1)  # Monitoring policy must be checked before changing this.
        self.assertEqual(logged['data_quality']['evaluations_partial'], 1)

    def test_shadow_runner_keeps_partial_visible_without_network_or_notifications(self):
        municipality = LocationCatalog().match_istat('093033')
        snap = shadow_service.snapshot_for(municipality)
        snap['hourly']['rain'][1] = None
        audit = shadow_service.FakeShadowRepository()
        service = shadow_service.LocalNoticeShadowService(
            device_repository=shadow_service.FakeDeviceRepository([shadow_service.device()]),
            shadow_repository=audit, source=shadow_service.FakeSource(snapshot=snap),
            config=shadow_service.config(), now=lambda: shadow_service.NOW)
        result = service.run()
        self.assertEqual(result.status, 'partial_evaluation')
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.rejected, 0)
        self.assertEqual(result.data_quality['evaluations_partial'], 1)
        self.assertEqual(audit.saved[0]['evaluation']['status'], 'partial_evaluation')

    def test_deferred_candidate_is_evaluated_but_not_sendable_yet(self):
        snap = native_snapshot(wind_gusts_10m=[20, 20, 80, 80, 20, 20])
        result = fixture.evaluate(snap)
        self.assertEqual(result['data_quality']['phenomena']['wind']['state'], 'evaluated_with_candidate')
        self.assertEqual(result['candidates'], [])
        self.assertTrue(any(o['reason'] == 'onset_beyond_notice_window' for o in result['observations']))
