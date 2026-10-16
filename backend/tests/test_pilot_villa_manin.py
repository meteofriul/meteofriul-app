"""Villa Manin publication only follows a reconciled public calendar."""
from datetime import date
import json
import unittest

from app.events.pilot_source_policy import gate_batch
from app.events.pilot_villa_manin import collect_villa_manin, parse_listing_cards


BASE = 'https://www.villamanin.it'
EVENT = BASE + '/evento/famiglie-al-museo/'


class Response:
    status_code = 200

    def __init__(self, body, headers=None):
        self.body = body.encode('utf-8') if isinstance(body, str) else body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def raise_for_status(self):
        return None

    def iter_content(self, *_):
        yield self.body


def record(*, event_url=EVENT, heading='Domenica 11 Ottobre',
           content=None):
    return {
        'id': 28250, 'status': 'publish', 'type': 'evento', 'link': event_url,
        'title': {'rendered': 'Famiglie al Museo'},
        'content': {'rendered': content or (
            f'<h2>{heading}</h2><p>Villa Manin a Codroipo accoglie le famiglie '
            'con laboratori dedicati alla storia e alla vita della villa.</p>')},
        'featured_media': 0, 'modified': '2026-10-01T12:00:00',
        '_embedded': {'wp:term': [[{'name': '2026', 'taxonomy': 'anno'}]]},
    }


def card(url=EVENT, *, start='11 Ottobre 2026', end='11 Ottobre 2026'):
    return (f'<article id="post-28250"><a href="{url}">Famiglie</a>'
            f'<div class="label_from"><h2>{start}</h2></div>'
            f'<div class="label_to"><h2>{end}</h2></div></article>')


def fake_get(row, *, listing=None, archive=None, detail=None):
    sources = {
        BASE + '/eventi/': listing if listing is not None else card(),
        BASE + '/anno/2026/': archive if archive is not None else
            f'<main><a href="{row["link"]}">Famiglie</a></main>',
        row['link']: detail if detail is not None else
            f'<h1>{row["title"]["rendered"]}</h1>{row["content"]["rendered"]}',
    }

    def get(url, **_):
        if '/wp-json/' in url:
            return Response(json.dumps([row]),
                            {'X-WP-Total': '1', 'X-WP-TotalPages': '1'})
        return Response(sources[url])
    return get


