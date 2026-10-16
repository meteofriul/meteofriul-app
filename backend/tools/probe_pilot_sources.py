"""Bounded public-source audit. Writes local evidence only; no cloud client."""
import json
import argparse
from functools import partial
import multiprocessing
from pathlib import Path
import sys
import tempfile
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.events.pilot_sources import source_adapters
from app.events.pilot_catalog import PILOT_PROJECT
from app.events.pilot_comparison import inspect
from app.events.pilot_source_policy import gate_batch
from app.events.source_pipeline import source_fetchers
from app.events.sources import villa_manin, erpac


def adapters():
    result = {'pilot:' + name: adapter for name, adapter in source_adapters(PILOT_PROJECT).items()}
    result.update({'legacy:' + name: adapter for name, adapter in source_fetchers('Pordenone', 100, 45.9569, 12.6605).items()})
    result['shadow:Villa Manin'] = villa_manin.fetch_villa_manin_shadow_catalog
    result['shadow:ERPAC'] = partial(erpac.fetch_erpac_home_shadow, include_details=True)
    return result


def worker(name, sender, details=False, resume=None):
    try:
        if resume and name == 'pilot:TurismoFVG':
            import requests
            from app.events.pilot_details import enrich_details
            previous = json.loads(Path(resume).read_text(encoding='utf-8'))
            if previous.get('status') != 'ok':
                raise ValueError('Only a successful source snapshot can be resumed')
            def fetch(url):
                response = requests.get(url, timeout=(4, 10), allow_redirects=False)
                if response.status_code != 200:
                    raise ValueError(f'detail HTTP {response.status_code}')
                return response.content.decode('utf-8', errors='replace')
            result = enrich_details(previous.get('events', []) + previous.get('detail_candidates', []),
                fetch_html=fetch, previous_cache=previous.get('detail_cache', {}),
                max_urls=None, deadline=time.monotonic()+330)
            batch = {**previous, **result, 'resumed_from': str(resume)}
        elif details and name == 'pilot:TurismoFVG':
            from app.events.pilot_details import collect_regional_with_details
            batch = collect_regional_with_details()
        else:
            batch = adapters()[name]()
        if isinstance(batch, list):
            batch = {'status': 'returned_unverified', 'events': batch,
                     'coverage': 'legacy Pordenone query limit 100; empty may mask upstream errors'}
        elif name.startswith('shadow:'):
            batch['events'] = batch.get('records', [])
        if name.startswith('pilot:'):
            batch = gate_batch(name.split(':', 1)[1], batch,
                               today=datetime.now(ZoneInfo('Europe/Rome')).date())
        sender.send(batch)
    except Exception as exc:
        sender.send({'status': 'error', 'error_type': type(exc).__name__, 'error': str(exc)[:500]})
    finally:
        sender.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--source', action='append', choices=list(adapters()))
    parser.add_argument('--timeout', type=int, default=None)
    parser.add_argument('--details', action='store_true', help='Run the bounded TurismoFVG detail stage too')
    parser.add_argument('--resume', help='Resume a saved TurismoFVG source snapshot without reloading its listing')
    args = parser.parse_args()
    if args.resume and args.source != ['pilot:TurismoFVG']:
        parser.error('--resume requires --source pilot:TurismoFVG')
    if args.timeout is not None and not 1 <= args.timeout <= 360:
        parser.error('timeout must be 1..360 seconds')
    folder = Path(tempfile.mkdtemp(prefix='meteofriul-source-audit-'))
    print(f'EVIDENCE {folder}', flush=True)
    context = multiprocessing.get_context('spawn')
    summaries = {}
    selected = args.source or [name for name in adapters() if args.all or name.startswith('pilot:')]
    for name in selected:
        started = time.monotonic()
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(target=worker, args=(name, sender, args.details, args.resume))
        print(f'START {name}', flush=True)
        try:
            process.start()
            sender.close()
            if receiver.poll(args.timeout or (120 if name.endswith('TurismoFVG') else 60)):
                try:
                    batch = receiver.recv()
                except EOFError:
                    batch = {'status': 'error', 'error_type': 'WorkerExit'}
            else:
                batch = {'status': 'error', 'error_type': 'Timeout'}
        finally:
            if process.pid:
                process.join(.2)
                if process.is_alive():
                    process.terminate()
                    process.join(2)
                if process.is_alive():
                    process.kill()
                    process.join()
                process.close()
            receiver.close()
            sender.close()
        batch['audit_collected_at'] = datetime.now(timezone.utc).isoformat()
        slug = name.lower().replace(' ', '-').replace(':', '-')
        (folder / f'{slug}.json').write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding='utf-8')
        audit = inspect(batch.get('events', []))
        summary = {'status': batch.get('status'), 'seconds': round(time.monotonic()-started, 1),
                   'detail_urls_checked': batch.get('detail_urls_checked', 0),
                   'pending_candidates': len(batch.get('detail_candidates', [])),
                   'records': audit['count'], 'exact_duplicate_groups': len(audit['exact_duplicate_groups']),
                   'review_count': len(batch.get('review_required', [])), 'error_type': batch.get('error_type'),
                   'error': batch.get('error'), 'coverage': batch.get('coverage', 'not_declared')}
        summaries[name] = summary
        print(json.dumps({name: summary}, ensure_ascii=False), flush=True)
    (folder / 'summary.json').write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
