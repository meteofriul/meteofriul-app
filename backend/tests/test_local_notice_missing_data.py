"""Missing measurements must never turn into reassuring zeroes or skipped hours."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from app.weather.local_notice_source import _adapt_icon_row, _national_interval, IconLocalNoticeSource
from app.weather.local_notice_quality import QualityCounter, evaluation_quality, sanitize_quality
from app.weather import local_notice_shadow as shadow
from app.repositories.local_notice_shadow import build_sanitized_shadow_record
from app.services.location import LocationCatalog
from app.services.morning_forecast_delivery import build_morning_forecast_body
from app.services.evening_forecast_delivery import build_evening_forecast_contents
import test_local_notice_source as source_fixture
import test_local_notice_shadow as detector_fixture
import test_local_notice_delivery_service as delivery
import test_morning_forecast_delivery as morning
import test_evening_forecast_delivery as evening
import test_send_local_weather_notices_job as job_fixture


class MissingDataTests(unittest.TestCase):
    def test_zero_remains_zero_and_bad_measurements_remain_unavailable(self):
        fields = {'precipitation_mm': 'precipitation', 'liquid_rain_mm': 'rain',
                  'snow_water_equivalent_mm': 'snowfall'}
        for native, adapted_field in fields.items():
            for value in (0, 1.25, None, False, True, '0', float('nan'), float('inf'), -1, 10**400):
                with self.subTest(field=native, value=repr(value)):
                    row = source_fixture.municipality_payload()['hourly'][0]
                    row[native] = value
                    result, _ = _adapt_icon_row(row, source_fixture.NOW)
                    expected = float(value) if type(value) in (int, float) and value in (0, 1.25) else None
                    self.assertEqual(result[adapted_field], expected)
            del row[native]
            self.assertIsNone(_adapt_icon_row(row, source_fixture.NOW)[0][adapted_field])

    def test_total_is_never_reconstructed_from_complete_or_partial_components(self):
        for rain, snow in ((1, 2), (1, None), (None, 2), (None, None), (0, 0)):
            row = source_fixture.municipality_payload()['hourly'][0]
            row.update(precipitation_mm=None, liquid_rain_mm=rain, snow_water_equivalent_mm=snow)
            adapted, _ = _adapt_icon_row(row, source_fixture.NOW)
            self.assertIsNone(adapted['precipitation'])
            self.assertIsNone(adapted['precipitation_probability'])

    def test_real_fontanafredda_row_stays_missing_with_its_resolution_reason(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/icon_fontanafredda_missing_accumulation.json').read_text())
        row = fixture['row']
        at = datetime.fromisoformat(row['valid_at'])
        adapted, issues = _adapt_icon_row(row, at)
        for field in ('precipitation', 'snowfall', 'precipitation_probability', 'weather_code'):
            self.assertIsNone(adapted[field])
        self.assertEqual(adapted['rain'], 0)
        self.assertTrue(any(i['variable'] == 'precipitation_mm' and i['reason'] == 'positive_within_encoding_resolution' for i in issues))
        snap = detector_fixture.build_snapshot(municipality='Fontanafredda', now=at.astimezone(shadow.FVG_ZONE), slot_count=6)
        snap['hourly']['native_weather_code'] = [1] * 6
        snap['hourly_units']['native_weather_code'] = 'wmo code'
        for field, value in adapted.items():
            if field != 'time':
                snap['hourly'][field][0] = value
        # Put this exact observation at the first evaluated hour.
        snap['hourly']['time'] = [(at + timedelta(hours=i)).isoformat() for i in range(6)]
        snap['source_run_id'] = fixture['source_run_id']
        snap['source_quality_issues'] = issues
        result = detector_fixture.evaluate(snap, municipality='Fontanafredda', now=at)
        self.assertEqual(result['status'], 'partial_evaluation')
        self.assertEqual(result['candidates'], [])
        self.assertEqual(result['data_quality']['evaluations_partial'], 1)
        self.assertIn({'at': row['valid_at'], 'variable': 'precipitation_mm', 'reason': 'positive_within_encoding_resolution'}, result['data_quality']['reasons'])

    def test_missing_thermal_row_is_kept_not_skipped(self):
        payload = source_fixture.municipality_payload()
        payload['hourly'][2]['apparent_temperature_c'] = None
        payload['hourly'][2]['quality_flags'] = ['invalid_T_Td_for_RH_no_clipping']
        issues = []
        adapted = IconLocalNoticeSource()._adapt_hourly(payload, fetched_at=source_fixture.NOW, quality_issues=issues)
        self.assertEqual(len(adapted['time']), 8)
        self.assertIsNone(adapted['apparent_temperature'][2])
        self.assertEqual(issues[0]['reason'], 'invalid_T_Td_for_RH_no_clipping')

    def test_national_interval_requires_both_measurements(self):
        self.assertEqual(_national_interval([0, 0], 1), 0)
        self.assertEqual(_national_interval([1, 3], 1), 2)
        for invalid in (None, False, '0', float('nan'), float('inf')):
            self.assertIsNone(_national_interval([invalid, 1], 1))
            self.assertIsNone(_national_interval([0, invalid], 1))

    def test_only_actual_six_hour_window_is_counted(self):
        snap = detector_fixture.build_snapshot(slot_count=8)
        snap['source_run_id'] = '20260814T000000Z'
        snap['hourly']['precipitation'][7] = None
        self.assertEqual(detector_fixture.evaluate(snap)['data_quality']['state'], 'evaluable')
        snap['hourly']['precipitation'][1] = None
        result = detector_fixture.evaluate(snap)
        self.assertEqual(result['status'], 'partial_evaluation')
        self.assertEqual(result['data_quality']['phenomena_not_possible'], 2)
        self.assertEqual(len(result['data_quality']['reasons']), 1)

    def test_dst_repeated_hour_is_distinct_and_notice_lead_uses_elapsed_time(self):
        now = datetime(2026, 10, 24, 23, 15, tzinfo=timezone.utc)
        snap = detector_fixture.build_snapshot(now=now.astimezone(shadow.FVG_ZONE))
        snap['hourly']['time'] = [(datetime(2026, 10, 25, tzinfo=timezone.utc) + timedelta(hours=i)).isoformat() for i in range(6)]
        result = detector_fixture.evaluate(snap, now=now)
        self.assertEqual(result['status'], 'no_candidate')
        self.assertEqual(result['snapshot']['eligible_slots'], 6)
        eligible, deferred = shadow._partition_notice_window([{'kind':'wind', 'event_at':'2026-10-25T02:00:00+01:00'}], now=now)
        self.assertEqual(eligible, [])
        self.assertEqual(deferred[0]['lead_minutes'], 105)

    def test_quality_counter_denominator_reason_and_privacy(self):
        bad = evaluation_quality({'source_run_id':'20260814T000000Z'}, [], [], failure='source_error')
        good = evaluation_quality({'source_run_id':'20260814T000000Z'}, [], [])
        counter = QualityCounter()
        counter.add(('093033', ''), bad)
        counter.add(('093033', ''), bad)
        counter.add(('093033', 'locality'), good)
        run = counter.summary()['by_source_run'][0]
        self.assertEqual((run['evaluations_expected'], run['evaluations_not_possible']), (2, 1))
        self.assertEqual(run['municipalities_expected'], 1)
        self.assertEqual(run['causes'], [{'variable':'source', 'reason':'source_error', 'evaluations':1}])
        bad['token'] = 'secret'
        bad['reasons'].append({'variable': [], 'reason': {}, 'at':'secret'})
        self.assertNotIn('secret', json.dumps(sanitize_quality(bad)))
        bad['reasons'] = 7
        self.assertEqual(sanitize_quality(bad)['reasons'], [])

    def test_missing_hour_cannot_produce_morning_or_evening_reassurance(self):
        municipality = LocationCatalog().match_istat('093033')
        for native in ('precipitation', 'rain', 'weather_code'):
            snap = morning.snapshot()
            snap['hourly'][native][6] = None
            self.assertEqual(build_morning_forecast_body(snap, municipality, now=morning.NOW), '')
            snap = evening.snapshot()
            snap['hourly'][native][evening.tomorrow_index(snap, 12)] = None
            self.assertEqual(build_evening_forecast_contents(snap, municipality, now=evening.NOW), {})
        snap = evening.snapshot()
        snap['hourly']['precipitation'][0] = None  # Today, outside tomorrow's scope.
        self.assertTrue(build_evening_forecast_contents(snap, municipality, now=evening.NOW))

    def test_two_devices_partial_once_wind_is_retained_and_audit_keeps_quality(self):
        devices = [delivery.device(device_id=letter*64, token=letter, enrollment_generation=delivery.PLAY_BETA_GENERATION,
                    app_check_app_id=delivery.PLAY_BETA_APP_ID) for letter in ('b', 'c')]
        snap = delivery.snapshot(wind_gust=70)
        snap['source_run_id'] = '20260814T000000Z'
        snap['hourly']['precipitation'][0] = None
        audit, sender = delivery.FakeAuditRepository(), delivery.FakeSender()
        service = delivery.LocalNoticeDeliveryServiceTests.make_service(self, devices=devices,
            source=delivery.FakeSource(snap), audit=audit, sender=sender, service_config=delivery.play_beta_config())
        result = service.run()
        self.assertEqual(result.data_quality['evaluations_expected'], 1)
        self.assertEqual(result.data_quality['evaluations_not_possible'], 0)
        self.assertEqual(result.data_quality['evaluations_partial'], 1)
        self.assertEqual(result.status, 'data_degraded')
        self.assertEqual(result.selected_kind, 'wind')
        self.assertEqual(result.attempted, 2)
        self.assertEqual(result.source_failed, 0)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.data_degraded_groups, 1)
        self.assertEqual(sender.payloads, [])
        self.assertEqual(result.summary()['data_quality'], result.data_quality)
        exit_code, logged, _ = job_fixture.SendLocalWeatherNoticesJobTests.run_job(self, value=result)
        self.assertEqual(exit_code, 1)  # Existing rejected/partial exit behavior is unchanged.
        self.assertEqual(logged['data_quality'], result.data_quality)
        evaluation = shadow.evaluate_local_notice_shadow('093033', snap, now=delivery.NOW,
            locality=delivery.FvgGeographyCatalog().match_locality_id(devices[0]['locality']['id']))
        clean = build_sanitized_shadow_record(evaluation=evaluation, municipality=LocationCatalog().match_istat('093033'), now=delivery.NOW, retention_days=14)
        self.assertEqual(clean['data_quality']['evaluations_partial'], 1)
        self.assertEqual(clean['snapshot']['source_run_id'], snap['source_run_id'])
        self.assertNotIn('token', json.dumps(clean, default=str))

    def test_invalid_numeric_values_block_dependent_detectors(self):
        for value in (False, '0', float('nan'), float('inf'), -1):
            snap = detector_fixture.build_snapshot()
            snap['hourly']['precipitation'][0] = value
            result = detector_fixture.evaluate(snap)
            self.assertEqual(result['status'], 'partial_evaluation')
            self.assertEqual(result['data_quality']['evaluations_partial'], 1)
