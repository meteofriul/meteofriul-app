"""Approved pilot sources and publication gates, separate from beta adapters."""
from datetime import date, time, timedelta
from urllib.parse import urlsplit
import math
import re

from . import engine
from .pilot_barcolana import (REGIONAL_MUSEUM, REGIONAL_PIAZZA_PAGES,
                              REGIONAL_PERIODS, REGIONAL_TALKS)
from .pilot_cinema_muto import is_edition_cover_url

APPROVED_SOURCES = {
    "TurismoFVG": "https://www.turismofvg.it/eventi",
    "Pordenonelegge": "https://www.pordenonelegge.it/programma",
    "Le Giornate del Cinema Muto": "https://www.giornatedelcinemamuto.it/",
    "Azalea": "https://www.azalea.it/",
    "CSS Udine": "https://www.cssudine.it/",
    "Teatro Verdi Pordenone": "https://teatroverdipordenone.it/la-stagione/",
    "Teatro Verdi Trieste": "https://www.teatroverdi-trieste.com/it/calendario-spettacoli/",
    "Pordenone Pensa": "https://www.pnpensa.it/",
    "Paesi in Festa": "https://paesiinfesta.com/",
    "SagreFVG": "https://sagrefvg.it/sagris/",
    "Villa Manin": "https://www.villamanin.it/eventi/",
    "Magazzino delle Idee": "https://magazzinodelleidee.it/eventi/",
    "MESS": "https://mess.regione.fvg.it/it/didattica-museale-171043",
    "Galleria Spazzapan": "https://galleriaspazzapan.regione.fvg.it/it/",
    "Barcolana": "https://www.barcolana.it/it/calendario-eventi",
}


def _review_urls(batch):
    """A partial batch must identify each quarantined page exactly once."""
    reviews = batch.get('review_required') or []
    if not isinstance(reviews, list):
        return None
    urls = [item.get('url') for item in reviews if isinstance(item, dict)
            and isinstance(item.get('reason'), str) and item['reason']]
    if (len(urls) != len(reviews) or any(not isinstance(url, str) or not url
                                         for url in urls)
            or len(set(urls)) != len(urls)):
        return None
    return set(urls)


def cinema_muto_batch_verified(batch, *, previous_batch=None):
    """Reconcile the official page inventory with every timed HTML widget."""
    proof = batch.get('verification')
    if not isinstance(proof, dict) or proof.get('collection_mode') != 'complete-official-html-calendar':
        return False
    days = proof.get('days')
    if not isinstance(days, list) or not 3 <= len(days) <= 12:
        return False
    try:
        edition = int(proof['edition_id'])
        first = date.fromisoformat(proof['start_date'])
        last = date.fromisoformat(proof['end_date'])
        main_first = date.fromisoformat(proof['main_start_date'])
        main_last = date.fromisoformat(proof['main_end_date'])
        dated = [date.fromisoformat(item['date']) for item in days]
        if any(not isinstance(item, dict) for item in days):
            return False
        previous_proof = (previous_batch.get('verification') if isinstance(previous_batch, dict)
                          else None) or {}
        if not isinstance(previous_proof, dict):
            previous_proof = {}
        previous_edition = previous_proof.get('edition_id')
        if previous_edition is not None and int(previous_edition) > edition:
            return False
        prior_count = (previous_proof.get('records_scanned')
                       or previous_proof.get('parsed_count'))
        same_edition = (previous_edition == str(edition)
                        and isinstance(prior_count, int) and prior_count > 0)
        if same_edition and (previous_proof.get('start_date') != first.isoformat()
                             or previous_proof.get('end_date') != last.isoformat()
                             or (proof['records_scanned']
                                 if previous_proof.get('records_scanned')
                                 else proof['parsed_count']) < prior_count * 0.9):
            return False
        events = batch['events']
        if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
            return False
        images = [event.get('image') for event in events]
        if any(images) and (not all(images) or len(set(images)) != 1
                            or not is_edition_cover_url(images[0], year=edition)):
            return False
        return (1000 <= edition <= 2099 and first.year == last.year == edition
                and first <= main_first <= main_last <= last
                and first >= main_first - timedelta(days=1)
                and last <= main_last + timedelta(days=1)
                and dated == [first + timedelta(days=index) for index in range(len(days))]
                and dated[-1] == last
                and proof['sitemap_page_count'] == len(days)
                and proof['records_scanned'] == sum(item['widgets_scanned'] for item in days)
                and proof['parsed_count'] == sum(item['slots_parsed'] for item in days)
                and proof['records_scanned']
                    == proof['parsed_count'] + proof['review_count'] + len(days)
                and proof['parsed_count'] == len(events)
                and proof['review_count'] == len(batch.get('review_required') or [])
                and proof['review_count'] == sum(
                    item['slots_reviewed'] for item in days)
                and proof['parsed_count'] > 0
                and len({item.get('source_id') for item in batch.get('review_required') or []})
                    == proof['review_count']
                and all(isinstance(item, dict)
                        and item.get('reason') in {
                            'invalid_calendar_time', 'venue_without_title',
                            'preopening_title_missing', 'unknown_calendar_venue',
                            'incomplete_or_changed_slot', 'duplicate_programme_slot'}
                        and item.get('source_id') not in {
                            event.get('source_id') for event in events}
                        and any(item.get('url') == day['url']
                                and re.fullmatch(
                                    re.escape(day['date']) + r'-\d+',
                                    item.get('source_id') or '')
                                for day in days)
                        for item in batch.get('review_required') or [])
                and all(item['slots_parsed'] >= 0
                        and item['slots_reviewed'] >= 0
                        and item['widgets_scanned']
                            == item['slots_parsed'] + item['slots_reviewed'] + 1
                        and urlsplit(item['url']).scheme == 'https'
                        and urlsplit(item['url']).hostname == 'www.giornatedelcinemamuto.it'
                        and urlsplit(item['url']).path == f"/calendario-{date.fromisoformat(item['date']):%d%m%y}/"
                        and not urlsplit(item['url']).query
                        for item in days)
                and all(sum(event.get('start_date') == item['date'] for event in events)
                        == item['slots_parsed'] for item in days)
                and all(sum(review.get('url') == item['url']
                            for review in batch.get('review_required') or [])
                        == item['slots_reviewed'] for item in days)
                and all(event.get('source') == 'Le Giornate del Cinema Muto'
                        and event.get('programme_id') == f'giornate-del-cinema-muto-{edition}'
                        and event.get('programme_start_date') == first.isoformat()
                        and event.get('programme_end_date') == last.isoformat()
                        and event.get('programme_main_start_date') == main_first.isoformat()
                        and event.get('programme_main_end_date') == main_last.isoformat()
                        and event.get('url') == next(item['url'] for item in days
                                                     if item['date'] == event.get('start_date'))
                        and bool(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',
                                              event.get('time') or ''))
                        for event in events))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def pordenonelegge_batch_verified(batch, *, previous_batch=None, today=None):
    """Check the complete-programme heading, day tabs and every parsed card."""
    proof = batch.get('verification')
    if not isinstance(proof, dict):
        return False
    if proof.get('collection_mode') == 'closed-verified-edition':
        prior = (previous_batch or {}).get('verification') or {}
        try:
            prior_end = prior.get('end_date') or prior.get('prior_end_date')
            prior_count = prior.get('parsed_count') or prior.get('prior_parsed_count')
            return (today is not None
                    and prior.get('collection_mode') in {
                        'complete-official-programme', 'closed-verified-edition'}
                    and prior.get('edition_id') == proof.get('edition_id')
                    and prior_end == proof.get('prior_end_date')
                    and date.fromisoformat(prior_end) < today
                    and isinstance(prior_count, int) and prior_count > 0
                    and proof.get('prior_parsed_count') == prior_count
                    and proof.get('as_of_date') == today.isoformat()
                    and proof.get('redirect_target', '').rstrip('/')
                        == 'https://www.pordenonelegge.it'
                    and proof.get('source_complete') is True
                    and batch.get('events') == []
                    and not batch.get('review_required'))
        except (TypeError, ValueError):
            return False
    days = proof.get('tab_dates') or []
    counts = proof.get('day_counts') or {}
    duplicates = proof.get('duplicate_by_day') or {}
    numeric = ('records_scanned', 'parsed_count', 'duplicate_count', 'review_count')
    if (proof.get('collection_mode') != 'complete-official-programme'
            or not isinstance(days, list) or not all(isinstance(day, str) for day in days)
            or not 3 <= len(days) <= 10 or len(days) != len(set(days))
            or not isinstance(counts, dict)
            or set(counts) != set(days) or set(duplicates) != set(days)
            or any(not isinstance(proof.get(key), int) or isinstance(proof[key], bool)
                   or proof[key] < 0 for key in numeric)
            or any(not isinstance(count, int) or isinstance(count, bool) or count < 1
                   for count in counts.values())
            or any(not isinstance(count, int) or isinstance(count, bool) or count < 0
                   for count in duplicates.values())):
        return False
    try:
        parsed_days = [date.fromisoformat(day) for day in days]
        edition = proof['edition_id']
        previous_proof = previous_batch.get('verification') if isinstance(previous_batch, dict) else {}
        if not isinstance(previous_proof, dict):
            previous_proof = {}
        prior_edition = previous_proof.get('edition_id')
        if prior_edition is not None and int(prior_edition) > int(edition):
            return False
        same_edition = (previous_proof.get('edition_id') == edition
                        and isinstance(previous_proof.get('records_scanned'), int)
                        and not isinstance(previous_proof['records_scanned'], bool)
                        and previous_proof['records_scanned'] > 0)
        no_regression = (not same_edition or (
            previous_proof.get('tab_dates') == days
            and proof['records_scanned'] >= previous_proof['records_scanned'] * 0.9))
        return (no_regression and days == sorted(days)
                and all(day.year == int(edition) for day in parsed_days)
                and proof['start_date'] == days[0]
                and proof['end_date'] == days[-1]
                and proof['records_scanned'] == sum(counts.values())
                == proof['parsed_count'] + proof['duplicate_count'] + proof['review_count']
                and proof['duplicate_count'] == sum(duplicates.values())
                and proof['review_count'] == len(batch.get('review_required') or [])
                and proof['parsed_count'] == len(batch.get('events', []))
                and proof['parsed_count'] > 0
                and len({item.get('source_id') for item in
                         batch.get('review_required') or []})
                    == proof['review_count']
                and all(isinstance(item, dict)
                        and item.get('reason') in {
                            'invalid_programme_time', 'missing_title_or_venue',
                            'schedule_change_requires_review',
                            'municipality_not_resolved'}
                        and item.get('date') in days
                        and re.fullmatch(r'https://www\.pordenonelegge\.it/eventi/[^?#]+',
                                         item.get('url') or '')
                        for item in batch.get('review_required') or [])
                and all(isinstance(event, dict) for event in batch['events'])
                and {event.get('start_date') for event in batch['events']} <= set(days)
                and all(sum(event.get('start_date') == day for event in batch['events'])
                        + sum(item.get('date') == day for item in
                              batch.get('review_required') or [])
                        + duplicates[day] == counts[day] for day in days)
                and all(event.get('source') == 'Pordenonelegge'
                        and event.get('programme_id') == f'pordenonelegge-{edition}'
                        and event.get('programme_start_date') == days[0]
                        and event.get('programme_end_date') == days[-1]
                        for event in batch['events']))
    except (KeyError, TypeError, ValueError):
        return False


