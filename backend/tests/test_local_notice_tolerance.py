"""Producer -> public JSON -> real adapter/evaluator/job, with network forbidden."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest

EXPERIMENT = Path(__file__).resolve().parents[2] / 'experiments/weather_autonomy'
sys.path.insert(0, str(EXPERIMENT))
from local_pipeline.accumulation_tolerance import build_accumulation_quality
from pilot_policy import rain_interval
from run_pilot import accumulation_quantum, accumulation_reference_mm
from app.weather.local_notice_source import _adapt_icon_row
from app.weather.local_notice_quality import QualityCounter, sanitize_quality
from app.weather.local_notice_tolerance import read_quality
import test_local_notice_shadow as detector
import test_local_notice_source as source
import test_local_notice_delivery_service as delivery


def known(value=0): return dict(value_mm=value, status='valid', uncertainty_mm=0)
def tiny(budget=0.001): return dict(value_mm=None, status='positive_within_encoding_resolution', uncertainty_mm=budget)


def public_row(*, rain=0, snow=0, total=0, unresolved=None, packing=True, native=2):
    row = source.municipality_payload()['hourly'][0]
    data = dict(RAIN_CON=known(rain), RAIN_GSP=known(), SNOW_CON=known(snow), SNOW_GSP=known(), TOT_PREC=known(total))
    data.update(unresolved or {})
    row.update(liquid_rain_mm=None if any(data[f]['value_mm'] is None for f in ('RAIN_CON','RAIN_GSP')) else rain,
               snow_water_equivalent_mm=None if any(data[f]['value_mm'] is None for f in ('SNOW_CON','SNOW_GSP')) else snow,
               precipitation_mm=data['TOT_PREC']['value_mm'], condition={'native_code':native, 'native_status':'valid'})
    row['accumulation_quality'] = build_accumulation_quality(data, {f:[0.0005,0.0005] for f in data} if packing else {})
    return row


def snapshot(rows, *, now=detector.NOW):
    now = now.astimezone(detector.ROME)
    snap = detector.build_snapshot(now=now, slot_count=len(rows))
    snap['hourly_units']['native_weather_code'] = 'wmo code'
    converted = []
    issues = []
    for i, row in enumerate(rows):
        at = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=i+1)
        row = copy.deepcopy(row); row['valid_at'] = at.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
        item, problems = _adapt_icon_row(json.loads(json.dumps(row)), at)
        converted.append(item); issues.extend(problems)
    snap['hourly'] = {f:[r.get(f) for r in converted] for f in converted[0]}
    snap['source_run_id'] = '20261019T000000Z'; snap['source_quality_issues'] = issues
    return snap


class NoticeToleranceTests(unittest.TestCase):
    def test_true_null_unknown_metadata_and_over_budget_block_only_dependencies(self):
        for row in (public_row(unresolved={'SNOW_GSP':tiny()},packing=False),
                    public_row(unresolved={'SNOW_GSP':tiny(0.021)}),
                    public_row(unresolved={'SNOW_GSP':dict(value_mm=None,status='invalid')})):
            result = detector.evaluate(snapshot([row]*6))
            self.assertEqual(result['data_quality']['phenomena']['snow']['state'],'not_evaluable')
            self.assertEqual(result['data_quality']['phenomena']['wind']['state'],'evaluated_no_candidate')

    def test_preserved_known_snow_component_produces_candidate_without_filling_public_null(self):
        row = public_row(snow=1.2,total=1.3,unresolved={'SNOW_GSP':tiny()})
        snap = snapshot([row]*6); before=copy.deepcopy(snap)
        result = detector.evaluate(snap)
        self.assertIsNotNone(detector.candidate_for(result,'snow'))
        self.assertTrue(result['data_quality']['phenomena']['snow']['uses_operational_tolerance'])
        self.assertEqual(snap,before)
        self.assertIsNone(snap['hourly']['snowfall'][0])
        self.assertEqual(result['data_quality']['phenomena']['snow']['state'],'evaluated_with_candidate')

    def test_rain_requires_known_peak_indicator_but_tolerates_other_hour(self):
        rows = [public_row(rain=8,total=8), public_row(rain=7,total=7),
                public_row(unresolved={'RAIN_GSP':tiny(), 'TOT_PREC':tiny()})] + [public_row()]*3
        snap=snapshot(rows); result=detector.evaluate(snap)
        self.assertIsNotNone(detector.candidate_for(result,'rain'))
        self.assertIsNone(snap['hourly']['precipitation_probability'][2])
        rows[0]=public_row(rain=8,unresolved={'TOT_PREC':tiny()})
        rows[1]=public_row(rain=7,unresolved={'TOT_PREC':tiny()})
        result=detector.evaluate(snapshot(rows))
        self.assertEqual(result['data_quality']['phenomena']['rain']['state'],'not_evaluable')

    def test_known_zero_and_generic_missing_are_not_tolerated(self):
        snap=snapshot([public_row()]*6)
        self.assertEqual(detector.evaluate(snap)['status'],'no_candidate')
        self.assertEqual(detector.evaluate(snap)['data_quality']['evaluations_with_tolerance'],0)
        snap['hourly']['precipitation_probability'][0]=None
        self.assertEqual(detector.evaluate(snap)['data_quality']['phenomena']['snow']['state'],'not_evaluable')

    def test_snow_threshold_uses_known_components_without_tolerance_as_extra_snow(self):
        for last, expected in ((0.599, False), (0.6, True), (0.601, True)):
            rows = [public_row(snow=amount,total=1,unresolved={'SNOW_GSP':tiny()})
                    for amount in (0.7, 0.7, last)] + [public_row()]*3
            result=detector.evaluate(snapshot(rows))
            self.assertEqual(detector.candidate_for(result,'snow') is not None, expected)
            self.assertTrue(result['data_quality']['phenomena']['snow']['uses_operational_tolerance'])

    def test_rain_threshold_is_unchanged_and_tolerance_is_never_added(self):
        for last, expected in ((6.999, False), (7, True), (7.001, True)):
            rows=[public_row(rain=8,total=8), public_row(rain=last,total=last),
                  public_row(unresolved={'RAIN_GSP':tiny(), 'TOT_PREC':tiny()})] + [public_row()]*3
            result=detector.evaluate(snapshot(rows))
            self.assertEqual(detector.candidate_for(result,'rain') is not None, expected)

    def test_candidate_keeps_partial_state_when_another_phenomenon_is_unavailable(self):
        snap=snapshot([public_row(snow=1.2,total=1.3,unresolved={'SNOW_GSP':tiny()})]*6)
        snap['hourly']['apparent_temperature'][0]=None
        result=detector.evaluate(snap)
        self.assertIsNotNone(detector.candidate_for(result,'snow'))
        self.assertEqual(result['data_quality']['state'],'partial')
        self.assertEqual(result['data_quality']['phenomena']['heat']['state'],'not_evaluable')

    def test_verified_tolerance_does_not_fill_morning_or_evening_summaries(self):
        from app.services.location import LocationCatalog
        from app.services.morning_forecast_delivery import build_morning_forecast_body
        from app.services.evening_forecast_delivery import build_evening_forecast_contents
        import test_morning_forecast_delivery as morning
        import test_evening_forecast_delivery as evening
        municipality=LocationCatalog().match_istat('093033')
        proof=public_row(unresolved={'TOT_PREC':tiny()})['accumulation_quality']
        snap=morning.snapshot(); snap['hourly']['precipitation'][6]=None
        snap['hourly']['accumulation_quality']=[proof]*len(snap['hourly']['time'])
        self.assertEqual(build_morning_forecast_body(snap,municipality,now=morning.NOW),'')
        snap=evening.snapshot(); snap['hourly']['precipitation'][evening.tomorrow_index(snap,12)]=None
        snap['hourly']['accumulation_quality']=[proof]*len(snap['hourly']['time'])
        self.assertEqual(build_evening_forecast_contents(snap,municipality,now=evening.NOW),{})

    def test_real_ciampac_increments_through_producer_contract_adapter_and_detector(self):
        frozen=json.loads((EXPERIMENT/'fixtures/ciampac-snow-tolerance-20261019.json').read_text(encoding='utf-8'))
        raw={f:{s['lead']:s for s in samples} for f,samples in frozen['fields'].items()}
        rows=[]
        for lead in (1,2,3):
            data={f:known() for f in ('RAIN_CON','RAIN_GSP')}; errors={}
            for field in ('TOT_PREC','SNOW_CON','SNOW_GSP'):
                p,c=raw[field][lead-1],raw[field][lead]
                data[field]=rain_interval(p['point']['value'],c['point']['value'],accumulation_quantum(p['metadata']),accumulation_quantum(c['metadata']),
                    previous_reference_mm=accumulation_reference_mm(p['metadata']),current_reference_mm=accumulation_reference_mm(c['metadata']))
                errors[field]=[p['metadata']['packingError'],c['metadata']['packingError']]
            row=public_row(unresolved={f:v for f,v in data.items() if v['value_mm'] is None}, native=int(raw['WW'][lead]['point']['value']))
            row['accumulation_quality']=build_accumulation_quality(data,errors)
            row['precipitation_mm']=data['TOT_PREC']['value_mm']
            rows.append(row)
        # Only the actual four fields are real; non-snow inputs/geography use explicit test fixtures.
        snap=snapshot(rows); result=detector.evaluate(snap)
        self.assertEqual(result['data_quality']['phenomena']['snow']['state'],'evaluated_no_candidate')
        self.assertTrue(result['data_quality']['phenomena']['snow']['uses_operational_tolerance'])
        for r in rows: r.pop('accumulation_quality')
        self.assertEqual(detector.evaluate(snapshot(rows))['data_quality']['phenomena']['snow']['state'],'not_evaluable')

    def test_tampered_units_schema_budget_and_component_sum_fail_closed(self):
        row=public_row(unresolved={'SNOW_GSP':tiny()})
        for key,value in [('unit','cm'),('tolerance_mm',2),('unquantified_components',True),('known_component_sum_mm',False),('resolution_budget_mm',1),('state',{})]:
            altered=copy.deepcopy(row); altered['accumulation_quality']['fields']['snow_water_equivalent_mm'][key]=value
            self.assertIsNone(read_quality(altered['accumulation_quality'],altered))
            self.assertEqual(detector.evaluate(snapshot([altered]*6))['data_quality']['phenomena']['snow']['state'],'not_evaluable')

    def test_invalid_or_absent_raw_value_cannot_be_laundered_into_verified_null(self):
        for invalid in (False, '0', -1, float('nan'), float('inf'), 'absent'):
            row=public_row(unresolved={'SNOW_GSP':tiny()})
            if invalid == 'absent':
                row.pop('snow_water_equivalent_mm')
            else:
                row['snow_water_equivalent_mm']=invalid
            result=detector.evaluate(snapshot([row]*6))
            outcome=result['data_quality']['phenomena']['snow']
            self.assertEqual(outcome['state'],'not_evaluable')
            self.assertFalse(outcome['uses_operational_tolerance'])
            self.assertIn('invalid_tolerance_contract', {r['reason'] for r in outcome['reasons']})

    def test_invalid_native_code_does_not_crash_tolerance_projection(self):
        for value in ([], {}, False, '73'):
            snap=snapshot([public_row(unresolved={'SNOW_GSP':tiny(), 'TOT_PREC':tiny()})]*6)
            snap['hourly']['native_weather_code'][0]=value
            result=detector.evaluate(snap)
            self.assertEqual(result['data_quality']['phenomena']['storm']['state'],'not_evaluable')
            self.assertEqual(result['data_quality']['phenomena']['ice']['state'],'not_evaluable')

    def test_audit_denominator_counts_tolerance_once_per_point(self):
        result=detector.evaluate(snapshot([public_row(unresolved={'SNOW_GSP':tiny()})]*6))
        clean=sanitize_quality(result['data_quality'])
        counter=QualityCounter();counter.add(('093033',''),clean);counter.add(('093033',''),clean)
        summary=counter.summary()
        self.assertEqual(summary['evaluations_expected'],1)
        self.assertEqual(summary['evaluations_with_tolerance'],1)
        self.assertEqual(summary['by_source_run'][0]['phenomena']['snow']['with_operational_tolerance'],1)

    def test_job_dry_run_never_sends_and_existing_deduplication_key_is_stable(self):
        rows=[public_row(snow=1.2,total=1.3,unresolved={'SNOW_GSP':tiny()})]*6
        snap=snapshot(rows,now=delivery.NOW)
        job_snapshot=copy.deepcopy(snap)
        job_snapshot['requested_location']=delivery.snapshot()['requested_location']
        sender=delivery.FakeSender(); audit=delivery.FakeAuditRepository()
        service=delivery.LocalNoticeDeliveryServiceTests().make_service(source=delivery.FakeSource(job_snapshot),sender=sender,audit=audit)
        result=service.run()
        self.assertEqual(sender.payloads,[])
        self.assertEqual(result.data_quality['evaluations_with_tolerance'],1)
        self.assertEqual(result.candidates,1)
        complete=snapshot([public_row(snow=1.2,total=1.3)]*6,now=delivery.NOW)
        a=detector.candidate_for(detector.evaluate(snap,now=delivery.NOW),'snow')
        b=detector.candidate_for(detector.evaluate(complete,now=delivery.NOW),'snow')
        self.assertEqual(a['dedupe'],b['dedupe'])


if __name__ == '__main__': unittest.main()
