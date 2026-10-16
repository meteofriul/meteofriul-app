import unittest
from datetime import date
from app.events.pilot_azalea import (
    ARCHIVE, SITEMAP, archive_cards, archive_next, collect_azalea, parse_event,
)

HTML = '''<h1>Concerto</h1><div class="single-event-date"><strong>06.09.2026</strong><span>19:00 h</span></div>
<div class="single-event-city"><strong>Codroipo</strong></div><h2>luogo</h2><p>Villa Manin</p>'''


def card(url, title, day, city):
    return f'''<article class="event-archive-card"><a class="card-title-link" href="{url}">{title}</a>
    <span class="event-archive-date">{day}</span><span class="event-archive-city">{city}</span></article>'''


class Response:
    def __init__(self, url, html):
        self.url, self.html, self.status_code = url, html, 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, _):
        yield self.html.encode('utf-8')


class AzaleaTests(unittest.TestCase):
    def parse(self, html=HTML, today=date(2026, 9, 6)):
        return parse_event(html, "https://www.azalea.it/eventi/prova/", today=today)

    def test_explicit_schedule(self):
        event = self.parse()
        self.assertEqual(event["start_date"], "2026-09-06")
        self.assertEqual(event["time"], "19:00")
        self.assertEqual(event["location_confidence"], "municipality")

    def test_article_date_is_not_fallback(self):
        with self.assertRaises(ValueError):
            self.parse(HTML.replace("06.09.2026", "") + '<meta datePublished="2026-08-19">')

    def test_past_hidden(self):
        self.assertIsNone(self.parse(today=date(2026, 9, 7)))

    def test_outside_region_hidden(self):
        self.assertIsNone(self.parse(HTML.replace("Codroipo", "Jesolo")))

    def test_invalid_hour_rejected(self):
        with self.assertRaises(ValueError):
            self.parse(HTML.replace("19:00", "29:00"))

    def test_cancellation_requires_review(self):
        with self.assertRaisesRegex(ValueError, "schedule change"):
            self.parse(HTML + '<div class="single-event-text"><p>Concerto annullato</p></div>')

    def test_detail_supplies_attributed_preview_and_official_image(self):
        html = HTML + '''<div class="single-event-text"><p>Un concerto speciale a Villa Manin.</p></div>
        <meta property="og:image" content="https://www.azalea.it/wp-content/uploads/2026/concerto.jpg">'''
        event = self.parse(html)
        self.assertIn('Un concerto speciale', event['description_excerpt'])
        self.assertEqual(event['description_source_name'], 'Azalea')
        self.assertEqual(event['description_source_url'], event['url'])
        self.assertEqual(event['image'], 'https://www.azalea.it/wp-content/uploads/2026/concerto.jpg')

    def test_listing_detail_mismatch_is_rejected(self):
        listing = {'url': 'https://www.azalea.it/eventi/prova/', 'title': 'Concerto',
                   'date': '2026-09-07', 'city': 'Codroipo'}
        with self.assertRaisesRegex(ValueError, 'disagree'):
            parse_event(HTML, listing['url'], today=date(2026, 9, 6), listing=listing)

    def test_archive_reads_visible_cards_and_ignores_other_links(self):
        url = 'https://www.azalea.it/eventi/prova/'
        html = f'<a href="{url}">ticker</a>' + card(url, 'Concerto', '06.09.2026', 'Codroipo')
        self.assertEqual(len(archive_cards(html)), 1)
        self.assertIsNone(archive_next(html, 1))
        self.assertEqual(archive_next(html +
            '<link rel="next" href="https://www.azalea.it/eventi/page/2/">', 1),
            'https://www.azalea.it/eventi/page/2/')

    def test_collector_stops_after_repeated_ghost_pages(self):
        url = 'https://www.azalea.it/eventi/prova/'
        outside = 'https://www.azalea.it/eventi/jesolo/'
        cards = card(url, 'Concerto', '06.09.2026', 'Codroipo') + card(
            outside, 'Altro', '06.09.2026', 'Jesolo')
        pages = {
            ARCHIVE: cards + '<link rel="next" href="https://www.azalea.it/eventi/page/2/">',
            'https://www.azalea.it/eventi/page/2/': cards +
                '<link rel="next" href="https://www.azalea.it/eventi/page/3/">',
            'https://www.azalea.it/eventi/page/3/': cards +
                '<link rel="next" href="https://www.azalea.it/eventi/page/4/">',
            url: HTML,
            outside: HTML.replace('Codroipo', 'Jesolo').replace('Concerto', 'Altro'),
            SITEMAP: '''<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <url><loc>https://www.azalea.it/eventi/prova/</loc>
                <lastmod>2026-09-01T00:00:00+00:00</lastmod></url>
                <url><loc>https://www.azalea.it/eventi/jesolo/</loc>
                <lastmod>2026-09-01T00:00:00+00:00</lastmod></url></urlset>''',
        }
        fetched = []
        def get(requested, **_):
            fetched.append(requested)
            return Response(requested, pages[requested])
        batch = collect_azalea(get=get, today=date(2026, 9, 6))
        self.assertEqual(len(batch['events']), 1)
        self.assertEqual(batch['verification']['listing_count'], 2)
        self.assertEqual(batch['verification']['detail_count'], 2)
        self.assertEqual(batch['verification']['source_complete'], True)
        self.assertEqual(batch['verification']['sitemap_event_urls'], 2)
        self.assertEqual(batch['verification']['sitemap_unlisted_delta_checked'], 0)
        self.assertEqual(len(batch['verification']['archive_pages']), 3)
        self.assertNotIn('https://www.azalea.it/eventi/page/4/', fetched)

    def test_sitemap_new_unlisted_future_event_blocks_collection(self):
        listed = 'https://www.azalea.it/eventi/prova/'
        hidden = 'https://www.azalea.it/eventi/hidden/'
        pages = {
            ARCHIVE: card(listed, 'Concerto', '06.09.2026', 'Codroipo'),
            listed: HTML,
            hidden: HTML.replace('Concerto', 'Hidden'),
            SITEMAP: f'''<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <url><loc>{listed}</loc><lastmod>2026-09-01T00:00:00+00:00</lastmod></url>
                <url><loc>{hidden}</loc><lastmod>2026-09-02T00:00:00+00:00</lastmod></url>
                </urlset>''',
        }
        with self.assertRaisesRegex(ValueError, 'absent from Azalea archive'):
            collect_azalea(get=lambda url, **_: Response(url, pages[url]),
                           today=date(2026, 9, 6))

    def test_exact_reschedule_evidence_is_needed(self):
        html = HTML.replace('Concerto', 'Concerto rinviato al 2027').replace(
            '06.09.2026', '01.07.2027') + '''<div class="single-event-text">
            <p>Il concerto e stato posticipato nel 2027. Il nuovo calendario delle date
            indica il posticipo del 03.07.2026 al 1 luglio 2027 a Codroipo, Villa Manin.</p></div>'''
        event = self.parse(html)
        self.assertEqual(event['start_date'], '2027-07-01')
        self.assertIn('posticipo', event['description_excerpt'])
        with self.assertRaisesRegex(ValueError, 'schedule change'):
            self.parse(html.replace('1 luglio 2027', '2 luglio 2027'))
