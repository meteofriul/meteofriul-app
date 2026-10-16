"""Resume a local TurismoFVG year audit without publishing any catalog."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.events.pilot_regional_checkpoint import decode_control, encode_control
from app.events import engine
from app.events.pilot_regional_filtered import fetch_year_partitioned
from app.events.pilot_regional_sitemap import discover_detail_urls
from app.events.pilot_regional_verified import collect_regional_verified


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cycles', type=int, default=4)
    parser.add_argument('--cycle-seconds', type=int, default=240)
    parser.add_argument('--reuse-index', action='store_true',
                        help='Local audit only: reuse a previously saved complete index')
    args = parser.parse_args()
    if not 1 <= args.cycles <= 8 or not 30 <= args.cycle_seconds <= 335:
        parser.error('invalid local audit bounds')
    args.output.mkdir(parents=True, exist_ok=True)
    checkpoint_path = args.output / 'turismofvg-checkpoint.json'
    result_path = args.output / 'pilot-turismofvg.json'
    calendar_path = args.output / 'turismofvg-calendar.json'
    sitemap_path = args.output / 'turismofvg-sitemap.json'

    def calendar_snapshot(start, end, *, max_workers):
        if args.reuse_index:
            calendar = json.loads(calendar_path.read_text(encoding='utf-8'))
            if (calendar.get('start') == start.isoformat()
                    and calendar.get('end') == end.isoformat()):
                if (calendar.get('cards_seen') != calendar.get('declared_results')
                        or calendar.get('cards_seen') != len(calendar.get('cards') or [])
                        or any(not engine.is_trusted_turismofvg_event_url(card.get('url'))
                               for card in calendar['cards'])):
                    raise ValueError('saved TurismoFVG calendar is incomplete or untrusted')
                return calendar
            return fetch_year_partitioned(start, end, max_workers=max_workers)
        calendar = fetch_year_partitioned(start, end, max_workers=max_workers)
        save_json(calendar_path, calendar)
        return calendar

    def sitemap_snapshot():
        if args.reuse_index:
            sitemap = json.loads(sitemap_path.read_text(encoding='utf-8'))
            if (sitemap.get('status') != 'ok'
                    or sitemap.get('unique_urls') != len(sitemap.get('detail_urls') or [])):
                raise ValueError('saved TurismoFVG sitemap is incomplete')
            return sitemap
        sitemap = discover_detail_urls()
        save_json(sitemap_path, sitemap)
        return sitemap

    for cycle in range(1, args.cycles + 1):
        previous = (decode_control(json.loads(checkpoint_path.read_text(encoding='utf-8')))
                    if checkpoint_path.exists() else None)
        print(json.dumps({'cycle': cycle, 'resuming': previous is not None,
                          'index_reused': args.reuse_index}), flush=True)
        try:
            result = collect_regional_verified(
                previous, max_seconds=args.cycle_seconds,
                fetch_calendar=calendar_snapshot, fetch_sitemap=sitemap_snapshot)
        except ValueError as exc:
            if str(exc).startswith(('TurismoFVG page count differs from declared results',
                                    'TurismoFVG changed result total or page size')):
                print(json.dumps({'cycle': cycle, 'status': 'index_changed_during_scan',
                                  'reason': str(exc)}), flush=True)
                continue
            raise
        control = result.get('year_control')
        if isinstance(control, dict):
            save_json(checkpoint_path, encode_control(control))
        verification = result.get('verification') or {}
        print(json.dumps({'cycle': cycle, 'status': result.get('status'),
                          'error_type': result.get('error_type'),
                          'source_complete': verification.get('source_complete'),
                          'inventory_urls': verification.get('inventory_urls'),
                          'pending': verification.get('pending'),
                          'ambiguous': verification.get('ambiguous'),
                          'review_required': verification.get('review_required'),
                          'events': len(result.get('events') or []),
                          'display_review': (result.get('review_required') or [])[:20]}),
              flush=True)
        if result.get('status') == 'ok':
            result['audit_collected_at'] = datetime.now(timezone.utc).isoformat()
            result['audit_index_reused'] = args.reuse_index
            save_json(result_path, result)
            print('EVIDENCE ' + str(result_path), flush=True)
            return
    raise SystemExit('TurismoFVG audit incomplete; checkpoint saved for another run')


if __name__ == '__main__':
    main()
