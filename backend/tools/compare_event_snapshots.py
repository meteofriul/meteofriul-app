"""Read two explicitly scoped snapshots; emit JSON to stdout, never publish."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.events.pilot_comparison import compare


def read_snapshot(path):
    payload = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(payload, dict) or not isinstance(payload.get('events'), list):
        raise ValueError('snapshot must contain events array')
    scope = payload.get('scope')
    required = {'as_of', 'date_from', 'date_to', 'lat', 'lon', 'radius_km'}
    if not isinstance(scope, dict) or not required <= scope.keys():
        raise ValueError('snapshot missing explicit acquisition scope')
    if not all(isinstance(event, dict) for event in payload['events']):
        raise ValueError('invalid event record')
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('legacy')
    parser.add_argument('pilot')
    args = parser.parse_args()
    a, b = read_snapshot(args.legacy), read_snapshot(args.pilot)
    if a['scope'] != b['scope']:
        parser.error('different acquisition scopes: comparison refused')
    report = compare(a['events'], b['events'])
    report['scope'] = a['scope']
    report['coverage'] = {'legacy': a.get('coverage', 'unknown'), 'pilot': b.get('coverage', 'unknown')}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
