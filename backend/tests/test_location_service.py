import json
import unittest
from pathlib import Path

from app.contracts.location import LocationSearchItem
from app.services.location import (
    LocationCatalog,
    LocationSearchSourceUnavailable,
    LocationService,
    LocationSourceUnavailable,
    NominatimLocationSearchSource,
    ReverseLocationSource,
)


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = WORKSPACE_ROOT / "contracts" / "runtime-api" / "v1" / "location"


class StubReverseSource:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def fetch(self, lat, lon):
        self.calls.append((lat, lon))
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class StubSearchSource:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def search(self, query, limit):
        self.calls.append((query, limit))
        if isinstance(self.payload, Exception):
            raise self.payload
        return [item.model_copy(deep=True) for item in self.payload]


class LocationCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = LocationCatalog()

    def test_catalog_contains_all_fvg_municipalities(self):
        self.assertEqual(len(self.catalog.municipalities), 215)
        self.assertEqual(len({item.istat_code for item in self.catalog.municipalities}), 215)

    def test_search_keeps_primary_city_ranking(self):
        result = self.catalog.search("pord")
        self.assertEqual(
            [item.name for item in result[:3]],
            ["Pordenone", "Pasiano di Pordenone", "Prata di Pordenone"],
        )

    def test_search_supports_province_codes(self):
        self.assertEqual(self.catalog.search("PN")[0].name, "Pordenone")
        self.assertEqual(self.catalog.search("UD")[0].name, "Udine")
        self.assertEqual(self.catalog.search("GO")[0].name, "Gorizia")
        self.assertEqual(self.catalog.search("TS")[0].name, "Trieste")

    def test_shared_search_fixture_matches_catalog_values(self):
        fixture = json.loads((FIXTURE_ROOT / "search-success.json").read_text(encoding="utf-8"))
        result = [item.model_dump() for item in self.catalog.search("pord")[:3]]
        self.assertEqual(result, fixture)


