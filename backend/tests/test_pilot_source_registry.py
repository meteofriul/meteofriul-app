"""Experimental collectors must never become public merely by being imported."""
import unittest
from datetime import date
from app.events.pilot_catalog import PILOT_PROJECT
from app.events.pilot_sources import source_adapters
from app.events.pilot_source_policy import APPROVED_SOURCES, validate_candidate


EXPECTED_INTEGRATED_SOURCES = {
    'TurismoFVG', 'Pordenonelegge', 'Azalea', 'CSS Udine',
    'Pordenone Pensa', 'Teatro Verdi Pordenone', 'Teatro Verdi Trieste',
    'Paesi in Festa', 'SagreFVG', 'Le Giornate del Cinema Muto',
    'Villa Manin',
    'Magazzino delle Idee',
    'MESS',
    'Galleria Spazzapan',
    'Barcolana',
}


class RegistryBoundaryTests(unittest.TestCase):
    def test_runtime_and_publication_allowlists_match(self):
        self.assertEqual(set(APPROVED_SOURCES), EXPECTED_INTEGRATED_SOURCES)
        self.assertEqual(set(source_adapters(PILOT_PROJECT)), EXPECTED_INTEGRATED_SOURCES)

    def test_unstudied_sources_remain_diagnostic_only(self):
        for name in ('ERPAC', 'Pro Loco FVG',
                     'Anteprima Sagre', 'EventiFVG'):
            with self.subTest(source=name):
                self.assertNotIn(name, source_adapters(PILOT_PROJECT))
                self.assertEqual(validate_candidate({'source': name}, today=date(2026, 9, 7)), ['unapproved_source'])
