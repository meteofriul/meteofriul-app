import unittest

from app.events.pilot_regional_location import (
    extract_turismofvg_map_point, resolve_turismofvg_municipality,
    resolve_turismofvg_municipalities, resolve_turismofvg_locality,
)


class RegionalLocationTests(unittest.TestCase):
    def test_source_spellings_of_municipalities(self):
        self.assertEqual(resolve_turismofvg_municipality('Duino-Aurisina').name,
                         'Duino Aurisina')
        self.assertEqual(resolve_turismofvg_municipality(
            'San Dorligo della Valle -Dolina').name,
            'San Dorligo della Valle')

    def test_hamlets_do_not_inherit_a_distant_municipal_centroid(self):
        for locality in ('Sistiana', 'Aprilia Marittima', 'Piancavallo'):
            with self.subTest(locality=locality):
                self.assertIsNone(resolve_turismofvg_municipality(locality))
        self.assertEqual(resolve_turismofvg_locality('Sistiana')[:2],
                         (45.7728922, 13.6391125))
        self.assertIsNone(resolve_turismofvg_locality('Aprilia Marittima'))

    def test_all_listed_towns_must_resolve_before_multi_place_card(self):
        places = resolve_turismofvg_municipalities('Udine, Trieste')
        self.assertEqual([place['name'] for place in places], ['Udine', 'Trieste'])
        self.assertIsNone(resolve_turismofvg_municipalities('Latisana, Aprilia Marittima'))

    def test_numeric_source_map_point_is_checked(self):
        page = ('<iframe id="gmap_canvas" src="https://www.google.com/maps/'
                'embed/v1/place?q=45.76575%2013.637&amp;zoom=13"></iframe>')
        self.assertEqual(extract_turismofvg_map_point(page), (45.76575, 13.637))
        self.assertIsNone(extract_turismofvg_map_point(
            page.replace('www.google.com', 'maps.example.com')))
        self.assertIsNone(extract_turismofvg_map_point(
            page.replace('45.76575', '55.76575')))


if __name__ == '__main__':
    unittest.main()
