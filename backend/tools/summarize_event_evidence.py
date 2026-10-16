"""Compare local evidence within one explicit space/time window; no network."""
import argparse
from collections import Counter
from datetime import date, timedelta
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.events.pilot_comparison import compare, normalized
from app.events import engine
from app.events.pilot_catalog import coordinate


def scoped(events, today, until):
    accepted, excluded = [], Counter()
    for event in events:
        item = normalized(event)
        try:
            start, end = date.fromisoformat(item['start']), date.fromisoformat(item['end'])
        except (ValueError, TypeError):
            excluded['invalid_date'] += 1
            continue
        if end < today or start > until:
            excluded['outside_date_window'] += 1
            continue
        lat, lon = coordinate(event.get('lat'), 90), coordinate(event.get('lon'), 180)
        # Do not perform remote geocoding or use the query town as a fallback.
        if lat is None or lon is None:
            excluded['unknown_coordinates'] += 1
            continue
        if engine.haversine_km(45.9569, 12.6605, lat, lon) > 20:
            excluded['outside_radius'] += 1
            continue
        accepted.append(event)
    return accepted, dict(excluded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folders', nargs='+', type=Path)
    parser.add_argument('--as-of', required=True, type=date.fromisoformat)
    args = parser.parse_args()
    batches = {}
    for folder in args.folders:
        for path in folder.glob('*.json'):
            if path.name in {'summary.json', 'comparison.json'}:
                continue
            batch = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(batch, dict) and isinstance(batch.get('events'), list):
                batches[path.stem] = batch
    legacy, pilot, exclusions = [], [], {}
    for name, batch in batches.items():
        events, excluded = scoped(batch['events'], args.as_of, args.as_of + timedelta(days=90))
        exclusions[name] = {'kept': len(events), 'excluded': excluded, 'status': batch.get('status')}
        if name.startswith('legacy-'):
            legacy.extend(events)
        elif name.startswith('pilot-'):
            pilot.extend(events)
    report = compare(legacy, pilot)
    report['scope'] = {'as_of': args.as_of.isoformat(), 'date_to': (args.as_of + timedelta(days=90)).isoformat(),
                       'lat': 45.9569, 'lon': 12.6605, 'radius_km': 20}
    report['source_exclusions'] = exclusions
    report['coverage_warning'] = 'Same filter, different acquisition scopes and times. No proven losses inferred.'
    target = args.folders[-1] / 'comparison.json'
    with target.open('x', encoding='utf-8') as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
    print(json.dumps({'legacy': len(legacy), 'pilot': len(pilot), 'candidate_pairs': len(report['candidate_pairs']),
                      'legacy_without_candidate': len(report['legacy_without_candidate']),
                      'pilot_without_candidate': len(report['pilot_without_candidate']),
                      'source_exclusions': exclusions, 'report': str(target)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
