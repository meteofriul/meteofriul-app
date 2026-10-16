"""Compact, bounded annual TurismoFVG control for the shared pilot catalog."""
import base64
import binascii
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