class VillaManinPilotTests(unittest.TestCase):
    today = date(2026, 10, 7)

    def test_reconciled_detail_publishes_one_dated_card_with_excerpt(self):
        batch = collect_villa_manin(get=fake_get(record()), today=self.today)
        accepted = gate_batch('Villa Manin', batch, today=self.today)
        self.assertEqual(accepted['status'], 'ok')
        self.assertEqual(batch['verification']['detail_pages_checked'], 1)
        self.assertEqual(len(accepted['events']), 1)
        event = accepted['events'][0]
        self.assertEqual(event['start_date'], '2026-10-11')
        self.assertEqual(event['event_city'], 'Codroipo')
        self.assertTrue(event['description_excerpt'])
        self.assertIsNone(event['image'])

    def test_archive_omission_stops_source(self):
        with self.assertRaisesRegex(ValueError, 'archive/API mismatch'):
            collect_villa_manin(get=fake_get(record(), archive='<main></main>'),
                                today=self.today)

    def test_future_rejected_date_stops_source(self):
        row = record(content='<h2>Prossimamente</h2><p>Villa Manin a Codroipo '
                     'offre laboratori per tutte le famiglie interessate.</p>')
        batch = collect_villa_manin(get=fake_get(row), today=self.today)
        self.assertEqual(batch['status'], 'error')
        self.assertEqual(batch['verification']['review_count'], 1)
        self.assertEqual(batch['events'], [])

    def mixed_rejected_batch(self):
        good = record()
        bad = record(event_url=BASE + '/evento/da-chiarire/', heading='Prossimamente')
        bad['id'] = 28251
        listing = card() + card(bad['link']).replace('post-28250', 'post-28251')
        archive = ''.join(f'<a href="{row["link"]}">Evento</a>' for row in (good, bad))
        get_page = fake_get(good, listing=listing, archive=archive)

        def get(url, **kwargs):
            if '/wp-json/' in url:
                return Response(json.dumps([good, bad]),
                                {'X-WP-Total': '2', 'X-WP-TotalPages': '1'})
            return get_page(url, **kwargs)
        return collect_villa_manin(get=get, today=self.today)

    def test_rejected_current_card_does_not_block_verified_card(self):
        batch = self.mixed_rejected_batch()
        self.assertEqual(batch['status'], 'ok')
        self.assertEqual(len(batch['review_required']), 1)
        accepted = gate_batch('Villa Manin', batch, today=self.today)
        self.assertEqual(accepted['status'], 'partial')
        self.assertEqual([event['url'] for event in accepted['events']], [EVENT])
        self.assertEqual(accepted['review_required'][0]['url'],
                         BASE + '/evento/da-chiarire/')

    def test_rejected_review_count_must_reconcile_with_inventory(self):
        for wrong_count in (0, 2, -1, True):
            with self.subTest(wrong_count=wrong_count):
                batch = self.mixed_rejected_batch()
                batch['verification']['rejected_review_count'] = wrong_count
                self.assertEqual(gate_batch('Villa Manin', batch, today=self.today)['status'],
                                 'error')

    def test_rejected_card_requires_identified_review(self):
        batch = self.mixed_rejected_batch()
        batch['review_required'] = []
        batch['verification']['review_count'] = 0
        self.assertEqual(gate_batch('Villa Manin', batch, today=self.today)['status'], 'error')

    def test_detail_date_disagreement_stops_source(self):
        batch = collect_villa_manin(get=fake_get(
            record(), detail='<h1>Famiglie al Museo</h1><h2>Domenica 12 Ottobre</h2>'),
            today=self.today)
        self.assertEqual(batch['status'], 'error')
        self.assertEqual(batch['review_required'][0]['reason'], 'detail_date_disagreement')

    def test_discrete_occurrences_never_become_a_daily_range(self):
        url = BASE + '/evento/lo-scrigno-del-doge-in-villa-manin/'
        heading = '25.04, 02.06, 20.09, 01.11, 08.12 2026 06.01.2027 dalle 9:00 alle 17:30'
        row = record(event_url=url, heading=heading)
        row['title']['rendered'] = 'Lo scrigno del Doge in Villa Manin'
        listing = card(url, start='25 Aprile 2026', end='6 Gennaio 2027')
        detail = f'<h1>{row["title"]["rendered"]}</h1>{row["content"]["rendered"]}'
        batch = collect_villa_manin(
            get=fake_get(row, listing=listing, detail=detail), today=self.today)
        self.assertEqual(batch['status'], 'ok')
        self.assertEqual([event['start_date'] for event in batch['events']],
                         ['2026-11-01', '2026-12-08', '2027-01-06'])
        self.assertTrue(all(event['start_date'] == event['end_date']
                            for event in batch['events']))

    def test_inverted_dates_on_past_card_are_counted_without_future_event(self):
        row = record(heading='7 Giugno 2026')
        listing = card(start='6 Giugno 2026', end='7 Giugno 2025')
        batch = collect_villa_manin(get=fake_get(
            row, listing=listing,
            detail='<h1>Famiglie al Museo</h1><h2>7 Giugno 2026</h2>'),
            today=self.today)
        self.assertEqual(batch['verification']['historical_card_conflicts'], 1)
        self.assertEqual(batch['verification']['inactive_records'], 1)
        self.assertEqual(batch['events'], [])
        self.assertEqual(gate_batch('Villa Manin', batch, today=self.today)['status'], 'ok')

    def test_previous_future_event_cannot_silently_disappear(self):
        batch = collect_villa_manin(get=fake_get(record()), today=self.today)
        previous = {'events': [{**batch['events'][0],
                                'url': BASE + '/evento/other/',
                                'start_date': '2026-12-01', 'end_date': '2026-12-01'}]}
        self.assertEqual(gate_batch('Villa Manin', batch, today=self.today,
                                    previous_batch=previous)['status'], 'error')

    def test_unknown_card_date_is_not_guessed(self):
        with self.assertRaisesRegex(ValueError, 'calendar date'):
            parse_listing_cards(card(start='Ottobre 2026'))


if __name__ == '__main__':
    unittest.main()