def sagrefvg_batch_verified(batch, *, today):
    verification = batch.get('verification') or {}
    windows = verification.get('windows') or []
    if (verification.get('collection_mode') != 'complete-annual-api-pages'
            or len(windows) < 3
            or any(not isinstance(window, dict) for window in windows)
            or not all(isinstance(verification.get(key), int)
                       and not isinstance(verification[key], bool)
                       and verification[key] >= 0
                       for key in ('records_scanned', 'past_count', 'active_count',
                                   'review_count'))):
        return False
    try:
        year = today.year
        for window in windows:
            count = window['declared_results']
            if (date.fromisoformat(window['start']) != date(year, 1, 1)
                    or date.fromisoformat(window['end']) != date(year, 12, 31)
                    or not isinstance(count, int) or isinstance(count, bool)
                    or count < 0 or window['records_read'] != count
                    or window['pages_read'] != max(1, (count + 49) // 50)):
                return False
            year += 1
        return (windows[-1]['declared_results'] == 0
                and windows[-2]['declared_results'] == 0
                and date.fromisoformat(verification['overflow_start']) == date(year, 1, 1)
                and verification['overflow_total'] == 0
                and verification['records_scanned']
                    == sum(window['records_read'] for window in windows)
                and verification['records_scanned']
                    == verification['past_count'] + verification['active_count']
                       + verification['review_count']
                and verification['active_count'] == len(batch.get('events', []))
                and verification['review_count'] == len(batch.get('review_required') or [])
                and all(isinstance(item, dict)
                        and isinstance(item.get('url'), str)
                        and item.get('url', '').startswith('https://sagrefvg.it/')
                        and isinstance(item.get('reason'), str)
                        and item['reason']
                        for item in batch.get('review_required') or [])
                and all(not event.get('image') or
                        event['image'].startswith('https://sagrefvg.it/wp-content/uploads/'
                                                  + event['start_date'][:4] + '/')
                        for event in batch.get('events', [])))
    except (KeyError, TypeError, ValueError):
        return False


def paesiinfesta_batch_verified(batch, *, today):
    verification = batch.get('verification') or {}
    counts = verification.get('list_counts') or {}
    surfaces = verification.get('surface_counts') or {}
    sitemap = verification.get('sitemap') or {}
    excluded = batch.get('excluded') or []
    expected_keys = {'sagre', 'rievocazioni'}
    expected_surfaces = {'home', 'fvg', 'udine', 'pordenone', 'archive'}
    numeric = ('listed_cards', 'detail_urls', 'detail_pages_read',
               'outside_fvg_urls', 'quarantined_before_detail',
               'surface_active_urls', 'extra_active_urls',
               'review_count', 'excluded_count')
    sitemap_numeric = ('post_maps_read', 'posts_seen', 'posts_in_scope',
                       'changed_unlisted', 'changed_checked', 'unknown_paths',
                       'active_added',
                       'review_count')
    if (set(counts) != expected_keys
            or any(not isinstance(counts[key], int) or isinstance(counts[key], bool)
                   or counts[key] < 1 for key in expected_keys)
            or set(surfaces) != expected_surfaces
            or any(not isinstance(surfaces[key], dict)
                   or any(not isinstance(surfaces[key].get(field), int)
                          or isinstance(surfaces[key][field], bool)
                          or surfaces[key][field] < 0
                          for field in ('fvg_cards_examined', 'active_fvg_urls'))
                   or surfaces[key]['fvg_cards_examined'] < 1
                   or surfaces[key]['active_fvg_urls'] > surfaces[key]['fvg_cards_examined']
                   for key in expected_surfaces)
            or any(not isinstance(verification.get(key), int)
                   or isinstance(verification[key], bool)
                   or verification[key] < 0 for key in numeric)
            or sitemap.get('baseline') != '2026-10-06T00:00:00+00:00'
            or any(not isinstance(sitemap.get(key), int)
                   or isinstance(sitemap[key], bool) or sitemap[key] < 0
                   for key in sitemap_numeric)):
        return False
    reviews = batch.get('review_required') or []
    review_urls = [item.get('url') for item in reviews if isinstance(item, dict)]
    if (len(review_urls) != len(reviews) or len(set(review_urls)) != len(reviews)
            or any(not isinstance(url, str)
                   or urlsplit(url).hostname != 'paesiinfesta.com'
                   or urlsplit(url).scheme != 'https' for url in review_urls)
            or any(item.get('reason') not in {'future_card_marked_archived',
                                              'detail_conflict'} for item in reviews)
            or verification['quarantined_before_detail'] != sum(
                item['reason'] == 'future_card_marked_archived' for item in reviews)
            or set(review_urls) & {event.get('url') for event in batch.get('events', [])
                                   if isinstance(event, dict)}
            or (reviews and not batch.get('events'))):
        return False
    return (verification['listed_cards'] == sum(counts.values())
            and verification['detail_urls']
                == verification['listed_cards'] + verification['extra_active_urls']
            and verification['detail_pages_read'] + verification['outside_fvg_urls']
                + verification['quarantined_before_detail']
                == verification['detail_urls']
            and verification['surface_active_urls']
                >= verification['extra_active_urls']
            and verification.get('surface_date') == today.isoformat()
            and 1 <= sitemap['post_maps_read'] <= 10
            and 1 <= sitemap['posts_in_scope'] <= sitemap['posts_seen'] <= 2000
            and sitemap['changed_checked'] == sitemap['changed_unlisted'] <= 8
            and sitemap['active_added'] <= sitemap['changed_checked']
            and sitemap['active_added'] == sum(
                isinstance(event, dict) and event.get('discovery_kind') == 'sitemap'
                for event in batch.get('events', []))
            and sitemap['unknown_paths'] == 0
            and sitemap['review_count'] == 0
            and verification['review_count'] == len(reviews)
            and verification['excluded_count'] == len(excluded)
            and all(isinstance(item, dict)
                    and item.get('reason') in {'outside_fvg', 'month_only_period',
                                               'provisional_cross_town_schedule'}
                    for item in excluded))


def turismofvg_retrospective_verified(verification, *, today):
    """Require a complete backward scan before claiming source coverage."""
    retrospective = verification.get('retrospective') or {}
    windows = retrospective.get('windows') or []
    older = retrospective.get('older_overflow') or {}
    if (retrospective.get('horizon_complete') is not True
            or retrospective.get('as_of_date') != today.isoformat()
            or len(windows) < 3
            or any(not isinstance(item, dict) for item in windows)
            or not isinstance(retrospective.get('unresolved_orphans'), int)
            or isinstance(retrospective.get('unresolved_orphans'), bool)
            or retrospective['unresolved_orphans'] != 0):
        return False
    try:
        expected_end = today - timedelta(days=1)
        for window in windows:
            start = date.fromisoformat(window['start'])
            end = date.fromisoformat(window['end'])
            if (start != date(expected_end.year, 1, 1) or end != expected_end
                    or any(not isinstance(window[key], int) or isinstance(window[key], bool)
                           for key in ('declared_results', 'cards_seen', 'pages'))
                    or window['declared_results'] != window['cards_seen']
                    or window['pages'] < 1):
                return False
            expected_end = start - timedelta(days=1)
        return (windows[-1]['declared_results'] == 0
                and windows[-2]['declared_results'] == 0
                and date.fromisoformat(older['start']) == date(1900, 1, 1)
                and date.fromisoformat(older['end']) == expected_end
                and older['declared_results'] == 0
                and sum(item['cards_seen'] for item in windows)
                    == retrospective['cards_seen']
                    == retrospective['declared_results'])
    except (KeyError, TypeError, ValueError):
        return False


def turismofvg_batch_verified(batch, *, today, previous_batch=None):
    verification = batch.get('verification') or {}
    if verification.get('collection_mode') == 'verified-rolling-45-day-window':
        try:
            from .pilot_regional_checkpoint import decode_control, resumable_details
            from .pilot_regional_year_control import summary as control_summary
            from .pilot_regional_verified import (job_results_fresh,
                                                  known_future_evidence,
                                                  evidence_overlaps_window,
                                                  evidence_has_future_after_window)
            from .pilot_regional_display_audit import create_year_display_audit
            control = batch['year_control']
            stats = control_summary(control)
            display = create_year_display_audit(control, today=today)
            end = today + timedelta(days=45)
            segments = control['calendar_segments']
            cursor = today
            for segment in segments:
                first, last = (date.fromisoformat(segment[key])
                               for key in ('start', 'end'))
                if (first != cursor or last < first
                        or last > date(first.year, 12, 31)
                        or segment['declared_results'] != segment['cards_seen']
                        or segment['pages'] < 1):
                    return False
                cursor = last + timedelta(days=1)
            previous_control = (decode_control(previous_batch['control_checkpoint'])
                                if previous_batch and previous_batch.get('control_checkpoint')
                                else None)
            from .pilot_regional_health import detail_health, detail_health_verified
            if (not detail_health_verified(control, previous_control=previous_control, today=today,
                    resumed_results=resumable_details(control, previous_batch, today=today))
                    or verification.get('detail_health') != detail_health(control)
                    or batch.get('detail_diagnostics') != control.get('detail_diagnostics')
                    or batch.get('detail_candidates')
                    or (not display['cards'] and (display['review'] or display['quarantined']))):
                return False
            prior_entries = (previous_control or {}).get('entries') or {}
            prior_index = ((previous_control or {}).get('sitemap_index')
                           or {url: entry.get('sitemap_lastmod')
                               for url, entry in prior_entries.items()
                               if entry.get('in_sitemap')})
            sitemap_index = control['sitemap_index']
            listed = {url for url, item in control['entries'].items()
                      if item['kind'] == 'calendar'
                      and item.get('listing_origin') != 'prior_verified'}
            future_evidence = known_future_evidence(
                previous_control, previous_batch)
            due_future = {
                url for url, witness in future_evidence.items()
                if evidence_overlaps_window(witness, today=today, window_end=end)
            }
            active_prior = {
                item['url'] for item in (previous_batch or {}).get('events', [])
                if item.get('url') and (item.get('end_date') or '') >= today.isoformat()
                and (not item.get('start_date')
                     or item['start_date'] <= end.isoformat())
            } | due_future
            changed = {url for url, lastmod in sitemap_index.items()
                       if url not in prior_index or prior_index[url] != lastmod}
            selected = listed | active_prior | changed
            carried_prior = active_prior - listed
            prior_detail = active_prior - listed - set(sitemap_index)
            far_expected = {
                url for url, witness in future_evidence.items()
                if evidence_has_future_after_window(witness, window_end=end)
            } | {
                url for url, result in control['results'].items()
                if (result.get('status') == 'detail_aligned'
                    and evidence_has_future_after_window(
                        {'entry': control['entries'][url], 'result': result},
                        window_end=end))
            }
            return (bool(segments) and cursor == end + timedelta(days=1)
                    and control['window_end'] == end.isoformat()
                    and control['as_of_date'] == today.isoformat()
                    and set(control['carried_prior_urls']) == carried_prior
                    and set(control['prior_detail_urls']) == prior_detail
                    and set(control['current_year_window_urls']) <= listed
                    and set(control['known_future']) == far_expected
                    and all(witness['result']['status'] == 'detail_aligned'
                            and witness['entry']
                            for witness in control['known_future'].values())
                    and all(
                        (control['entries'][url].get('listing_origin') == 'prior_verified'
                         and control['entries'][url].get('candidate')
                             == (prior_entries.get(url)
                                 or future_evidence.get(url, {}).get('entry')
                                 or {}).get('candidate'))
                        or control['entries'][url]['kind'] in {
                            'sitemap_only', 'prior_detail'}
                        for url in carried_prior)
                    and set(control['entries']) == selected
                    and len(sitemap_index) == control['sitemap_total_urls']
                    and control['sitemap_selected_urls']
                        == len(set(sitemap_index) & selected)
                    and control['calendar_pages'] == sum(
                        segment['pages'] for segment in segments)
                    and stats['inventory_complete'] is True
                    and display['inventory_complete'] is True
                    and verification['quarantine_count']
                        == len({item['url'] for item in
                                display['quarantined'] + display['review']})
                    and _review_urls(batch)
                        == {item['url'] for item in
                            display['quarantined'] + display['review']}
                    and verification['as_of_date'] == today.isoformat()
                    and verification['window_end'] == end.isoformat()
                    and verification['source_complete'] is True
                    and verification['within_budget'] is True
                    and verification['index_fingerprint'] == control['index_fingerprint']
                    and verification['inventory_urls'] == stats['inventory_urls']
                    and verification['calendar_pages'] == stats['calendar_pages']
                    and verification['sitemap_total_urls']
                        == control['sitemap_total_urls']
                    and verification['sitemap_selected_urls']
                        == control['sitemap_selected_urls']
                    and verification['prior_detail_count'] == len(prior_detail)
                    and verification['carried_prior_count'] == len(carried_prior)
                    and verification['known_future_count'] == len(far_expected)
                    and verification['calendar_segments'] == segments
                    and verification['cards_total'] == len(display['cards'])
                    and batch.get('events') == display['cards']
                    and job_results_fresh(control, today=today)
                    and not _review_urls(batch) & {
                        item.get('url') for item in display['cards']})
        except (AttributeError, KeyError, TypeError, ValueError):
            return False
    if verification.get('collection_mode') == 'complete-annual-year-control':
        try:
            from .pilot_regional_year_control import summary as control_summary
            from .pilot_regional_verified import (FAR_HOURS, INACTIVE_HOURS,
                                                  NEAR_HOURS, job_results_fresh)
            from .pilot_regional_display_audit import create_year_display_audit
            control = batch['year_control']
            stats = control_summary(control)
            display = create_year_display_audit(control, today=today)
            return (stats['source_complete'] is True
                    and display['source_complete'] is True
                    and not display['quarantined'] and not display['review']
                    and verification['as_of_date'] == today.isoformat()
                    and verification['source_complete'] is True
                    and verification['within_budget'] is True
                    and verification['near_detail_age_hours'] == NEAR_HOURS
                    and verification['far_detail_age_hours'] == FAR_HOURS
                    and verification['inactive_detail_age_hours'] == INACTIVE_HOURS
                    and job_results_fresh(control, today=today)
                    and verification['index_fingerprint'] == control['index_fingerprint']
                    and verification['inventory_urls'] == stats['inventory_urls']
                    and verification['calendar_pages'] == stats['calendar_pages']
                    and verification['cards_total'] == len(display['cards'])
                    and batch.get('events') == display['cards']
                    and not batch.get('review_required'))
        except (AttributeError, KeyError, TypeError, ValueError):
            return False
    expected = verification.get('declared_results')
    scanned = verification.get('cards_seen')
    pages = verification.get('pages')
    verified = verification.get('verified_events')
    unresolved = verification.get('unresolved_count')
    sitemap_only_unclassified = verification.get('sitemap_only_unclassified')
    windows = verification.get('windows') or []
    overflow = verification.get('overflow') or {}
    window_counts_valid = (len(windows) >= 3
                           and all(isinstance(item, dict)
                                   and all(isinstance(item.get(key), int)
                                           and not isinstance(item[key], bool)
                                           for key in ('declared_results', 'cards_seen', 'pages'))
                                   and item['declared_results'] == item['cards_seen']
                                   and item['pages'] > 0
                                   for item in windows)
                           and windows[-1]['declared_results'] == 0
                           and windows[-2]['declared_results'] == 0)
    try:
        window_dates_valid = (date.fromisoformat(windows[0]['start']) == today
                              and all(date.fromisoformat(item['end']) == date(
                                  date.fromisoformat(item['start']).year, 12, 31)
                                  for item in windows)
                              and all(date.fromisoformat(windows[index]['start'])
                                      == date.fromisoformat(windows[index - 1]['end']) + timedelta(days=1)
                                      for index in range(1, len(windows)))
                              and date.fromisoformat(overflow['start'])
                                      == date.fromisoformat(windows[-1]['end']) + timedelta(days=1)
                              and date.fromisoformat(overflow['end']) == date(2099, 12, 31))
    except (KeyError, TypeError, ValueError, IndexError):
        window_dates_valid = False
    return (all(isinstance(value, int) and not isinstance(value, bool)
                for value in (expected, scanned, pages, verified, unresolved))
            and verification.get('collection_mode') == 'annual-date-filters'
            and verification.get('horizon_complete') is True
            and turismofvg_retrospective_verified(verification, today=today)
            and overflow.get('declared_results') == 0
            and window_counts_valid and window_dates_valid
            and sum(item['declared_results'] for item in windows) == expected
            and sum(item['cards_seen'] for item in windows) == scanned
            and sum(item['pages'] for item in windows) == pages
            and expected > 0 and scanned == expected and pages > 0
            and verified == len(batch.get('events', [])) and unresolved == 0
            and isinstance(sitemap_only_unclassified, int)
            and not isinstance(sitemap_only_unclassified, bool)
            and sitemap_only_unclassified == 0
            and not batch.get('detail_candidates') and not batch.get('review_required')
            and all(isinstance(event, dict) and event.get('detail_status') == 'inspected'
                    for event in batch.get('events', [])))


def validate_candidate(event, *, today):
    """Require explicit event-date evidence; never substitute article timestamps.

    Returns review reasons, rather than converting ambiguous data into an event.
    `today` is supplied in the application's local timezone by the caller.
    """
    reasons = []
    source = event.get("source")
    if source not in APPROVED_SOURCES:
        return ["unapproved_source"]
    url = urlsplit(event.get("url") or "")
    if url.scheme != "https" or url.hostname != urlsplit(APPROVED_SOURCES[source]).hostname:
        reasons.append("invalid_source_url")
    if event.get("date_evidence_kind") not in {"event_schedule", "structured_event_start"}:
        reasons.append("event_date_not_verified")
    if not event.get("date_evidence"):
        reasons.append("missing_date_evidence")
    end_only = (source == 'TurismoFVG'
                and event.get('schedule_kind') == 'end_only')
    try:
        if end_only:
            evidence = str(event.get('date_evidence') or '').strip()
            evidence_start, evidence_end = engine.parse_event_date_range(evidence)
            if (event.get('start_date') is not None
                    or event.get('occurrences')
                    or not evidence.lower().startswith('fino al ')
                    or evidence_start != evidence_end
                    or evidence_end != date.fromisoformat(event.get('end_date') or '')):
                reasons.append('invalid_end_only_schedule')
            start = None
            end = date.fromisoformat(event.get('end_date') or '')
        else:
            start = date.fromisoformat(event.get("start_date") or "")
            end = date.fromisoformat(event.get("end_date") or event.get("start_date") or "")
            if end < start:
                reasons.append("inverted_dates")
        if end < today:
            reasons.append("past_event")
    except (ValueError, TypeError):
        reasons.append("invalid_dates")
    if not event.get("title") or not event.get("event_city"):
        reasons.append("missing_identity_or_municipality")
    if event.get("event_status") in {"cancelled", "postponed", "conflicting"}:
        reasons.append("schedule_requires_review")
    for field, bound in (('lat', 90), ('lon', 180)):
        value = event.get(field)
        if value is not None:
            try:
                if isinstance(value, bool) or not math.isfinite(float(value)) or abs(float(value)) > bound:
                    reasons.append('invalid_' + field)
            except (ValueError, TypeError):
                reasons.append('invalid_' + field)
    if (event.get('lat') is None) != (event.get('lon') is None):
        reasons.append('incomplete_coordinates')
    if event.get('location_confidence') == 'multiple_municipalities':
        places = event.get('listed_municipalities')
        if event.get('lat') is not None or event.get('lon') is not None:
            reasons.append('multi_place_has_single_point')
        if not isinstance(places, list) or not 2 <= len(places) <= 32:
            reasons.append('invalid_listed_municipalities')
        else:
            names = set()
            for place in places:
                if not isinstance(place, dict) or not isinstance(place.get('name'), str):
                    reasons.append('invalid_listed_municipalities')
                    break
                name = place['name'].strip().casefold()
                try:
                    valid = (name and math.isfinite(float(place['lat']))
                             and math.isfinite(float(place['lon']))
                             and abs(float(place['lat'])) <= 90
                             and abs(float(place['lon'])) <= 180)
                except (KeyError, TypeError, ValueError):
                    valid = False
                if not valid or name in names:
                    reasons.append('invalid_listed_municipalities')
                    break
                names.add(name)
    for field in ('time', 'end_time'):
        if event.get(field):
            try:
                time.fromisoformat(event[field])
            except (TypeError, ValueError):
                reasons.append('invalid_' + field)
    if event.get('time') and event.get('end_time') and 'invalid_time' not in reasons and 'invalid_end_time' not in reasons:
        if event.get('start_date') == (event.get('end_date') or event.get('start_date')) and time.fromisoformat(event['end_time']) <= time.fromisoformat(event['time']):
            reasons.append('ambiguous_end_time')
    for occurrence in event.get('occurrences') or []:
        try:
            day = date.fromisoformat(occurrence)
            if 'invalid_dates' not in reasons and (start is None or not start <= day <= end):
                reasons.append('occurrence_outside_range')
        except (TypeError, ValueError):
            reasons.append('invalid_occurrence')
    return reasons


def azalea_batch_verified(batch, *, today, previous_batch=None):
    """Reconcile every visible archive card with a checked detail and event."""
    proof = batch.get('verification') or {}
    pages = proof.get('archive_pages')
    listings = proof.get('listing_records')
    details = proof.get('detail_records')
    if (proof.get('collection_mode') != 'complete-official-upcoming-archive'
            or proof.get('source_complete') is not True
            or not isinstance(pages, list) or not 1 <= len(pages) <= 10
            or not isinstance(listings, list) or not 1 <= len(listings) <= 200
            or not isinstance(details, list) or len(details) != len(listings)
            or not isinstance(proof.get('sitemap_event_urls'), int)
            or not 1 <= proof['sitemap_event_urls'] <= 1000
            or not isinstance(proof.get('sitemap_unlisted_delta_checked'), int)
            or not 0 <= proof['sitemap_unlisted_delta_checked'] <= 50
            or proof.get('review_count') != len(batch.get('review_required') or [])
            or _review_urls(batch) is None):
        return False
    try:
        from .pilot_azalea import trusted_event_url
        if (proof['listing_count'] != len(listings)
                or proof['detail_count'] != len(details)
                or proof['included_count'] != len(batch['events'])):
            return False
        by_url = {item['url']: item for item in listings}
        checked = {item['url']: item['disposition'] for item in details}
        if (len(by_url) != len(listings) or len(checked) != len(details)
                or set(by_url) != set(checked)):
            return False
        if sum(page['new_urls'] for page in pages) != len(listings):
            return False
        for index, page in enumerate(pages, start=1):
            expected = ('https://www.azalea.it/eventi/' if index == 1 else
                        f'https://www.azalea.it/eventi/page/{index}/')
            if (page['url'] != expected or not isinstance(page['cards'], int)
                    or not 1 <= page['cards'] <= 100
                    or not isinstance(page['new_urls'], int)
                    or not 0 <= page['new_urls'] <= page['cards']):
                return False
        if pages[0]['new_urls'] != pages[0]['cards']:
            return False
        included = set()
        reviewed = _review_urls(batch)
        if reviewed != {url for url, status in checked.items()
                        if status == 'review_required'}:
            return False
        for url, item in by_url.items():
            if not trusted_event_url(url) or not item['title'] or not item['city']:
                return False
            day = date.fromisoformat(item['date'])
            town = engine.fvg_municipality_catalog.match_names(item['city'])
            disposition = checked[url]
            if disposition == 'included':
                if day < today or not town:
                    return False
                included.add(url)
            elif disposition == 'outside_region':
                if day < today or town:
                    return False
            elif disposition == 'past':
                if day >= today:
                    return False
            elif disposition == 'review_required':
                pass
            else:
                return False
        events = batch['events']
        if (len(events) != len(included) or {event['url'] for event in events} != included
                or events != sorted(events, key=lambda event: (
                    event['start_date'], event.get('time') or '',
                    event['event_city'], event['title']))):
            return False
        for event in events:
            item = by_url[event['url']]
            image = event.get('image')
            parsed_image = urlsplit(image or '')
            if (event.get('source') != 'Azalea'
                    or event.get('start_date') != item['date']
                    or event.get('end_date') != item['date']
                    or engine.normalize_for_search(event.get('event_city'))
                    != engine.normalize_for_search(item['city'])
                    or (image and (parsed_image.scheme != 'https'
                                   or parsed_image.hostname != 'www.azalea.it'
                                   or not parsed_image.path.startswith('/wp-content/uploads/')))):
                return False
            if event.get('description_excerpt') and (
                    event.get('description_source_name') != 'Azalea'
                    or event.get('description_source_url') != event['url']
                    or not event.get('description_checked_at')):
                return False
        previous = (previous_batch or {}).get('verification') or {}
        if previous.get('collection_mode') == proof['collection_mode']:
            new_keys = {(engine.normalize_for_search(item['title']),
                         engine.normalize_for_search(item['city']), item['date'])
                        for item in listings}
            for prior in previous.get('listing_records') or []:
                if (date.fromisoformat(prior['date']) >= today
                        and engine.fvg_municipality_catalog.match_names(prior['city'])
                        and prior['url'] not in by_url
                        and (engine.normalize_for_search(prior['title']),
                             engine.normalize_for_search(prior['city']),
                             prior['date']) not in new_keys):
                    return False
        return True
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def _css_retention_key(event):
    """Recognize a renamed official page only within its season and location."""
    from .pilot_css import SEASON_PATHS, trusted_event_url

    url = event.get('url')
    if not isinstance(url, str) or not trusted_event_url(url):
        return None
    parsed = urlsplit(url)
    identity = re.fullmatch(
        r'/(stagione-[a-z-]+)/(20[0-9]{2})/([1-9][0-9]*)/[a-z0-9]+(?:-[a-z0-9]+)*',
        parsed.path)
    if (url != 'https://www.cssudine.it' + parsed.path
            or not identity or identity[1] not in SEASON_PATHS
            or event.get('source') != 'CSS Udine'):
        return None
    location = (event.get('event_city'), event.get('venue'))
    if any(not isinstance(value, str) or not value.strip() for value in location):
        return None
    return (identity.groups() + (event['start_date'],)
            + tuple(' '.join(value.split()).casefold() for value in location))


def css_batch_verified(batch, *, today, previous_batch=None):
    """Reconcile all six CSS season indexes with their detail dispositions."""
    proof = batch.get('verification') or {}
    pages = proof.get('surface_counts')
    listings = proof.get('listing_records')
    details = proof.get('detail_records')
    if (proof.get('collection_mode') != 'complete-css-current-season-indexes'
            or proof.get('source_complete') is not True
            or not isinstance(pages, list) or len(pages) != 6
            or not isinstance(listings, list) or not 1 <= len(listings) <= 250
            or not isinstance(details, list) or len(details) != len(listings)
            or proof.get('review_count') != len(batch.get('review_required') or [])
            or _review_urls(batch) is None):
        return False
    try:
        from .pilot_css import BASE, SEASON_PATHS, trusted_event_url
        if (proof['listing_count'] != len(listings)
                or proof['detail_count'] != len(details)
                or proof['event_count'] != len(batch['events'])
                or proof['excluded_count'] != len(batch['excluded'])):
            return False
        if sum(page['new_urls'] for page in pages) != len(listings):
            return False
        for path, page in zip(SEASON_PATHS, pages):
            expected = BASE + path
            if (page['url'] != expected or not isinstance(page['cards'], int)
                    or not 1 <= page['cards'] <= 250
                    or not isinstance(page['new_urls'], int)
                    or not 0 <= page['new_urls'] <= page['cards']):
                return False
        listed = {item['url']: item for item in listings}
        checked = {item['url']: item['disposition'] for item in details}
        if (len(listed) != len(listings) or len(checked) != len(details)
                or set(listed) != set(checked)):
            return False
        allowed_exclusions = {'past', 'season_umbrella', 'dates_not_defined',
                              'municipality_not_fixed'}
        reviewed = _review_urls(batch)
        if reviewed != {url for url, status in checked.items()
                        if status == 'review_required'}:
            return False
        included = {url for url, disposition in checked.items()
                    if disposition == 'included'}
        if (proof['included_detail_urls'] != len(included)
                or len(batch['excluded']) != len(listings) - len(included) - len(reviewed)
                or {item['url'] for item in batch['excluded']}
                   != set(listed) - included - reviewed):
            return False
        for url, item in listed.items():
            if (not trusted_event_url(url) or not item['title']
                    or not item['schedule'] or not item['venue']
                    or checked[url] not in allowed_exclusions | {'included', 'review_required'}):
                return False
        for item in batch['excluded']:
            if item['reason'] != checked[item['url']]:
                return False
        events = batch['events']
        if ({event['url'] for event in events} != included
                or events != sorted(events, key=lambda event: (
                    event['start_date'], event.get('time') or '',
                    event['event_city'], event['title'], event['url']))):
            return False
        for event in events:
            image = urlsplit(event.get('image') or '')
            if (event.get('source') != 'CSS Udine'
                    or event['url'] not in included
                    or image.scheme != 'https' or image.hostname != 'www.cssudine.it'
                    or not image.path.startswith('/media/spettacoli/')
                    or event.get('description_source_name') != 'CSS Udine'
                    or event.get('description_source_url') != event['url']
                    or not event.get('description_excerpt')
                    or event['description_excerpt'].casefold().startswith((
                        'iscriviti al servizio newsletter',
                        'ricerca tra tutti gli spettacoli',
                        'ricerca tramite google',
                        'css teatro stabile di innovazione',
                        'il sito utilizza cookie'))
                    or not event.get('description_checked_at')):
                return False
        previous = (previous_batch or {}).get('events') or []
        new_exact = {(event['url'], event['start_date'],
                      engine.normalize_for_search(event['event_city']))
                     for event in events}
        new_keys = {(engine.normalize_for_search(event['title']),
                     event['start_date'], engine.normalize_for_search(event['event_city']))
                    for event in events}
        new_identities = {_css_retention_key(event) for event in events} - {None}
        for old in previous:
            if (date.fromisoformat(old['start_date']) >= today
                    and old['url'] not in reviewed
                    and (old['url'], old['start_date'],
                         engine.normalize_for_search(old['event_city'])) not in new_exact
                    and (engine.normalize_for_search(old['title']),
                         old['start_date'],
                         engine.normalize_for_search(old['event_city'])) not in new_keys
                    and _css_retention_key(old) not in new_identities):
                return False
        return True
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def pnpensa_batch_verified(batch, *, today, previous_batch=None):
    """Require every WordPress post to match the official sitemap and a disposition."""
    proof = batch.get('verification') or {}
    posts = proof.get('post_records')
    pages = proof.get('page_records')
    details = proof.get('detail_records')
    if (proof.get('collection_mode') != 'complete-pnpensa-post-api-and-sitemap'
            or proof.get('source_complete') is not True
            or not isinstance(posts, list) or not posts
            or not isinstance(pages, list) or not pages
            or not isinstance(details, list) or len(details) != len(posts)
            or proof.get('review_count') != len(batch.get('review_required') or [])
            or _review_urls(batch) is None):
        return False
    try:
        from .pilot_pnpensa import trusted_page_url, trusted_post_url

        if (proof['post_count'] != len(posts)
                or proof['sitemap_count'] != len(posts)
                or proof['page_count'] != len(pages)
                or proof['page_sitemap_count'] != len(pages)
                or proof['event_count'] != len(batch['events'])):
            return False
        ids = {post['id'] for post in posts}
        urls = {post['url'] for post in posts}
        page_ids = {page['id'] for page in pages}
        page_urls = {page['url'] for page in pages}
        checked = {item['url']: item['disposition'] for item in details}
        if (len(ids) != len(posts) or len(urls) != len(posts)
                or len(page_ids) != len(pages) or len(page_urls) != len(pages)
                or any(not trusted_page_url(url) for url in page_urls)
                or len(checked) != len(posts) or set(checked) != urls
                or any(not trusted_post_url(url) for url in urls)
                or any(value not in {'included', 'past', 'no_defined_event_date',
                                     'review_required'}
                       for value in checked.values())):
            return False
        reviewed = _review_urls(batch)
        if reviewed != ({url for url, status in checked.items()
                         if status == 'review_required'}
                        | (reviewed & page_urls)):
            return False
        included = {url for url, value in checked.items() if value == 'included'}
        events = batch['events']
        if ({event['url'] for event in events} != included
                or events != sorted(events, key=lambda item: (
                    item['start_date'], item.get('time') or '',
                    item['event_city'], item['title'], item['url']))):
            return False
        for event in events:
            image = urlsplit(event.get('image') or '')
            if (event.get('source') != 'Pordenone Pensa'
                    or event['start_date'] < today.isoformat()
                    or not engine.fvg_municipality_catalog.match_names(event['event_city'])
                    or not event.get('description_excerpt')
                    or event.get('description_source_name') != 'Pordenone Pensa'
                    or event.get('description_source_url') != event['url']
                    or not event.get('description_checked_at')
                    or (event.get('image') and (
                        image.scheme != 'https' or image.hostname != 'www.pnpensa.it'
                        or not image.path.startswith('/wp-content/uploads/')))):
                return False
        previous = (previous_batch or {}).get('events') or []
        new_keys = {(event['url'], event['start_date'], event['event_city'])
                    for event in events}
        for old in previous:
            if (date.fromisoformat(old['start_date']) >= today
                    and old['url'] not in reviewed
                    and (old['url'], old['start_date'], old['event_city']) not in new_keys):
                return False
        return True
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def verdi_pordenone_batch_verified(batch, *, today, previous_batch=None):
    """Reconcile current list pages, recent sitemap and every detail."""
    proof = batch.get('verification') or {}
    pages = proof.get('listing_pages')
    listed = proof.get('listing_urls')
    recent = proof.get('recent_sitemap_urls')
    season_urls = proof.get('season_api_urls')
    season_terms = proof.get('season_term_ids')
    details = proof.get('detail_records')
    if (proof.get('collection_mode') != 'complete-verdi-pordenone-current-list-and-sitemap'
            or proof.get('source_complete') is not True
            or not isinstance(pages, list) or not 1 <= len(pages) <= 10
            or not isinstance(listed, list) or not 1 <= len(listed) <= 150
            or not isinstance(recent, list) or not 1 <= len(recent) <= 1000
            or not isinstance(season_urls, list)
            or not isinstance(season_terms, list) or not 1 <= len(season_terms) <= 3
            or not isinstance(details, list) or not details
            or proof.get('review_count') != len(batch.get('review_required') or [])
            or _review_urls(batch) is None):
        return False
    try:
        from .pilot_verdi_pordenone import BASE

        expected_pages = {BASE + '/la-stagione/'} | {
            BASE + f'/la-stagione/page/{number}/'
            for number in range(2, len(pages) + 1)}
        if ({page['url'] for page in pages} != expected_pages
                or any(not 1 <= page['links'] <= 12 for page in pages)
                or sum(page['links'] for page in pages) != len(listed)
                or proof['listing_count'] != len(listed)
                or proof['season_api_count'] != len(listed)
                or season_urls != listed
                or season_terms != sorted(set(season_terms))
                or any(not isinstance(term, int) or term <= 0 for term in season_terms)
                or proof['recent_sitemap_count'] != len(recent)
                or proof['archive_sitemap_count'] != 1000
                or proof['archive_changed_unlisted'] != 0
                or proof['detail_count'] != len(details)
                or proof['event_count'] != len(batch['events'])
                or listed != sorted(set(listed))
                or recent != sorted(set(recent))):
            return False
        all_urls = set(recent) | set(listed)
        checked = {item['url']: item['disposition'] for item in details}
        if (len(checked) != len(details) or set(checked) != all_urls
                or any(not re.fullmatch(
                    r'https://teatroverdipordenone\.it/spettacolo/[^/]+/', url)
                    for url in all_urls)
                or any(value not in {'included', 'past', 'review_required'}
                       for value in checked.values())
                or any(url not in listed for url, status in checked.items()
                       if status == 'included')):
            return False
        included = {url for url, value in checked.items() if value == 'included'}
        reviewed = _review_urls(batch)
        if reviewed != {url for url, value in checked.items()
                        if value == 'review_required'}:
            return False
        events = batch['events']
        if ({event['url'] for event in events} != included
                or events != sorted(events, key=lambda item: (
                    item['start_date'], item.get('time') or '',
                    item['event_city'], item['title'], item['url']))):
            return False
        for event in events:
            image = urlsplit(event.get('image') or '')
            if (event.get('source') != 'Teatro Verdi Pordenone'
                    or event['event_city'] != 'Pordenone'
                    or event['start_date'] < today.isoformat()
                    or image.scheme != 'https'
                    or image.hostname != 'teatroverdipordenone.it'
                    or not image.path.startswith('/wp-content/uploads/')
                    or event.get('description_source_name') != 'Teatro Verdi Pordenone'
                    or event.get('description_source_url') != event['url']
                    or not event.get('description_excerpt')
                    or not event.get('description_checked_at')):
                return False
        new_keys = {(event['url'], event['start_date'], event.get('time'),
                     event['event_city']) for event in events}
        for old in (previous_batch or {}).get('events') or []:
            if (date.fromisoformat(old['start_date']) >= today
                    and old['url'] not in reviewed
                    and (old['url'], old['start_date'], old.get('time'),
                         old['event_city']) not in new_keys):
                return False
        return True
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def verdi_trieste_batch_verified(batch, *, today, previous_batch=None):
    """Require season API, public calendar, sitemap and detail dates to agree."""
    proof = batch.get('verification') or {}
    listed = proof.get('calendar_urls')
    calendar = proof.get('calendar_records')
    season = proof.get('season_api_urls')
    terms = proof.get('season_term_ids')
    details = proof.get('detail_records')
    if (proof.get('collection_mode') != 'complete-verdi-trieste-season-api-calendar-details'
            or proof.get('source_complete') is not True
            or not isinstance(listed, list) or not 1 <= len(listed) <= 100
            or not isinstance(calendar, list) or len(calendar) != len(listed)
            or not isinstance(season, list) or not 1 <= len(season) <= 300
            or not isinstance(terms, list) or not 1 <= len(terms) <= 3
            or not isinstance(details, list) or not details
            or proof.get('review_count') != len(batch.get('review_required') or [])
            or _review_urls(batch) is None):
        return False
    try:
        if (listed != sorted(set(listed)) or season != sorted(set(season))
                or terms != sorted(set(terms))
                or any(not isinstance(term, int) or term <= 0 for term in terms)
                or proof['calendar_count'] != len(listed)
                or proof['season_api_count'] != len(season)
                or not 446 <= proof['sitemap_count'] <= 1000
                or proof['changed_unlisted_count'] != 0
                or proof['detail_count'] != len(details)
                or proof['event_count'] != len(batch['events'])):
            return False
        all_urls = set(listed) | set(season)
        if (any(not re.fullmatch(
                r'https://www\.teatroverdi-trieste\.com/it/spettacoli/[^/]+/', url)
                for url in all_urls)
                or {row['url'] for row in calendar} != set(listed)
                or {row['url'] for row in details} != all_urls
                or len({row['url'] for row in details}) != len(details)):
            return False
        detail_by_url = {row['url']: row for row in details}
        for row in calendar:
            dates = row['future_dates']
            if (not isinstance(dates, list) or dates != sorted(set(dates))
                    or (detail_by_url[row['url']]['disposition'] != 'review_required'
                        and dates != detail_by_url[row['url']]['future_dates'])):
                return False
        reviewed = _review_urls(batch)
        if reviewed != {row['url'] for row in details
                        if row['disposition'] == 'review_required'}:
            return False
        events = batch['events']
        if events != sorted(events, key=lambda item: (
                item['start_date'], item.get('time') or '', item['event_city'],
                item['title'], item['url'])):
            return False
        for row in details:
            url = row['url']
            matching = [event for event in events if event['url'] == url]
            dates = sorted({event['start_date'] for event in matching})
            if row['disposition'] == 'review_required':
                if row['future_dates'] or row['future_slot_count'] or matching:
                    return False
                continue
            if (row['disposition'] not in {'included', 'past'}
                    or row['future_dates'] != dates
                    or row['future_slot_count'] != len(matching)
                    or (row['disposition'] == 'included') != bool(matching)):
                return False
        seen = set()
        seen_dates = set()
        for event in events:
            image = urlsplit(event.get('image') or '')
            key = (event['url'], event['start_date'], event.get('time'))
            if (key in seen or event.get('source') != 'Teatro Verdi Trieste'
                    or event['event_city'] != 'Trieste'
                    or event['start_date'] < today.isoformat()
                    or not event.get('time')
                    or image.scheme != 'https'
                    or image.hostname != 'www.teatroverdi-trieste.com'
                    or not image.path.startswith('/wp-content/uploads/')
                    or (event.get('description_excerpt') and (
                        event.get('description_source_name') != 'Teatro Verdi Trieste'
                        or event.get('description_source_url') != event['url']
                        or not event.get('description_checked_at')))):
                return False
            seen.add(key)
            seen_dates.add((event['url'], event['start_date']))
        for old in (previous_batch or {}).get('events') or []:
            key = (old['url'], old['start_date'], old.get('time'))
            if (old['start_date'] >= today.isoformat()
                    and old['url'] not in reviewed
                    and (key not in seen if old.get('time') else
                         (old['url'], old['start_date']) not in seen_dates)):
                return False
        return True
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def villa_manin_batch_verified(batch, *, today, previous_batch=None):
    proof = batch.get('verification') or {}
    keys = ('records_scanned', 'api_pages', 'year_archive_pages',
            'year_archive_count', 'calendar_cards', 'historical_card_conflicts',
            'active_records', 'inactive_records', 'rejected_records',
            'rejected_past_cards', 'rejected_outside_current_surfaces',
            'rejected_review_count',
            'review_count', 'detail_pages_checked', 'detail_verified_count',
            'active_review_count',
            'projected_count')
    if (proof.get('collection_mode') != 'complete-villa-manin-api-calendar-year-archive'
            or proof.get('source_complete') is not True
            or any(not isinstance(proof.get(key), int) or isinstance(proof[key], bool)
                   or proof[key] < 0 for key in keys)):
        return False
    events = batch.get('events')
    if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
        return False
    previous_events = (previous_batch or {}).get('events', [])
    if not isinstance(previous_events, list):
        return False
    reviewed = _review_urls(batch)
    if reviewed is None or proof['review_count'] != len(reviewed):
        return False
    current_keys = {(event.get('url'), event.get('start_date')) for event in events}
    for old in previous_events:
        if not isinstance(old, dict):
            return False
        if (old.get('end_date', old.get('start_date', '')) >= today.isoformat()
                and old.get('url') not in reviewed) and (
                old.get('url'), old.get('start_date')) not in current_keys:
            return False
    from .sources.villa_manin import is_trusted_villa_manin_event_url, is_trusted_villa_manin_image_url
    return (1 <= proof['records_scanned'] <= 2000
            and proof['api_pages'] == (proof['records_scanned'] + 99) // 100
            and 1 <= proof['year_archive_pages'] <= 20
            and 1 <= proof['year_archive_count'] <= proof['records_scanned']
            and 1 <= proof['calendar_cards'] <= proof['records_scanned']
            and proof['historical_card_conflicts'] <= proof['calendar_cards']
            and proof['records_scanned'] == proof['active_records']
                + proof['inactive_records'] + proof['rejected_records']
            and proof['rejected_records'] == proof['rejected_past_cards']
                + proof['rejected_outside_current_surfaces'] + proof['rejected_review_count']
            and proof['rejected_review_count'] <= proof['review_count']
            and proof['review_count'] == len(batch.get('review_required') or [])
            and proof['active_records'] == proof['detail_verified_count']
                + proof['active_review_count']
            and proof['detail_verified_count'] <= proof['detail_pages_checked']
                <= proof['active_records']
            and proof['projected_count'] == len(events)
            and proof['detail_verified_count'] <= len(events)
            and not reviewed & {event.get('url') for event in events}
            and all(isinstance(url, str) and
                    is_trusted_villa_manin_event_url(url) for url in reviewed)
            and len(current_keys) == len(events)
            and all(event.get('source') == 'Villa Manin'
                    and event.get('event_city') == 'Codroipo'
                    and event.get('venue') == 'Villa Manin'
                    and is_trusted_villa_manin_event_url(event.get('url'))
                    and (not event.get('image') or is_trusted_villa_manin_image_url(event['image']))
                    and (not event.get('description_excerpt') or (
                        event.get('description_source_name') == 'Villa Manin'
                        and event.get('description_source_url') == event['url']))
                    for event in events))


def magazzino_batch_verified(batch, *, today, previous_batch=None):
    proof = batch.get('verification') or {}
    keys = ('records_scanned', 'api_pages', 'sitemap_entries', 'sitemap_unique',
            'year_archive_count', 'event_list_pages', 'event_list_urls',
            'exhibition_urls', 'exhibition_dates_checked',
            'current_past', 'archived', 'active_count',
            'detail_count', 'review_count')
    if (proof.get('collection_mode') != 'complete-magazzino-api-sitemap-and-public-lists'
            or proof.get('source_complete') is not True
            or any(not isinstance(proof.get(key), int) or isinstance(proof[key], bool)
                   or proof[key] < 0 for key in keys)):
        return False
    events = batch.get('events')
    previous = (previous_batch or {}).get('events', [])
    if not isinstance(events, list) or not isinstance(previous, list):
        return False
    reviewed = _review_urls(batch)
    if reviewed is None or proof['review_count'] != len(reviewed):
        return False
    current_keys = {(event.get('url'), event.get('start_date')) for event in events
                    if isinstance(event, dict)}
    if len(current_keys) != len(events):
        return False
    for old in previous:
        if not isinstance(old, dict):
            return False
        if (old.get('end_date', old.get('start_date', '')) >= today.isoformat()
                and old.get('url') not in reviewed) and (
                old.get('url'), old.get('start_date')) not in current_keys:
            return False
    from .pilot_magazzino import event_url, image_url
    return (1 <= proof['records_scanned'] <= 2000
            and proof['api_pages'] == (proof['records_scanned'] + 99) // 100
            and proof['sitemap_unique'] == proof['records_scanned']
            and proof['sitemap_entries'] >= proof['sitemap_unique']
            and 1 <= proof['year_archive_count'] <= proof['records_scanned']
            and 1 <= proof['event_list_pages'] <= 10
            and 1 <= proof['event_list_urls'] <= proof['records_scanned']
            and 1 <= proof['exhibition_urls'] <= proof['records_scanned']
            and proof['exhibition_dates_checked'] <= proof['active_count']
                + proof['review_count']
            and proof['records_scanned'] == proof['archived']
                + proof['current_past'] + proof['active_count']
                + proof['review_count']
            and proof['active_count'] == proof['detail_count'] == len(events)
            and proof['review_count'] == len(batch.get('review_required') or [])
            and reviewed is not None
            and not reviewed & {event.get('url') for event in events}
            and all(event_url(url) == url for url in reviewed)
            and all(isinstance(event, dict)
                    and event.get('source') == 'Magazzino delle Idee'
                    and event.get('event_city') == 'Trieste'
                    and event.get('venue') == 'Magazzino delle Idee'
                    and event_url(event.get('url')) == event.get('url')
                    and (not event.get('image') or image_url(event['image']) == event['image'])
                    and (not event.get('description_excerpt') or (
                        event.get('description_source_name') == 'Magazzino delle Idee'
                        and event.get('description_source_url') == event['url']))
                    for event in events))


def spazzapan_batch_verified(batch, *, today, previous_batch=None):
    """Reconcile each active detail against the complete official inventory."""
    from .pilot_spazzapan import (BASE, SOURCE, EXHIBITION_PAGES, EXPECTED_INVENTORIES,
                                  OCTOBER_28_EVENT, REVIEWED_EXHIBITION_PERIODS,
                                  EXHIBITION_NEWS_IDS, NEWS_EVENTS)
    proof = batch.get('verification') or {}
    events = batch.get('events')
    reviews = batch.get('review_required')
    event_ids = proof.get('event_inventory_ids')
    if (not isinstance(event_ids, list) or any(type(value) is not int for value in event_ids)
            or len(set(event_ids)) != len(event_ids)
            or set(event_ids) not in (EXPECTED_INVENTORIES['events'],
                                     EXPECTED_INVENTORIES['events'] | {OCTOBER_28_EVENT['api_id']})):
        return False
    additional_announced = OCTOBER_28_EVENT['api_id'] in event_ids
    news_event_ids = proof.get('news_event_ids', [])
    if (not isinstance(news_event_ids, list)
            or any(type(value) is not int for value in news_event_ids)
            or len(set(news_event_ids)) != len(news_event_ids)
            or not set(news_event_ids) <= set(NEWS_EVENTS)):
        return False
    current_ids = proof.get('current_exhibition_ids')
    archived = proof.get('archived_exhibitions')
    if (not isinstance(current_ids, list)
            or any(type(value) is not int for value in current_ids)
            or len(set(current_ids)) != len(current_ids)
            or not isinstance(archived, list)
            or any(not isinstance(item, dict) for item in archived)):
        return False
    archived_ids = set()
    paths = {str(value): path for path, value in EXHIBITION_PAGES.items()}
    for item in archived:
        source_id = item.get('source_id')
        if not isinstance(source_id, str) or source_id not in paths:
            return False
        period = REVIEWED_EXHIBITION_PERIODS.get(int(source_id))
        if period is None:
            return False
        start, end, intro = period
        if (source_id in archived_ids or end >= today.isoformat()
                or item.get('url') != BASE + '/it' + paths[source_id]
                or item.get('start_date') != start or item.get('end_date') != end
                or item.get('date_evidence') != intro):
            return False
        archived_ids.add(source_id)
    if ({str(value) for value in current_ids} & archived_ids
            or {str(value) for value in current_ids} | archived_ids != set(paths)):
        return False
    retired_news_ids = proof.get('retired_news_ids')
    if (not isinstance(retired_news_ids, list)
            or any(type(value) is not int for value in retired_news_ids)
            or len(set(retired_news_ids)) != len(retired_news_ids)
            or any(str(EXHIBITION_NEWS_IDS.get(value)) not in archived_ids
                   for value in retired_news_ids)):
        return False
    if (proof.get('collection_mode') != 'reconciled-spazzapan-event-exhibition-news'
            or proof.get('source_complete') is not True
            or proof.get('event_api_count') != len(event_ids)
            or proof.get('event_category_count') != 2 + int(additional_announced)
            or proof.get('current_exhibition_count') != len(current_ids)
            or proof.get('exhibition_count') != 7
            or proof.get('historical_plural_count') != 1
            or not isinstance(proof.get('news_count'), int)
            or proof['news_count'] < 78 - len(retired_news_ids) + (2 if additional_announced else 0) + len(news_event_ids)
            or proof.get('reviewed_2026_news') != 44 - len(retired_news_ids) + (2 if additional_announced else 0) + len(news_event_ids)
            or proof.get('verified_distinct_current') != 4 + int(additional_announced) + len(news_event_ids)
            or not isinstance(events, list)
            or any(not isinstance(event, dict) for event in events)
            or proof.get('projected_count') != len(events)
            or not isinstance(reviews, list)
            or _review_urls(batch) is None
            or not isinstance(proof.get('active_count'), int)
            or not isinstance(proof.get('review_count'), int)
            or proof['review_count'] != len(reviews)
            or proof['active_count'] != len(events) + len(reviews)):
        return False
    expected = {
        '232202': ('/it/fvg7002-eventi-collaterali-di-ottobre-172985',
                   '2026-07-23', '2026-11-29', True),
        '232607': ('/it/fvg7003-sergio-pausig-173388',
                   '2026-09-11', '2026-10-11', True),
        '84819': ('/it/giornata-del-contemporaneo-2026-75485',
                  '2026-10-10', '2026-10-10', True),
        '233611': ('/it/eventi-collaterali-ottobre-174329',
                   '2026-10-14', '2026-10-14', True),
    }
    if additional_announced:
        extra = OCTOBER_28_EVENT
        expected[str(extra['source_id'])] = ('/it' + extra['path'], extra['date'], extra['date'], False)
    for source_id in news_event_ids:
        extra = NEWS_EVENTS[source_id]
        expected[str(source_id)] = ('/it' + extra['path'], extra['date'], extra['date'], True)
    active = {key for key, (_, _, end, _) in expected.items()
              if end >= today.isoformat()}
    included = {str(event.get('source_id')) for event in events}
    reviewed = {str(item.get('source_id')) for item in reviews
                if isinstance(item, dict)}
    if (proof['active_count'] != len(active)
            or len(included) != len(events)
            or len(reviewed) != len(reviews)
            or included & reviewed
            or included | reviewed != active
            or (active and not events)
            or any(not isinstance(item, dict)
                   or str(item.get('source_id')) not in active
                   or item.get('url') != BASE + expected[str(item['source_id'])][0]
                   or item.get('reason') not in {
                       'event_detail_requires_review',
                       'exhibition_detail_requires_review'}
                   or not isinstance(item.get('detail'), str)
                   or not item['detail']
                   for item in reviews)):
        return False
    for event in events:
        path, start, end, needs_excerpt = expected[str(event['source_id'])]
        image = urlsplit(event.get('image') or '')
        if (event.get('source') != SOURCE
                or event.get('url') != BASE + path
                or (event.get('start_date'), event.get('end_date')) != (start, end)
                or event.get('event_city') != "Gradisca d'Isonzo"
                or image.scheme != 'https'
                or image.hostname != 'galleriaspazzapan.regione.fvg.it'
                or not image.path.startswith('/media/files/erpac_spazzapan/previews/')
                or event.get('location_confidence') != 'municipality'
                or validate_candidate(event, today=today)):
            return False
        if needs_excerpt and (not event.get('description_excerpt')
                              or event.get('description_source_name') != SOURCE
                              or event.get('description_source_url') != event['url']
                              or not event.get('description_checked_at')):
            return False
        if (event['source_id'] == '233611'
                and (event.get('time') != '18:00'
                     or len(event.get('description_excerpt') or '') < 80
                     or 'a breve ulteriori dettagli' in
                     event['description_excerpt'].casefold())):
            return False
        if event['source_id'] == str(OCTOBER_28_EVENT['source_id']) and event.get('time') != '18:00':
            return False
        if str(event['source_id']) in {str(key) for key in NEWS_EVENTS}:
            extra = NEWS_EVENTS[int(event['source_id'])]
            if (event.get('time') != extra['time'] or event.get('title') != extra['title']
                    or event.get('venue') != 'Galleria Spazzapan'):
                return False
        if not needs_excerpt and event.get('description_excerpt'):
            return False
    previous = (previous_batch or {}).get('events') or []
    current = {(event['source_id'], event['start_date']) for event in events}
    return all(isinstance(old, dict) and
               (old.get('end_date', '') < today.isoformat() or
                str(old.get('source_id')) in reviewed or
                (old.get('source_id'), old.get('start_date')) in current)
               for old in previous)


def mess_batch_verified(batch, *, today, previous_batch=None):
    """Reconcile every programme slot and the reviewed news inventory."""
    proof = batch.get('verification') or {}
    events = batch.get('events')
    previous = (previous_batch or {}).get('events') or []
    if (proof.get('collection_mode') != 'complete-mess-programme-and-news'
            or proof.get('source_complete') is not True
            or proof.get('declared_laboratories') != 36
            or not isinstance(proof.get('parsed_laboratories'), int)
            or not isinstance(proof.get('reviewed_laboratories'), int)
            or proof['parsed_laboratories'] + proof['reviewed_laboratories'] != 36
            or proof.get('museum_locations') != 18
            or proof.get('two_sessions_per_museum') is not True
            or proof.get('news_category_id') != 18221
            or not isinstance(proof.get('news_records'), int)
            or proof['news_records'] < 51
            or proof.get('reviewed_2026_news') != 24
            or not isinstance(proof.get('unresolved_news'), int)
            or not 0 <= proof['unresolved_news'] <= 3
            or not isinstance(events, list) or not isinstance(previous, list)
            or proof.get('projected_count') != len(events)
            or not isinstance(proof.get('laboratory_count'), int)
            or not 0 <= proof['laboratory_count'] <= 36
            or proof.get('corroborated_exhibitions') !=
               len(events) - proof['laboratory_count']
            or not 0 <= proof['corroborated_exhibitions'] <= 3
            or len(events) > 39
            or _review_urls(batch) is None
            or not isinstance(proof.get('slot_records'), list)
            or len(proof['slot_records']) != 36):
        return False
    from .pilot_programmes import reviewed_programme_metadata
    from .pilot_mess import (PROGRAMME_URL, BASE, REVIEWED_ACTIVE_NEWS,
                             REVIEWED_LABORATORY_SLOTS_2026)

    slots = proof['slot_records']
    active_slots = [item for item in slots
                    if isinstance(item, dict)
                    and isinstance(item.get('date'), str)
                    and item['date'] >= today.isoformat()]
    if (any(not isinstance(item, dict)
            or item.get('slot') != index
            or item.get('date') != day
            or item.get('museum_id') != museum_id
            or not isinstance(item.get('parsed'), bool)
            or item.get('disposition') not in (
                {'past'} if day < today.isoformat()
                else {'included', 'review_required'})
            or (day >= today.isoformat()
                and item['parsed'] != (item['disposition'] == 'included'))
            for index, (item, (day, museum_id)) in enumerate(
                zip(slots, REVIEWED_LABORATORY_SLOTS_2026), 1))
            or sum(item['parsed'] for item in slots)
               != proof['parsed_laboratories']
            or sum(item['disposition'] == 'included' for item in slots)
               != proof['laboratory_count']
            or sum(item['disposition'] == 'review_required' for item in slots)
               != proof.get('active_laboratory_review_count')
            or (active_slots and all(item.get('disposition') == 'review_required'
                                     for item in active_slots))):
        return False
    reviews = batch.get('review_required') or []
    lab_reviews = [item for item in reviews if isinstance(item, dict)
                   and item.get('reason') == 'laboratory_requires_review']
    news_reviews = [item for item in reviews if isinstance(item, dict)
                    and item.get('reason') == 'news_exhibition_requires_review']
    expected_reviews = {
        (PROGRAMME_URL + '#laboratorio-' + str(item['slot']),
         f'mess-laboratori-2026-{item["museum_id"]}-{item["date"]}',
         item['slot'])
        for item in slots if item['disposition'] == 'review_required'}
    if (len(reviews) != len(lab_reviews) + len(news_reviews)
            or len(lab_reviews) != len(expected_reviews)
            or {(item.get('url'), item.get('source_id'), item.get('slot'))
                for item in lab_reviews} != expected_reviews
            or any(not isinstance(item, dict)
                   or item.get('reason') != 'laboratory_requires_review'
                   or not isinstance(item.get('detail'), str)
                   or not item['detail'] for item in lab_reviews)):
        return False
    active_news = {article_id: item for article_id, item in
                   REVIEWED_ACTIVE_NEWS.items()
                   if item['end'] >= today.isoformat()}
    if (not events and (active_news or any(
            item['date'] >= today.isoformat() for item in slots))):
        return False
    expected_news_reviews = {
        (BASE + '/it' + active_news[article_id]['path'],
         f'mess-news-{article_id}') for article_id in active_news}
    if (proof['unresolved_news'] != len(news_reviews)
            or len(news_reviews) != len({item.get('source_id')
                                          for item in news_reviews})
            or any((item.get('url'), item.get('source_id'))
                   not in expected_news_reviews
                   or not isinstance(item.get('detail'), str)
                   or not item['detail'] for item in news_reviews)):
        return False
    seen = set()
    included_slots = set()
    included_news = set()
    laboratories = news = 0
    for event in events:
        if not isinstance(event, dict) or event.get('source') != 'MESS':
            return False
        identity = (event.get('source_id'), event.get('start_date'))
        if identity in seen or validate_candidate(event, today=today):
            return False
        if event.get('mess_content_kind') == 'news_exhibition':
            news += 1
            try:
                article_id = int(event['source_id'].split('-')[-1])
            except (KeyError, TypeError, ValueError):
                return False
            expected = REVIEWED_ACTIVE_NEWS.get(article_id)
            if (not expected or event.get('url') != BASE + '/it' + expected['path']
                    or (event.get('start_date'), event.get('end_date'),
                        event.get('event_city')) != (expected['start'],
                                                     expected['end'], expected['city'])
                    or not str(event.get('image') or '').startswith(
                        BASE + '/media/files/erpac_mess/previews/')
                    or event.get('description_source_name') != 'MESS'
                    or event.get('description_source_url') != event.get('url')
                    or not event.get('description_excerpt')
                    or not event.get('description_checked_at')):
                return False
            included_news.add(article_id)
        else:
            laboratories += 1
            slot = event.get('programme_slot')
            if (not isinstance(slot, int) or not 1 <= slot <= 36
                    or slots[slot - 1]['disposition'] != 'included'
                    or event.get('start_date') != slots[slot - 1]['date']
                    or event.get('source_id') !=
                    f'mess-laboratori-2026-{slots[slot - 1]["museum_id"]}-{slots[slot - 1]["date"]}'
                    or slot in included_slots):
                return False
            included_slots.add(slot)
            if (event.get('url') != PROGRAMME_URL
                or event.get('description_source_name') != 'MESS'
                or event.get('description_source_url') != PROGRAMME_URL
                or not event.get('description_excerpt')
                or not event.get('description_checked_at')
                or reviewed_programme_metadata(event) is None):
                return False
        seen.add(identity)
    if (laboratories != proof['laboratory_count']
            or included_slots != {item['slot'] for item in slots
                                  if item['disposition'] == 'included'}
            or news != proof['corroborated_exhibitions']
            or len(included_news) != news
            or included_news & {int(item['source_id'].split('-')[-1])
                                for item in news_reviews}
            or included_news | {int(item['source_id'].split('-')[-1])
                                for item in news_reviews} != set(active_news)):
        return False
    reviewed_ids = {item['source_id'] for item in reviews}
    for old in previous:
        if (not isinstance(old, dict)
                or old.get('start_date', '') >= today.isoformat()
                and (old.get('source_id'), old.get('start_date')) not in seen
                and old.get('source_id') not in reviewed_ids):
            return False
    return True


def barcolana_batch_verified(batch, *, today, previous_batch=None):
    """Verify the official programme and every still-current regional mirror."""
    proof = batch.get('verification') or {}
    events = batch.get('events') or []
    previous = (previous_batch or {}).get('verification') or {}
    try:
        event, = events
        sessions = event['programme_sessions']
        counts = proof['day_counts']
        scanned = proof['records_scanned']
        parsed = proof['parsed_count']
        duplicate = proof['duplicate_count']
        sitemap_count = proof['sitemap_event_url_count']
        orphan_count = proof['sitemap_known_orphan_count']
        sitemap_lag = proof['sitemap_lag_rows']
        detail_count = proof['detail_url_count']
        mirror_count = proof['regional_piazza_page_count']
        mirror_rows = proof['regional_piazza_row_count']
        museum_rows = proof['regional_museum_row_count']
        talk_rows = proof['regional_talk_row_count']
        supplement_count = proof['regional_supplement_count']
        active_piazza = {url: day for url, day in REGIONAL_PIAZZA_PAGES.items()
                         if day >= today.isoformat()}
        active_periods = {url: period for url, period in REGIONAL_PERIODS.items()
                          if period[1] >= today.isoformat()}
        regional_urls = set(active_piazza) | set(active_periods)
        expected_piazza_supplements = int(
            '2026-10-08' in active_piazza.values())
        expected_disagreements = ([{
            'day': '2026-10-07',
            'title': 'CONCERTO DI MUSICA SACRA SERBO-ORTODOSSA',
            'official_time': '19:30', 'regional_time': '19:00'}]
            if '2026-10-07' in active_piazza.values() else [])
        supplements = [item for item in sessions
                       if item['url'] in regional_urls]
        official_sessions = [item for item in sessions
                             if item['url'] not in regional_urls]
        if not all(isinstance(value, int) and not isinstance(value, bool)
                   for value in (scanned, parsed, duplicate, sitemap_count,
                                 orphan_count, sitemap_lag, detail_count, mirror_count,
                                 mirror_rows, museum_rows, talk_rows,
                                 supplement_count, *counts.values())):
            return False
        if (proof.get('collection_mode') != 'complete-official-html-calendar'
                or proof.get('as_of_date') != today.isoformat()
                or proof.get('edition_id') != '2026'
                or proof.get('main_start_date') != '2026-10-02'
                or proof.get('main_end_date') != '2026-10-11'
                or scanned < 500 or scanned != parsed + duplicate
                or scanned != sum(counts.values())
                or orphan_count not in {0, 1}
                or sitemap_lag != scanned - (sitemap_count - orphan_count)
                or sitemap_lag < 0 or sitemap_lag > scanned * .1
                or detail_count < 0 or detail_count > parsed
                or duplicate < 0 or parsed != len(official_sessions)
                or len(sessions) != parsed + supplement_count
                or mirror_count != len(active_piazza)
                or mirror_rows < mirror_count
                or museum_rows < int(REGIONAL_MUSEUM in active_periods)
                or (REGIONAL_MUSEUM not in active_periods and museum_rows != 0)
                or talk_rows != (2 if REGIONAL_TALKS in active_periods else 0)
                or supplement_count != len(supplements)
                or proof.get('regional_piazza_supplement_count') != expected_piazza_supplements
                or sum(item['url'] in active_piazza
                       for item in supplements) != expected_piazza_supplements
                or event.get('regional_mirror_days') != active_piazza
                or event.get('regional_mirror_periods') != active_periods
                or proof.get('regional_piazza_time_disagreements') != expected_disagreements
                or parsed < 450 or len(counts) < 10
                or sorted(counts) != list(counts)
                or any(date.fromisoformat(day).year != 2026 or count < 1
                       for day, count in counts.items())
                or proof.get('first_date') != next(iter(counts))
                or proof.get('last_date') != next(reversed(counts))
                or not {'2026-10-02', '2026-10-11'} <= set(counts)
                or (previous.get('edition_id') == '2026'
                    and scanned < previous.get('records_scanned', 0) * .9)
                or event.get('source') != 'Barcolana'
                or event.get('url') != APPROVED_SOURCES['Barcolana']
                or event.get('title') != 'Barcolana 2026'
                or event.get('event_city') != 'Trieste'
                or event.get('start_date') != proof['first_date']
                or event.get('end_date') != proof['last_date']
                or event.get('occurrences') != list(counts)
                or event.get('display_mode') != 'umbrella'
                or event.get('programme_city') != 'Trieste'
                or not event.get('image')
                or urlsplit(event['image']).scheme != 'https'
                or urlsplit(event['image']).hostname != 'www.barcolana.it'
                or not event.get('description_excerpt')
                or event.get('description_source_name') != 'Barcolana'
                or event.get('description_source_url') != proof.get('image_source_url')
                or batch.get('review_required')):
            return False
        identities = [(item['start_date'], item['title'].casefold(),
                       (item.get('place') or '').casefold(), item.get('time'),
                       item.get('end_time')) for item in sessions]
        detail_urls = [item['url'] for item in official_sessions if item['url'] != event['url']]
        return (len(set(identities)) == len(sessions)
                and len(detail_urls) == detail_count
                and len(detail_urls) == len(set(detail_urls))
                and all(urlsplit(url).scheme == 'https'
                        and urlsplit(url).hostname == 'www.barcolana.it'
                        and urlsplit(url).path.startswith('/it/eventi/')
                        and '/2026/' in urlsplit(url).path
                        for url in detail_urls)
                and all(item['start_date'] in counts and item['url']
                        and item['title'] and not item.get('place') == 'None'
                        for item in sessions)
                and all(item.get('time') and item.get('place') and
                        (item['start_date'] == active_piazza[item['url']]
                         if item['url'] in active_piazza else
                         active_periods[item['url']][0] <= item['start_date']
                         <= active_periods[item['url']][1])
                        for item in supplements)
                and all(not item.get('time') for item in sessions
                        if 'CERIMONIA DI CHIUSURA DEL TOUR MONDIALE VESPUCCI'
                        in item['title'].upper()))
    except (KeyError, TypeError, ValueError, StopIteration):
        return False


def gate_batch(source, batch, *, today, previous_batch=None):
    """Publication gate for every registered pilot source, not just Azalea."""
    if source not in APPROVED_SOURCES or batch.get('status') != 'ok':
        return batch
    if source == 'TurismoFVG' and not turismofvg_batch_verified(
            batch, today=today, previous_batch=previous_batch):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    if source == 'Azalea' and not azalea_batch_verified(
            batch, today=today, previous_batch=previous_batch):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    if source == 'CSS Udine' and not css_batch_verified(
            batch, today=today, previous_batch=previous_batch):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    if source == 'Pordenone Pensa' and not pnpensa_batch_verified(
            batch, today=today, previous_batch=previous_batch):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    if source == 'Teatro Verdi Pordenone' and not verdi_pordenone_batch_verified(
            batch, today=today, previous_batch=previous_batch):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    if source == 'Teatro Verdi Trieste' and not verdi_trieste_batch_verified(
            batch, today=today, previous_batch=previous_batch):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    if source == 'Villa Manin' and not villa_manin_batch_verified(
            batch, today=today, previous_batch=previous_batch):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    if source == 'Magazzino delle Idee' and not magazzino_batch_verified(
            batch, today=today, previous_batch=previous_batch):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    if source == 'MESS' and not mess_batch_verified(
            batch, today=today, previous_batch=previous_batch):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    if source == 'Galleria Spazzapan' and not spazzapan_batch_verified(
            batch, today=today, previous_batch=previous_batch):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    if source == 'Paesi in Festa' and not paesiinfesta_batch_verified(batch, today=today):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    if source == 'SagreFVG' and not sagrefvg_batch_verified(batch, today=today):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    if source == 'Pordenonelegge' and not pordenonelegge_batch_verified(
            batch, previous_batch=previous_batch, today=today):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    if source == 'Le Giornate del Cinema Muto' and not cinema_muto_batch_verified(
            batch, previous_batch=previous_batch):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    if source == 'Barcolana' and not barcolana_batch_verified(
            batch, today=today, previous_batch=previous_batch):
        return {**batch, 'status': 'error', 'error_type': 'source_verification_failed'}
    accepted, review = [], list(batch.get('review_required', []))
    serious_exclusions = 0
    isolated_exclusion = None
    for event in batch.get('events', []):
        reasons = validate_candidate(event, today=today) if isinstance(event, dict) else ['invalid_record']
        if isinstance(event, dict) and event.get('source') != source:
            reasons.append('source_mismatch')
        if reasons:
            if reasons != ['past_event']:
                serious_exclusions += 1
                isolated_exclusion = event if isinstance(event, dict) else None
                review.append({'url': event.get('url') if isinstance(event, dict) else None,
                               'source_id': event.get('source_id') if isinstance(event, dict) else None,
                               'reason': 'publication_gate', 'reasons': sorted(set(reasons))})
        else:
            accepted.append(event)
    strict_source = source in {'TurismoFVG', 'Azalea', 'CSS Udine', 'Villa Manin',
                               'Magazzino delle Idee', 'MESS',
                               'Galleria Spazzapan',
                               'Paesi in Festa', 'SagreFVG',
                               'Pordenonelegge', 'Le Giornate del Cinema Muto',
                               'Barcolana'}
    partial = bool(review)
    # Source-specific inventory verification already passed. One identifiable
    # malformed card can be quarantined without concealing a parser-wide loss.
    # Multiple unexpected exclusions or an empty accepted set remain fatal.
    isolated_url = (isolated_exclusion or {}).get('url')
    isolated_identity = (isolated_exclusion or {}).get('source_id')
    isolated_url_unique = sum(
        isinstance(event, dict) and event.get('url') == isolated_url
        for event in batch.get('events', [])) == 1
    duplicate_review = any(
        isinstance(item, dict) and item.get('url') == isolated_url
        and (not isolated_identity or not item.get('source_id')
             or item.get('source_id') == isolated_identity)
        for item in batch.get('review_required', []))
    safe_single_card = bool(
        serious_exclusions == 1 and accepted
        and isinstance(isolated_url, str) and isolated_url
        and urlsplit(isolated_url).scheme == 'https'
        and urlsplit(isolated_url).hostname
            == urlsplit(APPROVED_SOURCES[source]).hostname
        and (isolated_url_unique or isolated_identity)
        and not duplicate_review
        and isolated_exclusion.get('source') == source)
    strict_failure = bool(strict_source and serious_exclusions and not safe_single_card)
    return {**batch, 'status': ('error' if strict_failure else
                              'partial' if partial else 'ok'),
            'error_type': 'publication_gate_exclusions' if strict_failure else batch.get('error_type'),
            'events': accepted, 'review_required': review,
            'publication_gate': {'input_count': len(batch.get('events', [])), 'accepted_count': len(accepted),
                                 'excluded_count': len(batch.get('events', [])) - len(accepted)}}
