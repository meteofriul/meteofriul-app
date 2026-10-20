"""Offline diagnosis of the frozen deployed ICON producer; no network or GRIB download."""
import copy
import hashlib
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(r'F:\proggetto Meteo Friul App\meteo FRIUL')
OUT = ROOT / '.tmp/icon-tolerance-phase3-20261019'
SOURCE = OUT / 'context/experiments/weather_autonomy'
sys.path.insert(0, str(SOURCE))
sys.dont_write_bytecode = True

def deny_network(*args, **kwargs):
    raise AssertionError('Network access forbidden during offline diagnosis')

with patch.object(socket.socket, 'connect', deny_network), patch.object(socket, 'create_connection', deny_network):
    import run_pilot as pilot
    import test_run_pilot as fixtures
    fixture = fixtures.snapshot_fixture()
    points = fixture['points']
    field_cases = []
    for field in pilot.CONTRACTS:
        data = copy.deepcopy(fixture['raw'][field])
        url = data['url']
        def record(current_data):
            return pilot._with_checkpoint_integrity({
                'schema_version': pilot.CHECKPOINT_SCHEMA_VERSION,
                'kind': 'icon_extracted_field_checkpoint',
                'intent_sha256': 'd'*64, 'run': fixtures.RUN,
                'field': field, 'url': url,
                'grid_hash': fixture['grid_hash'], 'grid_points': fixture['grid_points'],
                'data': current_data,
            })
        kwargs = dict(intent_sha='d'*64, field=field, run=fixtures.RUN, url=url, points=points)
        pilot._validate_field_checkpoint(record(data), **kwargs)
        for packing_error in (None, 0.0005):
            enriched = copy.deepcopy(data)
            for meta in enriched['metadata']:
                meta['packingError'] = packing_error
            try:
                pilot._validate_field_checkpoint(record(enriched), **kwargs)
            except ValueError as error:
                assert str(error) == 'Checkpoint metadata is invalid', str(error)
                field_cases.append({'field': field, 'packingError': packing_error, 'old_metadata_accepted': True,
                                    'new_metadata_accepted': False, 'error': str(error)})
            else:
                raise AssertionError('Expected the deployed validator to reject its own new metadata')

    class FakeEcCodes:
        """Only the external GRIB interface is synthetic; Decoder.decode is unmodified."""
        def __init__(self, mode):
            self.mode = mode
        def codes_new_from_message(self, data):
            return int(data.decode('ascii'))
        def codes_set(self, handle, key, value):
            assert (key, value) == ('stepUnits', 1)
        def codes_get(self, handle, key):
            if key == 'packingError':
                if self.mode == 'absent':
                    raise KeyError(key)
                return 0.0005
            if key == 'missingValue':
                return 9999.0
            return fixtures.metadata('T_2M', handle)[key]
        def codes_grib_find_nearest_multiple(self, handle, lsm, lats, lons):
            return [dict(p, value=293.15) for p in fixture['grid_points']]
        def codes_get_elements(self, handle, key, indexes):
            return [293.15] * len(indexes)
        def codes_release(self, handle):
            pass

    decoder_cases = []
    for mode in ('available', 'absent'):
        decoder = pilot.Decoder.__new__(pilot.Decoder)
        decoder.ec = FakeEcCodes(mode)
        decoder.points = points
        decoder.grid_points = decoder.grid_hash = decoder.indexes = None
        decoder.seen = set()
        decoder.seconds = decoder.mapping_seconds = 0.0
        decoder.mapping_builds = 0
        rows = [decoder.decode(str(step).encode('ascii'), 'T_2M', fixtures.RUN, step) for step in range(73)]
        data = copy.deepcopy(fixture['raw']['T_2M'])
        data['values'] = [row[0] for row in rows]
        data['metadata'] = [row[1] for row in rows]
        assert all('packingError' in meta for meta in data['metadata'])
        with patch.object(pilot, '_commit_new_bytes') as commit:
            try:
                pilot._save_field_checkpoint(Path('unused-no-disk-write'), intent_sha='d'*64,
                    field='T_2M', run=fixtures.RUN, url=data['url'], points=points,
                    decoder=decoder, data=data)
            except ValueError as error:
                assert str(error) == 'Checkpoint metadata is invalid'
                decoder_cases.append({'packingError_provider_mode': mode, 'real_decoder_used': True,
                    'decoded_messages': len(rows), 'points_per_message': len(points),
                    'checkpoint_error': str(error), 'checkpoint_write_attempted': commit.called})
            else:
                raise AssertionError('Unexpected checkpoint acceptance')
            commit.assert_not_called()

result = {
    'kind': 'offline_diagnosis_not_live_replay',
    'deployed_source_sha256': hashlib.sha256((SOURCE/'run_pilot.py').read_bytes()).hexdigest(),
    'network_access': False, 'new_source_acquisition': False,
    'production_source_modified': False,
    'field_cases': field_cases, 'decoder_to_checkpoint_cases': decoder_cases,
    'conclusion': 'Decoder always adds packingError but checkpoint validator forbids it; first complete field cannot be saved.',
    'cloud_evidence_limit': 'Cloud logs suppress the inner exception; exact historical innermost failure cannot be read back. The deployed defect is deterministic and matches early acquisition failure before the first field-completed log.'
}
(OUT/'packing-error-diagnosis-20261020.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'old_metadata_accepted_fields':len(pilot.CONTRACTS),'new_metadata_rejections':len(field_cases),
                  'real_decoder_cases':decoder_cases,'network_access':False,'evidence':str(OUT/'packing-error-diagnosis-20261020.json')},ensure_ascii=False,indent=2))
