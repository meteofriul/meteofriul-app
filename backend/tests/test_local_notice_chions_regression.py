"""Real Chions regression: an unavailable perceived temperature must not erase an hour."""
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import unittest

from app.services.location import LocationCatalog
from app.weather.local_notice_source import IconLocalNoticeSource
from app.weather.local_notice_shadow import evaluate_local_notice_shadow
import test_local_notice_source as source

FIXTURE = Path(__file__).with_name('fixtures') / 'icon_chions_20261021.json'


class ChionsPublishedRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def fetch(self, stamp, *, sidecar=True, tamper=False):
        data = self.data
        run = data['source_run_id']
        latest = {'provider': 'icon2i', 'latest': {
            'source_run_id': run, 'manifest_path': f'runs/{run}/manifest.json'}}
        manifest = {'provider': 'icon2i', 'source_run_id': run,
                    'objects': {data['istat']: data['descriptor']}}
        evidence = data['sidecar_body']
        if tamper:
            altered = json.loads(evidence)
            altered['weather_sha256'] = '0' * 64
            evidence = json.dumps(altered)
        bodies = [json.dumps(latest), json.dumps(manifest), data['weather_body']]
        if sidecar:
            bodies.append(evidence)
        session = source.FakeSession([
            source.FakeResponse(json.loads(body), raw=body.encode('utf-8')) for body in bodies])
        now = datetime.fromisoformat(stamp)
        snapshot = IconLocalNoticeSource(session=session, now=lambda: now,
                                        accumulation_sidecar=sidecar).fetch(
            LocationCatalog().match_istat(data['istat']))
        return snapshot, evaluate_local_notice_shadow(data['istat'], snapshot, now=now)

    def test_real_run_keeps_hour_and_only_heat_unavailable(self):
        self.assertEqual(hashlib.sha256(self.data['weather_body'].encode()).hexdigest(),
                         self.data['descriptor']['sha256'])
        for stamp in self.data['evaluated_at']:
            with self.subTest(at=stamp):
                snapshot, result = self.fetch(stamp)
                self.assertEqual(snapshot['accumulation_evidence_status'], 'verified')
                times = [datetime.fromisoformat(t) for t in snapshot['hourly']['time']]
                self.assertTrue(all((b-a).total_seconds() == 3600 for a,b in zip(times,times[1:])))
                index = next(i for i,t in enumerate(times) if t.hour == 22)
                self.assertIsNone(snapshot['hourly']['apparent_temperature'][index])
                self.assertEqual(result['validation_errors'], [])
                self.assertEqual(result['status'], 'partial_evaluation')
                self.assertEqual(result['candidates'], [])
                quality = result['data_quality']
                self.assertEqual(quality['phenomena_expected'], 6)
                self.assertEqual(quality['phenomena_not_possible'], 1)
                self.assertEqual({k for k,v in quality['phenomena'].items()
                                  if v['state'] == 'not_evaluable'}, {'heat'})
                self.assertEqual(quality['reasons'][0]['reason'], 'invalid_T_Td_for_RH_no_clipping')
        # Tolerance is required at 17:00, while 18:00 has no accumulation gap in its window.
        self.assertEqual(self.fetch(self.data['evaluated_at'][0])[1]['data_quality']['evaluations_with_tolerance'], 1)
        self.assertEqual(self.fetch(self.data['evaluated_at'][1])[1]['data_quality']['evaluations_with_tolerance'], 0)

    def test_no_or_invalid_sidecar_never_authorizes_a_tolerance(self):
        for options in ({'sidecar': False}, {'tamper': True}):
            with self.subTest(options=options):
                snapshot, result = self.fetch(self.data['evaluated_at'][0], **options)
                self.assertIn(snapshot['accumulation_evidence_status'], {'disabled', 'invalid'})
                states = result['data_quality']['phenomena']
                self.assertEqual({k for k,v in states.items() if v['state'] == 'not_evaluable'},
                                 {'heat', 'rain', 'snow'})
                self.assertEqual(result['data_quality']['evaluations_with_tolerance'], 0)
                self.assertEqual(result['validation_errors'], [])

    def test_a_real_missing_hour_is_still_rejected(self):
        snapshot, _ = self.fetch(self.data['evaluated_at'][0])
        broken = copy.deepcopy(snapshot)
        for values in broken['hourly'].values():
            del values[2]
        result = evaluate_local_notice_shadow(self.data['istat'], broken,
                                             now=datetime.fromisoformat(self.data['evaluated_at'][0]))
        self.assertEqual(result['status'], 'rejected')
        self.assertIn('future_slots_not_hourly', result['validation_errors'])


if __name__ == '__main__':
    unittest.main()
