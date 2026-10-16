import json
import unittest
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import urlsplit

import requests

from app.services.webcams import (
    WebcamManifestService,
    load_shadow_webcam_manifest,
    validate_webcam_manifest,
)


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = WORKSPACE_ROOT / "backend" / "app" / "data"
PUBLIC_ROOT = WORKSPACE_ROOT / "frontend" / "public"
PHOTO_DATA_ROOT = WORKSPACE_ROOT / "frontend" / "src" / "data" / "discover"
CATALOG_FILES = {
    "active": "webcams_active.json",
    "candidates": "webcams_candidates.json",
    "suspended": "webcams_suspended.json",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_identity(url):
    parsed = urlsplit(url)
    return parsed.hostname.lower(), parsed.path.rstrip("/"), parsed.query


class WebcamCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_catalogs = {
            name: read_json(DATA_ROOT / filename)
            for name, filename in CATALOG_FILES.items()
        }
        cls.catalogs = {
            "active": validate_webcam_manifest(cls.raw_catalogs["active"]),
            **{
                name: load_shadow_webcam_manifest(DATA_ROOT / CATALOG_FILES[name])
                for name in ("candidates", "suspended")
            },
        }
        cls.active_by_id = {
            record.id: record for record in cls.catalogs["active"].records
        }
        cls.photo_manifest = read_json(PHOTO_DATA_ROOT / "municipalityPhotos.json")
        cls.photo_credits = read_json(
            PHOTO_DATA_ROOT / "municipalityPhotoCredits.json"
        )

    def test_real_catalogs_validate_with_reviewed_counts(self):
        self.assertEqual(self.catalogs["active"].version, 32)
        for name, expected_count in (
            ("active", 35),
            ("candidates", 4),
            ("suspended", 2),
        ):
            with self.subTest(catalog=name):
                catalog = self.catalogs[name]
                raw_key = "webcams" if name == "active" else "candidates"
                self.assertEqual(len(catalog.records), expected_count)
                self.assertEqual(
                    len(self.raw_catalogs[name][raw_key]), expected_count
                )
                self.assertEqual(
                    catalog.mode, "active" if name == "active" else "shadow"
                )

    def test_ids_are_unique_and_shared_source_pages_are_explicitly_reviewed(self):
        ids = {}
        sources = {}
        for name, catalog in self.catalogs.items():
            for record in catalog.records:
                with self.subTest(catalog=name, webcam=record.id):
                    self.assertNotIn(record.id, ids)
                    identity = source_identity(record.sourcePage)
                    ids[record.id] = name
                    sources.setdefault(identity, []).append(record.id)

        shared_sources = {
            identity: webcam_ids
            for identity, webcam_ids in sources.items()
            if len(webcam_ids) > 1
        }
        self.assertEqual(
            shared_sources,
            {
                source_identity("https://www.meteo.fvg.it/webcam_img.php?ln=it"): [
                    "barcis-paese",
                    "cividale-campanile-ex-monastero",
                    "cividale-piazza-duomo",
                    "cividale-piazza-paolo-diacono",
                    "spilimbergo-duomo",
                ],
                source_identity("https://www.cisartrieste.it/meteo-m-grisa/"): [
                    "cisar-monte-grisa-sud-est",
                    "cisar-monte-grisa-sud-ovest",
                ],
                source_identity(
                    "https://www.comune.monfalcone.go.it/it/novita-220905/"
                    "notizie-220906/condizioni-del-vento-marina-julia-21786"
                ): [
                    "monfalcone-marina-julia-1",
                    "monfalcone-marina-julia-2",
                ],
            },
        )

    def test_every_fallback_is_an_existing_reviewed_and_credited_local_photo(self):
        for name, catalog in self.catalogs.items():
            for record in catalog.records:
                with self.subTest(catalog=name, webcam=record.id):
                    photo_url = record.fallbackImageUrl
                    self.assertRegex(
                        photo_url, r"^/municipalities/photos/\d{6}-photo\.webp$"
                    )
                    photo_path = (PUBLIC_ROOT / photo_url.lstrip("/")).resolve()
                    self.assertTrue(photo_path.is_relative_to(PUBLIC_ROOT.resolve()))
                    self.assertTrue(photo_path.is_file(), str(photo_path))
                    with photo_path.open("rb") as photo:
                        header = photo.read(12)
                    self.assertEqual(header[:4], b"RIFF")
                    self.assertEqual(header[8:12], b"WEBP")

                    runtime_photos = [
                        photo for photo in self.photo_manifest["photos"]
                        if photo["localUrl"] == photo_url
                    ]
                    credits = [
                        credit for credit in self.photo_credits["photos"]
                        if credit["localUrl"] == photo_url
                    ]
                    self.assertEqual(len(runtime_photos), 1)
                    self.assertEqual(len(credits), 1)
                    credit = credits[0]
                    self.assertEqual(credit["istatCode"], runtime_photos[0]["istatCode"])
                    self.assertEqual(credit["municipality"], record.municipality)
                    self.assertEqual(credit["reviewStatus"], "approved")
                    for field in (
                        "author", "license", "licenseUrl", "sourcePageUrl", "assetUrl"
                    ):
                        self.assertTrue(credit.get(field, "").strip(), field)
                    for language in ("it", "fur"):
                        self.assertTrue(
                            credit.get("modifications", {}).get(language, "").strip()
                        )

    def test_only_reviewed_snapshots_have_images_with_explicit_source_and_attribution(self):
        raw_by_id = {
            record["id"]: record for record in self.raw_catalogs["active"]["webcams"]
        }
        self.assertEqual(
            {record.id for record in self.catalogs["active"].records if record.imageUrl},
            {
                "sacile", "grado-al-bosco",
                "cividale-campanile-ex-monastero", "cividale-piazza-duomo",
                "cividale-piazza-paolo-diacono",
                "lignano-punta-faro", "lignano-spiaggia-centrale",
                "lignano-piazza-fontana", "lignano-pineta-pontile",
                "lignano-riviera",
                "cisar-monte-grisa-sud-est", "cisar-monte-grisa-sud-ovest",
                "cisar-lanterna-nord",
                "forni-varmost",
                "piancavallo-panorama",
                "piancavallo-nevelandia",
                "sappada-panorama",
                "sella-nevea-canin",
                "san-daniele-centro",
                "trieste-san-giusto",
                "zoncolan-panorama",
                "udine-panorama-castello",
                "gemona-centro",
                "trieste-miramare",
                "moruzzo-panorama",
                "spilimbergo-duomo",
                "monfalcone-marina-julia-1",
                "monfalcone-marina-julia-2",
                "barcis-paese",
                "claut-pradut",
            },
        )
        for record in self.catalogs["active"].records:
            with self.subTest(webcam=record.id):
                self.assertEqual(record.health, "ok")
                self.assertEqual(urlsplit(record.sourcePage).scheme, "https")
                self.assertTrue(record.provider.strip())
                if record.id != "gemona-centro":
                    self.assertIsNone(record.playerUrl)
                    self.assertNotIn("playerUrl", raw_by_id[record.id])
                    self.assertNotIn("player_url", raw_by_id[record.id])
                if record.id == "grado-al-bosco":
                    self.assertEqual(
                        record.imageUrl,
                        "https://cam.kitelifefvg.it/webcam_grado.php",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(
                        record.attribution,
                        "Residence Hotel Al Bosco · Kite Life FVG",
                    )
                    self.assertEqual(
                        record.attributionUrl,
                        "https://www.kitelifefvg.it/webcam/",
                    )
                    self.assertEqual(
                        record.sourcePage,
                        "https://grado.it/it/scoprire-grado/webcam",
                    )
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/031009-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id == "sacile":
                    self.assertEqual(
                        record.imageUrl,
                        "https://sacilemeteo.altervista.org/hik/webcam_r.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.attribution, "© Luigi Carbonera")
                    self.assertEqual(
                        record.attributionUrl,
                        "https://sacilemeteo.altervista.org/hik/webcam_hik.html",
                    )
                    self.assertEqual(record.sourcePage, record.attributionUrl)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/093037-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id.startswith("monfalcone-marina-julia-"):
                    expected_monfalcone = {
                        "monfalcone-marina-julia-1": (
                            "Monfalcone - Marina Julia 1",
                            "Marina Julia · vista sud-est",
                            45.77413,
                            13.52914,
                            "monfalcone-cam-marinaJulia1.php",
                        ),
                        "monfalcone-marina-julia-2": (
                            "Monfalcone - Marina Julia 2",
                            "Marina Julia · vista sud-ovest",
                            45.77274,
                            13.52759,
                            "monfalcone-cam-marinaJulia2.php",
                        ),
                    }
                    name, area, lat, lon, image_name = expected_monfalcone[record.id]
                    self.assertEqual(record.name, name)
                    self.assertEqual(record.area, area)
                    self.assertEqual((record.lat, record.lon), (lat, lon))
                    self.assertEqual(
                        record.imageUrl,
                        "https://anemometro.comune.monfalcone.go.it/" + image_name,
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.provider, "Comune di Monfalcone")
                    self.assertEqual(record.attribution, "CC BY 4.0 predefinita")
                    self.assertEqual(
                        record.attributionUrl,
                        "https://www.comune.monfalcone.go.it/it/note-legali-30726",
                    )
                    self.assertEqual(
                        record.sourcePage,
                        "https://www.comune.monfalcone.go.it/it/novita-220905/"
                        "notizie-220906/condizioni-del-vento-marina-julia-21786",
                    )
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/031012-photo.webp",
                    )
                    self.assertEqual(record.mapClusterId, "monfalcone-marina-julia")
                    self.assertEqual(
                        record.mapClusterLabel, "Monfalcone · Marina Julia"
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id == "gemona-centro":
                    self.assertEqual(record.name, "Gemona del Friuli - Duomo")
                    self.assertEqual(record.area, "Centro storico · Duomo")
                    self.assertEqual(record.provider, "WeatherCam · Meteo System")
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(
                        record.imageUrl,
                        "https://www.meteoproject.it/ftp/webcam/"
                        "gemonadelfriuli/gemona.jpg",
                    )
                    self.assertIsNone(record.playerUrl)
                    self.assertNotIn("playerUrl", raw_by_id[record.id])
                    self.assertEqual(
                        record.sourcePage,
                        "https://www.weathercam.it/webcam/gemona",
                    )
                    self.assertEqual(record.attribution, record.provider)
                    self.assertEqual(record.attributionUrl, record.sourcePage)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/030043-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id.startswith("cividale-"):
                    expected_cividale_images = {
                        "cividale-campanile-ex-monastero": (
                            "CividaleVedutadalcampanile-cividale_campanileexmonastero.jpg"
                        ),
                        "cividale-piazza-duomo": (
                            "CividalePiazzaDuomo-cividale_piazzaduomo.jpg"
                        ),
                        "cividale-piazza-paolo-diacono": (
                            "CividalePiazzaDiacono-cividale_piazzadiacono.jpg"
                        ),
                    }
                    self.assertEqual(
                        record.imageUrl,
                        "https://www.meteo.fvg.it/ext/webcams/webcams/"
                        + expected_cividale_images[record.id],
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.provider, "ARPA FVG - OSMER e GRN")
                    self.assertEqual(record.attribution, "ARPA FVG - OSMER e GRN")
                    self.assertEqual(record.attributionUrl, "https://www.meteo.fvg.it/")
                    self.assertEqual(
                        record.sourcePage,
                        "https://www.meteo.fvg.it/webcam_img.php?ln=it",
                    )
                    self.assertEqual(record.mapClusterId, "cividale-del-friuli")
                    self.assertEqual(record.mapClusterLabel, "Cividale del Friuli")
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/030026-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id.startswith("lignano-"):
                    expected_lignano = {
                        "lignano-punta-faro": (
                            "webcam6.jpg", "webcam-spiaggia-punta-faro",
                        ),
                        "lignano-spiaggia-centrale": (
                            "webcam3.jpg", "webcam-spiaggia-lignano-sabbiadoro",
                        ),
                        "lignano-piazza-fontana": (
                            "webcam4.jpg", "webcam-piazza-fontana-centro",
                        ),
                        "lignano-pineta-pontile": (
                            "webcam2.jpg", "webcam-spiaggia-lignano-pineta",
                        ),
                        "lignano-riviera": ("webcam.jpg", ""),
                    }
                    image_name, page_path = expected_lignano[record.id]
                    self.assertEqual(
                        record.imageUrl,
                        f"https://www.lignanosabbiadoro.com/images/{image_name}",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.attribution, "LignanoSabbiadoro.com")
                    self.assertEqual(record.attributionUrl, record.sourcePage)
                    expected_source = "https://www.lignanosabbiadoro.com/webcam"
                    if page_path:
                        expected_source = f"{expected_source}/{page_path}"
                    self.assertEqual(record.sourcePage, expected_source)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/030049-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id.startswith("cisar-"):
                    expected_cisar = {
                        "cisar-monte-grisa-sud-est": (
                            "Monte Grisa · Sud-est",
                            "https://www.cisartrieste.it/meteo/grisa/cam1.jpg",
                            "https://www.cisartrieste.it/meteo-m-grisa/",
                        ),
                        "cisar-monte-grisa-sud-ovest": (
                            "Monte Grisa · Sud-ovest",
                            "https://www.cisartrieste.it/meteo/grisa/cam2.jpg",
                            "https://www.cisartrieste.it/meteo-m-grisa/",
                        ),
                        "cisar-lanterna-nord": (
                            "Lanterna · Nord",
                            "https://www.cisartrieste.it/meteo/lanterna/cam3.jpg",
                            "https://www.cisartrieste.it/meteo-lanterna/",
                        ),
                    }
                    name, image_url, source_page = expected_cisar[record.id]
                    self.assertEqual(record.name, name)
                    self.assertEqual(record.imageUrl, image_url)
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.provider, "CISAR Trieste APS")
                    self.assertEqual(record.sourcePage, source_page)
                    self.assertEqual(record.attribution, "CISAR Trieste APS")
                    self.assertEqual(record.attributionUrl, source_page)
                    self.assertEqual(record.municipality, "Trieste")
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/032006-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id == "forni-varmost":
                    self.assertEqual(
                        record.imageUrl,
                        "https://panodata.panomax.com/cams/1987/preview_og.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.name, "Forni di Sopra - Malga Varmost")
                    self.assertEqual(record.area, "Malga Varmost")
                    self.assertEqual(record.provider, "Panomax / PromoTurismoFVG")
                    self.assertEqual(
                        record.sourcePage,
                        "https://fornidisopra.panomax.com/",
                    )
                    self.assertEqual(record.attribution, record.provider)
                    self.assertEqual(record.attributionUrl, record.sourcePage)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/030041-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id == "zoncolan-panorama":
                    self.assertEqual(
                        record.imageUrl,
                        "https://panodata.panomax.com/cams/1988/preview_og.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.name, "Monte Zoncolan - Panorama")
                    self.assertEqual(record.area, "Monte Zoncolan · quota 1.750 m")
                    self.assertEqual(record.provider, "Panomax / PromoTurismoFVG")
                    self.assertEqual(record.sourcePage, "https://zoncolan.panomax.com/")
                    self.assertEqual(record.attribution, record.provider)
                    self.assertEqual(record.attributionUrl, record.sourcePage)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/030112-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id == "piancavallo-panorama":
                    self.assertEqual(
                        record.imageUrl,
                        "https://panodata.panomax.com/cams/1981/preview_og.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.name, "Piancavallo - Panorama")
                    self.assertEqual(record.area, "Piancavallo · quota 1.625 m")
                    self.assertEqual(record.provider, "Panomax / PromoTurismoFVG")
                    self.assertEqual(
                        record.sourcePage,
                        "https://piancavallo.panomax.com/",
                    )
                    self.assertEqual(record.attribution, record.provider)
                    self.assertEqual(record.attributionUrl, record.sourcePage)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/093004-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id == "piancavallo-nevelandia":
                    self.assertEqual(
                        record.imageUrl,
                        "https://www.meteo.fvg.it/ext/webcams/webcams/"
                        "Piancavallo-Nevelandia-image.cgi.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.name, "Piancavallo - Nevelandia")
                    self.assertEqual(record.area, "Piancavallo · Nevelandia")
                    self.assertEqual(record.lat, 46.112847)
                    self.assertEqual(record.lon, 12.52325)
                    self.assertEqual(
                        record.provider,
                        "Nevelandia / Piancavallo 1265",
                    )
                    self.assertEqual(
                        record.sourcePage,
                        "https://www.nevelandia.com/webcam-piancavallo/",
                    )
                    self.assertEqual(
                        record.attribution,
                        "PromoTurismoFVG · ARPA FVG - OSMER e GRN",
                    )
                    self.assertEqual(
                        record.attributionUrl,
                        "https://www.meteo.fvg.it/webcam_img.php?ln=it",
                    )
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/093004-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id == "moruzzo-panorama":
                    self.assertEqual(
                        record.imageUrl,
                        "https://www.meteo.fvg.it/ext/webcams/webcams/"
                        "Moruzzo-moruzzo.jpg.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.name, "Moruzzo - Panorama verso ovest")
                    self.assertEqual(record.area, "Panorama verso ovest")
                    self.assertEqual(record.lat, 46.1196936077918)
                    self.assertEqual(record.lon, 13.1235643188482)
                    self.assertEqual(
                        record.provider,
                        "Comune di Moruzzo / Meteo-Project",
                    )
                    self.assertEqual(
                        record.sourcePage,
                        "https://www.weathercam.it/webcam/moruzzo",
                    )
                    self.assertEqual(
                        record.attribution,
                        "WeatherCam / Meteo-Project · ARPA FVG - OSMER e GRN",
                    )
                    self.assertEqual(
                        record.attributionUrl,
                        "https://www.meteo.fvg.it/webcam_img.php?ln=it",
                    )
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/030063-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id == "spilimbergo-duomo":
                    self.assertEqual(
                        record.imageUrl,
                        "https://www.meteo.fvg.it/ext/webcams/webcams/"
                        "Spilimbergo-Duomo-spilimbergo_piazzaduomo.jpg.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.name, "Spilimbergo - Duomo")
                    self.assertEqual(record.area, "Piazza Duomo")
                    self.assertEqual(record.lat, 46.110679)
                    self.assertEqual(record.lon, 12.904467)
                    self.assertEqual(record.provider, "PromoTurismoFVG")
                    self.assertEqual(
                        record.sourcePage,
                        "https://www.meteo.fvg.it/webcam_img.php?ln=it",
                    )
                    self.assertEqual(
                        record.attribution,
                        "PromoTurismoFVG · ARPA FVG - OSMER e GRN",
                    )
                    self.assertEqual(record.attributionUrl, record.sourcePage)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/093044-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id == "barcis-paese":
                    self.assertEqual(record.name, "Barcis - Panorama del paese")
                    self.assertEqual(record.municipality, "Barcis")
                    self.assertIsNone(record.lat)
                    self.assertIsNone(record.lon)
                    self.assertEqual(
                        record.imageUrl,
                        "https://www.meteo.fvg.it/ext/webcams/webcams/"
                        "Barcis2-barcis.jpg.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.provider, "PromoTurismoFVG")
                    self.assertEqual(
                        record.sourcePage,
                        "https://www.meteo.fvg.it/webcam_img.php?ln=it",
                    )
                    self.assertEqual(
                        record.attribution,
                        "PromoTurismoFVG · ARPA FVG - OSMER e GRN",
                    )
                    self.assertEqual(record.attributionUrl, record.sourcePage)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/093006-photo.webp",
                    )
                elif record.id == "claut-pradut":
                    self.assertEqual(record.name, "Claut - Rifugio Pradut")
                    self.assertEqual(record.municipality, "Claut")
                    self.assertEqual((record.lat, record.lon), (46.25613, 12.56501))
                    self.assertEqual(
                        record.imageUrl,
                        "https://www.parcodolomitifriulane.it/webcam/PN01/cam000M.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(
                        record.provider, "Parco Naturale Dolomiti Friulane",
                    )
                    self.assertEqual(
                        record.sourcePage,
                        "https://www.parcodolomitifriulane.it/vivere-il-parco/"
                        "webcam-meteo/",
                    )
                    self.assertEqual(
                        record.attribution,
                        "Parco Naturale Dolomiti Friulane · Rifugio Pradut",
                    )
                    self.assertEqual(record.attributionUrl, record.sourcePage)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/093015-photo.webp",
                    )
                elif record.id == "sappada-panorama":
                    self.assertEqual(
                        record.imageUrl,
                        "https://panodata.panomax.com/cams/1894/preview_og.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.name, "Sappada - Panorama")
                    self.assertEqual(record.area, "Panorama del paese")
                    self.assertEqual(record.provider, "Panomax / PromoTurismoFVG")
                    self.assertEqual(record.sourcePage, "https://sappada.panomax.com/")
                    self.assertEqual(record.attribution, record.provider)
                    self.assertEqual(record.attributionUrl, record.sourcePage)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/030189-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id == "sella-nevea-canin":
                    self.assertEqual(
                        record.imageUrl,
                        "https://panodata.panomax.com/cams/1984/preview_og.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.name, "Sella Nevea - Monte Canin")
                    self.assertEqual(record.area, "Sella Nevea · Monte Canin")
                    self.assertEqual(record.provider, "Panomax / PromoTurismoFVG")
                    self.assertEqual(
                        record.sourcePage,
                        "https://sellanevea.panomax.com/",
                    )
                    self.assertEqual(record.attribution, record.provider)
                    self.assertEqual(record.attributionUrl, record.sourcePage)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/030025-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id == "san-daniele-centro":
                    self.assertEqual(
                        record.imageUrl,
                        "https://panodata.panomax.com/cams/9495/preview_og.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.name, "San Daniele del Friuli - Centro")
                    self.assertEqual(record.area, "Centro")
                    self.assertEqual(record.provider, "Panomax / PromoTurismoFVG")
                    self.assertEqual(
                        record.sourcePage,
                        "https://sandanieledelfriuli.panomax.com/",
                    )
                    self.assertEqual(record.attribution, record.provider)
                    self.assertEqual(record.attributionUrl, record.sourcePage)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/030099-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id == "trieste-san-giusto":
                    self.assertEqual(
                        record.imageUrl,
                        "https://panodata.panomax.com/cams/6949/preview_og.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.name, "Trieste - Colle di San Giusto")
                    self.assertEqual(record.area, "Colle di San Giusto")
                    self.assertEqual(record.provider, "Panomax / PromoTurismoFVG")
                    self.assertEqual(record.sourcePage, "https://trieste.panomax.com/")
                    self.assertEqual(record.attribution, record.provider)
                    self.assertEqual(record.attributionUrl, record.sourcePage)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/032006-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id == "udine-panorama-castello":
                    self.assertEqual(
                        record.imageUrl,
                        "https://panodata.panomax.com/cams/2859/preview_og.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.name, "Udine - Panorama dal Castello")
                    self.assertEqual(record.area, "Specola del Castello")
                    self.assertEqual(
                        record.provider,
                        "Comune di Udine · PromoTurismoFVG · Panomax",
                    )
                    self.assertEqual(
                        record.sourcePage,
                        "https://udine.panomax.com/",
                    )
                    self.assertEqual(record.attribution, record.provider)
                    self.assertEqual(record.attributionUrl, record.sourcePage)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/030129-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                elif record.id == "trieste-miramare":
                    self.assertEqual(
                        record.imageUrl,
                        "https://www.meteosystem.com/webcam/miramare/"
                        "parco_miramare.jpg",
                    )
                    self.assertEqual(record.mediaType, "snapshot")
                    self.assertEqual(record.name, "Trieste - Parco di Miramare")
                    self.assertEqual(record.area, "Parco di Miramare")
                    self.assertEqual(record.provider, "Meteo System")
                    self.assertEqual(
                        record.sourcePage,
                        "https://www.meteosystem.com/stazione/"
                        "trieste-miramare/webcam.php",
                    )
                    self.assertEqual(record.attribution, record.provider)
                    self.assertEqual(record.attributionUrl, record.sourcePage)
                    self.assertEqual(
                        record.fallbackImageUrl,
                        "/municipalities/photos/032006-photo.webp",
                    )
                    for field in ("license", "licenseUrl", "license_url"):
                        self.assertNotIn(field, raw_by_id[record.id])
                else:
                    self.assertIsNone(record.imageUrl)
                    self.assertIsNone(record.mediaType)
                    for field in ("imageUrl", "image_url", "mediaType", "media_type"):
                        self.assertNotIn(field, raw_by_id[record.id])

    def test_replaced_sources_have_explicit_correct_identities_and_page_urls(self):
        expected = {
            "grado-al-bosco": (
                "Grado Pineta - Isolotto Sacca dei Moreri",
                "Grado.it",
                "https://grado.it/it/scoprire-grado/webcam",
            ),
            "monfalcone-marina": (
                "Monfalcone - Spiaggia di Marina Monfalcone",
                "Marina Monfalcone",
                "https://marinamonfalcone.com/it/webcam/",
            ),
            "monfalcone-marina-julia-1": (
                "Monfalcone - Marina Julia 1",
                "Comune di Monfalcone",
                "https://www.comune.monfalcone.go.it/it/novita-220905/"
                "notizie-220906/condizioni-del-vento-marina-julia-21786",
            ),
            "monfalcone-marina-julia-2": (
                "Monfalcone - Marina Julia 2",
                "Comune di Monfalcone",
                "https://www.comune.monfalcone.go.it/it/novita-220905/"
                "notizie-220906/condizioni-del-vento-marina-julia-21786",
            ),
            "sacile": (
                "Sacile",
                "SacileMeteo",
                "https://sacilemeteo.altervista.org/hik/webcam_hik.html",
            ),
            "piancavallo-panorama": (
                "Piancavallo - Panorama",
                "Panomax / PromoTurismoFVG",
                "https://piancavallo.panomax.com/",
            ),
            "piancavallo-nevelandia": (
                "Piancavallo - Nevelandia",
                "Nevelandia / Piancavallo 1265",
                "https://www.nevelandia.com/webcam-piancavallo/",
            ),
            "moruzzo-panorama": (
                "Moruzzo - Panorama verso ovest",
                "Comune di Moruzzo / Meteo-Project",
                "https://www.weathercam.it/webcam/moruzzo",
            ),
            "spilimbergo-duomo": (
                "Spilimbergo - Duomo",
                "PromoTurismoFVG",
                "https://www.meteo.fvg.it/webcam_img.php?ln=it",
            ),
            "zoncolan-panorama": (
                "Monte Zoncolan - Panorama",
                "Panomax / PromoTurismoFVG",
                "https://zoncolan.panomax.com/",
            ),
            "forni-varmost": (
                "Forni di Sopra - Malga Varmost",
                "Panomax / PromoTurismoFVG",
                "https://fornidisopra.panomax.com/",
            ),
            "cividale-campanile-ex-monastero": (
                "Cividale del Friuli - Veduta dal campanile",
                "ARPA FVG - OSMER e GRN",
                "https://www.meteo.fvg.it/webcam_img.php?ln=it",
            ),
            "cividale-piazza-duomo": (
                "Cividale del Friuli - Piazza Duomo",
                "ARPA FVG - OSMER e GRN",
                "https://www.meteo.fvg.it/webcam_img.php?ln=it",
            ),
            "cividale-piazza-paolo-diacono": (
                "Cividale del Friuli - Piazza Paolo Diacono",
                "ARPA FVG - OSMER e GRN",
                "https://www.meteo.fvg.it/webcam_img.php?ln=it",
            ),
        }
        for webcam_id, identity in expected.items():
            with self.subTest(webcam=webcam_id):
                self.assertIn(webcam_id, self.active_by_id)
                record = self.active_by_id[webcam_id]
                self.assertEqual(
                    (record.name, record.provider, record.sourcePage), identity
                )

        for obsolete_id in (
            "grado-spiaggia", "monfalcone-marina-julia", "piancavallo-sauc",
            "zoncolan-baita-goles", "val-saisera", "forni-chianeit",
            "cividale-natisone", "aquileia-basilica",
        ):
            with self.subTest(obsolete_id=obsolete_id):
                self.assertNotIn(obsolete_id, self.active_by_id)

    def test_replacements_do_not_reuse_pc_coordinates_or_api_identity(self):
        for webcam_id in ("sacile", "monfalcone-marina"):
            with self.subTest(webcam=webcam_id):
                record = self.active_by_id[webcam_id]
                self.assertIsNone(record.lat)
                self.assertIsNone(record.lon)
                self.assertIsNone(record.sourceCheckUrl)
                self.assertIsNone(record.sourceCheckExpectedId)
                self.assertNotEqual(
                    urlsplit(record.sourcePage).hostname,
                    "monitor.protezionecivile.fvg.it",
                )

    def test_sappada_and_sella_nevea_are_promoted_to_active_only(self):
        candidate_ids = {
            record.id for record in self.catalogs["candidates"].records
        }
        for webcam_id, name, source_page in (
            ("sappada-panorama", "Sappada - Panorama", "https://sappada.panomax.com/"),
            (
                "sella-nevea-canin", "Sella Nevea - Monte Canin",
                "https://sellanevea.panomax.com/",
            ),
        ):
            with self.subTest(webcam=webcam_id):
                self.assertIn(webcam_id, self.active_by_id)
                record = self.active_by_id[webcam_id]
                self.assertEqual(record.name, name)
                self.assertEqual(record.sourcePage, source_page)
                self.assertEqual(record.provider, "Panomax / PromoTurismoFVG")
                self.assertNotIn(webcam_id, candidate_ids)

    def test_moruzzo_is_promoted_to_active_only_with_osmer_declared_coordinates(self):
        candidate_ids = {
            record.id for record in self.catalogs["candidates"].records
        }
        record = self.active_by_id["moruzzo-panorama"]

        self.assertNotIn(record.id, candidate_ids)
        self.assertEqual(record.lat, 46.1196936077918)
        self.assertEqual(record.lon, 13.1235643188482)
        self.assertNotEqual((record.lat, record.lon), (46.121, 13.139))

    def test_spilimbergo_promotes_only_the_valid_duomo_view(self):
        record = self.active_by_id["spilimbergo-duomo"]

        self.assertEqual((record.lat, record.lon), (46.110679, 12.904467))
        self.assertNotIn("spilimbergo-municipio", self.active_by_id)

    def test_barcis_and_pradut_are_active_but_la_pussa_stays_candidate_only(self):
        self.assertIn("barcis-paese", self.active_by_id)
        self.assertIn("claut-pradut", self.active_by_id)
        self.assertNotIn("claut-val-settimana", self.active_by_id)
        self.assertIn(
            "claut-val-settimana",
            {record.id for record in self.catalogs["candidates"].records},
        )
        self.assertNotIn("Cimolais", {
            record.municipality for record in self.catalogs["active"].records
        })
        self.assertNotIn("Erto e Casso", {
            record.municipality for record in self.catalogs["active"].records
        })

    def test_monfalcone_marina_julia_views_form_a_distinct_cluster(self):
        cluster = [
            record for record in self.catalogs["active"].records
            if record.mapClusterId == "monfalcone-marina-julia"
        ]

        self.assertEqual(
            [record.id for record in cluster],
            ["monfalcone-marina-julia-1", "monfalcone-marina-julia-2"],
        )
        self.assertTrue(all(
            record.mapClusterLabel == "Monfalcone · Marina Julia"
            for record in cluster
        ))
        self.assertTrue(all(
            record.provider == "Comune di Monfalcone" for record in cluster
        ))
        self.assertTrue(all(record.group == "coast" for record in cluster))
        self.assertNotEqual(
            (cluster[0].lat, cluster[0].lon),
            (cluster[1].lat, cluster[1].lon),
        )
        self.assertNotEqual(cluster[0].sourcePage, self.active_by_id[
            "monfalcone-marina"
        ].sourcePage)

    def test_lignano_webcams_form_one_explicit_editorial_map_cluster(self):
        cluster = [
            record for record in self.catalogs["active"].records
            if record.mapClusterId == "lignano-sabbiadoro"
        ]
        self.assertEqual(
            [record.id for record in cluster],
            [
                "lignano-punta-faro",
                "lignano-spiaggia-centrale",
                "lignano-piazza-fontana",
                "lignano-pineta-pontile",
                "lignano-riviera",
            ],
        )
        self.assertTrue(all(record.mapClusterLabel == "Lignano Sabbiadoro" for record in cluster))
        self.assertTrue(all(record.municipality == "Lignano Sabbiadoro" for record in cluster))
        self.assertTrue(all(record.group == "coast" for record in cluster))
        self.assertFalse(any(
            record.mapClusterId == "lignano-sabbiadoro"
            for record in self.catalogs["active"].records
            if not record.id.startswith("lignano-")
        ))

    def test_cividale_webcams_form_one_current_osmer_cluster(self):
        cluster = [
            record for record in self.catalogs["active"].records
            if record.mapClusterId == "cividale-del-friuli"
        ]
        self.assertEqual(
            [record.id for record in cluster],
            [
                "cividale-campanile-ex-monastero",
                "cividale-piazza-duomo",
                "cividale-piazza-paolo-diacono",
            ],
        )
        self.assertTrue(all(
            record.mapClusterLabel == "Cividale del Friuli" for record in cluster
        ))
        self.assertTrue(all(
            record.provider == "ARPA FVG - OSMER e GRN" for record in cluster
        ))
        self.assertTrue(all(record.group == "plain" for record in cluster))

    def test_cisar_webcams_are_individual_records_with_only_verified_coordinates(self):
        grisa_ids = (
            "cisar-monte-grisa-sud-est",
            "cisar-monte-grisa-sud-ovest",
        )
        for webcam_id in grisa_ids:
            with self.subTest(webcam=webcam_id):
                record = self.active_by_id[webcam_id]
                self.assertEqual(record.lat, 45.693070)
                self.assertEqual(record.lon, 13.749281)
                self.assertEqual(record.mapClusterId, "trieste-monte-grisa")
                self.assertEqual(record.mapClusterLabel, "Monte Grisa")

        lanterna = self.active_by_id["cisar-lanterna-nord"]
        self.assertEqual(lanterna.lat, 45.649173)
        self.assertEqual(lanterna.lon, 13.755975)
        self.assertIsNone(lanterna.mapClusterId)
        self.assertIsNone(lanterna.mapClusterLabel)

    def test_stale_sources_are_documented_only_in_the_non_publishing_suspended_catalog(self):
        suspended = self.raw_catalogs["suspended"]
        self.assertEqual(suspended["mode"], "shadow")
        self.assertIs(suspended["publish"], False)
        self.assertNotIn("webcams", suspended)
        self.assertEqual(
            {record.id for record in self.catalogs["suspended"].records},
            {"aquileia-basilica", "val-saisera"},
        )
        for record in self.catalogs["suspended"].records:
            with self.subTest(webcam=record.id):
                self.assertEqual(record.health, "offline")
                self.assertTrue(suspended["suspensionReasons"][record.id].strip())

    def test_default_local_service_exposes_exactly_the_active_catalog(self):
        session = Mock(spec=requests.Session)
        service = WebcamManifestService(manifest_url="", session=session)
        manifest = service.get_manifest()

        self.assertEqual(service.local_path.resolve(), DATA_ROOT / CATALOG_FILES["active"])
        self.assertTrue(manifest.ok)
        self.assertEqual(manifest.source, "local")
        self.assertEqual(manifest.count, 35)
        self.assertEqual(
            {record.id for record in manifest.webcams}, set(self.active_by_id)
        )
        udine = next(
            record for record in manifest.webcams
            if record.id == "udine-panorama-castello"
        )
        self.assertEqual(
            udine.imageUrl,
            "https://panodata.panomax.com/cams/2859/preview_og.jpg",
        )
        session.get.assert_not_called()

    def test_service_fails_closed_if_pointed_at_either_real_shadow_catalog(self):
        for name in ("candidates", "suspended"):
            with self.subTest(catalog=name):
                session = Mock(spec=requests.Session)
                service = WebcamManifestService(
                    local_path=DATA_ROOT / CATALOG_FILES[name],
                    manifest_url="",
                    session=session,
                )
                manifest = service.get_manifest()
                self.assertFalse(manifest.ok)
                self.assertEqual(manifest.status, "unavailable")
                self.assertEqual(manifest.count, 0)
                self.assertEqual(manifest.webcams, [])
                session.get.assert_not_called()

    def test_remote_suspended_catalog_cannot_override_the_active_catalog(self):
        session = Mock(spec=requests.Session)
        response = session.get.return_value
        response.url = "https://example.test/webcams_suspended.json"
        response.json.return_value = self.raw_catalogs["suspended"]
        service = WebcamManifestService(
            manifest_url=response.url,
            session=session,
        )
        manifest = service.get_manifest()

        self.assertTrue(manifest.ok)
        self.assertEqual(manifest.status, "fallback")
        self.assertEqual(manifest.source, "local")
        self.assertEqual(manifest.count, 35)
        self.assertEqual(
            {record.id for record in manifest.webcams}, set(self.active_by_id)
        )
        session.get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
