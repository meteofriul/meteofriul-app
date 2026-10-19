"""Independent, fail-closed reader of evidence bound to public ICON v1 bytes."""
import copy
import hashlib
import json

from app.weather.local_notice_tolerance import read_quality

MAX_BYTES = 512 * 1024


def attach_evidence(payload, body, descriptor, sidecar):
    if (not isinstance(body, bytes) or not isinstance(descriptor, dict)
            or descriptor.get('sha256') != hashlib.sha256(body).hexdigest()
            or type(descriptor.get('json_bytes')) is not int
            or descriptor['json_bytes'] != len(body) or json.loads(body) != payload):
        raise ValueError('weather descriptor mismatch')
    if (not isinstance(sidecar, dict)
            or set(sidecar) != {'schema_version', 'source_run_id', 'istat_code', 'weather_sha256', 'hourly'}
            or sidecar['schema_version'] != 'icon-accumulation-sidecar.v1'
            or sidecar['source_run_id'] != payload['source_run_id']
            or sidecar['istat_code'] != payload['municipality']['istat_code']
            or sidecar['weather_sha256'] != descriptor['sha256']
            or not isinstance(sidecar['hourly'], list)
            or len(sidecar['hourly']) != len(payload['hourly'])):
        raise ValueError('sidecar identity mismatch')
    result = copy.deepcopy(payload)
    present = False
    for row, item in zip(result['hourly'], sidecar['hourly']):
        if (not isinstance(row, dict) or 'accumulation_quality' in row
                or not isinstance(item, dict) or set(item) != {'valid_at', 'accumulation_quality'}
                or item['valid_at'] != row['valid_at']):
            raise ValueError('sidecar hourly mismatch')
        quality = item['accumulation_quality']
        if quality is not None:
            if read_quality(quality, row) is None:
                raise ValueError('sidecar proof invalid')
            row['accumulation_quality'] = quality
            present = True
    if not present:
        raise ValueError('sidecar has no evidence')
    return result
