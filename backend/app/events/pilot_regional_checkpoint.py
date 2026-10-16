"""Compact, bounded annual TurismoFVG control for the shared pilot catalog."""
import base64
import binascii
from datetime import date, datetime, timedelta, timezone
import json
import zlib


SCHEMA = 'turismofvg-year-control-checkpoint-v1'
MAX_RAW_BYTES = 6 * 1024 * 1024
MAX_ENCODED_BYTES = 2 * 1024 * 1024


def encode_control(control):
    if not isinstance(control, dict) or control.get('schema') != 'turismofvg-current-year-control-v1':
        raise ValueError('invalid TurismoFVG control')
    raw = json.dumps(control, ensure_ascii=False, separators=(',', ':'),
                     allow_nan=False).encode('utf-8')
    if len(raw) > MAX_RAW_BYTES:
        raise ValueError('TurismoFVG control too large')
    value = base64.b64encode(zlib.compress(raw, level=6)).decode('ascii')
    if len(value) > MAX_ENCODED_BYTES:
        raise ValueError('TurismoFVG checkpoint too large')
    return {'schema': SCHEMA, 'encoding': 'zlib+base64', 'value': value}


def decode_control(checkpoint):
    if (not isinstance(checkpoint, dict) or checkpoint.get('schema') != SCHEMA
            or checkpoint.get('encoding') != 'zlib+base64'
            or not isinstance(checkpoint.get('value'), str)
            or len(checkpoint['value']) > MAX_ENCODED_BYTES):
        raise ValueError('invalid TurismoFVG checkpoint')
    try:
        packed = base64.b64decode(checkpoint['value'], validate=True)
        decoder = zlib.decompressobj()
        raw = decoder.decompress(packed, MAX_RAW_BYTES + 1)
        if (len(raw) > MAX_RAW_BYTES or decoder.unconsumed_tail
                or decoder.unused_data or not decoder.eof):
            raise ValueError('oversized or truncated TurismoFVG checkpoint')
        raw += decoder.flush()
        if len(raw) > MAX_RAW_BYTES:
            raise ValueError('oversized TurismoFVG checkpoint')
        control = json.loads(raw)
    except (binascii.Error, zlib.error, UnicodeDecodeError,
            json.JSONDecodeError) as exc:
        raise ValueError('corrupt TurismoFVG checkpoint') from exc
    if (not isinstance(control, dict)
            or control.get('schema') != 'turismofvg-current-year-control-v1'):
        raise ValueError('unexpected TurismoFVG control schema')
    return control


def resumable_details(control, previous_batch, *, today, now=None):
    """Reuse detail proof only; failed inventories never replace verified ones."""
    from .pilot_regional_verified import _result_within_age
    from .pilot_regional_year_control import INSPECTION_VERSION
    checkpoint = (previous_batch or {}).get('last_attempt_control_checkpoint')
    if not checkpoint:
        return {}
    now = now or datetime.now(timezone.utc)
    try:
        attempt = decode_control(checkpoint)
        checked_day = date.fromisoformat(attempt['as_of_date'])
        if (attempt.get('inspection_version') != INSPECTION_VERSION
                or not today - timedelta(days=30) <= checked_day <= today
                or not isinstance(attempt.get('entries'), dict)
                or not isinstance(attempt.get('results'), dict)):
            return {}
    except (KeyError, TypeError, ValueError):
        return {}
    reusable = {}
    for url, entry in control['entries'].items():
        old_entry = attempt['entries'].get(url)
        result = attempt['results'].get(url)
        if (not isinstance(old_entry, dict) or not isinstance(result, dict)
                or not entry.get('signature')
                or old_entry.get('signature') != entry['signature']
                or result.get('status') not in {'detail_aligned', 'past_event',
                    'non_event', 'non_event_experience', 'excluded_current_year'}
                or not _result_within_age(result, today=today, now=now)):
            continue
        reusable[url] = result
    return reusable