class LocationServiceTests(unittest.TestCase):
    def test_search_keeps_fvg_first_and_deduplicates_national_results(self):
        source = StubSearchSource([
            LocationSearchItem(
                name="Udine",
                admin1="Friuli-Venezia Giulia",
                latitude=46.0635,
                longitude=13.2356,
                population=100170,
                provinceName="Udine",
            ),
            LocationSearchItem(
                name="Torino",
                admin1="Piemonte",
                latitude=45.0703,
                longitude=7.6869,
                population=847398,
                provinceName="Torino",
            ),
        ])
        service = LocationService(search_source=source)
        local_results = service.catalog.search("udine")

        result = service.search("udine")
        expected_local_count = min(len(local_results), 7)

        self.assertEqual(
            [item.name for item in result[:expected_local_count]],
            [item.name for item in local_results[:expected_local_count]],
        )
        self.assertEqual(result[expected_local_count].name, "Torino")
        self.assertEqual(result[0].istatCode, "030129")
        self.assertEqual(result[0].province, "UD")
        self.assertEqual(result[expected_local_count].istatCode, "")
        self.assertEqual(result[expected_local_count].province, "")
        self.assertEqual(result[expected_local_count].provinceName, "Torino")
        self.assertEqual(source.calls, [("udine", 8)])

    def test_search_reserves_bounded_space_for_national_results(self):
        source = StubSearchSource([
            LocationSearchItem(
                name=name,
                admin1=region,
                latitude=latitude,
                longitude=longitude,
            )
            for name, region, latitude, longitude in (
                ("Sanremo", "Liguria", 43.8173, 7.7772),
                ("San Severo", "Puglia", 41.6856, 15.3815),
                ("San Miniato", "Toscana", 43.6795, 10.8512),
                ("San Bonifacio", "Veneto", 45.3959, 11.2735),
            )
        ])
        service = LocationService(search_source=source)
        local_results = service.catalog.search("san")
        self.assertEqual(len(local_results), 8)

        result = service.search("san")

        self.assertEqual(len(result), 8)
        self.assertEqual(
            [item.name for item in result[:5]],
            [item.name for item in local_results[:5]],
        )
        self.assertEqual(
            [item.name for item in result[5:]],
            ["Sanremo", "San Severo", "San Miniato"],
        )
        self.assertEqual(source.calls, [("san", 8)])

    def test_search_falls_back_to_fvg_when_national_source_is_unavailable(self):
        source = StubSearchSource(
            LocationSearchSourceUnavailable("location_search_source_failed")
        )
        result = LocationService(search_source=source).search("pord")

        self.assertEqual(
            [item.name for item in result[:3]],
            ["Pordenone", "Pasiano di Pordenone", "Prata di Pordenone"],
        )
        self.assertEqual(source.calls, [("pord", 8)])

    def test_search_surfaces_outage_when_no_local_fallback_matches(self):
        source = StubSearchSource(
            LocationSearchSourceUnavailable("location_search_source_failed")
        )

        with self.assertRaises(LocationSearchSourceUnavailable):
            LocationService(search_source=source).search("torino")

    def test_reverse_without_accuracy_returns_offline_canonical_municipality(self):
        source = StubReverseSource(AssertionError("public reverse source called"))
        service = LocationService(reverse_source=source)

        result = service.reverse(45.9567, 12.6605)

        expected = json.loads((FIXTURE_ROOT / "reverse-fvg-success.json").read_text(encoding="utf-8"))
        self.assertEqual(result.model_dump(), expected)
        self.assertEqual(result.dataPoint.source, "municipality_catalog")
        self.assertNotEqual((result.dataPoint.lat, result.dataPoint.lon), (result.lat, result.lon))
        self.assertEqual(source.calls, [])

    def test_reverse_with_precise_accuracy_resolves_offline_localities(self):
        cases = (
            (
                45.9892108,
                12.5473156,
                "Vigonovo",
                "Fontanafredda",
                "093022",
            ),
            (
                46.2479446,
                12.4703415,
                "Cellino di Sopra",
                "Claut",
                "093015",
            ),
            (
                46.1440410,
                12.6372055,
                "Malnisio",
                "Montereale Valcellina",
                "093027",
            ),
            (
                46.1507328,
                12.6490079,
                "Grizzo",
                "Montereale Valcellina",
                "093027",
            ),
        )

        source = StubReverseSource(AssertionError("public reverse source called"))
        service = LocationService(reverse_source=source)
        for latitude, longitude, locality_name, municipality_name, istat in cases:
            with self.subTest(locality=locality_name):
                result = service.reverse(latitude, longitude, accuracy_m=20)

                self.assertEqual(result.city, municipality_name)
                self.assertEqual(result.displayName, locality_name)
                self.assertEqual(result.istatCode, istat)
                self.assertEqual(result.locality.name, locality_name)
                self.assertEqual(result.locality.source, "rafvg_irdat_5000")
                self.assertEqual(result.municipality.name, municipality_name)
                self.assertEqual(result.municipality.source, "istat_boundaries")
                self.assertEqual(result.resolution.status, "resolved")
                self.assertTrue(result.resolution.localityCorroborated)
                self.assertEqual(result.resolution.matchMethod, "nearest")
                self.assertIsNotNone(result.resolution.distanceM)
                self.assertIsNotNone(result.resolution.runnerUpDistanceM)
        self.assertEqual(source.calls, [])

    def test_cellino_nearest_is_selected_only_below_the_ambiguity_limit(self):
        service = LocationService(
            reverse_source=StubReverseSource(AssertionError("source called"))
        )
        precise = service.reverse(
            46.2479446,
            12.4703415,
            accuracy_m=30,
        )
        ambiguous = service.reverse(
            46.2479446,
            12.4703415,
            accuracy_m=32,
        )

        self.assertEqual(precise.displayName, "Cellino di Sopra")
        self.assertEqual(precise.resolution.matchMethod, "nearest")
        self.assertAlmostEqual(precise.resolution.distanceM, 55.8, places=1)
        self.assertAlmostEqual(
            precise.resolution.runnerUpDistanceM,
            138.3,
            places=1,
        )
        self.assertEqual(precise.dataPoint.source, "rafvg_irdat_5000")
        self.assertEqual(
            (precise.dataPoint.lat, precise.dataPoint.lon),
            (46.247575, 12.46985),
        )
        self.assertEqual(ambiguous.displayName, "Claut")
        self.assertIsNone(ambiguous.locality)
        self.assertEqual(ambiguous.resolution.status, "municipality_only")
        self.assertIsNone(ambiguous.resolution.matchMethod)

    def test_reverse_without_accuracy_never_uses_a_nearest_locality(self):
        result = LocationService(
            reverse_source=StubReverseSource(AssertionError("source called"))
        ).reverse(
            45.9892108,
            12.5473156,
        )

        self.assertEqual(result.displayName, "Fontanafredda")
        self.assertIsNone(result.locality)
        self.assertEqual(result.municipality.name, "Fontanafredda")
        self.assertEqual(result.municipality.istatCode, "093022")
        self.assertEqual(result.resolution.status, "municipality_only")
        self.assertIsNone(result.resolution.matchMethod)

    def test_reverse_resolves_an_external_place_to_its_public_canonical_point(self):
        source = StubReverseSource({
            "lat": "44.4938203",
            "lon": "11.3426327",
            "name": "Bologna",
            "address": {
                "city": "Bologna",
                "state": "Emilia-Romagna",
                "country": "Italia",
                "country_code": "it",
            },
        })
        service = LocationService(reverse_source=source)

        result = service.reverse(44.4949, 11.3426, accuracy_m=20)
        expected = json.loads(
            (FIXTURE_ROOT / "reverse-outside-fvg-success.json").read_text(encoding="utf-8")
        )

        self.assertEqual(result.model_dump(), expected)
        self.assertEqual(result.city, "Bologna")
        self.assertEqual(result.displayName, "Bologna")
        self.assertEqual(result.region, "Emilia-Romagna")
        self.assertEqual(
            (result.dataPoint.lat, result.dataPoint.lon, result.dataPoint.source),
            (44.4938203, 11.3426327, "nominatim_place"),
        )
        self.assertEqual(result.resolution.status, "external_place")
        self.assertEqual(result.resolution.matchMethod, "nearest")
        self.assertLess(result.resolution.distanceM, 200)
        self.assertIsNone(result.municipality)
        self.assertIsNone(result.locality)
        self.assertEqual(source.calls, [(44.4949, 11.3426)])

    def test_reverse_external_place_fails_closed_when_the_source_is_unavailable(self):
        service = LocationService(
            reverse_source=StubReverseSource(LocationSourceUnavailable("offline"))
        )

        with self.assertRaisesRegex(LocationSourceUnavailable, "offline"):
            service.reverse(44.4949, 11.3426, accuracy_m=20)

    def test_reverse_rejects_invalid_direct_accuracy(self):
        service = LocationService()
        with self.assertRaisesRegex(ValueError, "location_accuracy_invalid"):
            service.reverse(45.9567, 12.6605, accuracy_m=-1)


