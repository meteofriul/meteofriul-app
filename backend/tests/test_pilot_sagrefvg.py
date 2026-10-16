import json
import unittest
from datetime import date

from app.events.pilot_sagrefvg import (
    API, SOURCE, annual_window, collect_sagrefvg, event_from_api,
    resolve_municipality, edition_preview_image,
)
from app.events.pilot_source_policy import gate_batch


def row(event_id=1, *, title='San Foca di San Quirino (PN) – Sagra della Madonna del Rosario',
        city='San Foca', lat=46.0603295, lon=12.6941097,
        start='2026-10-01 08:00:00', end='2026-10-11 23:30:00'):
    return {'id': event_id, 'url': f'https://sagrefvg.it/sagre/san-foca-{event_id}/',
            'title': title, 'status': 'publish', 'start_date': start, 'end_date': end,
            'description': '<p>La sagra propone specialità locali e musica nel borgo.</p>',
            'venue': {'city': city, 'country': 'Italy',
                      'geo_lat': lat, 'geo_lng': lon}}


class Response:
    def __init__(self, body):
        self.body, self.url, self.status_code = body, API, 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, _):
        yield json.dumps(self.body).encode('utf-8')


class SagreFvgTests(unittest.TestCase):
    def test_hamlet_parent_province_and_venue_coordinates(self):
        town, locality = resolve_municipality(
            'Ghirano di Prata (PN) – Sagra del Baccalà 2026', {'city': 'Ghirano'})
        self.assertEqual((town.name, locality),
                         ('Prata di Pordenone', 'Ghirano di Prata'))
        event = event_from_api(row())
        self.assertEqual((event['event_city'], event['start_date'], event['end_date']),
                         ('San Quirino', '2026-10-01', '2026-10-11'))
        self.assertEqual(event['title'], 'Sagra della Madonna del Rosario')
        self.assertEqual(event['description_source_url'], event['url'])
        self.assertEqual(event['location_confidence'], 'venue')
        with self.assertRaisesRegex(ValueError, 'municipality conflict'):
            event_from_api(row(city='Pordenone'))
        with self.assertRaisesRegex(ValueError, 'outside municipality'):
            event_from_api(row(lat=45.8, lon=13.0))
        cancelled = row()
        cancelled['description'] = '<p>La festa è stata rinviata a nuova data.</p>'
        with self.assertRaisesRegex(ValueError, 'schedule requires review'):
            event_from_api(cancelled)

    def test_missing_venue_coordinates_use_approximate_municipality(self):
        event = event_from_api(row(lat=None, lon=None))
        self.assertEqual(event['location_confidence'], 'municipality')
        self.assertIsInstance(event['lat'], float)

    def test_card_image_uses_current_edition_landscape_crop(self):
        source = row()
        source['image'] = {'sizes': {'qi_blocks_image_size_landscape': {
            'url': 'https://sagrefvg.it/wp-content/uploads/2026/09/san-foca-1088x650.jpg'}}}
        event = event_from_api(source)
        self.assertEqual(event['image'],
                         'https://sagrefvg.it/wp-content/uploads/2026/09/san-foca-1088x650.jpg')
        source['image']['sizes']['qi_blocks_image_size_landscape']['url'] = (
            'https://sagrefvg.it/wp-content/uploads/2025/09/san-foca-1088x650.jpg')
        self.assertIsNone(event_from_api(source)['image'])
        source['image']['sizes']['qi_blocks_image_size_landscape']['url'] = (
            'https://example.com/wp-content/uploads/2026/09/san-foca-1088x650.jpg')
        self.assertIsNone(edition_preview_image(source, 2026))

    def test_camporosso_locality_uses_verified_tarvisio_parent(self):
        source = row(title='Camporosso (UD) – Festa del Ringraziamento 2026',
                     city='Camporosso in Valcanale', lat=46.5090459, lon=13.5253728,
                     start='2026-10-11 08:00:00', end='2026-10-11 23:30:00')
        event = event_from_api(source)
        self.assertEqual((event['event_city'], event['place'], event['start_date']),
                         ('Tarvisio', 'Camporosso', '2026-10-11'))
        with self.assertRaisesRegex(ValueError, 'province unresolved'):
            event_from_api({**source, 'title': 'Camporosso (TS) – Festa del Ringraziamento 2026'})

    def test_missing_title_province_requires_matching_structured_venue(self):
        source = row(title='San Leonardo di Campolongo/Tapogliano – 2ª Festa del Borgo di San Leonardo',
                     city='Campolongo Tapogliano', lat=None, lon=None,
                     start='2026-10-11 08:00:00', end='2026-10-11 23:30:00')
        source['venue'].update({
            'venue': 'San Leonardo di Campolongo / Tapogliano (UD)',
            'url': 'https://sagrefvg.it/luogo/san-leonardo-di-campolongo-tapogliano-ud/',
            'province': 'Udine', 'stateprovince': 'Udine'})
        event = event_from_api(source)
        self.assertEqual((event['event_city'], event['place'], event['start_date']),
                         ('Campolongo Tapogliano',
                          'San Leonardo di Campolongo/Tapogliano', '2026-10-11'))
        for field, value in (('province', 'Gorizia'),
                             ('venue', 'San Leonardo (UD)'),
                             ('url', 'https://example.com/luogo/san-leonardo-di-campolongo-tapogliano-ud/')):
            changed = {**source, 'venue': {**source['venue'], field: value}}
            with self.assertRaisesRegex(ValueError, 'verified province'):
                event_from_api(changed)
        with self.assertRaisesRegex(ValueError, 'municipality conflict'):
            event_from_api({**source, 'venue': {**source['venue'], 'city': 'San Leonardo'}})

    def test_gonars_text_repairs_truncated_api_end(self):
        source = row(title='Gonars (UD) – Festa d’Autunno 2026',
                     city='Gonars', lat=None, lon=None,
                     start='2026-10-10 09:00:00', end='2026-10-10 23:30:00')
        source['url'] = ('https://sagrefvg.it/sagre/'
                         'gonars-ud-gonars-si-veste-dautunno-duplicate-1-2/')
        source['description'] = ('Il programma si apre sabato 10 ottobre con musica. '
                                 'Domenica 11 ottobre le vie del paese si animano.')
        event = event_from_api(source)
        self.assertEqual((event['start_date'], event['end_date']),
                         ('2026-10-10', '2026-10-11'))
        self.assertIn('programme 10-11 ottobre 2026', event['date_evidence'])
        with self.assertRaisesRegex(ValueError, 'programme/date mismatch'):
            event_from_api({**source, 'description': 'Sabato 10 ottobre musica in paese.'})

    def test_complete_year_and_overflow_are_required_by_gate(self):
        active = row()

        def get(url, *, params, **_):
            year = int(params['start_date'][:4])
            if params['end_date'] == '2099-12-31':
                return Response({'events': [], 'total': 0, 'total_pages': 0})
            records = [active] if year == 2026 else []
            return Response({'events': records, 'total': len(records),
                             'total_pages': 1 if records else 0})

        batch = collect_sagrefvg(get=get, today=date(2026, 10, 6))
        self.assertEqual(batch['status'], 'ok')
        self.assertEqual(len(batch['events']), 1)
        self.assertEqual(gate_batch(SOURCE, batch, today=date(2026, 10, 6))['status'], 'ok')
        batch['verification']['records_scanned'] = 0
        self.assertEqual(gate_batch(SOURCE, batch, today=date(2026, 10, 6))['status'], 'error')

    def test_year_pagination_rejects_missing_record(self):
        first = [row(i) for i in range(1, 51)]
        second = [row(51)]

        def get(url, *, params, **_):
            return Response({'events': first if params['page'] == 1 else second,
                             'total': 51, 'total_pages': 2})

        records, proof = annual_window(get, 2026)
        self.assertEqual((len(records), proof['pages_read']), (51, 2))
        second.clear()
        with self.assertRaisesRegex(ValueError, 'page count changed'):
            annual_window(get, 2026)


if __name__ == '__main__':
    unittest.main()
