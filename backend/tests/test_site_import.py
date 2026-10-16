import unittest

from fastapi.testclient import TestClient

from app.api.promotions import get_site_import_service
from app.infrastructure.ads_admin_auth import AdsAdminContext, require_ads_admin
from app.main import create_app
from app.services.site_import import SiteImportError, _category_for, _validated_public_url, extract_site_fields


HTML = """
<!doctype html>
<html>
  <head>
    <title>Ale Hair Studio | Pordenone</title>
    <meta property="og:title" content="Capelli su misura da Ale Hair Studio">
    <meta property="og:description" content="Tagli, colore e trattamenti professionali nel centro di Pordenone.">
    <meta property="og:image" content="/media/salone.webp">
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "HairSalon",
        "name": "Ale Hair Studio",
        "legalName": "Ale Hair Studio SRL",
        "telephone": "+39 0434 123456",
        "email": "amministrazione@alehair.example",
        "vatID": "IT01234567890",
        "taxID": "01234567890",
        "address": {
          "@type": "PostalAddress",
          "streetAddress": "Via Roma 12",
          "postalCode": "33170",
          "addressLocality": "Pordenone",
          "addressRegion": "PN"
        }
      }
    </script>
  </head>
  <body>Partita IVA 01234567890</body>
</html>
"""


class SiteImportExtractionTests(unittest.TestCase):
    def test_extracts_card_and_billing_fields(self):
        result = extract_site_fields(HTML, "https://alehair.example/")
        fields = result["fields"]

        self.assertEqual(fields["businessName"], "Ale Hair Studio")
        self.assertEqual(fields["legalName"], "Ale Hair Studio SRL")
        self.assertEqual(fields["businessAddress"], "Via Roma 12")
        self.assertEqual(fields["city"], "Pordenone")
        self.assertEqual(fields["category"], "Benessere e persona")
        self.assertEqual(fields["contactPhone"], "+39 0434 123456")
        self.assertEqual(fields["vatNumber"], "01234567890")
        self.assertEqual(fields["taxCode"], "01234567890")
        self.assertEqual(fields["postalCode"], "33170")
        self.assertEqual(fields["province"], "PN")
        self.assertEqual(fields["billingEmail"], "amministrazione@alehair.example")
        self.assertEqual(fields["destinationUrl"], "https://alehair.example/")
        self.assertEqual(result["imageUrl"], "https://alehair.example/media/salone.webp")

    def test_classifies_media_and_marketing_sites(self):
        self.assertEqual(
            _category_for({"AdvertisingAgency"}, "Strategie di comunicazione"),
            "Marketing, comunicazione e media",
        )
        self.assertEqual(_category_for({"Photographer"}, "Ritratti"), "Fotografia e video")

    def test_blocks_private_and_local_urls(self):
        for url in ("http://127.0.0.1/", "http://[::1]/", "http://localhost/"):
            with self.subTest(url=url), self.assertRaises(SiteImportError) as error:
                _validated_public_url(url)
            self.assertEqual(error.exception.code, "site_import_url_unsafe")

    def test_requires_http_or_https(self):
        with self.assertRaises(SiteImportError) as error:
            _validated_public_url("file:///etc/passwd")
        self.assertEqual(error.exception.code, "site_import_url_invalid")


class SiteImportApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_endpoint_requires_ads_admin_and_returns_imported_draft(self):
        denied = self.client.post(
            "/api/admin/promotions/import-site",
            json={"url": "https://alehair.example/"},
        )
        self.assertEqual(denied.status_code, 401)

        class FakeImporter:
            def import_site(self, url):
                return {"finalUrl": url, "fields": {"businessName": "Ale Hair Studio"}, "image": None, "warnings": []}

        self.app.dependency_overrides[require_ads_admin] = lambda: AdsAdminContext(
            uid="admin",
            email="admin@example.test",
            claims={"adsAdmin": True},
        )
        self.app.dependency_overrides[get_site_import_service] = lambda: FakeImporter()
        accepted = self.client.post(
            "/api/admin/promotions/import-site",
            json={"url": "https://alehair.example/"},
        )

        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["fields"]["businessName"], "Ale Hair Studio")


if __name__ == "__main__":
    unittest.main()
