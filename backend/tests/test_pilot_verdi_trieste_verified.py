import copy
import json
import unittest
from datetime import date

from app.events.pilot_source_policy import gate_batch
from app.events.pilot_verdi_trieste import (
    BASE, SEASON_API, SHOW_API, SHOW_SITEMAP, SITEMAP_INDEX, URL,
    collect_verdi_trieste, parse_detail,
)

A = BASE + '/it/spettacoli/prova/'
B = BASE + '/it/spettacoli/extra/'
IMAGE = BASE + '/wp-content/uploads/2026/10/prova.jpg'


def detail(title, slots):
    return ('<meta property="og:image" content="' + IMAGE + '">'
            '<h1>' + title + '</h1>' + ''.join(
                '<div class="spettacolo-date-wrapper">'
                '<span class="spettacolo-ticket-date">' + day + '</span>'
                '<span class="spettacolo-ticket-time">Ore ' + hour + '</span></div>'
                for day, hour in slots) +
            '<main id="spettacolo-content"><p>Un programma musicale dedicato alle opere '
            'di compositori contemporanei e alla loro interpretazione.</p></main>')


class Response:
    status_code = 200

    def __init__(self, body, headers=None):
        self.body = body.encode()
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, _):
        yield self.body


def fixture(*, extra_italian=False):
    show_api = (SHOW_API + '?stagione=295&per_page=100&lang=it'
                '&_fields=id,link,stagione,lang')
    ns = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    index = f'<sitemapindex xmlns="{ns}"><sitemap><loc>{SHOW_SITEMAP}</loc></sitemap></sitemapindex>'
    urls = [A, B] + [BASE + f'/it/spettacoli/passato-{n}/' for n in range(444)]
    urls += [BASE + '/it/spettacoli/',
             BASE + '/en/spettacoli/the-tale-of-aida/',
             BASE + '/en/spettacoli/']
    if extra_italian:
        urls.append(BASE + '/it/spettacoli/nuovo/')
    sitemap = (f'<urlset xmlns="{ns}">' + ''.join(
        f'<url><loc>{url}</loc><lastmod>{"2026-10-07T12:14:50+00:00" if url in urls[-(4 if extra_italian else 3):] else "2026-10-01T00:00:00+00:00"}</lastmod></url>'
        for url in urls) + '</urlset>')
    pages = {
        URL: ('<h2 class="spettacolo-list-title"><a href="' + A + '">Prova</a></h2>'
              '<span class="spettacolo-list-date">14 ottobre 2026</span>'),
        SITEMAP_INDEX: index,
        SHOW_SITEMAP: sitemap,
        SEASON_API: json.dumps([{'id': 295, 'name': '2026/27', 'count': 2}]),
        show_api: json.dumps([{'id': 1, 'link': A, 'stagione': [295], 'lang': 'it'},
                              {'id': 2, 'link': B, 'stagione': [295], 'lang': 'it'}]),
        A: detail('Prova', [('14 Ottobre 2026', '11:00'), ('14 Ottobre 2026', '18:00')]),
        B: detail('Extra', [('1 Novembre 2026', '20:00')]),
    }
    def get(url, **_):
        headers = {'X-WP-Total': '1', 'X-WP-TotalPages': '1'} if url == SEASON_API else (
            {'X-WP-Total': '2', 'X-WP-TotalPages': '1'} if url == show_api else {})
        return Response(pages[url], headers)
    return collect_verdi_trieste(get=get, today=date(2026, 10, 7))


class VerdiTriesteVerifiedTests(unittest.TestCase):
    def test_detail_keeps_two_times_on_same_day(self):
        events, _ = parse_detail(detail('Prova', [
            ('14 Ottobre 2026', '11:00'), ('14 Ottobre 2026', '18:00')]),
            A, today=date(2026, 10, 7))
        self.assertEqual([event['time'] for event in events], ['11:00', '18:00'])
        self.assertTrue(all(event['image'] == IMAGE for event in events))

    def test_past_header_without_ticket_slots(self):
        old = ('<h1>Passato</h1><span class="spettacolo-header-small-title">'
               '<strong>Domenica 20 settembre 2026 ore 18.00</strong></span>')
        events, slots = parse_detail(old, A, today=date(2026, 10, 7))
        self.assertEqual(events, [])
        self.assertEqual(slots[0][0], date(2026, 9, 20))

    def test_current_api_adds_show_absent_from_calendar(self):
        batch = fixture()
        self.assertEqual((batch['verification']['calendar_count'],
                          batch['verification']['season_api_count'],
                          batch['verification']['detail_count'], len(batch['events'])),
                         (1, 2, 2, 3))
        self.assertEqual({event['url'] for event in batch['events']}, {A, B})
        self.assertEqual(gate_batch('Teatro Verdi Trieste', batch,
                                    today=date(2026, 10, 7))['status'], 'ok')
        damaged = copy.deepcopy(batch)
        damaged['verification']['calendar_records'][0]['future_dates'] = []
        self.assertEqual(gate_batch('Teatro Verdi Trieste', damaged,
                                    today=date(2026, 10, 7))['status'], 'error')

    def test_recent_archive_indexes_and_english_pages_are_not_italian_shows(self):
        batch = fixture()
        self.assertEqual(batch['verification']['changed_unlisted_count'], 0)
        self.assertEqual(gate_batch('Teatro Verdi Trieste', batch,
                                    today=date(2026, 10, 7))['status'], 'ok')
        with self.assertRaisesRegex(ValueError, 'outside inventory'):
            fixture(extra_italian=True)

    def test_disappeared_replica_blocks_refresh(self):
        batch = fixture()
        old = copy.deepcopy(batch['events'][0])
        old['time'] = '12:00'
        failed = gate_batch('Teatro Verdi Trieste', batch,
                            today=date(2026, 10, 7), previous_batch={'events': [old]})
        self.assertEqual(failed['error_type'], 'source_verification_failed')

    def test_old_calendar_date_without_time_matches_new_detail(self):
        batch = fixture()
        old = copy.deepcopy(batch['events'][0])
        old.pop('time')
        checked = gate_batch('Teatro Verdi Trieste', batch,
                             today=date(2026, 10, 7), previous_batch={'events': [old]})
        self.assertEqual(checked['status'], 'ok')
