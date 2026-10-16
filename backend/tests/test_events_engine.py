import unittest
from datetime import date
from unittest.mock import patch

import requests

from app.events import engine


class FakeResponse:
    def __init__(self, text="<html></html>", url=None):
        self.text = text
        self.url = url

    def raise_for_status(self):
        return None


class FakeJsonResponse(FakeResponse):
    def __init__(self, payload):
        super().__init__()
        self.payload = payload

    def json(self):
        return self.payload


class EventsEngineTests(unittest.TestCase):
    def setUp(self):
        engine.events_cache.clear()
        engine.local_events_response_cache.clear()
        engine.local_events_refreshing.clear()
        engine.local_events_refresh_started.clear()
        engine.local_events_refresh_outcomes.clear()
        engine.turismofvg_detail_cache.clear()
        engine.turismofvg_locality_cache.clear()

    @staticmethod
    def local_events_response(*, count=1, status="fresh", completed=None, pending=None):
        return {
            "city": "Pordenone",
            "events": [
                {
                    "title": f"Evento {index}",
                    "source": "SagreFVG",
                    "date": "21 agosto 2026",
                }
                for index in range(count)
            ],
            "source": "SagreFVG",
            "sources": ["SagreFVG"],
            "cache": {
                "status": status,
                "completed_sources": completed or [],
                "pending_sources": pending or [],
            },
        }

    def test_pordenone_source_collection_includes_nearby_porcia(self):
        municipalities = engine.nearby_fvg_municipalities(
            "Pordenone",
            45.9567,
            12.6605,
        )

        self.assertLessEqual(
            len(municipalities),
            engine.EVENTS_NEARBY_SOURCE_MUNICIPALITY_LIMIT,
        )
        self.assertEqual(municipalities[0].name, "Pordenone")
        self.assertIn("Porcia", [item.name for item in municipalities])

    def test_turismofvg_specs_add_nearby_locality_without_repeating_active_city(self):
        specs = engine.turismofvg_request_specs(
            "Pordenone",
            "2090",
            ["2090", "2087"],
        )
        base_localities = [
            spec["params"]["locality"]
            for spec in specs
            if spec["url"] == engine.TURISMOFVG_EVENTS_FILTER_URL
        ]

        self.assertEqual(base_localities.count("2090"), 1)
        self.assertEqual(base_localities.count("2087"), 1)

    def test_turismofvg_specs_add_candidate_title_catalog_lookup(self):
        specs = engine.turismofvg_request_specs(
            "Trieste",
            "1874",
            search_queries=["Ila Bêka. Fotoni"],
        )

        lookup = [spec for spec in specs if spec.get("catalog_lookup")]
        self.assertEqual(len(lookup), 1)
        self.assertEqual(lookup[0]["params"]["q"], "Ila Bêka. Fotoni")

    def test_guarded_official_feed_joins_the_normal_event_pipeline(self):
        current = date.today()
        today = current.isoformat()
        month = (
            "gennaio febbraio marzo aprile maggio giugno luglio agosto "
            "settembre ottobre novembre dicembre"
        ).split()[current.month - 1]
        official = {
            "title": "Visite Tematiche",
            "url": "https://www.villamanin.it/evento/visite-tematiche/",
            "official_site": "https://www.villamanin.it/evento/visite-tematiche/",
            "date": f"{current.day} {month} {current.year}",
            "start_date": today,
            "end_date": today,
            "event_city": "Codroipo",
            "place": "Villa Manin - Codroipo",
            "venue": "Villa Manin",
            "lat": 45.9614,
            "lon": 12.9777,
            "source": "Villa Manin",
            "is_real": True,
            "category": "cultura",
            "category_label": "Cultura",
        }
        fetchers = (
            "fetch_turismofvg_events",
            "fetch_sagrefvg_events",
            "fetch_prolocofvg_events",
            "fetch_paesiinfesta_events",
            "fetch_eventifvg_events",
        )
        patches = [patch.object(engine, name, return_value=[]) for name in fetchers]
        for current in patches:
            current.start()
            self.addCleanup(current.stop)

        with patch.object(
            engine,
            "load_guarded_official_events",
            return_value=[official],
        ), patch.object(
            engine,
            "enrich_selected_event_images",
            side_effect=lambda events: events,
        ), patch.object(
            engine,
            "cache_selected_event_images",
            side_effect=lambda events: events,
        ):
            response = engine.build_local_events_response(
                "Codroipo",
                limit=6,
                lat=45.9614,
                lon=12.9777,
            )

        self.assertEqual([item["title"] for item in response["events"]], ["Visite Tematiche"])
        self.assertEqual(response["cache"]["source_counts"]["official_guarded"], 1)
        self.assertIn("official_guarded", response["cache"]["completed_sources"])

    def test_local_guarded_preview_can_show_a_future_event_for_visual_review(self):
        future = {
            "title": "Cena in bianco",
            "date": "5 settembre 2099",
            "source": "Villa Manin",
        }

        with patch.object(engine, "event_source_feed_mode", return_value="preview"):
            filtered = engine.filter_event_window_with_guarded_preview(
                [future],
                [future],
            )

        self.assertEqual(
            filtered,
            [{**future, "preview_outside_window": True}],
        )

    def test_active_guarded_feed_keeps_the_normal_event_window(self):
        future = {
            "title": "Cena in bianco",
            "date": "5 settembre 2099",
            "source": "Villa Manin",
        }

        with patch.object(engine, "event_source_feed_mode", return_value="active"):
            filtered = engine.filter_event_window_with_guarded_preview(
                [future],
                [future],
            )

        self.assertEqual(filtered, [])

    def test_turismofvg_category_navigation_is_not_treated_as_event(self):
        self.assertTrue(
            engine.is_turismofvg_navigation_link(
                {"url": "https://www.turismofvg.it/eventi/feste-tradizionali"}
            )
        )
        self.assertFalse(
            engine.is_turismofvg_navigation_link(
                {
                    "url": "https://www.turismofvg.it/eventi/sagra-dell-assunta-498528"
                }
            )
        )
        self.assertTrue(
            engine.is_turismofvg_navigation_link(
                {"url": "https://www.turismofvg.it/eventi/convegni"}
            )
        )

    def test_turismofvg_next_page_is_taken_only_from_official_load_more_link(self):
        html = """
            <a href="/eventi?category=3588&amp;locality=1874&amp;page=1">
              <strong>carica altri eventi</strong>
            </a>
        """

        self.assertEqual(
            engine.extract_turismofvg_next_page_url(
                html,
                "https://www.turismofvg.it/eventi?category=3588&locality=1874",
            ),
            "https://www.turismofvg.it/eventi?category=3588&locality=1874&page=1",
        )
        self.assertIsNone(
            engine.extract_turismofvg_next_page_url(
                '<a href="https://example.org/eventi?page=1">carica altri eventi</a>',
                "https://www.turismofvg.it/eventi",
            )
        )

    def test_turismofvg_detail_url_validation_is_fail_closed(self):
        self.assertTrue(
            engine.is_trusted_turismofvg_event_url(
                "https://www.turismofvg.it/eventi/udin-disore-tra-passato-e-futuro"
            )
        )
        self.assertTrue(engine.is_trusted_turismofvg_event_url(
            "https://www.turismofvg.it/events20/details/377881"))
        self.assertFalse(engine.is_trusted_turismofvg_event_url(
            "https://www.turismofvg.it/events20/details/377881/redirect"))
        self.assertFalse(
            engine.is_trusted_turismofvg_event_url(
                "https://www.turismofvg.it/eventi/fiere-e-mercatini"
            )
        )
        self.assertFalse(
            engine.is_trusted_turismofvg_event_url(
                "https://www.turismofvg.it.evil.example/eventi/evento"
            )
        )
        self.assertFalse(
            engine.is_trusted_turismofvg_event_url(
                "http://www.turismofvg.it/eventi/evento"
            )
        )
        self.assertFalse(
            engine.is_trusted_turismofvg_event_url(
                "https://www.turismofvg.it/eventi/evento?redirect=example.org"
            )
        )
        self.assertFalse(
            engine.is_trusted_turismofvg_event_url(
                "https://www.turismofvg.it/eventi/evento#programma"
            )
        )

    def test_turismofvg_description_comes_only_from_the_official_description_block(self):
        html = """
            <section class="c-detail__body">
              <div class="body_col1 extra-class">
                <p>
                  <h2>Descrizione</h2>
                  <div>
                    <p>Mercatino dell&#39;usato e dell&#39;artigianato durante la mattina.</p>
                    <p>Una seconda frase che non deve essere persa.</p>
                  </div>
                </p>
                <p><h2>Organizzato da:</h2>Pro Loco Borgo Sole</p>
              </div>
              <div class="body_col2">
                <div style="background-image: url(icn__calendar.svg)">18 marzo 2026</div>
              </div>
            </section>
        """

        self.assertEqual(
            engine.extract_turismofvg_description(html),
            "Mercatino dell'usato e dell'artigianato durante la mattina. "
            "Una seconda frase che non deve essere persa.",
        )
        metadata = engine.extract_turismofvg_detail_metadata(html)
        self.assertEqual(
            metadata["description"],
            "Mercatino dell'usato e dell'artigianato durante la mattina. "
            "Una seconda frase che non deve essere persa.",
        )
        self.assertNotIn("Pro Loco Borgo Sole", metadata["description"])

    def test_turismofvg_venue_separates_the_verified_street_address(self):
        venue, address = engine.split_event_venue_address(
            "Centro Polisportivo Comunale di Villanova “A. Lupieri” - via Pirandello, 33"
        )

        self.assertEqual(
            venue,
            "Centro Polisportivo Comunale di Villanova “A. Lupieri”",
        )
        self.assertEqual(address, "via Pirandello, 33")

    def test_turismofvg_card_extracts_multiple_day_range_without_neighbor_context(self):
        html = """
            <a href="/eventi/ila-beka-fotoni-493895" class="c-eventsResults__item small">
              <div class="item_info">
                <div class="info_rows info_date">
                  <div class="col1 multipledays"></div>
                  <div class="col2"><strong>Trieste</strong></div>
                  <div class="col3" title="Mostre"></div>
                </div>
              </div>
              <div class="item_title">
                <span class="multiple_days_string">dal 27 giugno al 11 ottobre</span>
                <h2 class="title"><strong>Ila Bêka - Fotoni</strong></h2>
              </div>
            </a>
        """

        links = engine.extract_turismofvg_card_links(html)

        self.assertEqual(len(links), 1)
        self.assertEqual(
            links[0]["extracted_date"],
            f"dal 27 giugno al 11 ottobre {engine.datetime.now().year}",
        )

    def test_turismofvg_discrete_schedule_preserves_each_official_occurrence(self):
        self.assertEqual(
            engine.parse_turismofvg_discrete_occurrences(
                "13 e 27 giugno, 18 luglio, 29 agosto 2026"
            ),
            [
                "2026-06-13",
                "2026-06-27",
                "2026-07-18",
                "2026-08-29",
            ],
        )
        self.assertEqual(
            engine.parse_turismofvg_discrete_occurrences(
                "sabato 27 giugno 2026 - domenica 11 ottobre 2026"
            ),
            [],
        )
        self.assertEqual(
            engine.parse_turismofvg_discrete_occurrences(
                "10, 11 /17, 18 / 24, 25 ottobre 2026"
            ),
            ["2026-10-10", "2026-10-11", "2026-10-17", "2026-10-18",
             "2026-10-24", "2026-10-25"],
        )

    def test_turismofvg_card_attaches_discrete_occurrences_to_the_link(self):
        html = """
            <a href="/eventi/semi-d-arte" class="c-eventsResults__item small">
              <div class="item_info"><div class="col2"><strong>Codroipo</strong></div></div>
              <div class="item_title">
                <span class="multiple_days_string">13 e 27 giugno, 18 luglio, 29 agosto 2026</span>
                <h2 class="title"><strong>Semi d'arte</strong></h2>
              </div>
            </a>
        """

        links = engine.extract_turismofvg_card_links(html)

        self.assertEqual(
            links[0]["occurrences"],
            ["2026-06-13", "2026-06-27", "2026-07-18", "2026-08-29"],
        )

    def test_turismofvg_card_decodes_invisible_html_entity_in_real_event_url(self):
        html = ('<a class="c-eventsResults__item" '
                'href="/eventi/&#8203;iii-edizione-che-cura-che-fa">'
                '<h2 class="title">&#8203;III Edizione Che cura che fa</h2>'
                '<div class="info_date"><div class="col1">'
                '<strong>15</strong><p>OTT</p></div></div></a>')
        card = engine.extract_turismofvg_card_links(html)[0]
        self.assertEqual(card['title'], 'III Edizione Che cura che fa')
        self.assertIn('\u200biii-edizione', card['url'])
        self.assertTrue(engine.is_trusted_turismofvg_event_url(card['url']))
        self.assertEqual(engine.clean_event_text('&#8203;III Edizione'), 'III Edizione')

    def test_similar_traditional_events_in_different_municipalities_are_not_merged(self):
        fontanafredda = {
            "title": "Festa dell'Assunta 2026",
            "date": "dal 6 al 17 agosto 2026",
            "place": "Fontanafredda",
            "event_city": "Fontanafredda",
            "category": "sagra",
        }
        porcia = {
            "title": "Sagra dell'Assunta",
            "date": "dal 31 luglio al 16 agosto 2026",
            "place": "Porcia",
            "event_city": "Porcia",
            "category": "sagra",
        }

        self.assertFalse(engine.events_are_probable_duplicates(fontanafredda, porcia))

    def test_same_venue_words_do_not_merge_distinct_villa_manin_events(self):
        scrigno = {
            "title": "Lo scrigno del Doge in Villa Manin",
            "date": "dal 25 aprile 2026 al 6 gennaio 2027",
            "place": "Villa Manin - Codroipo",
            "event_city": "Codroipo",
            "category": "cultura",
        }
        visite = {
            "title": "Visite Tematiche a Villa Manin",
            "date": "dal 20 giugno al 5 settembre 2026",
            "place": "Villa Manin - Codroipo",
            "event_city": "Codroipo",
            "category": "cultura",
        }

        self.assertFalse(engine.events_are_probable_duplicates(scrigno, visite))

    def test_municipality_name_in_title_is_not_enough_to_merge_gorizia_events(self):
        dag = {
            "title": "DAG - Digital Art Gallery Gorizia",
            "date": "dal 17 dicembre 2025 al 31 dicembre 2026",
            "place": "Gorizia",
            "event_city": "Gorizia",
            "category": "cultura",
        }
        festival = {
            "title": "Festival della storia di Gorizia",
            "date": "dal 1 al 30 settembre 2026",
            "place": "Gorizia",
            "event_city": "Gorizia",
            "category": "cultura",
        }

        self.assertFalse(engine.events_are_probable_duplicates(dag, festival))

    def test_same_traditional_event_with_source_word_variants_is_still_merged(self):
        first = {
            "title": "Festa dell'Assunta 2026",
            "date": "dal 6 al 17 agosto 2026",
            "place": "Porcia",
            "event_city": "Porcia",
            "category": "sagra",
        }
        second = {
            "title": "Sagra dell'Assunta",
            "date": "dal 9 al 16 agosto 2026",
            "place": "Porcia",
            "event_city": "Porcia",
            "category": "sagra",
        }

        self.assertTrue(engine.events_are_probable_duplicates(first, second))

    def test_saint_abbreviation_and_edition_variants_are_merged(self):
        turismo = {
            "title": "44^ Sagra di S. Agostino",
            "date": "venerdì 21 agosto 2026 - lunedì 31 agosto 2026",
            "place": "Pordenone",
            "event_city": "Pordenone",
            "venue": "Torre di Pordenone",
            "source": "TurismoFVG",
            "category": "sagra",
            "location_confidence": "city_text",
        }
        sagrefvg = {
            "title": "Torre di Pordenone (PN) – Sagra di Sant’Agostino",
            "date": "21 agosto 2026 - 31 agosto 2026",
            "place": "Torre di Pordenone",
            "event_city": "Pordenone",
            "venue": "Torre di Pordenone",
            "address": "Via Scipio Slataper",
            "lat": 45.9723922,
            "lon": 12.6746172,
            "location_confidence": "exact",
            "source": "SagreFVG",
            "category": "sagra",
        }

        self.assertTrue(engine.events_are_probable_duplicates(turismo, sagrefvg))
        merged = engine.dedupe_similar_events([turismo, sagrefvg], "Pordenone")
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["lat"], 45.9723922)
        self.assertEqual(merged[0]["address"], "Via Scipio Slataper")

    def test_povoletto_roman_quarte_d_avost_alias_is_strictly_merged(self):
        turismo = {
            "title": "Sagra della Quarte d'Avost",
            "date": "giovedì 20 agosto 2026 - martedì 25 agosto 2026",
            "place": "Piazzale Mons. Valerio Zamparo, Povoletto",
            "event_city": "Povoletto",
            "venue": "Piazzale Mons. Valerio Zamparo, Povoletto",
            "description": "Festa della Madonna della Cintura organizzata dalla Pro Loco Povoletto.",
            "source": "TurismoFVG",
            "category": "sagra",
            "location_confidence": "city_text",
        }
        sagrefvg = {
            "title": "Povoletto (UD) – 299ª Sagra IV d’Avost",
            "date": "20 agosto 2026 - 25 agosto 2026",
            "place": "Povoletto (UD)",
            "event_city": "Povoletto",
            "venue": "Povoletto (UD)",
            "address": "Via Dante Alighieri, 7, 33040 Povoletto UD",
            "source": "SagreFVG",
            "category": "sagra",
            "location_confidence": "city_text",
        }

        self.assertTrue(engine.events_are_probable_duplicates(turismo, sagrefvg))

        merged = engine.dedupe_similar_events([turismo, sagrefvg], "Udine")

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "TurismoFVG")
        self.assertEqual(merged[0]["address"], "Via Dante Alighieri, 7, 33040 Povoletto UD")
        self.assertEqual(merged[0]["alternate_sources"], ["TurismoFVG", "SagreFVG"])

        cached_response = engine.clone_local_events_response_with_cache(
            {
                "city": "Udine",
                "events": [turismo, sagrefvg],
                "source": "multi",
                "sources": ["TurismoFVG", "SagreFVG"],
                "cache": {"status": "stale"},
            },
            "stale",
        )
        self.assertEqual(len(cached_response["events"]), 1)
        self.assertEqual(cached_response["events"][0]["source"], "TurismoFVG")
        self.assertEqual(cached_response["sources"], ["TurismoFVG"])

        other_municipality = {
            **sagrefvg,
            "title": "Silvella di San Vito di Fagagna (UD) – Sagre da quarte d’Avost",
            "date": "20 agosto 2026 - 23 agosto 2026",
            "place": "Silvella",
            "event_city": "Silvella",
            "venue": "Silvella",
        }
        discordant_range = {
            **sagrefvg,
            "date": "20 agosto 2026 - 24 agosto 2026",
        }

        self.assertFalse(engine.events_are_probable_duplicates(turismo, other_municipality))
        self.assertFalse(engine.events_are_probable_duplicates(turismo, discordant_range))

    def test_generic_paesi_in_festa_records_merge_only_with_exact_locality_and_range(self):
        verified_pairs = [
            (
                {
                    "title": "Villanova di Pordenone (PN) – 49ª Festa in Piassa",
                    "date": "20 agosto 2026 - 31 agosto 2026",
                    "place": "Villanova di Pordenone",
                    "event_city": "Pordenone",
                    "venue": "Villanova di Pordenone",
                    "source": "SagreFVG",
                    "category": "sagra",
                },
                {
                    "title": "Sagra di Villanova di Pordenone",
                    "date": "dal 20 al 31 agosto 2026",
                    "place": "Villanova di Pordenone",
                    "event_city": "Villanova di Pordenone",
                    "source": "Paesi in Festa",
                    "category": "sagra",
                },
            ),
            (
                {
                    "title": "Torre di Pordenone (PN) – Sagra di Sant’Agostino",
                    "date": "21 agosto 2026 - 31 agosto 2026",
                    "place": "Torre di Pordenone",
                    "event_city": "Pordenone",
                    "venue": "Torre di Pordenone",
                    "source": "SagreFVG",
                    "category": "sagra",
                },
                {
                    "title": "Sagra di Torre di Pordenone",
                    "date": "dal 21 al 31 agosto 2026",
                    "place": "Torre di Pordenone",
                    "event_city": "Torre di Pordenone",
                    "source": "Paesi in Festa",
                    "category": "sagra",
                },
            ),
            (
                {
                    "title": "Castions di Zoppola (PN) – Festeggiamenti al Parco Burgos",
                    "date": "20 agosto 2026 - 30 agosto 2026",
                    "place": "Castions Di Zoppola",
                    "event_city": "Castions",
                    "venue": "Castions Di Zoppola",
                    "source": "SagreFVG",
                    "category": "sagra",
                },
                {
                    "title": "Sagra di Castions di Zoppola",
                    "date": "dal 20 al 30 agosto 2026",
                    "place": "Castions di Zoppola",
                    "event_city": "Castions di Zoppola",
                    "source": "Paesi in Festa",
                    "category": "sagra",
                },
            ),
        ]

        for primary, generic in verified_pairs:
            with self.subTest(primary=primary["title"]):
                self.assertTrue(engine.events_are_probable_duplicates(primary, generic))

        turismo_villanova = {
            "title": "49^ Festa in Piassa",
            "date": "giovedì 20 agosto 2026 - lunedì 31 agosto 2026",
            "place": "Pordenone",
            "event_city": "Pordenone",
            "venue": "Centro Polisportivo Comunale di Villanova A. Lupieri",
            "description": "Programma ufficiale completo della festa.",
            "source": "TurismoFVG",
            "category": "sagra",
            "location_confidence": "city_text",
        }
        sagrefvg_villanova, paesi_villanova = verified_pairs[0]
        sagrefvg_villanova = {
            **sagrefvg_villanova,
            "address": "Via Luigi Pirandello",
            "lat": 45.9434238,
            "lon": 12.6712263,
            "location_confidence": "exact",
        }
        merged = engine.dedupe_similar_events(
            [turismo_villanova, sagrefvg_villanova, paesi_villanova],
            "Pordenone",
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "TurismoFVG")
        self.assertEqual(merged[0]["description"], "Programma ufficiale completo della festa.")
        self.assertEqual(merged[0]["address"], "Via Luigi Pirandello")
        self.assertEqual(merged[0]["location_confidence"], "exact")
        self.assertEqual(
            merged[0]["alternate_sources"],
            ["TurismoFVG", "SagreFVG", "Paesi in Festa"],
        )

        villanova = verified_pairs[0][1]
        torre = verified_pairs[1][0]
        self.assertFalse(engine.events_are_probable_duplicates(villanova, torre))

        different_range = {
            **verified_pairs[0][0],
            "title": "Mercato estivo di Villanova",
            "date": "20 agosto 2026 - 30 agosto 2026",
            "source": "TurismoFVG",
            "category": "mercato",
        }
        self.assertFalse(engine.events_are_probable_duplicates(villanova, different_range))

    def test_tiezzo_frazione_and_azzano_municipality_are_merged_by_verified_venue(self):
        turismo = {
            "title": "37^ Festa paesana di Tiezzo",
            "date": "21 agosto 2026 - 6 settembre 2026",
            "place": "Azzano Decimo",
            "event_city": "Azzano Decimo",
            "venue": "Campo dell'oratorio di Tiezzo Piazza Garibaldi",
            "description": "Festa tradizionale della comunità di Tiezzo.",
            "lat": 45.9092,
            "lon": 12.7144,
            "location_confidence": "municipality",
            "source": "TurismoFVG",
            "category": "sagra",
        }
        sagrefvg = {
            "title": "Tiezzo di Azzano X (PN) – Festa Paesana 2026",
            "date": "21 agosto 2026 - 6 settembre 2026",
            "place": "Tiezzo",
            "event_city": "Tiezzo",
            "venue": "Tiezzo",
            "address": "Piazza Garibaldi",
            "lat": 45.8918777,
            "lon": 12.6728855,
            "location_confidence": "exact",
            "source": "SagreFVG",
            "category": "sagra",
        }

        self.assertTrue(engine.events_are_probable_duplicates(turismo, sagrefvg))

        events = engine.dedupe_similar_events([turismo, sagrefvg], "Pordenone")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "TurismoFVG")
        self.assertEqual(events[0]["event_city"], "Azzano Decimo")
        self.assertEqual(events[0]["venue"], "Campo dell'oratorio di Tiezzo Piazza Garibaldi")
        self.assertEqual(events[0]["address"], "Piazza Garibaldi")
        self.assertEqual(events[0]["lat"], 45.8918777)
        self.assertEqual(events[0]["lon"], 12.6728855)
        self.assertEqual(events[0]["location_confidence"], "exact")
        self.assertEqual(events[0]["alternate_sources"], ["TurismoFVG", "SagreFVG"])

    def test_generic_venue_words_do_not_link_different_municipalities(self):
        pordenone = {
            "title": "Festa paesana 2026",
            "date": "21 agosto 2026 - 23 agosto 2026",
            "place": "Pordenone",
            "event_city": "Pordenone",
            "venue": "Centro civico Piazza Garibaldi",
            "category": "sagra",
        }
        udine = {
            "title": "Festa paesana 2026",
            "date": "21 agosto 2026 - 23 agosto 2026",
            "place": "Udine",
            "event_city": "Udine",
            "venue": "Centro civico Piazza Garibaldi",
            "category": "sagra",
        }

        self.assertFalse(engine.event_places_are_related(pordenone, udine))
        self.assertFalse(engine.events_are_probable_duplicates(pordenone, udine))

    def test_location_prefix_does_not_hide_the_same_event_title(self):
        sagrefvg = {
            "title": "San Daniele del Friuli (UD) – San Daniele in Festa",
            "date": "21 agosto 2026 - 23 agosto 2026",
            "source": "SagreFVG",
            "place": "San Daniele del Friuli (UD)",
            "event_city": "San Daniele del Friuli",
            "category": "sagra",
        }
        eventifvg = {
            "title": "San Daniele in Festa",
            "date": "21 agosto 2026 - 23 agosto 2026",
            "source": "EventiFVG",
            "place": "San Daniele del Friuli",
            "event_city": "San Daniele del Friuli",
            "category": "sagra",
        }

        self.assertTrue(engine.events_are_probable_duplicates(sagrefvg, eventifvg))
        merged = engine.dedupe_similar_events([sagrefvg, eventifvg], "Udine")
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "SagreFVG")
        self.assertEqual(merged[0]["alternate_sources"], ["SagreFVG", "EventiFVG"])

    def test_camel_case_event_name_matches_the_spaced_title(self):
        sagrefvg = {
            "title": "Udine / San Pio X (UD) – FestaInsieme",
            "date": "20 agosto 2026 - 23 agosto 2026",
            "source": "SagreFVG",
            "place": "San Pio X",
            "event_city": "Udine",
            "category": "sagra",
        }
        turismo = {
            "title": "Festa insieme San Pio X",
            "date": "giovedi 20 agosto 2026 - domenica 23 agosto 2026",
            "source": "TurismoFVG",
            "place": "Udine",
            "event_city": "Udine",
            "venue": "San Pio X",
            "category": "sagra",
        }

        self.assertTrue(engine.events_are_probable_duplicates(sagrefvg, turismo))
        merged = engine.dedupe_similar_events([sagrefvg, turismo], "Udine")
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "TurismoFVG")
        self.assertEqual(merged[0]["alternate_sources"], ["TurismoFVG", "SagreFVG"])

    def test_repeated_program_dates_use_full_official_event_range(self):
        event_url = "https://www.turismofvg.it/eventi/sagra-dell-assunta-498528"
        links = [
            {
                "title": "Sagra dell'Assunta",
                "url": event_url,
                "start": 0,
                "end": 20,
                "extracted_date": date,
                "place": "Porcia",
                "classification": engine.classify_event("Sagra dell'Assunta"),
                "provider_categories": "Feste tradizionali",
                "provider_category_list": ["Feste tradizionali"],
            }
            for date in ("9 agosto 2026", "14 agosto 2026")
        ]
        detail = {
            "date": "venerdi 31 luglio 2026 - domenica 16 agosto 2026",
            "event_city": "Porcia",
            "place": "Porcia",
            "venue": "Centro Pastorale Giovanni Paolo II",
            "description": "Festa tradizionale con stand e musica.",
            "provider_categories": "Feste tradizionali",
            "provider_category_list": ["Feste tradizionali"],
            **engine.classify_event("Sagra dell'Assunta"),
        }

        with (
            patch.object(engine, "resolve_turismofvg_locality_id", return_value="2090"),
            patch.object(
                engine,
                "resolve_turismofvg_nearby_locality_ids",
                return_value=["2090", "2087"],
            ),
            patch.object(
                engine,
                "turismofvg_request_specs",
                return_value=[
                    {
                        "url": engine.TURISMOFVG_EVENTS_FILTER_URL,
                        "params": {"locality": "2087"},
                        "topic": "",
                        "classification": None,
                    }
                ],
            ),
            patch.object(engine.requests, "get", return_value=FakeResponse()),
            patch.object(engine, "extract_turismofvg_card_links", return_value=links),
            patch.object(engine, "find_context", return_value="Sagra tradizionale a Porcia"),
            patch.object(engine, "fetch_turismofvg_event_detail", return_value=detail) as fetch_detail,
            patch.object(engine, "geocode_event_place", return_value=(45.96301, 12.61642)),
        ):
            events = engine.fetch_turismofvg_events(
                "Pordenone",
                limit=10,
                origin_lat=45.9567,
                origin_lon=12.6605,
            )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["title"], "Sagra dell'Assunta")
        self.assertEqual(events[0]["event_city"], "Porcia")
        self.assertEqual(
            events[0]["date"],
            "venerdi 31 luglio 2026 - domenica 16 agosto 2026",
        )
        self.assertEqual(events[0]["category"], "sagra")
        self.assertEqual(events[0]["description"], "Festa tradizionale con stand e musica.")
        fetch_detail.assert_called_once_with(event_url, {"User-Agent": "Meteo-Friul-App/1.0"})

    def test_single_day_traditional_card_checks_full_official_event_range(self):
        event_url = "https://www.turismofvg.it/eventi/31-ed-festeggiamenti-al-parco-burgos"
        links = [
            {
                "title": "31^ ed. Festeggiamenti al Parco Burgos",
                "url": event_url,
                "start": 0,
                "end": 20,
                "extracted_date": "22 agosto 2026",
                "place": "Zoppola",
                "classification": engine.classify_event("Concerto", "Musica"),
                "provider_categories": "Musica",
                "provider_category_list": ["Musica"],
            }
        ]
        detail = {
            "date": "giovedi 20 agosto 2026 - domenica 30 agosto 2026",
            "event_city": "Zoppola",
            "place": "Castions di Zoppola",
            "venue": "Parco Burgos",
            "description": "Programma completo dei festeggiamenti.",
            "provider_categories": "Musica, Enogastronomia, Feste tradizionali",
            "provider_category_list": [
                "Musica",
                "Enogastronomia",
                "Feste tradizionali",
            ],
            **engine.classify_event("Festeggiamenti", "Feste tradizionali"),
        }

        with (
            patch.object(engine, "resolve_turismofvg_locality_id", return_value="2090"),
            patch.object(engine, "resolve_turismofvg_nearby_locality_ids", return_value=[]),
            patch.object(
                engine,
                "turismofvg_request_specs",
                return_value=[
                    {
                        "url": engine.TURISMOFVG_EVENTS_FILTER_URL,
                        "params": {"locality": "2090"},
                        "topic": "",
                        "classification": None,
                    }
                ],
            ),
            patch.object(engine.requests, "get", return_value=FakeResponse()),
            patch.object(engine, "extract_turismofvg_card_links", return_value=links),
            patch.object(engine, "find_context", return_value="Festeggiamenti a Castions"),
            patch.object(engine, "fetch_turismofvg_event_detail", return_value=detail) as fetch_detail,
            patch.object(engine, "geocode_event_place", return_value=(45.9749, 12.8007)),
        ):
            events = engine.fetch_turismofvg_events(
                "Pordenone",
                limit=10,
                origin_lat=45.9567,
                origin_lon=12.6605,
            )

        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0]["date"],
            "giovedi 20 agosto 2026 - domenica 30 agosto 2026",
        )
        self.assertEqual(events[0]["event_city"], "Zoppola")
        self.assertEqual(events[0]["venue"], "Parco Burgos")
        fetch_detail.assert_called_once_with(event_url, {"User-Agent": "Meteo-Friul-App/1.0"})

    def test_turismofvg_fetch_follows_server_pagination_and_finds_ongoing_event(self):
        first_url = "https://www.turismofvg.it/eventi?category=3588&locality=1874"
        next_url = f"{first_url}&page=1"
        first_html = f"""
            page-zero
            <a href="/eventi?category=3588&amp;locality=1874&amp;page=1">
              <strong>carica altri eventi</strong>
            </a>
        """
        second_html = "page-one"

        def link(title, url):
            return {
                "title": title,
                "url": url,
                "start": 0,
                "end": 20,
                "extracted_date": "dal 27 giugno al 11 ottobre 2026",
                "place": "Trieste",
                "classification": engine.classify_event(title, "Mostre"),
                "provider_categories": "Mostre",
                "provider_category_list": ["Mostre"],
            }

        responses = [
            FakeResponse(first_html, first_url),
            FakeResponse(second_html, next_url),
        ]

        with (
            patch.object(engine, "resolve_turismofvg_locality_id", return_value="1874"),
            patch.object(engine, "resolve_turismofvg_nearby_locality_ids", return_value=[]),
            patch.object(
                engine,
                "turismofvg_request_specs",
                return_value=[
                    {
                        "url": engine.TURISMOFVG_EVENTS_URL,
                        "params": {"category": "3588", "locality": "1874"},
                        "topic": "Mostre",
                        "classification": engine.turismofvg_topic_classification("Mostre"),
                    }
                ],
            ),
            patch.object(engine.requests, "get", side_effect=responses) as get,
            patch.object(
                engine,
                "extract_turismofvg_card_links",
                side_effect=lambda html: [
                    link(
                        "Evento iniziale",
                        "https://www.turismofvg.it/eventi/evento-iniziale",
                    )
                ]
                if "page-zero" in html
                else [
                    link(
                        "Ila Bêka - Fotoni",
                        "https://www.turismofvg.it/eventi/ila-beka-fotoni-493895",
                    )
                ],
            ),
            patch.object(engine, "find_context", return_value="Mostre a Trieste"),
            patch.object(engine, "geocode_event_place", return_value=(45.6495, 13.7768)),
        ):
            events = engine.fetch_turismofvg_events("Trieste", limit=100)

        self.assertIn("Ila Bêka - Fotoni", [event["title"] for event in events])
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[1].args[0], next_url)

    def test_strict_turismofvg_page_retries_one_transient_timeout(self):
        with (
            patch.object(engine, "resolve_turismofvg_locality_id", return_value="1874"),
            patch.object(engine, "resolve_turismofvg_nearby_locality_ids", return_value=[]),
            patch.object(
                engine,
                "turismofvg_request_specs",
                return_value=[
                    {
                        "url": engine.TURISMOFVG_EVENTS_URL,
                        "params": {"locality": "1874"},
                        "topic": "",
                        "classification": None,
                    }
                ],
            ),
            patch.object(
                engine.requests,
                "get",
                side_effect=[requests.ReadTimeout("transient"), FakeResponse()],
            ) as get,
            patch("app.events.http_client.time.sleep") as sleep,
        ):
            events = engine.fetch_turismofvg_events(
                "Trieste", limit=100, strict=True
            )

        self.assertEqual(events, [])
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once()

    def test_strict_turismofvg_page_remains_fail_closed_after_retry(self):
        with (
            patch.object(engine, "resolve_turismofvg_locality_id", return_value="1874"),
            patch.object(engine, "resolve_turismofvg_nearby_locality_ids", return_value=[]),
            patch.object(
                engine,
                "turismofvg_request_specs",
                return_value=[
                    {
                        "url": engine.TURISMOFVG_EVENTS_URL,
                        "params": {"locality": "1874"},
                        "topic": "",
                        "classification": None,
                    }
                ],
            ),
            patch.object(
                engine.requests,
                "get",
                side_effect=[
                    requests.ReadTimeout("first"),
                    requests.ReadTimeout("second"),
                ],
            ) as get,
            patch("app.events.http_client.time.sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "pagina non acquisita"):
                engine.fetch_turismofvg_events(
                    "Trieste", limit=100, strict=True
                )

        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once()

    def test_turismofvg_locality_network_failure_is_not_cached_for_seven_days(self):
        headers = {"User-Agent": "Meteo-Friul-App/1.0"}
        with patch.object(
            engine.requests,
            "get",
            side_effect=[
                requests.ConnectionError("first"),
                requests.ConnectionError("second"),
            ],
        ) as get:
            self.assertEqual(engine.fetch_turismofvg_locality_ids(headers), {})
            self.assertEqual(engine.fetch_turismofvg_locality_ids(headers), {})

        self.assertEqual(get.call_count, 2)
        self.assertNotIn("turismofvg-locality-ids", engine.turismofvg_locality_cache)

    def test_sagrefvg_api_queries_overlapping_events_instead_of_bounded_end_dates(self):
        target = {
            "title": "Tiezzo di Azzano X (PN) – Festa Paesana 2026",
            "url": (
                "https://sagrefvg.it/sagre/"
                "tiezzo-di-azzano-x-pn-festa-paesana-2025-duplicate-1/"
            ),
            "description": "Festa tradizionale nel campo dell'oratorio.",
            "start_date": "2026-08-21 08:00:00",
            "end_date": "2026-09-06 23:30:00",
            "venue": {
                "venue": "Tiezzo",
                "address": "Piazza Garibaldi",
                "city": "Tiezzo",
                "geo_lat": 45.8918777,
                "geo_lng": 12.6728855,
            },
        }

        with patch.object(
            engine.requests,
            "get",
            return_value=FakeJsonResponse({"events": [target]}),
        ) as get:
            events = engine.fetch_sagrefvg_events_api(limit=100)

        params = get.call_args.kwargs["params"]
        today = date.today()
        horizon = today + engine.timedelta(days=engine.EVENTS_UPCOMING_WINDOW_DAYS)

        self.assertNotIn("start_date", params)
        self.assertNotIn("end_date", params)
        self.assertEqual(params["ends_after"], f"{today.isoformat()} 00:00:00")
        self.assertEqual(params["starts_before"], f"{horizon.isoformat()} 23:59:59")
        self.assertEqual(len(events), 1)
        self.assertIn("Tiezzo di Azzano X", events[0]["title"])
        self.assertEqual(events[0]["event_city"], "Tiezzo")
        self.assertEqual(events[0]["venue"], "Tiezzo")
        self.assertEqual(events[0]["address"], "Piazza Garibaldi")
        self.assertEqual(events[0]["date"], "21 agosto 2026 - 6 settembre 2026")
        self.assertEqual(events[0]["lat"], 45.8918777)
        self.assertEqual(events[0]["lon"], 12.6728855)
        self.assertEqual(events[0]["location_confidence"], "exact")

    def test_explicit_current_sagrefvg_date_wins_over_historical_url_year(self):
        today = date.today()
        start = today + engine.timedelta(days=1)
        end = today + engine.timedelta(days=17)
        current_year = today.year
        historical_year = current_year - 1
        event = {
            "title": f"Tiezzo di Azzano X (PN) – Festa Paesana {current_year}",
            "url": (
                "https://sagrefvg.it/sagre/"
                f"tiezzo-di-azzano-x-pn-festa-paesana-{historical_year}-duplicate-1/"
            ),
            "date": (
                f"{engine.format_numeric_date(start.strftime('%d/%m/%Y'))} - "
                f"{engine.format_numeric_date(end.strftime('%d/%m/%Y'))}"
            ),
            "source": "SagreFVG",
        }

        self.assertEqual(engine.filter_past_events([event]), [event])

    def test_historical_url_year_still_blocks_ambiguous_sagrefvg_date(self):
        today = date.today()
        start = today + engine.timedelta(days=1)
        end = today + engine.timedelta(days=5)
        historical_year = today.year - 1
        start_without_year = engine.format_numeric_date(start.strftime("%d/%m/%Y")).rsplit(" ", 1)[0]
        end_without_year = engine.format_numeric_date(end.strftime("%d/%m/%Y")).rsplit(" ", 1)[0]
        event = {
            "title": "Tiezzo di Azzano X (PN) – Festa Paesana",
            "url": f"https://sagrefvg.it/sagre/tiezzo-festa-paesana-{historical_year}/",
            "date": f"{start_without_year} - {end_without_year}",
            "source": "SagreFVG",
        }

        self.assertEqual(engine.filter_past_events([event]), [])

    def test_local_events_response_cache_key_does_not_change_with_parser_version(self):
        original = engine.local_events_cache_key(
            "Pordenone",
            100,
            45.9567,
            12.6605,
        )

        with patch.object(engine, "EVENTS_CACHE_VERSION", "v40-parser-change"):
            after_parser_update = engine.local_events_cache_key(
                "Pordenone",
                100,
                45.9567,
                12.6605,
            )

        self.assertEqual(after_parser_update, original)

    def test_response_contract_upgrade_keeps_shared_persistent_cache_key(self):
        original = engine.local_events_cache_key(
            "Pordenone",
            100,
            45.9567,
            12.6605,
        )

        with patch.object(engine, "EVENTS_RESPONSE_CONTRACT_VERSION", "future-contract"):
            after_contract_update = engine.local_events_cache_key(
                "Pordenone",
                100,
                45.9567,
                12.6605,
            )

        self.assertEqual(after_contract_update, original)
        self.assertIn("v40-without-anteprima-sagre", original)

    def test_cached_tiezzo_duplicate_is_upgraded_and_merged_on_read(self):
        cached = {
            "city": "Pordenone",
            "events": [
                {
                    "title": "37^ Festa paesana di Tiezzo",
                    "date": "21 agosto 2026 - 6 settembre 2026",
                    "place": "Azzano Decimo",
                    "event_city": "Azzano Decimo",
                    "venue": "Campo dell'oratorio di Tiezzo Piazza Garibaldi",
                    "lat": 45.9092,
                    "lon": 12.7144,
                    "location_confidence": "municipality",
                    "source": "TurismoFVG",
                    "category": "sagra",
                },
                {
                    "title": "Tiezzo di Azzano X (PN) – Festa Paesana 2026",
                    "date": "21 agosto 2026 - 6 settembre 2026",
                    "place": "Tiezzo",
                    "event_city": "Tiezzo",
                    "lat": 45.8918777,
                    "lon": 12.6728855,
                    "source": "SagreFVG",
                    "category": "sagra",
                },
            ],
            "source": "multi",
            "sources": ["TurismoFVG", "SagreFVG"],
            "cache": {"status": "fresh"},
        }

        response = engine.clone_local_events_response_with_cache(cached, "fresh")

        self.assertEqual(len(response["events"]), 1)
        event = response["events"][0]
        self.assertEqual(event["source"], "TurismoFVG")
        self.assertEqual(event["alternate_sources"], ["TurismoFVG", "SagreFVG"])
        self.assertEqual(event["lat"], 45.8918777)
        self.assertEqual(event["lon"], 12.6728855)
        self.assertEqual(event["location_confidence"], "exact")
        self.assertEqual(response["sources"], ["TurismoFVG"])

    def test_first_useful_partial_response_can_seed_shared_cache(self):
        candidate = self.local_events_response(
            count=8,
            status="partial",
            completed=["sagrefvg", "proloco"],
            pending=["turismo"],
        )

        self.assertTrue(engine.should_replace_local_events_cache(candidate, None))

    def test_partial_response_does_not_replace_complete_cache(self):
        candidate = self.local_events_response(
            count=12,
            status="partial",
            completed=["sagrefvg", "proloco"],
            pending=["turismo"],
        )
        existing = self.local_events_response(
            count=8,
            status="fresh",
            completed=["sagrefvg", "proloco", "turismo"],
        )

        self.assertFalse(
            engine.should_replace_local_events_cache(
                candidate,
                existing,
                existing_age=engine.EVENTS_STALE_TTL + 1,
            )
        )

    def test_more_complete_partial_response_can_improve_partial_cache(self):
        candidate = self.local_events_response(
            count=9,
            status="partial",
            completed=["sagrefvg", "proloco", "eventifvg"],
            pending=["turismo"],
        )
        existing = self.local_events_response(
            count=8,
            status="partial",
            completed=["sagrefvg", "proloco"],
            pending=["turismo", "eventifvg"],
        )

        self.assertTrue(engine.should_replace_local_events_cache(candidate, existing))

    def test_identical_partial_response_does_not_rewrite_shared_cache(self):
        candidate = self.local_events_response(
            count=8,
            status="partial",
            completed=["sagrefvg", "proloco"],
            pending=["turismo"],
        )
        existing = self.local_events_response(
            count=8,
            status="partial",
            completed=["sagrefvg", "proloco"],
            pending=["turismo"],
        )

        self.assertFalse(engine.should_replace_local_events_cache(candidate, existing))

    def test_initial_partial_refresh_is_persisted_and_keeps_partial_outcome(self):
        candidate = self.local_events_response(
            count=8,
            status="partial",
            completed=["sagrefvg", "proloco"],
            pending=["turismo"],
        )
        key = "pordenone-partial-cache-test"

        with (
            patch.object(engine, "local_events_cache_key", return_value=key),
            patch.object(engine, "load_best_local_events_cache_entry", return_value=None),
            patch.object(engine, "build_local_events_response", return_value=candidate),
            patch.object(engine, "set_cache") as set_cache,
            patch.object(engine, "store_persistent_local_events_cache", return_value=True) as store,
        ):
            response = engine.refresh_local_events_cache(
                "Pordenone",
                100,
                45.9567,
                12.6605,
            )

        self.assertIs(response, candidate)
        set_cache.assert_called_once_with(engine.local_events_response_cache, key, candidate)
        store.assert_called_once_with(key, candidate)
        self.assertEqual(engine.local_events_recent_refresh_outcome(key), "partial")

    def test_refresh_outcome_expires_before_a_new_source_attempt(self):
        with patch.object(engine.time, "time", return_value=100):
            engine.set_local_events_refresh_outcome("pordenone", "source_unavailable")

        with patch.object(engine.time, "time", return_value=161):
            self.assertIsNone(engine.local_events_recent_refresh_outcome("pordenone"))


if __name__ == "__main__":
    unittest.main()
