from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile

from experiments.weather_autonomy import municipal_seat_reconciliation as seat_reconciliation
from experiments.weather_autonomy.municipal_seat_reconciliation import (
    MunicipalSeatReconciliationError,
    build_from_paths,
    build_reconciliation_audit,
    load_reconciliation_audit,
    read_anncsu_workbook,
    read_ipa_entities_workbook,
    source_provenance,
    validate_reconciliation_audit,
    write_create_only,
)
from experiments.weather_autonomy.national_catalog import canonical_json_bytes


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _column(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _write_xlsx(
    path: Path,
    headers: list[str],
    rows: list[list[str]],
    *,
    shared_strings: bool,
) -> None:
    ElementTree.register_namespace("", MAIN_NS)
    ElementTree.register_namespace("r", DOC_REL_NS)
    workbook = ElementTree.Element(f"{{{MAIN_NS}}}workbook")
    sheets = ElementTree.SubElement(workbook, f"{{{MAIN_NS}}}sheets")
    ElementTree.SubElement(
        sheets,
        f"{{{MAIN_NS}}}sheet",
        {"name": "Dati", "sheetId": "1", f"{{{DOC_REL_NS}}}id": "rId1"},
    )
    relationships = ElementTree.Element(f"{{{REL_NS}}}Relationships")
    ElementTree.SubElement(
        relationships,
        f"{{{REL_NS}}}Relationship",
        {
            "Id": "rId1",
            "Type": f"{DOC_REL_NS}/worksheet",
            "Target": "worksheets/sheet1.xml",
        },
    )
    worksheet = ElementTree.Element(f"{{{MAIN_NS}}}worksheet")
    sheet_data = ElementTree.SubElement(worksheet, f"{{{MAIN_NS}}}sheetData")
    strings: list[str] = []
    string_index: dict[str, int] = {}
    for row_number, values in enumerate([headers, *rows], 1):
        row = ElementTree.SubElement(
            sheet_data, f"{{{MAIN_NS}}}row", {"r": str(row_number)}
        )
        for column_number, value in enumerate(values, 1):
            value = str(value)
            cell = ElementTree.SubElement(
                row,
                f"{{{MAIN_NS}}}c",
                {"r": f"{_column(column_number)}{row_number}"},
            )
            if shared_strings:
                cell.set("t", "s")
                if value not in string_index:
                    string_index[value] = len(strings)
                    strings.append(value)
                ElementTree.SubElement(cell, f"{{{MAIN_NS}}}v").text = str(
                    string_index[value]
                )
            else:
                cell.set("t", "inlineStr")
                inline = ElementTree.SubElement(cell, f"{{{MAIN_NS}}}is")
                ElementTree.SubElement(inline, f"{{{MAIN_NS}}}t").text = value

    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", ElementTree.tostring(workbook))
        archive.writestr(
            "xl/_rels/workbook.xml.rels", ElementTree.tostring(relationships)
        )
        archive.writestr("xl/worksheets/sheet1.xml", ElementTree.tostring(worksheet))
        if shared_strings:
            shared = ElementTree.Element(f"{{{MAIN_NS}}}sst")
            for value in strings:
                item = ElementTree.SubElement(shared, f"{{{MAIN_NS}}}si")
                ElementTree.SubElement(item, f"{{{MAIN_NS}}}t").text = value
            archive.writestr(
                "xl/sharedStrings.xml", ElementTree.tostring(shared)
            )


def _catalog() -> dict:
    content = {
        "catalog_version": "synthetic-v1",
        "kind": "meteofriul.weather.national_municipality_catalog",
        "municipalities": [
            {
                "cadastral_code": "I452",
                "istat_code": "112001",
                "name": "Comune sardo corrente",
                "province_abbreviation": "SS",
                "region_iso": "IT-88",
            },
            {
                "cadastral_code": "G888",
                "istat_code": "093033",
                "name": "Pordenone",
                "province_abbreviation": "PN",
                "region_iso": "IT-36",
            },
        ],
    }
    document = deepcopy(content)
    document["catalog_sha256"] = hashlib.sha256(
        canonical_json_bytes(content)
    ).hexdigest()
    return document


def _anncsu_rows() -> list[dict[str, str]]:
    return [
        {
            "regione": "SARDEGNA",
            "provincia_amministrativa": "SASSARI",
            "comune": "COMUNE SARDO CORRENTE",
            "codice_ipa": "c_i452",
            "codice_amministrativo": "I452",
            # Deliberately stale: the join must never use this field.
            "codice_istat": "090001",
            "accessi_in_anncsu": "100",
            "di_cui_con_coordinate": "75",
        },
        {
            "regione": "FRIULI-VENEZIA GIULIA",
            "provincia_amministrativa": "PORDENONE",
            "comune": "PORDENONE",
            "codice_ipa": "c_g888",
            "codice_amministrativo": "G888",
            "codice_istat": "93033",
            "accessi_in_anncsu": "20",
            "di_cui_con_coordinate": "20",
        },
    ]


def _ipa_rows() -> list[dict[str, str]]:
    return [
        {
            "codice_ipa": "c_i452",
            "denominazione_ente": "Comune sardo corrente",
            "codice_catastale_comune": "I452",
            "cap": "07100",
            "indirizzo": "Piazza Municipio 1",
            "data_aggiornamento": "2026-09-20",
        },
        {
            "codice_ipa": "c_g888",
            "denominazione_ente": "Comune di Pordenone",
            "codice_catastale_comune": "G888",
            "cap": "33170",
            "indirizzo": "Corso Vittorio Emanuele II 64",
            "data_aggiornamento": "2026-09-20",
        },
    ]


def _sources(catalog: dict) -> dict:
    return source_provenance(
        catalog=catalog,
        catalog_file_sha256="a" * 64,
        anncsu_file_sha256="b" * 64,
        anncsu_reference_date="2026-03-31",
        ipa_file_sha256="c" * 64,
        ipa_reference_date="2026-09-20",
    )


class MunicipalSeatReconciliationTests(unittest.TestCase):
    def test_cadastral_chain_survives_stale_sardinia_istat_without_coordinates(self):
        catalog = _catalog()

        audit = build_reconciliation_audit(
            catalog,
            _anncsu_rows(),
            _ipa_rows(),
            sources=_sources(catalog),
            expected_count=2,
        )

        sardinia = audit["records"][1]
        self.assertEqual(sardinia["istat_code"], "112001")
        self.assertEqual(sardinia["anncsu"]["reported_istat_code"], "090001")
        self.assertFalse(sardinia["anncsu"]["reported_istat_matches_catalog"])
        self.assertEqual(
            sardinia["anncsu"]["coordinate_coverage_basis_points"], 7500
        )
        self.assertEqual(sardinia["ipa_seat"]["address"], "Piazza Municipio 1")
        self.assertEqual(sardinia["point_resolution"]["status"], "pending")
        self.assertIsNone(sardinia["point_resolution"]["latitude"])
        self.assertIsNone(sardinia["point_resolution"]["longitude"])
        self.assertIsNone(sardinia["point_resolution"]["method"])
        self.assertEqual(audit["summary"]["pending"], 2)
        validate_reconciliation_audit(audit, catalog=catalog, expected_count=2)

    def test_duplicate_anncsu_and_ipa_keys_fail_closed_per_municipality(self):
        catalog = _catalog()
        anncsu = _anncsu_rows()
        anncsu.append(dict(anncsu[0]))
        ipa = _ipa_rows()
        ipa.append(dict(ipa[1]))

        audit = build_reconciliation_audit(
            catalog,
            anncsu,
            ipa,
            sources=_sources(catalog),
            expected_count=2,
        )

        by_code = {item["istat_code"]: item for item in audit["records"]}
        self.assertEqual(
            by_code["112001"]["point_resolution"]["reason_code"],
            "anncsu_duplicate_administrative_code",
        )
        self.assertIsNone(by_code["112001"]["anncsu"])
        self.assertEqual(
            by_code["093033"]["point_resolution"]["reason_code"],
            "ipa_duplicate_code",
        )
        self.assertEqual(audit["summary"]["unresolved"], 2)

    def test_ipa_cadastral_mismatch_and_missing_address_are_unresolved(self):
        catalog = _catalog()
        ipa = _ipa_rows()
        ipa[0]["codice_catastale_comune"] = "A001"
        ipa[1]["indirizzo"] = ""

        audit = build_reconciliation_audit(
            catalog,
            _anncsu_rows(),
            ipa,
            sources=_sources(catalog),
            expected_count=2,
        )

        by_code = {item["istat_code"]: item for item in audit["records"]}
        self.assertEqual(
            by_code["112001"]["point_resolution"]["reason_code"],
            "ipa_municipality_cadastral_mismatch",
        )
        self.assertEqual(
            by_code["093033"]["point_resolution"]["reason_code"],
            "ipa_seat_address_missing",
        )

    def test_missing_anncsu_or_ipa_link_remains_in_complete_audit(self):
        catalog = _catalog()
        anncsu = _anncsu_rows()[1:]

        audit = build_reconciliation_audit(
            catalog,
            anncsu,
            [],
            sources=_sources(catalog),
            expected_count=2,
        )

        self.assertEqual(len(audit["records"]), 2)
        by_code = {item["istat_code"]: item for item in audit["records"]}
        self.assertEqual(
            by_code["112001"]["point_resolution"]["reason_code"],
            "anncsu_municipality_missing",
        )
        self.assertEqual(
            by_code["093033"]["point_resolution"]["reason_code"],
            "ipa_entity_missing",
        )

    def test_hash_and_catalog_binding_reject_tampering(self):
        catalog = _catalog()
        audit = build_reconciliation_audit(
            catalog,
            _anncsu_rows(),
            _ipa_rows(),
            sources=_sources(catalog),
            expected_count=2,
        )
        altered = deepcopy(audit)
        altered["records"][0]["ipa_seat"]["address"] = "Indirizzo alterato"
        with self.assertRaisesRegex(MunicipalSeatReconciliationError, "records hash"):
            validate_reconciliation_audit(altered, expected_count=2)

        rebound = deepcopy(audit)
        rebound["records"][0]["name"] = "Nome alterato"
        rebound["records_sha256"] = hashlib.sha256(
            canonical_json_bytes(rebound["records"])
        ).hexdigest()
        content = dict(rebound)
        content.pop("audit_sha256")
        rebound["audit_sha256"] = hashlib.sha256(
            canonical_json_bytes(content)
        ).hexdigest()
        with self.assertRaisesRegex(MunicipalSeatReconciliationError, "bound catalog"):
            validate_reconciliation_audit(
                rebound, catalog=catalog, expected_count=2
            )

    def test_xlsx_parser_handles_official_inline_and_shared_string_shapes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            anncsu_path = root / "anncsu.xlsx"
            ipa_path = root / "ipa.xlsx"
            anncsu_headers = [
                "Regione",
                "Provincia Amministrativa",
                "COMUNE",
                "CODICE IPA",
                "CODICE AMMINISTRATIVO",
                "CODICE ISTAT",
                "ACCESSI IN ANNCSU",
                "DI CUI CON COORDINATE",
            ]
            _write_xlsx(
                anncsu_path,
                anncsu_headers,
                [["SARDEGNA", "SASSARI", "TEST", "c_i452", "I452", "90001", "10", ""]],
                shared_strings=False,
            )
            ipa_headers = [
                "Codice_IPA",
                "Denominazione_ente",
                "Codice_catastale_comune",
                "CAP",
                "Indirizzo",
                "Data_aggiornamento",
            ]
            _write_xlsx(
                ipa_path,
                ipa_headers,
                [["c_i452", "Comune test", "I452", "07100", "Via Test 1", "2026-09-20"]],
                shared_strings=True,
            )

            anncsu = read_anncsu_workbook(anncsu_path)
            ipa = read_ipa_entities_workbook(ipa_path)

            self.assertEqual(anncsu[0]["codice_amministrativo"], "I452")
            self.assertEqual(anncsu[0]["di_cui_con_coordinate"], "")
            self.assertEqual(ipa[0]["indirizzo"], "Via Test 1")

    def test_parser_never_substitutes_codice_istat_for_administrative_code(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong.xlsx"
            _write_xlsx(
                path,
                [
                    "CODICE ISTAT",
                    "CODICE IPA",
                    "ACCESSI IN ANNCSU",
                    "DI CUI CON COORDINATE",
                ],
                [["112001", "c_i452", "1", "1"]],
                shared_strings=False,
            )
            with self.assertRaisesRegex(
                MunicipalSeatReconciliationError, "required headers"
            ):
                read_anncsu_workbook(path)

    def test_build_from_paths_is_deterministic_and_load_rejects_noncanonical_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = _catalog()
            catalog_path = root / "catalog.json"
            # Match the checked-in national catalog writer contract.
            catalog_path.write_bytes(canonical_json_bytes(catalog) + b"\n")
            anncsu_path = root / "anncsu.xlsx"
            ipa_path = root / "ipa.xlsx"
            _write_xlsx(
                anncsu_path,
                [
                    "Regione",
                    "Provincia Amministrativa",
                    "COMUNE",
                    "CODICE IPA",
                    "CODICE AMMINISTRATIVO",
                    "CODICE ISTAT",
                    "ACCESSI IN ANNCSU",
                    "DI CUI CON COORDINATE",
                ],
                [list(row.values()) for row in _anncsu_rows()],
                shared_strings=False,
            )
            _write_xlsx(
                ipa_path,
                [
                    "Codice_IPA",
                    "Denominazione_ente",
                    "Codice_catastale_comune",
                    "CAP",
                    "Indirizzo",
                    "Data_aggiornamento",
                ],
                [list(row.values()) for row in _ipa_rows()],
                shared_strings=True,
            )
            expected_anncsu_sha256 = hashlib.sha256(
                anncsu_path.read_bytes()
            ).hexdigest()
            expected_ipa_sha256 = hashlib.sha256(ipa_path.read_bytes()).hexdigest()

            first = build_from_paths(
                catalog_path=catalog_path,
                anncsu_path=anncsu_path,
                ipa_path=ipa_path,
                expected_anncsu_sha256=expected_anncsu_sha256,
                expected_ipa_sha256=expected_ipa_sha256,
                anncsu_reference_date="2026-03-31",
                ipa_reference_date="2026-09-20",
                expected_count=2,
            )
            second = build_from_paths(
                catalog_path=catalog_path,
                anncsu_path=anncsu_path,
                ipa_path=ipa_path,
                expected_anncsu_sha256=expected_anncsu_sha256,
                expected_ipa_sha256=expected_ipa_sha256,
                anncsu_reference_date="2026-03-31",
                ipa_reference_date="2026-09-20",
                expected_count=2,
            )
            self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))

            mismatches = (
                ("0" * 64, expected_ipa_sha256, "ANNCSU source SHA-256 mismatch"),
                (expected_anncsu_sha256, "0" * 64, "IPA source SHA-256 mismatch"),
            )
            for anncsu_digest, ipa_digest, expected_error in mismatches:
                with self.subTest(expected_error=expected_error), self.assertRaisesRegex(
                    MunicipalSeatReconciliationError, expected_error
                ):
                    build_from_paths(
                        catalog_path=catalog_path,
                        anncsu_path=anncsu_path,
                        ipa_path=ipa_path,
                        expected_anncsu_sha256=anncsu_digest,
                        expected_ipa_sha256=ipa_digest,
                        anncsu_reference_date="2026-03-31",
                        ipa_reference_date="2026-09-20",
                        expected_count=2,
                    )

            noncanonical = root / "noncanonical.json"
            noncanonical.write_text(json.dumps(first, indent=2), encoding="utf-8")
            with self.assertRaisesRegex(
                MunicipalSeatReconciliationError, "not canonical"
            ):
                load_reconciliation_audit(
                    noncanonical, catalog=catalog, expected_count=2
                )

    def test_build_hashes_and_parses_the_same_snapshot_during_file_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = _catalog()
            catalog_path = root / "catalog.json"
            catalog_path.write_bytes(canonical_json_bytes(catalog) + b"\n")
            anncsu_path = root / "anncsu.xlsx"
            ipa_path = root / "ipa.xlsx"
            _write_xlsx(
                anncsu_path,
                [
                    "Regione",
                    "Provincia Amministrativa",
                    "COMUNE",
                    "CODICE IPA",
                    "CODICE AMMINISTRATIVO",
                    "CODICE ISTAT",
                    "ACCESSI IN ANNCSU",
                    "DI CUI CON COORDINATE",
                ],
                [list(row.values()) for row in _anncsu_rows()],
                shared_strings=False,
            )
            _write_xlsx(
                ipa_path,
                [
                    "Codice_IPA",
                    "Denominazione_ente",
                    "Codice_catastale_comune",
                    "CAP",
                    "Indirizzo",
                    "Data_aggiornamento",
                ],
                [list(row.values()) for row in _ipa_rows()],
                shared_strings=True,
            )
            original_anncsu = anncsu_path.read_bytes()
            original_ipa = ipa_path.read_bytes()

            def snapshot_then_replace(path):
                source = Path(path)
                snapshot = source.read_bytes()
                if source == anncsu_path:
                    source.write_bytes(b"concurrent replacement, not an XLSX")
                return snapshot

            with patch.object(
                seat_reconciliation,
                "_read_file_snapshot",
                side_effect=snapshot_then_replace,
            ):
                audit = build_from_paths(
                    catalog_path=catalog_path,
                    anncsu_path=anncsu_path,
                    ipa_path=ipa_path,
                    expected_anncsu_sha256=hashlib.sha256(
                        original_anncsu
                    ).hexdigest(),
                    expected_ipa_sha256=hashlib.sha256(original_ipa).hexdigest(),
                    anncsu_reference_date="2026-03-31",
                    ipa_reference_date="2026-09-20",
                    expected_count=2,
                )

            self.assertEqual(audit["summary"]["pending"], 2)
            self.assertEqual(
                audit["sources"]["anncsu_georeferencing"]["sha256"],
                hashlib.sha256(original_anncsu).hexdigest(),
            )
            self.assertEqual(
                anncsu_path.read_bytes(), b"concurrent replacement, not an XLSX"
            )

    def test_negative_shared_string_index_is_rejected(self):
        cell = ElementTree.fromstring(
            f'<c xmlns="{MAIN_NS}" t="s"><v>-1</v></c>'
        )
        with self.assertRaisesRegex(
            MunicipalSeatReconciliationError, "shared-string reference"
        ):
            seat_reconciliation._cell_value(cell, ("must-not-be-selected",))

    def test_duplicate_zip_members_and_oversized_snapshots_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workbook = root / "ambiguous.xlsx"
            _write_xlsx(
                workbook,
                [
                    "CODICE AMMINISTRATIVO",
                    "CODICE IPA",
                    "ACCESSI IN ANNCSU",
                    "DI CUI CON COORDINATE",
                ],
                [["I452", "c_i452", "1", "1"]],
                shared_strings=False,
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with ZipFile(workbook, "a") as archive:
                    archive.writestr("xl/workbook.xml", b"duplicate")
            with self.assertRaisesRegex(
                MunicipalSeatReconciliationError, "duplicate archive members"
            ):
                read_anncsu_workbook(workbook)

            oversized = root / "oversized.bin"
            oversized.write_bytes(b"12345")
            with patch.object(
                seat_reconciliation, "_MAX_SOURCE_FILE_BYTES", 4
            ), self.assertRaisesRegex(
                MunicipalSeatReconciliationError, "safe size limit"
            ):
                seat_reconciliation._read_file_snapshot(oversized)

    def test_impossible_provenance_date_is_rejected(self):
        catalog = _catalog()
        with self.assertRaisesRegex(MunicipalSeatReconciliationError, "valid date"):
            source_provenance(
                catalog=catalog,
                catalog_file_sha256="a" * 64,
                anncsu_file_sha256="b" * 64,
                anncsu_reference_date="2026-99-99",
                ipa_file_sha256="c" * 64,
                ipa_reference_date="2026-09-20",
            )

    def test_create_only_never_overwrites_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            write_create_only(path, b"first")
            with self.assertRaisesRegex(
                MunicipalSeatReconciliationError, "create-only"
            ):
                write_create_only(path, b"second")
            self.assertEqual(path.read_bytes(), b"first")


if __name__ == "__main__":
    unittest.main()
