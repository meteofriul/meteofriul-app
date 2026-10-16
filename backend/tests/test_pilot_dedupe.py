import unittest
from app.events.pilot_dedupe import deduplicate


class DedupeTests(unittest.TestCase):
    def test_conflicting_end_times_not_merged(self):
        a = self.event(end_time='20:00')
        self.assertEqual(len(deduplicate([a, {**a, 'end_time': '21:00'}])), 2)
    def test_missing_time_requires_same_source_reference(self):
        a = {**self.event(source="TurismoFVG", url="https://example.org/a"), "time": None}
        self.assertEqual(len(deduplicate([a, dict(a)])), 1)
        self.assertEqual(len(deduplicate([a, {**a, "url": "https://example.org/b"}])), 2)

    def test_place_and_address_conflicts_are_preserved(self):
        a = self.event(place="Teatro A", address="Via A")
        self.assertEqual(len(deduplicate([a, {**a, "place": "Teatro B"}])), 2)
        self.assertEqual(len(deduplicate([a, {**a, "address": "Via B"}])), 2)

    def event(self, **changes):
        return dict(title="Concerto", start_date="2026-09-06", end_date="2026-09-06",
                    time="19:00", event_city="Udine", **changes)

    def test_official_wins_and_provenance_preserved(self):
        result = deduplicate([
            self.event(source="TurismoFVG", url="https://example.org/a",
                       venue="Teatro Nuovo Giovanni da Udine"),
            self.event(source="Azalea", url="https://www.azalea.it/eventi/a/",
                       venue="Teatro Nuovo Giovanni da Udine")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source"], "Azalea")
        self.assertEqual(len(result[0]["source_urls"]), 2)

    def test_sessions_not_collapsed(self):
        a = self.event(source="Azalea")
        for changes in ({"time": "21:00"}, {"time": None}, {"event_city": "Pordenone"}):
            self.assertEqual(len(deduplicate([a, {**a, **changes}])), 2)

    def test_conflicting_venues_not_merged(self):
        a = self.event(venue="Teatro A")
        self.assertEqual(len(deduplicate([a, {**a, "venue": "Teatro B"}])), 2)

    def test_verified_sagra_pairs_share_one_card_without_inventing_time(self):
        examples = [
            ('Sagra della Capra / Perdon dal Rosari', 'San Paolo di Morsano al Tagliamento',
             'Sagra della Capra', 'San Paolo al Tagliamento', 'Morsano al Tagliamento'),
            ('Festeggiamenti Maniagolibero', 'Maniagolibero di Maniago',
             'Festeggiamenti Maniagolibero', 'Maniagolibero', 'Maniago'),
            ('Sagra della Madonna del Rosario', 'San Foca di San Quirino',
             'Sagra Madonna del Rosario', 'San Foca di San Quirino', 'San Quirino'),
            ('Oktoberfest 2026', 'Pescincanna di Fiume Veneto',
             '14^ ed. OktoberFest', 'Pescincanna di Fiume Veneto', 'Fiume Veneto'),
            ('Sagre da las Masanètes 2026', 'Villaorba di Basiliano',
             'Sagra delle Masanette', 'Villaorba di Basiliano', 'Basiliano'),
        ]
        for left_title, left_place, right_title, right_place, city in examples:
            with self.subTest(title=left_title):
                left = dict(source='SagreFVG', url='https://sagrefvg.it/sagre/a/',
                            title=left_title, place=left_place, event_city=city,
                            start_date='2026-10-09', end_date='2026-10-11', time=None)
                right = {**left, 'source': 'Paesi in Festa',
                         'url': 'https://paesiinfesta.com/friuli-venezia-giulia/a/',
                         'title': right_title, 'place': right_place}
                merged = deduplicate([left, right])
                self.assertEqual(len(merged), 1)
                self.assertEqual(len(merged[0]['source_urls']), 2)

    def test_sagra_pair_requires_same_locality_date_and_distinctive_name(self):
        left = dict(source='SagreFVG', url='https://sagrefvg.it/sagre/a/',
                    title='Sagra della Capra', place='San Paolo di Morsano al Tagliamento',
                    event_city='Morsano al Tagliamento', start_date='2026-10-09',
                    end_date='2026-10-11', time=None)
        right = {**left, 'source': 'Paesi in Festa',
                 'url': 'https://paesiinfesta.com/friuli-venezia-giulia/a/'}
        for changes in ({'place': 'Rauscedo'}, {'end_date': '2026-10-12'},
                        {'title': 'Festa del Vino'}, {'event_city': 'Codroipo'}):
            with self.subTest(changes=changes):
                self.assertEqual(len(deduplicate([left, {**right, **changes}])), 2)

    def test_radici_del_vino_2026_prefers_current_copy(self):
        regional = dict(source='Paesi in Festa',
                        url='https://paesiinfesta.com/friuli-venezia-giulia/pordenone/sagra-di-rauscedo-di-gan-giorgio-della-richinvelda/',
                        title='Le Radici del Vino',
                        place='Rauscedo di San Giorgio della Richinvelda',
                        event_city='San Giorgio della Richinvelda',
                        start_date='2026-10-09', end_date='2026-10-11', time=None,
                        description_excerpt='9^ Fiera Viticoltura d’Eccellenza',
                        description_source_name='Paesi in Festa',
                        description_source_url='https://paesiinfesta.com/friuli-venezia-giulia/pordenone/sagra-di-rauscedo-di-gan-giorgio-della-richinvelda/',
                        description_checked_at='2026-10-07T09:52:53+00:00')
        sagre = {**regional, 'source': 'SagreFVG',
                 'url': 'https://sagrefvg.it/sagre/rauscedo-di-san-giorgio-della-richinvelda-pn-le-radici-del-vino-duplicate-1/',
                 'title': 'Le Radici del Vino 2026',
                 'description_excerpt': 'Giunta alla sua 8ª edizione, la manifestazione torna.',
                 'description_source_name': 'SagreFVG',
                 'description_source_url': 'https://sagrefvg.it/sagre/rauscedo-di-san-giorgio-della-richinvelda-pn-le-radici-del-vino-duplicate-1/'}
        for rows in ([regional, sagre], [sagre, regional]):
            with self.subTest(first=rows[0]['source']):
                result = deduplicate(rows)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['source'], 'Paesi in Festa')
                self.assertEqual(result[0]['description_excerpt'], regional['description_excerpt'])
                self.assertEqual(result[0]['description_source_url'], regional['url'])
                self.assertEqual(len(result[0]['source_urls']), 2)

        later = [{**row, 'start_date': '2027-10-09',
                  'end_date': '2027-10-11'} for row in (regional, sagre)]
        self.assertNotEqual(deduplicate(later)[0]['source'], 'Paesi in Festa')

    def test_official_theatre_sessions_replace_short_regional_period(self):
        official = dict(source='CSS Udine',
                        url='https://www.cssudine.it/stagione-contatto/2026/2871/rita-maffei-francesca-osso-mrs-dalloway-1',
                        title='Rita Maffei / Francesca Osso / Mrs Dalloway #1',
                        event_city='Udine', venue='Teatro Palamostre, Sala ex GAMUD',
                        place='Udine', time='20:30')
        rows = [{**official, 'start_date': day, 'end_date': day}
                for day in ('2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31')]
        regional = dict(source='TurismoFVG',
                        url='https://www.turismofvg.it/eventi/mrs-dalloway-1-502637',
                        title='Mrs Dalloway #1', event_city='Udine',
                        venue='Teatro Palamostre', place='Teatro Palamostre',
                        time=None, start_date='2026-10-28', end_date='2026-10-31')
        merged = deduplicate([regional] + rows)
        self.assertEqual(len(merged), 4)
        self.assertTrue(all(row['source'] == 'CSS Udine' for row in merged))
        self.assertTrue(all(regional['url'] in row['source_urls'] for row in merged))
        self.assertEqual(len(deduplicate([regional] + rows[:-1])), 4)

    def test_verified_2026_period_conflicts_keep_one_complete_card(self):
        paesi = dict(source='Paesi in Festa',
                     url='https://paesiinfesta.com/friuli-venezia-giulia/udine/campoformido/',
                     title='Un giorno con Napoleone', event_city='Campoformido',
                     place='Campoformido', time=None,
                     start_date='2026-10-09', end_date='2026-10-11')
        regional = {**paesi, 'source': 'TurismoFVG',
                    'url': 'https://www.turismofvg.it/eventi/un-giorno-con-napoleone-466090',
                    'start_date': '2026-10-10', 'venue': 'Piazza del Trattato'}
        merged = deduplicate([regional, paesi])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['url'], paesi['url'])
        self.assertIn(regional['url'], merged[0]['source_urls'])
        self.assertEqual(len(deduplicate([regional, {**paesi, 'start_date': '2027-10-09',
                                                'end_date': '2027-10-11'}])), 2)

    def test_same_source_specific_detail_replaces_generic_duplicate(self):
        broad = dict(source='TurismoFVG',
                     url='https://www.turismofvg.it/eventi/un-giorno-con-napoleone-504752',
                     title='Un giorno con Napoleone', event_city='Campoformido',
                     venue='Campoformido', place='Campoformido', time=None,
                     start_date='2026-10-10', end_date='2026-10-11')
        specific = {**broad,
                    'url': 'https://www.turismofvg.it/eventi/un-giorno-con-napoleone-466090',
                    'venue': 'Piazza del Trattato, Campoformido',
                    'place': 'Piazza del Trattato, Campoformido'}
        merged = deduplicate([broad, specific])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['url'], specific['url'])
        self.assertEqual(len(merged[0]['source_urls']), 2)
        same_day_early = {**specific, 'start_date': '2026-11-01',
                          'end_date': '2026-11-01', 'time': '16:00'}
        same_day_late = {**same_day_early, 'url': broad['url'], 'time': '20:00'}
        self.assertEqual(len(deduplicate([same_day_early, same_day_late])), 2)

    def test_villa_manin_discrete_programme_replaces_regional_date_range(self):
        official = dict(source='Villa Manin',
                        url='https://www.villamanin.it/evento/lo-scrigno-del-doge-in-villa-manin/',
                        title='Lo scrigno del Doge in Villa Manin',
                        event_city='Codroipo', venue='Villa Manin',
                        schedule_kind='explicit_occurrence', time=None)
        rows = [{**official, 'start_date': day, 'end_date': day}
                for day in ('2026-11-01', '2026-12-08', '2027-01-06')]
        regional = dict(source='TurismoFVG',
                        url='https://www.turismofvg.it/eventi/lo-scrigno-del-doge',
                        title='Lo scrigno del Doge in Villa Manin - Mercatino',
                        event_city='Codroipo', venue='Villa Manin - Passariano',
                        start_date='2026-04-25', end_date='2026-12-08', time=None)
        merged = deduplicate([regional, *rows])
        self.assertEqual(len(merged), 3)
        self.assertTrue(all(item['source'] == 'Villa Manin' for item in merged))
        self.assertIn(regional['url'], merged[0]['source_urls'])

        for altered in ({'event_city': 'Udine'}, {'venue': 'Altro luogo'},
                        {'title': 'Un altro mercatino'}):
            self.assertEqual(len(deduplicate([{**regional, **altered}, *rows])), 4)
        self.assertEqual(len(deduplicate([regional, rows[0]])), 2)

    def test_same_day_villa_manin_detail_wins_over_regional_card(self):
        official = dict(source='Villa Manin',
                        url='https://www.villamanin.it/evento/famiglie-al-museo/',
                        title='Famiglie al Museo', event_city='Codroipo',
                        venue='Villa Manin', place='Villa Manin - Codroipo',
                        start_date='2026-10-11', end_date='2026-10-11', time=None)
        regional = {**official, 'source': 'TurismoFVG',
                    'url': 'https://www.turismofvg.it/eventi/famiglie-al-museo',
                    'venue': 'Villa Manin - Passariano', 'place': 'Villa Manin'}
        merged = deduplicate([regional, official])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['source'], 'Villa Manin')
        self.assertEqual(len(merged[0]['source_urls']), 2)
        self.assertEqual(len(deduplicate([{**regional, 'title': 'Un altro laboratorio'},
                                          official])), 2)

    def test_magazzino_exhibition_is_not_duplicated_with_turismofvg(self):
        official = dict(source='Magazzino delle Idee',
                        url='https://magazzinodelleidee.it/evento/ila-beka-fotoni/',
                        title='Ila Bêka - Fotoni', event_city='Trieste',
                        venue='Magazzino delle Idee',
                        place='Magazzino delle Idee, Trieste',
                        start_date='2026-06-27', end_date='2026-10-11', time=None)
        regional = {**official, 'source': 'TurismoFVG',
                    'url': 'https://www.turismofvg.it/eventi/ila-beka-fotoni-493895',
                    'place': 'Magazzino delle Idee'}
        merged = deduplicate([regional, official])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['source'], 'Magazzino delle Idee')
        self.assertEqual(len(merged[0]['source_urls']), 2)
        self.assertEqual(len(deduplicate([{**regional, 'event_city': 'Gorizia'},
                                          official])), 2)

    def test_same_venue_cross_source_chooses_one_official_card_with_richer_preview(self):
        official = dict(source='CSS Udine', url='https://cssudine.it/spettacolo/a/',
                        title='Lo spettacolo', start_date='2026-11-12',
                        end_date='2026-11-12', event_city='Udine',
                        venue='Teatro Palamostre', place='Teatro Palamostre, Udine',
                        time=None, lat=46.07, lon=13.24,
                        location_confidence='municipality')
        regional = {**official, 'source': 'TurismoFVG',
                    'url': 'https://www.turismofvg.it/eventi/lo-spettacolo',
                    'place': 'Udine', 'image': 'https://www.turismofvg.it/image.jpg',
                    'description_excerpt': 'Una descrizione verificata della rappresentazione.',
                    'description_source_name': 'TurismoFVG',
                    'description_source_url': 'https://www.turismofvg.it/eventi/lo-spettacolo',
                    'description_checked_at': '2026-10-07T00:00:00+00:00'}
        for rows in ([regional, official], [official, regional]):
            with self.subTest(order=rows[0]['source']):
                merged = deduplicate(rows)
                self.assertEqual(len(merged), 1)
                self.assertEqual(merged[0]['source'], 'CSS Udine')
                self.assertEqual(merged[0]['url'], official['url'])
                self.assertEqual(merged[0]['image'], regional['image'])
                self.assertEqual(merged[0]['description_excerpt'], regional['description_excerpt'])
                self.assertEqual(merged[0]['description_source_name'], 'TurismoFVG')
                self.assertEqual(merged[0]['description_source_url'], regional['url'])
                self.assertEqual(len(merged[0]['source_urls']), 2)

        official_copy = {**official,
                         'description_excerpt': 'La descrizione ufficiale dello spettacolo.',
                         'description_source_name': 'CSS Udine',
                         'description_source_url': official['url'],
                         'description_checked_at': '2026-10-07T00:00:00+00:00'}
        preferred = deduplicate([regional, official_copy])[0]
        self.assertEqual(preferred['description_excerpt'], official_copy['description_excerpt'])
        self.assertEqual(preferred['description_source_url'], official['url'])

        unverified_copy = {**regional, 'description_checked_at': None}
        self.assertNotIn('description_excerpt', deduplicate([unverified_copy, official])[0])

    def test_cross_source_identity_needs_matching_venue_and_single_schedule(self):
        official = dict(source='CSS Udine', url='https://cssudine.it/spettacolo/a/',
                        title='Lo spettacolo', start_date='2026-11-12',
                        end_date='2026-11-12', event_city='Udine',
                        venue='Teatro Palamostre', place='Udine', time=None)
        regional = {**official, 'source': 'TurismoFVG',
                    'url': 'https://www.turismofvg.it/eventi/lo-spettacolo'}
        for changes in ({'venue': 'Teatro Nuovo Giovanni da Udine'},
                        {'venue': None}, {'start_date': '2026-11-13'},
                        {'event_city': 'Pordenone'}, {'time': '20:00'},
                        {'programme_id': 'lo-spettacolo-2026'},
                        {'title': 'Visita guidata'}):
            with self.subTest(changes=changes):
                self.assertEqual(len(deduplicate([official, {**regional, **changes}])), 2)

        generic = {**official, 'title': 'Visita guidata'}
        self.assertEqual(len(deduplicate([generic, {**regional, 'title': 'Visita guidata'}])), 2)

        timed_generic = {**generic, 'time': '20:00', 'venue': None}
        self.assertEqual(len(deduplicate([
            timed_generic, {**timed_generic, 'source': 'TurismoFVG',
                            'url': regional['url']}])), 2)

    def test_same_reference_selects_more_complete_card_independent_of_order(self):
        base = dict(source='TurismoFVG', url='https://www.turismofvg.it/eventi/a',
                    title='Concerto', start_date='2026-11-12', end_date='2026-11-12',
                    event_city='Udine', place='Udine', time=None)
        enriched = {**base, 'image': 'https://www.turismofvg.it/image.jpg',
                    'description_excerpt': 'Il programma della serata è pubblicato.',
                    'description_source_name': 'TurismoFVG',
                    'description_source_url': base['url']}
        for rows in ([base, enriched], [enriched, base]):
            self.assertEqual(deduplicate(rows)[0]['image'], enriched['image'])
            self.assertEqual(deduplicate(rows)[0]['description_excerpt'],
                             enriched['description_excerpt'])
