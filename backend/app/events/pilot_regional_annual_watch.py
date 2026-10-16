"""Weekly inventory cross-check for the rolling TurismoFVG publication window.

The annual search is read only. It never replaces a verified near-term batch,
and it does not claim to have inspected every annual detail page.
"""
from datetime import date
import multiprocessing

from .pilot_regional_filtered import fetch_year_partitioned


def collect_watch(today, window_urls, *, fetch_calendar=fetch_year_partitioned):
    if not isinstance(today, date) or not isinstance(window_urls, (list, tuple, set)):
        raise ValueError('invalid TurismoFVG annual watch input')
    annual = fetch_calendar(date(today.year, 1, 1),
                            date(today.year, 12, 31), max_workers=16)
    cards = annual.get('cards') or []
    if (annual.get('start') != date(today.year, 1, 1).isoformat()
            or annual.get('end') != date(today.year, 12, 31).isoformat()
            or annual.get('declared_results') != annual.get('cards_seen')
            or annual.get('cards_seen') != len(cards)
            or not isinstance(annual.get('pages'), int) or annual['pages'] < 1):
        raise ValueError('incomplete TurismoFVG annual inventory')
    annual_urls = {card['url'] for card in cards}
    missing = sorted(set(window_urls) - annual_urls)
    return {'source_complete': not missing,
            'as_of_date': today.isoformat(),
            'calendar_cards': len(cards),
            'calendar_pages': annual['pages'],
            'calendar_urls': len(annual_urls),
            'window_urls_compared': len(set(window_urls)),
            'missing_window_urls': missing[:20],
            'missing_window_count': len(missing)}


def _worker(sender, today, window_urls):
    try:
        sender.send(('ok', collect_watch(today, window_urls)))
    except Exception as exc:
        sender.send(('error', type(exc).__name__ + ': ' + str(exc)[:180]))
    finally:
        sender.close()


def run_bounded_watch(today, window_urls, *, timeout=240):
    if not 30 <= timeout <= 240:
        raise ValueError('invalid TurismoFVG annual watch timeout')
    context = multiprocessing.get_context('spawn')
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(sender, today, list(window_urls)))
    try:
        process.start()
        sender.close()
        if receiver.poll(timeout):
            try:
                status, result = receiver.recv()
            except EOFError:
                raise RuntimeError('TurismoFVG annual watch worker exited') from None
            if status != 'ok':
                raise RuntimeError(result)
            return result
        raise TimeoutError('TurismoFVG annual inventory watch timed out')
    finally:
        if process.pid is not None:
            process.join(timeout=0.2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()
        sender.close()
        receiver.close()
