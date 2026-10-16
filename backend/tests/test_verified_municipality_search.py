import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.national_municipalities import NationalMunicipalityCatalogError
from app.services.verified_municipality_search import search_verified_municipalities


class VerifiedMunicipalitySearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def test_urbino_and_rome_have_exact_catalog_identities(self):
        for query, code, province in (
            ("Urbino", "041067", "PU"),
            ("Roma", "058091", "RM"),
        ):
            with self.subTest(query=query):
                result = self.client.get(
                    "/api/location/municipalities/search", params={"q": query}
                )
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()[0]["istatCode"], code)
                self.assertEqual(result.json()[0]["province"], province)
                self.assertEqual(result.json()[0]["providerId"], code)
                self.assertIsNotNone(result.json()[0]["latitude"])

    def test_fvg_code_is_present_without_changing_regional_search(self):
        result = self.client.get(
            "/api/location/municipalities/search", params={"q": "Pordenone"}
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()[0]["istatCode"], "093033")
        self.assertEqual(result.json()[0]["admin1"], "Friuli Venezia Giulia")

    def test_homonyms_are_not_collapsed_or_guessed(self):
        matches = search_verified_municipalities("Castro")
        self.assertEqual(
            [(item.istatCode, item.province) for item in matches[:2]],
            [("016065", "BG"), ("075096", "LE")],
        )
        self.assertEqual(
            [(item.istatCode, item.province) for item in search_verified_municipalities("Castro BG")],
            [("016065", "BG")],
        )

    def test_catalog_failure_is_explicit_and_never_returns_an_unverified_code(self):
        with patch(
            "app.api.location.search_verified_municipalities",
            side_effect=NationalMunicipalityCatalogError("catalog damaged"),
        ):
            result = self.client.get(
                "/api/location/municipalities/search", params={"q": "Urbino"}
            )
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.json()["detail"]["code"], "municipality_catalog_unavailable")


if __name__ == "__main__":
    unittest.main()
