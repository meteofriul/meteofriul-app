import unittest
from copy import deepcopy
from datetime import date, datetime, timedelta

from app.events.pilot_catalog import PILOT_PROJECT, merge_collection, query_catalog
from app.events.pilot_cinema_muto import (
    HOME, SITEMAP, WEEKDAYS, collect_cinema_muto, edition_cover, parse_day, parse_home,
    parse_sitemap,
)
from app.events.pilot_programmes import (
    CINEMA_MUTO_TURISMO_2026, annotate_reviewed_regional_programme,
    cinema_muto_edition, reviewed_programme_metadata,
)
from app.events.pilot_source_policy import gate_batch


def calendar_url(day):
    return HOME + f"calendario-{day:%d%m%y}/"


def home(year=2027, image=None):
    if image is None:
        image = f"{HOME}wp-content/uploads/{year}/08/COVER-GCM{year}.jpg"
    meta = f'<meta property="og:image" content="{image}">' if image else ""
    return (meta + f"<h3>LE GIORNATE DEL CINEMA MUTO 46</h3>"
            f"<h4>PORDENONE 3 | 5 OTTOBRE {year} onsite</h4>")


def sitemap(days):
    return ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + ''.join(f'<url><loc>{calendar_url(day)}</loc></url>' for day in days)
            + '</urlset>')


def daily(day, *, extra="", venue=""):
    heading = f"CALENDARIO {WEEKDAYS[day.weekday()]} {day.day} OTTOBRE"
    if venue:
        slot = (f'<p><strong>20:45</strong> - {venue}</p>'
                '<p>Evento di pre-apertura - Ingresso gratuito con prenotazione obbligatoria</p>'
                '<p>FOR HEAVEN’S SAKE (US 1926)</p>')
    else:
        slot = '<p><strong>09:00</strong> - ORIGINI / EARLY CINEMA<br>THE WOODEN LEG</p>'
    return (f'<title>Le Giornate del Cinema Muto | Calendario {day.year}</title>'
            f'<h1>{heading}</h1>'
            f'<div class="siteorigin-widget-tinymce textwidget"><p>{heading}</p></div>'
            f'<div class="siteorigin-widget-tinymce textwidget">{slot}</div>{extra}')


class FakeResponse:
    status_code = 200

    def __init__(self, body):
        self.body = body.encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, _):
        yield self.body


