"""Extra evidence for notice jobs, bound to an unchanged public v1 document.

The checkpoint retains the enriched input. Publication projects only the extra
hourly key out of the public body; measurements, flags and two-hour rows survive.
The immutable sidecar is visible only while its public run is authorized.
"""
import hashlib
import json
import re

from .accumulation_tolerance import validate_accumulation_quality
from .contract_v1 import ContractError, canonical_json_bytes

SCHEMA = "icon-accumulation-sidecar.v1"
MAX_BYTES = 512 * 1024
KEY_PATTERN = re.compile(r"weather/v1/icon2i/runs/(?P<run>\d{8}T\d{6}Z)/accumulation-quality/(?P<istat>\d{6})\.json\Z")


def split_document(body):
    value = json.loads(body)
    evidence = []
    present = False
    for row in value['hourly']:
        quality = row.pop('accumulation_quality', None)
        if quality is not None:
            validate_accumulation_quality(quality, row)
            present = True
        evidence.append(dict(valid_at=row['valid_at'], accumulation_quality=quality))
    if not present:
        return body, None
    public = canonical_json_bytes(value)
    sidecar = dict(schema_version=SCHEMA, source_run_id=value['source_run_id'],
                   istat_code=value['municipality']['istat_code'],
                   weather_sha256=hashlib.sha256(public).hexdigest(), hourly=evidence)
    encoded = canonical_json_bytes(sidecar)
    validate_sidecar(encoded, public)
    return public, encoded


def validate_sidecar(body, weather_body):
    if not isinstance(body, bytes) or not 1 <= len(body) <= MAX_BYTES:
        raise ContractError('ICON accumulation sidecar size invalid')
    try:
        value, weather = json.loads(body), json.loads(weather_body)
        if (not isinstance(value, dict)
                or set(value) != {'schema_version', 'source_run_id', 'istat_code', 'weather_sha256', 'hourly'}
                or value['schema_version'] != SCHEMA
                or canonical_json_bytes(value) != body
                or value['source_run_id'] != weather['source_run_id']
                or value['istat_code'] != weather['municipality']['istat_code']
                or value['weather_sha256'] != hashlib.sha256(weather_body).hexdigest()
                or not isinstance(value['hourly'], list)
                or len(value['hourly']) != len(weather['hourly'])):
            raise ValueError('identity or hash mismatch')
        present = False
        for item, row in zip(value['hourly'], weather['hourly']):
            if (not isinstance(item, dict) or set(item) != {'valid_at', 'accumulation_quality'}
                    or item['valid_at'] != row['valid_at'] or 'accumulation_quality' in row):
                raise ValueError('hourly alignment mismatch')
            if item['accumulation_quality'] is not None:
                validate_accumulation_quality(item['accumulation_quality'], row)
                present = True
        if not present:
            raise ValueError('empty evidence')
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        raise ContractError('invalid ICON accumulation sidecar') from error
    return value
