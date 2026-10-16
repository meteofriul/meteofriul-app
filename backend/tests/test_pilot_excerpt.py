import unittest

from app.events.pilot_excerpt import (
    attributed_excerpt,
    extract_meta_excerpt,
    make_excerpt,
    remove_cross_page_duplicates,
)


class PilotExcerptTests(unittest.TestCase):
    def test_excerpt_is_plain_bounded_source_text(self):
        text = "<p>" + "Una descrizione ufficiale dell'evento. " * 12 + "</p>"
        excerpt = make_excerpt(text)
        self.assertLessEqual(len(excerpt), 180)
        self.assertNotIn("<p>", excerpt)
        self.assertTrue(excerpt.endswith(".") or excerpt.endswith("…"))

    def test_html_spacing_does_not_split_italian_apostrophes(self):
        self.assertEqual(make_excerpt("L ’evento racconta la città e la sua storia."),
                         "L’evento racconta la città e la sua storia.")

    def test_meta_description_attribute_order_is_irrelevant(self):
        html = '<meta content="Un racconto teatrale dedicato alla città e ai suoi abitanti." name="description">'
        self.assertEqual(
            extract_meta_excerpt(html, title="Concerto"),
            "Un racconto teatrale dedicato alla città e ai suoi abitanti.",
        )

    def test_attribution_requires_an_https_source(self):
        self.assertEqual(attributed_excerpt(
            "Descrizione ufficiale sufficientemente dettagliata.",
            source_name="Fonte", source_url="http://example.org/evento",
        ), {})
        fields = attributed_excerpt(
            "Descrizione ufficiale sufficientemente dettagliata.",
            source_name="Fonte", source_url="https://example.org/evento",
            checked_at="2026-09-22T10:00:00+00:00",
        )
        self.assertEqual(fields["description_source_name"], "Fonte")
        self.assertEqual(fields["description_source_url"], "https://example.org/evento")

    def test_repeated_cross_page_meta_copy_is_treated_as_boilerplate(self):
        repeated = "La descrizione generica del sito usata in tutte le pagine."
        events = [
            {
                "description_excerpt": repeated,
                "description_source_name": "Fonte",
                "description_source_url": f"https://example.org/evento-{index}",
            }
            for index in range(2)
        ]
        remove_cross_page_duplicates(events)
        self.assertTrue(all("description_excerpt" not in event for event in events))

    def test_repeated_performances_from_one_page_keep_the_excerpt(self):
        events = [{
            "description_excerpt": "La descrizione ufficiale dello spettacolo.",
            "description_source_name": "Fonte",
            "description_source_url": "https://example.org/spettacolo",
        } for _ in range(2)]
        remove_cross_page_duplicates(events)
        self.assertTrue(all("description_excerpt" in event for event in events))


if __name__ == "__main__":
    unittest.main()