class CinemaMutoTests(unittest.TestCase):
    def fixture(self):
        days = [date(2027, 10, 2) + timedelta(days=index) for index in range(5)]
        pages = {HOME: home(), SITEMAP: sitemap(days)}
        pages.update({calendar_url(day): daily(day, venue='Teatro Zancanaro Sacile'
                         if day == days[0] else '') for day in days})
        calls = []

        def get(url, **_):
            calls.append(url)
            return FakeResponse(pages[url])

        return days, pages, calls, get

    def test_sitemap_to_calendar_to_single_card(self):
        days, _, calls, get = self.fixture()
        batch = collect_cinema_muto(get=get)
        self.assertEqual(calls, [HOME, SITEMAP, *(calendar_url(day) for day in days)])
        self.assertEqual(batch['verification']['sitemap_page_count'], 5)
        self.assertEqual(batch['verification']['records_scanned'], 10)
        self.assertEqual(batch['verification']['parsed_count'], 5)
        self.assertEqual(batch['events'][0]['event_city'], 'Sacile')
        self.assertEqual(batch['events'][0]['image'],
                         f'{HOME}wp-content/uploads/2027/08/COVER-GCM2027.jpg')
        self.assertEqual(batch['events'][0]['title'], 'FOR HEAVEN’S SAKE (US 1926)')
        self.assertIn('prenotazione obbligatoria', batch['events'][0]['access_notes'])
        self.assertEqual(batch['events'][1]['event_city'], 'Pordenone')
        self.assertEqual(batch['events'][1]['title'], 'ORIGINI / EARLY CINEMA')
        gated = gate_batch('Le Giornate del Cinema Muto', batch, today=days[1])
        self.assertEqual(gated['status'], 'ok')
        self.assertEqual(len(gated['events']), 4)
        catalog = merge_collection(PILOT_PROJECT, None,
                                   {'Le Giornate del Cinema Muto': gated},
                                   '2027-10-03T12:00:00Z')
        town = gated['events'][0]
        result = query_catalog(catalog, town['lat'], town['lon'], radius=50,
                               now=datetime.fromisoformat('2027-10-03T12:00:00Z'))
        self.assertEqual(len(result['events']), 1)
        card = result['events'][0]
        self.assertEqual(card['title'], 'Le Giornate del Cinema Muto 2027')
        self.assertEqual(card['active_session_count'], 4)
        self.assertEqual(card['programme_main_start_date'], '2027-10-03')
        self.assertEqual(card['programme_end_date'], '2027-10-06')
        self.assertEqual(len(card['programme_sessions']), 4)
        self.assertEqual(card['image'], batch['events'][0]['image'])

    def test_cover_requires_the_official_current_edition_image(self):
        valid = f'{HOME}wp-content/uploads/2026/08/COVER-YouTube-GCM2026.jpg'
        self.assertEqual(edition_cover(home(2026, valid), year=2026), valid)
        self.assertIsNone(edition_cover(home(2026, ''), year=2026))
        self.assertIsNone(edition_cover(home(2026, valid.replace('2026/08', '2025/08')),
                                        year=2026))
        self.assertIsNone(edition_cover(home(2026, valid.replace('GCM2026', 'GCM2025')),
                                        year=2026))
        self.assertIsNone(edition_cover(home(2026, valid.replace(HOME, 'https://other.example/')),
                                        year=2026))
        self.assertIsNone(edition_cover(home(2026, valid + '?old=1'), year=2026))
        self.assertIsNone(edition_cover(home(2026, valid.replace(HOME, HOME[:-1] + ':8443/')),
                                        year=2026))
        self.assertIsNone(edition_cover(home(2026, valid)
                                        + f'<meta property="og:image" content="{valid}">',
                                        year=2026))

    def test_missing_day_or_extra_date_fails_closed(self):
        days, _, _, _ = self.fixture()
        main_start, main_end = parse_home(home())
        with self.assertRaises(ValueError):
            parse_sitemap(sitemap(days[:2] + days[3:]),
                          main_start=main_start, main_end=main_end)
        with self.assertRaises(ValueError):
            parse_sitemap(sitemap(days + [date(2027, 10, 7)]),
                          main_start=main_start, main_end=main_end)
        dates_2026 = [date(2026, 10, 3) + timedelta(days=index) for index in range(8)]
        with self.assertRaisesRegex(ValueError, 'extra dates missing'):
            parse_sitemap(sitemap(dates_2026),
                          main_start=date(2026, 10, 3), main_end=date(2026, 10, 10))

    def test_day_heading_and_unknown_widget_fail_closed(self):
        day = date(2027, 10, 3)
        metadata = cinema_muto_edition(day, day, day, day)
        with self.assertRaisesRegex(ValueError, 'heading disagrees'):
            parse_day(daily(day).replace('DOMENICA', 'LUNEDÌ'),
                      day=day, url=calendar_url(day), metadata=metadata)
        with self.assertRaisesRegex(ValueError, 'unclassified calendar widget'):
            parse_day(daily(day, extra='<div class="siteorigin-widget-tinymce">Altro</div>'),
                      day=day, url=calendar_url(day), metadata=metadata)

    def test_gate_blocks_lost_slot_and_same_edition_regression(self):
        days, _, _, get = self.fixture()
        batch = collect_cinema_muto(get=get)
        damaged = deepcopy(batch)
        damaged['events'].pop()
        self.assertEqual(gate_batch('Le Giornate del Cinema Muto', damaged,
                                    today=days[1])['error_type'],
                         'source_verification_failed')
        previous = {'verification': {'edition_id': '2027', 'parsed_count': 7,
                                     'start_date': days[0].isoformat(),
                                     'end_date': days[-1].isoformat()}}
        self.assertEqual(gate_batch('Le Giornate del Cinema Muto', batch,
                                    today=days[1], previous_batch=previous)['status'], 'error')
        stale_cover = deepcopy(batch)
        stale_cover['events'][0]['image'] = stale_cover['events'][0]['image'].replace(
            '2027/08', '2026/08')
        self.assertEqual(gate_batch('Le Giornate del Cinema Muto', stale_cover,
                                    today=days[1])['error_type'], 'source_verification_failed')

    def test_exact_regional_card_supplies_preview_without_duplicate(self):
        metadata = cinema_muto_edition(date(2026, 10, 2), date(2026, 10, 11),
                                       date(2026, 10, 3), date(2026, 10, 10))
        regional = annotate_reviewed_regional_programme({
            'source': 'TurismoFVG', 'url': CINEMA_MUTO_TURISMO_2026,
            'title': '45° Le Giornate del Cinema Muto',
            'start_date': '2026-10-03', 'end_date': '2026-10-10',
            'event_city': 'Pordenone', 'place': 'Pordenone',
            'lat': 45.9567, 'lon': 12.6605,
            'description_excerpt': 'Proiezioni e incontri dedicati al cinema muto.',
            'description_source_name': 'TurismoFVG',
            'description_source_url': CINEMA_MUTO_TURISMO_2026,
            'image': 'https://www.turismofvg.it/proxyvfs.axd/ext,full/r301069?v=464509&ext=.jpg',
        })
        self.assertEqual(regional['programme_role'], 'umbrella')
        self.assertIsNone(reviewed_programme_metadata({
            **regional, 'end_date': '2026-10-09', 'programme_id': None}))
        session = {**metadata, 'programme_role': 'session',
                   'source': 'Le Giornate del Cinema Muto',
                   'url': calendar_url(date(2026, 10, 6)),
                   'title': 'Proiezione', 'start_date': '2026-10-06',
                   'end_date': '2026-10-06', 'time': '09:00',
                   'event_city': 'Pordenone', 'place': 'Pordenone',
                   'lat': 45.9567, 'lon': 12.6605,
                   'image': f'{HOME}wp-content/uploads/2026/08/COVER-YouTube-GCM2026.jpg'}
        catalog = merge_collection(PILOT_PROJECT, None,
                                   {'TurismoFVG': {'status': 'ok', 'events': [regional]},
                                    'Le Giornate del Cinema Muto': {'status': 'ok', 'events': [session]}},
                                   '2026-10-06T12:00:00Z')
        result = query_catalog(catalog, 45.9567, 12.6605,
                               now=datetime.fromisoformat('2026-10-06T12:00:00Z'))
        self.assertEqual(len(result['events']), 1)
        card = result['events'][0]
        self.assertEqual(card['active_session_count'], 1)
        self.assertEqual(card['description_excerpt'], regional['description_excerpt'])
        self.assertEqual(card['image'], session['image'])
        self.assertEqual(card['programme_sessions'][0]['url'], session['url'])
        fallback_catalog = merge_collection(PILOT_PROJECT, None,
                                            {'TurismoFVG': {'status': 'ok', 'events': [regional]},
                                             'Le Giornate del Cinema Muto': {
                                                 'status': 'ok', 'events': [{key: value for key, value
                                                                            in session.items() if key != 'image'}]}},
                                            '2026-10-06T12:00:00Z')
        fallback = query_catalog(fallback_catalog, 45.9567, 12.6605,
                                 now=datetime.fromisoformat('2026-10-06T12:00:00Z'))
        self.assertEqual(fallback['events'][0]['image'], regional['image'])


if __name__ == '__main__':
    unittest.main()
