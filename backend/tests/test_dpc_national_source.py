import unittest
from datetime import datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from app.services.dpc_national_source import (
    DPC_NATIONAL_BULLETIN_URL,
    DPC_RAW_BASE,
    DpcNationalSource,
    DpcNationalSourceError,
    discover_dpc_national_assets,
    extract_dpc_cap_xml,
)

from tests.test_dpc_national_alerts import CAP_HEADER, cap, info
from tests.test_dpc_national_zone_snapshot import enough_rows, zone_zip


REVISION = "20260924_1434"
XML_URL = f"{DPC_RAW_BASE}/xml/{REVISION}.zip"
SHP_URL = f"{DPC_RAW_BASE}/shp/{REVISION}_shp.zip"


def page(xml_url=XML_URL, shp_url=SHP_URL):
    return (
        f'<html><a href="{shp_url}">SHP</a>'
        f'<a href="{xml_url}">XML</a></html>'
    )


def xml_zip(cap_payload, *, cap_name=f"Cap_{REVISION}.xml", extra=None):
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr(cap_name, cap_payload)
        archive.writestr("BCR_testo_DCAT_AP_IT.xml", "<metadata />")
        archive.writestr("README.txt", "fixture")
        if extra is not None:
            archive.writestr(extra, "unsafe")
    return stream.getvalue()


class DpcNationalSourceTests(unittest.TestCase):
    def test_discovers_one_same_revision_official_asset_pair(self):
        self.assertEqual(
            discover_dpc_national_assets(page()),
            {"revision": REVISION, "xml_url": XML_URL, "shp_url": SHP_URL},
        )

    def test_rejects_missing_ambiguous_or_mixed_revision_assets(self):
        cases = (
            page(shp_url=""),
            page() + f'<a href="{DPC_RAW_BASE}/xml/20260924_1435.zip">other</a>',
            page(shp_url=f"{DPC_RAW_BASE}/shp/20260924_1435_shp.zip"),
        )
        for candidate in cases:
            with self.subTest(candidate=candidate):
                with self.assertRaises(DpcNationalSourceError):
                    discover_dpc_national_assets(candidate)

    def test_extracts_only_the_revision_pinned_cap(self):
        payload = xml_zip(cap())
        self.assertEqual(extract_dpc_cap_xml(payload, REVISION), cap().encode())
        with self.assertRaisesRegex(DpcNationalSourceError, "unsafe"):
            extract_dpc_cap_xml(xml_zip(cap(), extra="nested/file"), REVISION)
        with self.assertRaisesRegex(DpcNationalSourceError, "unsafe"):
            extract_dpc_cap_xml(
                xml_zip(cap(), cap_name="Cap_20260924_1435.xml"), REVISION
            )

    def test_fetches_parses_and_reconciles_atomically(self):
        responses = {
            DPC_NATIONAL_BULLETIN_URL: page().encode(),
            XML_URL: xml_zip(cap()),
            SHP_URL: zone_zip(enough_rows()),
        }
        calls = []

        def fetcher(url, max_bytes):
            calls.append((url, max_bytes))
            return responses[url]

        result = DpcNationalSource(fetcher).fetch(
            acquired_at=datetime.fromisoformat("2026-09-24T13:00:00+00:00")
        )

        self.assertTrue(result["reconciled"])
        self.assertFalse(result["active"])
        self.assertEqual(result["zone_count"], 100)
        self.assertEqual(result["revision"]["source_revision"], REVISION)
        self.assertEqual(result["acquisition"]["cap_url"], XML_URL)
        self.assertEqual([call[0] for call in calls], [
            DPC_NATIONAL_BULLETIN_URL,
            XML_URL,
            SHP_URL,
        ])

    def test_non_public_cap_is_classified_without_accepting_it(self):
        draft = cap(header=CAP_HEADER.replace("<status>Actual", "<status>Test"))
        responses = {
            DPC_NATIONAL_BULLETIN_URL: page().encode(),
            XML_URL: xml_zip(draft),
            SHP_URL: zone_zip(enough_rows()),
        }
        with self.assertRaisesRegex(
            DpcNationalSourceError, "^dpc_source_cap_not_public$"
        ):
            DpcNationalSource(lambda url, _: responses[url]).fetch()

    def test_other_invalid_cap_remains_a_source_failure(self):
        invalid = cap(info(event="rischio sconosciuto"))
        responses = {
            DPC_NATIONAL_BULLETIN_URL: page().encode(),
            XML_URL: xml_zip(invalid),
            SHP_URL: zone_zip(enough_rows()),
        }
        with self.assertRaisesRegex(
            DpcNationalSourceError, "^dpc_source_cap_contract_invalid$"
        ):
            DpcNationalSource(lambda url, _: responses[url]).fetch()


if __name__ == "__main__":
    unittest.main()