class ReverseLocationSourceTests(unittest.TestCase):
    def test_source_requests_city_level_data_with_coarse_coordinates_and_caches_it(self):
        class ValidResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "lat": "44.4938203",
                    "lon": "11.3426327",
                    "address": {"city": "Bologna"},
                }

        class RecordingSession:
            def __init__(self):
                self.calls = []

            def get(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return ValidResponse()

        session = RecordingSession()
        source = ReverseLocationSource(session=session)

        first = source.fetch(44.4949188, 11.3429472)
        second = source.fetch(44.49491, 11.34294)

        self.assertEqual(first, second)
        self.assertEqual(len(session.calls), 1)
        params = session.calls[0][1]["params"]
        self.assertEqual(params["lat"], 44.495)
        self.assertEqual(params["lon"], 11.343)
        self.assertEqual(params["zoom"], 10)

    def test_source_rejects_invalid_payloads(self):
        class InvalidResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"display_name": "missing address"}

        class InvalidSession:
            def get(self, *args, **kwargs):
                return InvalidResponse()

        source = ReverseLocationSource(session=InvalidSession())

        with self.assertRaises(LocationSourceUnavailable):
            source.fetch(45.9567, 12.6605)


class NominatimLocationSearchSourceTests(unittest.TestCase):
    @staticmethod
    def vercelli_payload(**overrides):
        return {
            "place_id": 75677120,
            "osm_type": "relation",
            "osm_id": 1552703,
            "name": "Vercelli",
            "lat": "45.3251557",
            "lon": "8.4227666",
            "category": "boundary",
            "type": "administrative",
            "addresstype": "city",
            "place_rank": 16,
            "address": {
                "city": "Vercelli",
                "county": "Vercelli",
                "ISO3166-2-lvl6": "IT-VC",
                "state": "Piemonte",
                "country": "Italia",
                "country_code": "it",
            },
            **overrides,
        }

    def test_vercelli_province_is_excluded_but_city_and_province_code_survive(self):
        city = self.vercelli_payload()
        province = self.vercelli_payload(
            place_id=75594758,
            osm_id=1552705,
            lat="45.5553827",
            lon="8.3462837",
            addresstype="county",
            place_rank=12,
            address={key: value for key, value in city["address"].items() if key != "city"},
        )

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return [province, city]

        class Session:
            def get(self, *args, **kwargs):
                return Response()

        source = NominatimLocationSearchSource(session=Session())
        result = LocationService(search_source=source).search("Vercelli")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Vercelli")
        self.assertEqual(result[0].province, "VC")
        self.assertEqual(result[0].provinceName, "Vercelli")
        self.assertEqual(result[0].latitude, 45.3251557)
        self.assertEqual(result[0].providerId, "75677120")

    def test_source_excludes_explicit_supralocal_types_without_using_name(self):
        for address_type in (
            "continent", "country", "region", "state", "state_district", "province", "county",
        ):
            with self.subTest(address_type=address_type):
                self.assertIsNone(NominatimLocationSearchSource._parse_result(
                    self.vercelli_payload(addresstype=address_type, place_rank=None),
                ))
                self.assertIsNone(NominatimLocationSearchSource._parse_result(
                    self.vercelli_payload(addresstype=None, category="place", type=address_type),
                ))

    def test_source_keeps_municipalities_and_smaller_localities(self):
        for address_type, rank in (
            ("municipality", 13), ("city", 16), ("town", 18), ("village", 19),
            ("hamlet", 20), ("suburb", 19), ("locality", 25), ("isolated_dwelling", 22),
        ):
            with self.subTest(address_type=address_type):
                result = NominatimLocationSearchSource._parse_result(
                    self.vercelli_payload(addresstype=address_type, place_rank=rank),
                )
                self.assertIsNotNone(result)
                self.assertEqual(result.province, "VC")

    def test_missing_address_type_uses_rank_only_for_administrative_boundaries(self):
        for rank in (4, 8, 12, "12"):
            with self.subTest(rank=rank):
                self.assertIsNone(NominatimLocationSearchSource._parse_result(
                    self.vercelli_payload(addresstype=None, place_rank=rank),
                ))
        for rank in (13, 16, None, "invalid", 0, True):
            with self.subTest(rank=rank):
                self.assertIsNotNone(NominatimLocationSearchSource._parse_result(
                    self.vercelli_payload(addresstype=None, place_rank=rank),
                ))
        self.assertIsNone(NominatimLocationSearchSource._parse_result(
            self.vercelli_payload(addresstype=None, category=None, **{
                "class": "boundary", "place_rank": 12,
            }),
        ))
        self.assertIsNotNone(NominatimLocationSearchSource._parse_result(
            self.vercelli_payload(addresstype=None, category=None, type=None, place_rank=12),
        ))
        self.assertIsNotNone(NominatimLocationSearchSource._parse_result(
            self.vercelli_payload(addresstype=None, category=None, type=None, place_rank=None),
        ))

    def test_province_requires_italian_two_letter_iso_and_keeps_name_as_fallback(self):
        for province_iso in (None, "", "VC", "IT-21", "FR-VC", "IT-VCC", "IT-V1", "IT-VČ"):
            with self.subTest(province_iso=province_iso):
                payload = self.vercelli_payload()
                payload["address"]["ISO3166-2-lvl6"] = province_iso
                result = NominatimLocationSearchSource._parse_result(payload)
                self.assertEqual(result.province, "")
                self.assertEqual(result.provinceName, "Vercelli")
        payload = self.vercelli_payload()
        payload["address"]["ISO3166-2-lvl6"] = " it-vc "
        self.assertEqual(NominatimLocationSearchSource._parse_result(payload).province, "VC")

    def test_nearby_homonyms_in_different_provinces_remain_distinct(self):
        first = self.vercelli_payload(name="San Pietro", lat="45.3", lon="8.4")
        second = self.vercelli_payload(name="San Pietro", lat="45.31", lon="8.41", place_id=2)
        second["address"].update({"county": "Novara", "ISO3166-2-lvl6": "IT-NO"})
        results = [NominatimLocationSearchSource._parse_result(item) for item in (first, second)]

        result = LocationService(search_source=StubSearchSource(results)).search("San Pietro")
        national = [item for item in result if item.provider == "nominatim_search"]
        self.assertEqual([item.province for item in national], ["VC", "NO"])

    def test_distant_homonyms_in_same_province_remain_distinct(self):
        first = self.vercelli_payload(name="San Pietro", lat="45.3", lon="8.4")
        second = self.vercelli_payload(name="San Pietro", lat="45.6", lon="8.4", place_id=2)
        results = [NominatimLocationSearchSource._parse_result(item) for item in (first, second)]

        result = LocationService(search_source=StubSearchSource(results)).search("San Pietro")
        national = [item for item in result if item.provider == "nominatim_search"]
        self.assertEqual(len(national), 2)

    def test_source_requests_italian_results_maps_optional_fields_and_caches(self):
        class ValidResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return [
                    {
                        "place_id": 123456,
                        "osm_id": 44874,
                        "name": "Torino",
                        "lat": "45.0703",
                        "lon": "7.6869",
                        "address": {
                            "city": "Torino",
                            "county": "Torino",
                            "state": "Piemonte",
                            "country": "Italia",
                            "country_code": "it",
                        },
                    },
                    {
                        "place_id": 654321,
                        "name": "Paris",
                        "lat": "48.8534",
                        "lon": "2.3488",
                        "address": {
                            "city": "Paris",
                            "state": "Ile-de-France",
                            "country": "France",
                            "country_code": "fr",
                        },
                    },
                    {
                        "place_id": 999999,
                        "name": "Invalid",
                        "lat": "not-a-number",
                        "lon": "12",
                        "address": {
                            "state": "Piemonte",
                            "country": "Italia",
                            "country_code": "it",
                        },
                    },
                ]

        class RecordingSession:
            def __init__(self):
                self.calls = []

            def get(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return ValidResponse()

        session = RecordingSession()
        source = NominatimLocationSearchSource(
            session=session,
            timeout_seconds=4,
        )

        first = source.search("  Torino  ")
        second = source.search("torino")

        self.assertEqual(first, second)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(
            session.calls[0][0][0],
            "https://nominatim.openstreetmap.org/search",
        )
        params = session.calls[0][1]["params"]
        self.assertEqual(params["q"], "Torino")
        self.assertEqual(params["countrycodes"], "it")
        self.assertEqual(params["accept-language"], "it")
        self.assertEqual(params["limit"], 8)
        self.assertEqual(params["addressdetails"], 1)
        self.assertEqual(params["format"], "jsonv2")
        self.assertEqual(
            session.calls[0][1]["headers"]["User-Agent"],
            "Meteo-Friul-App/3.0 (+https://meteofriul.it)",
        )
        self.assertEqual(session.calls[0][1]["timeout"], 4)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].name, "Torino")
        self.assertEqual(first[0].admin1, "Piemonte")
        self.assertEqual(first[0].provinceName, "Torino")
        self.assertEqual(first[0].province, "")
        self.assertEqual(first[0].istatCode, "")
        self.assertEqual(first[0].country, "Italia")
        self.assertEqual(first[0].countryCode, "IT")
        self.assertEqual(first[0].provider, "nominatim_search")
        self.assertEqual(first[0].providerId, "123456")

    def test_source_rejects_invalid_payloads(self):
        class InvalidResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"results": "invalid"}

        class InvalidSession:
            def get(self, *args, **kwargs):
                return InvalidResponse()

        source = NominatimLocationSearchSource(session=InvalidSession())

        with self.assertRaises(LocationSearchSourceUnavailable):
            source.search("Roma")


if __name__ == "__main__":
    unittest.main()
