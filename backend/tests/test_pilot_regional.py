import unittest
import requests
from unittest.mock import Mock, patch
from app.events.pilot_regional import collect_regional
from app.events import engine


class RegionalTests(unittest.TestCase):
    @staticmethod
    def total_markup(count):
        return f'<div class="c-events_result__total"><span>{count} eventi trovati</span></div>'

    def test_connection_retry_is_bounded_and_does_not_restart_catalog(self):
        get = Mock(side_effect=requests.ConnectionError('interrupted'))
        with patch('app.events.http_client.time.sleep'):
            with self.assertRaises(requests.ConnectionError):
                collect_regional(get=get)
        self.assertEqual(get.call_count, 2)
    def test_pilot_never_fills_missing_year_but_legacy_default_unchanged(self):
        html = '<a class="c-eventsResults__item" href="/eventi/test"><h2 class="title">Evento prova</h2><span class="multiple_days_string">12 settembre</span></a>'
        self.assertIsNone(engine.extract_turismofvg_card_links(html, require_explicit_year=True)[0]['extracted_date'])
        self.assertIsNotNone(engine.extract_turismofvg_card_links(html)[0]['extracted_date'])
        html = html.replace('12 settembre', '12 settembre 2027')
        self.assertEqual(engine.extract_turismofvg_card_links(html, require_explicit_year=True)[0]['extracted_date'], '12 settembre 2027')
    def test_budget_above_hard_cap_rejected(self):
        get = Mock()
        with self.assertRaisesRegex(ValueError, "page budget"):
            collect_regional(get=get, max_pages=129)
        get.assert_not_called()

    def test_collection_can_exceed_old_twenty_page_limit(self):
        pages = [f'<a href="/eventi?page={n}">Carica altri eventi</a>' for n in range(1, 21)]
        result = self.run_pages(pages + ['<p>Fine</p>'], max_pages=128)
        self.assertEqual(result['pages'], 21)

    def run_pages(self, pages, max_pages=20):
        responses = [Mock(text=self.total_markup(len(pages)) + html,
                          url="https://www.turismofvg.it/eventi") for html in pages]
        card = {"url": "https://www.turismofvg.it/example", "title": "Evento", "place": "Udine", "extracted_date": "6 settembre 2026"}
        with patch("app.events.pilot_regional.engine.extract_turismofvg_card_links", return_value=[card]):
            return collect_regional(get=Mock(side_effect=responses), max_pages=max_pages)

    def test_pagination_and_deduplication(self):
        result = self.run_pages(['<a href="/eventi?page=2">Carica altri eventi</a>', '<p>Fine</p>'])
        self.assertEqual(result["pages"], 2)
        self.assertEqual(result['declared_results'], 2)
        self.assertEqual(result['cards_seen'], 2)
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["events"][0]["location_confidence"], "municipality")

    def test_exact_reviewed_programme_url_is_annotated_without_title_heuristics(self):
        response = Mock(text=self.total_markup(1) + '<p>Fine</p>', url="https://www.turismofvg.it/eventi")
        cards = [{
            "url": "https://www.turismofvg.it/eventi/pordenonelegge-2026",
            "title": "Titolo editoriale variabile", "place": "Pordenone",
            "extracted_date": "dal 16 settembre al 20 settembre 2026",
        }]
        with patch("app.events.pilot_regional.engine.extract_turismofvg_card_links", return_value=cards):
            event = collect_regional(get=Mock(return_value=response))["events"][0]
        self.assertEqual(event["programme_id"], "pordenonelegge-2026")
        self.assertEqual(event["programme_role"], "umbrella")

    def test_pending_detail_keeps_listing_image_and_category(self):
        response = Mock(text=self.total_markup(1) + '<p>Fine</p>', url='https://www.turismofvg.it/eventi')
        card = {
            'url': 'https://www.turismofvg.it/eventi/mostra',
            'title': 'Mostra', 'place': 'Pordenone', 'extracted_date': None,
            'image': 'https://www.turismofvg.it/immagini/mostra.jpg',
            'classification': {'category': 'cultura', 'category_label': 'Mostre'},
        }
        with patch('app.events.pilot_regional.engine.extract_turismofvg_card_links', return_value=[card]):
            result = collect_regional(get=Mock(return_value=response))
        self.assertEqual(result['events'], [])
        candidate = result['detail_candidates'][0]
        self.assertEqual(candidate['image'], card['image'])
        self.assertEqual(candidate['category'], 'cultura')
        self.assertEqual(candidate['category_label'], 'Mostre')

    def test_invalid_next_link_is_not_complete(self):
        with self.assertRaisesRegex(ValueError, "pagination"):
            self.run_pages(['<a href="https://example.com">Carica altri eventi</a>'])

    def test_budget_does_not_publish_partial_catalog(self):
        with self.assertRaisesRegex(ValueError, "budget exceeded"):
            self.run_pages(['<a href="/eventi?page=2">Carica altri eventi</a>'], max_pages=1)

    def test_loop_rejected(self):
        with self.assertRaisesRegex(ValueError, "looping"):
            self.run_pages(['<a href="/eventi?page=2">Carica altri eventi</a>'] * 2)

    def test_network_error_propagates(self):
        with self.assertRaises(TimeoutError):
            collect_regional(get=Mock(side_effect=TimeoutError))

    def test_empty_markup_rejected(self):
        response = Mock(text="<html></html>", url="https://www.turismofvg.it/eventi")
        with self.assertRaisesRegex(ValueError, "missing declared result total"):
            collect_regional(get=Mock(return_value=response))

    def test_declared_total_must_match_all_cards(self):
        response = Mock(text=self.total_markup(2) + '<p>Fine</p>',
                        url='https://www.turismofvg.it/eventi')
        card = {'url': 'https://www.turismofvg.it/eventi/prova', 'title': 'Prova',
                'place': 'Udine', 'extracted_date': '6 settembre 2026'}
        with patch('app.events.pilot_regional.engine.extract_turismofvg_card_links', return_value=[card]):
            with self.assertRaisesRegex(ValueError, 'card count differs'):
                collect_regional(get=Mock(return_value=response))

    def test_declared_total_change_aborts_catalog(self):
        first = Mock(text=self.total_markup(2) + '<a href="/eventi?page=1">Carica altri eventi</a>',
                     url='https://www.turismofvg.it/eventi')
        second = Mock(text=self.total_markup(3) + '<p>Fine</p>',
                      url='https://www.turismofvg.it/eventi?page=1')
        card = {'url': 'https://www.turismofvg.it/eventi/prova', 'title': 'Prova',
                'place': 'Udine', 'extracted_date': '6 settembre 2026'}
        with patch('app.events.pilot_regional.engine.extract_turismofvg_card_links', return_value=[card]):
            with self.assertRaisesRegex(ValueError, 'total changed'):
                collect_regional(get=Mock(side_effect=[first, second]))

    def test_yearless_badges_accumulate_for_repeated_event(self):
        def card(day):
            return (f'<a class="c-eventsResults__item" href="/eventi/sagra">'
                    f'<div class="info_date"><div class="col1"><strong>{day}</strong><p>OTT</p></div></div>'
                    '<strong class="col2">Polcenigo</strong><h1 class="title">Sagra</h1></a>')
        response = Mock(text=self.total_markup(2) + card(10) + card(17),
                        url='https://www.turismofvg.it/eventi')
        result = collect_regional(get=Mock(return_value=response))
        self.assertEqual(result['cards_seen'], 2)
        self.assertEqual(result['detail_candidates'][0]['listing_day_months'],
                         ['10 ottobre', '17 ottobre'])

    def test_alternate_official_detail_path_counts_as_catalog_card(self):
        html = (self.total_markup(1) +
                '<a class="c-eventsResults__item" href="/events20/details/377881">'
                '<div class="info_date"><div class="col1"><strong>9</strong><p>OTT</p></div></div>'
                '<strong class="col2">Trieste</strong>'
                '<h1 class="title">Barcolana 58: L’incanto dei castelli</h1></a>')
        response = Mock(text=html, url='https://www.turismofvg.it/eventi')
        result = collect_regional(get=Mock(return_value=response))
        self.assertEqual(result['cards_seen'], 1)
        self.assertEqual(result['detail_candidates'][0]['url'],
                         'https://www.turismofvg.it/events20/details/377881')


if __name__ == "__main__":
    unittest.main()
