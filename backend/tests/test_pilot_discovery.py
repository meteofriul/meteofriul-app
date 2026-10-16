import unittest
from app.events.pilot_discovery import highlighted_candidates


def slide(url='/eventi/festival-2026'):
    return ('<div class="c-events_showreel__slide"><h2 class="c-events_showreel__title">Festival 2026</h2>'
            '<h3><strong>16 SETTEMBRE</strong> 2026</h3><h4><strong>Pordenone</strong></h4>'
            '<a href="' + url + '" class="c-events_showreel__link">Evento</a></div>')


class DiscoveryTests(unittest.TestCase):
    def test_highlight_is_candidate_not_one_day_event(self):
        item = highlighted_candidates(slide())[0]
        self.assertEqual(item['event_city'], 'Pordenone')
        self.assertEqual(item['date_hint'], '16 SETTEMBRE 2026')
        self.assertNotIn('start_date', item)
        self.assertNotIn('end_date', item)

    def test_repeated_highlights_are_discovered_once(self):
        self.assertEqual(len(highlighted_candidates(slide() * 2)), 1)

    def test_external_references_not_followed(self):
        self.assertEqual(highlighted_candidates(slide('https://example.org/eventi/festival')), [])

    def test_missing_date_not_extracted_from_title(self):
        html = slide().replace('<h3><strong>16 SETTEMBRE</strong> 2026</h3>', '')
        self.assertIsNone(highlighted_candidates(html)[0]['date_hint'])
