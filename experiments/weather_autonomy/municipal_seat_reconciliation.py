"""Build an offline audit for Italy's municipal-seat forecast points.

This gate deliberately does *not* emit forecast coordinates.  It reconciles
the current Meteo Friul municipality catalog with two reviewed institutional
workbooks:

* ANNCSU's municipality georeferencing coverage workbook; and
* IndicePA's ``Enti`` workbook, which contains the official entity address.

The only identity chain is::

    catalog.cadastral_code
      -> ANNCSU ``CODICE AMMINISTRATIVO``
      -> ANNCSU ``CODICE IPA``
      -> IndicePA ``Codice_IPA``

ANNCSU ``CODICE ISTAT`` is retained as audit evidence but is never a join key.
That distinction is material after administrative-code changes such as the
2026 Sardinia reorganisation.

The implementation is standard-library only, deterministic, fail-closed and
offline.  Output is create-only and every record keeps latitude/longitude
null until a later, separately reviewed address-to-access resolution gate.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

try:  # pragma: no cover - exercised by direct CLI execution
    from .national_catalog import (
        EXPECTED_MUNICIPALITY_COUNT,
        NationalCatalogError,
        canonical_json_bytes,
        validate_catalog,
    )
except ImportError:  # pragma: no cover
    from national_catalog import (  # type: ignore
        EXPECTED_MUNICIPALITY_COUNT,
        NationalCatalogError,
        canonical_json_bytes,
        validate_catalog,
    )


AUDIT_KIND = "meteofriul.weather.municipal_seat_reconciliation_audit"
AUDIT_SCHEMA_VERSION = 1
ANNCSU_DATASET = "ANNCSU georeferencing coverage by municipality"
ANNCSU_SOURCE_URL = (
    "https://www.anncsu.gov.it/export/sites/anncsu/.allegati/"
    "Georeferenziazione-accessi-ANNCSU_31-MARZO.xlsx"
)
IPA_DATASET = "IndicePA Enti"
IPA_SOURCE_URL = (
    "https://indicepa.gov.it/ipa-dati/dataset/"
    "5baa3eb8-266e-455a-8de8-b1f434c279b2/resource/"
    "d09adf99-dc10-4349-8c53-27b1e5aa97b6/download/enti.xlsx"
)

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ISTAT_RE = re.compile(r"^\d{6}$")
_CADASTRAL_RE = re.compile(r"^[A-Z]\d{3}$")
_IPA_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CELL_REFERENCE_RE = re.compile(r"^([A-Z]+)[1-9]\d*$")

_MAX_XLSX_MEMBERS = 256
_MAX_SOURCE_FILE_BYTES = 64 * 1024 * 1024
_MAX_XLSX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
_MAX_SHARED_STRINGS = 1_000_000
_MAX_WORKSHEET_ROWS = 250_000
_MAX_WORKSHEET_COLUMNS = 256
_MAX_CELL_CHARS = 16_384
_HEADER_SCAN_LIMIT = 50

_ANNCSU_HEADERS = (
    "regione",
    "provincia_amministrativa",
    "comune",
    "codice_ipa",
    "codice_amministrativo",
    "codice_istat",
    "accessi_in_anncsu",
    "di_cui_con_coordinate",
)
_IPA_HEADERS = (
    "codice_ipa",
    "denominazione_ente",
    "codice_catastale_comune",
    "cap",
    "indirizzo",
    "data_aggiornamento",
)

_RECORD_KEYS = frozenset(
    {
        "anncsu",
        "cadastral_code",
        "ipa_seat",
        "istat_code",
        "name",
        "point_resolution",
        "province_abbreviation",
        "region_iso",
    }
)
_ANNCSU_KEYS = frozenset(
    {
        "access_count",
        "administrative_code",
        "coordinate_coverage_basis_points",
        "georeferenced_access_count",
        "ipa_code",
        "reported_istat_code",
        "reported_istat_matches_catalog",
        "reported_municipality_name",
        "reported_province",
        "reported_region",
    }
)
_IPA_KEYS = frozenset(
    {
        "address",
        "denomination",
        "ipa_code",
        "municipality_cadastral_code",
        "municipality_cadastral_matches_catalog",
        "postal_code",
        "updated_at",
    }
)
_POINT_KEYS = frozenset(
    {"latitude", "longitude", "method", "reason_code", "status"}
)
_UNRESOLVED_REASONS = frozenset(
    {
        "anncsu_duplicate_administrative_code",
        "anncsu_ipa_code_missing",
        "anncsu_municipality_missing",
        "ipa_duplicate_code",
        "ipa_entity_missing",
        "ipa_municipality_cadastral_mismatch",
        "ipa_seat_address_missing",
    }
)


class MunicipalSeatReconciliationError(ValueError):
    """Institutional inputs cannot produce an unambiguous seat audit."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_file_snapshot(path: str | Path) -> bytes:
    """Return the one immutable byte snapshot used for hashing and parsing."""

    with Path(path).open("rb") as stream:
        content = stream.read(_MAX_SOURCE_FILE_BYTES + 1)
    if len(content) > _MAX_SOURCE_FILE_BYTES:
        raise MunicipalSeatReconciliationError("source file exceeds the safe size limit")
    return content


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _required_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise MunicipalSeatReconciliationError(
            f"expected {label} SHA-256 is invalid"
        )
    return value


def _normalise_header(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip().casefold()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > _MAX_CELL_CHARS:
        raise MunicipalSeatReconciliationError("XLSX cell exceeds the safe text limit")
    return text


def _xlsx_guard(archive: ZipFile) -> None:
    members = archive.infolist()
    if len(members) > _MAX_XLSX_MEMBERS:
        raise MunicipalSeatReconciliationError("XLSX contains too many archive members")
    names = [item.filename for item in members]
    if len(names) != len(set(names)):
        raise MunicipalSeatReconciliationError("XLSX contains duplicate archive members")
    if sum(item.file_size for item in members) > _MAX_XLSX_UNCOMPRESSED_BYTES:
        raise MunicipalSeatReconciliationError("XLSX exceeds the safe uncompressed limit")
    for item in members:
        path = PurePosixPath(item.filename)
        if path.is_absolute() or ".." in path.parts:
            raise MunicipalSeatReconciliationError("XLSX contains an unsafe member path")


def _first_worksheet_path(archive: ZipFile) -> str:
    try:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationships = ElementTree.fromstring(
            archive.read("xl/_rels/workbook.xml.rels")
        )
    except (KeyError, ElementTree.ParseError) as error:
        raise MunicipalSeatReconciliationError("XLSX workbook metadata is invalid") from error

    sheet = workbook.find(f"{{{_MAIN_NS}}}sheets/{{{_MAIN_NS}}}sheet")
    if sheet is None:
        raise MunicipalSeatReconciliationError("XLSX has no worksheet")
    relation_id = sheet.get(f"{{{_DOC_REL_NS}}}id", "")
    target = ""
    for relation in relationships.findall(f"{{{_REL_NS}}}Relationship"):
        if relation.get("Id") == relation_id:
            target = relation.get("Target", "")
            break
    if not target:
        raise MunicipalSeatReconciliationError("XLSX first worksheet is unresolved")
    if target.startswith("/"):
        target = target.lstrip("/")
    else:
        target = str(PurePosixPath("xl") / target)
    target = str(PurePosixPath(target))
    if not target.startswith("xl/") or ".." in PurePosixPath(target).parts:
        raise MunicipalSeatReconciliationError("XLSX worksheet path is unsafe")
    if target not in archive.namelist():
        raise MunicipalSeatReconciliationError("XLSX worksheet member is missing")
    return target


def _shared_strings(archive: ZipFile) -> tuple[str, ...]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return ()
    values: list[str] = []
    try:
        with archive.open("xl/sharedStrings.xml") as stream:
            for _event, element in ElementTree.iterparse(stream, events=("end",)):
                if element.tag == f"{{{_MAIN_NS}}}si":
                    value = "".join(
                        node.text or ""
                        for node in element.iter(f"{{{_MAIN_NS}}}t")
                    )
                    values.append(_clean_text(value))
                    if len(values) > _MAX_SHARED_STRINGS:
                        raise MunicipalSeatReconciliationError(
                            "XLSX shared-string table exceeds the safe limit"
                        )
                    element.clear()
    except ElementTree.ParseError as error:
        raise MunicipalSeatReconciliationError("XLSX shared strings are invalid") from error
    return tuple(values)


def _column_number(reference: str) -> int:
    match = _CELL_REFERENCE_RE.fullmatch(reference)
    if match is None:
        raise MunicipalSeatReconciliationError("XLSX cell reference is invalid")
    result = 0
    for character in match.group(1):
        result = result * 26 + ord(character) - ord("A") + 1
    if result > _MAX_WORKSHEET_COLUMNS:
        raise MunicipalSeatReconciliationError("XLSX worksheet has too many columns")
    return result


def _cell_value(cell: ElementTree.Element, shared: Sequence[str]) -> str:
    if cell.find(f"{{{_MAIN_NS}}}f") is not None:
        raise MunicipalSeatReconciliationError("XLSX formulas are not accepted as evidence")
    cell_type = cell.get("t", "")
    if cell_type == "inlineStr":
        return _clean_text(
            "".join(
                node.text or ""
                for node in cell.iter(f"{{{_MAIN_NS}}}t")
            )
        )
    value_node = cell.find(f"{{{_MAIN_NS}}}v")
    if value_node is None or value_node.text is None:
        return ""
    value = value_node.text
    if cell_type == "s":
        if re.fullmatch(r"\d+", value) is None:
            raise MunicipalSeatReconciliationError(
                "XLSX shared-string reference is invalid"
            )
        try:
            return shared[int(value)]
        except (IndexError, ValueError) as error:
            raise MunicipalSeatReconciliationError(
                "XLSX shared-string reference is invalid"
            ) from error
    if cell_type == "e":
        raise MunicipalSeatReconciliationError("XLSX contains an error cell")
    return _clean_text(value)


def _read_xlsx_table_bytes(
    content: bytes,
    *,
    required_headers: Iterable[str],
    selected_headers: Iterable[str],
) -> tuple[dict[str, str], ...]:
    """Read selected columns from the first XLSX sheet without dependencies.

    A header may occur within the first 50 rows.  Header matching is
    case/spacing/underscore insensitive, but duplicate normalised headers and
    formulas fail closed.
    """

    required = {_normalise_header(item) for item in required_headers}
    selected = {_normalise_header(item) for item in selected_headers} | required
    try:
        with ZipFile(BytesIO(content)) as archive:
            _xlsx_guard(archive)
            shared = _shared_strings(archive)
            worksheet_path = _first_worksheet_path(archive)
            header_by_column: dict[int, str] | None = None
            output: list[dict[str, str]] = []
            observed_rows = 0
            with archive.open(worksheet_path) as stream:
                for _event, element in ElementTree.iterparse(stream, events=("end",)):
                    if element.tag != f"{{{_MAIN_NS}}}row":
                        continue
                    observed_rows += 1
                    if observed_rows > _MAX_WORKSHEET_ROWS:
                        raise MunicipalSeatReconciliationError(
                            "XLSX worksheet exceeds the safe row limit"
                        )
                    cells: dict[int, str] = {}
                    for cell in element.findall(f"{{{_MAIN_NS}}}c"):
                        column = _column_number(cell.get("r", ""))
                        if column in cells:
                            raise MunicipalSeatReconciliationError(
                                "XLSX row contains a duplicate cell reference"
                            )
                        cells[column] = _cell_value(cell, shared)

                    if header_by_column is None:
                        candidate: dict[int, str] = {}
                        seen_headers: set[str] = set()
                        duplicate_header = False
                        for column, raw in cells.items():
                            header = _normalise_header(raw)
                            if not header:
                                continue
                            if header in seen_headers:
                                duplicate_header = True
                            candidate[column] = header
                            seen_headers.add(header)
                        if required <= seen_headers:
                            if duplicate_header:
                                raise MunicipalSeatReconciliationError(
                                    "XLSX contains duplicate normalised headers"
                                )
                            header_by_column = candidate
                        elif observed_rows >= _HEADER_SCAN_LIMIT:
                            break
                    else:
                        record = {
                            header: cells.get(column, "")
                            for column, header in header_by_column.items()
                            if header in selected
                        }
                        if any(record.values()):
                            output.append(record)
                    element.clear()
    except (BadZipFile, OSError, ElementTree.ParseError) as error:
        raise MunicipalSeatReconciliationError("XLSX is unreadable") from error

    if header_by_column is None:
        missing = ", ".join(sorted(required))
        raise MunicipalSeatReconciliationError(
            f"XLSX required headers were not found: {missing}"
        )
    return tuple(output)


def read_xlsx_table(
    path: str | Path,
    *,
    required_headers: Iterable[str],
    selected_headers: Iterable[str],
) -> tuple[dict[str, str], ...]:
    """Read one immutable file snapshot and parse that exact snapshot."""

    return _read_xlsx_table_bytes(
        _read_file_snapshot(path),
        required_headers=required_headers,
        selected_headers=selected_headers,
    )


def read_anncsu_workbook(path: str | Path) -> tuple[dict[str, str], ...]:
    return read_anncsu_workbook_bytes(_read_file_snapshot(path))


def read_anncsu_workbook_bytes(content: bytes) -> tuple[dict[str, str], ...]:
    return _read_xlsx_table_bytes(
        content,
        required_headers=(
            "CODICE AMMINISTRATIVO",
            "CODICE IPA",
            "ACCESSI IN ANNCSU",
            "DI CUI CON COORDINATE",
        ),
        selected_headers=_ANNCSU_HEADERS,
    )


def read_ipa_entities_workbook(path: str | Path) -> tuple[dict[str, str], ...]:
    return read_ipa_entities_workbook_bytes(_read_file_snapshot(path))


def read_ipa_entities_workbook_bytes(
    content: bytes,
) -> tuple[dict[str, str], ...]:
    return _read_xlsx_table_bytes(
        content,
        required_headers=(
            "Codice_IPA",
            "Denominazione_ente",
            "Codice_catastale_comune",
            "CAP",
            "Indirizzo",
            "Data_aggiornamento",
        ),
        selected_headers=_IPA_HEADERS,
    )


def _normalise_cadastral(value: Any, *, allow_empty: bool = False) -> str:
    result = _clean_text(value).upper()
    if allow_empty and not result:
        return ""
    if not _CADASTRAL_RE.fullmatch(result):
        raise MunicipalSeatReconciliationError(
            f"invalid cadastral/administrative code: {result!r}"
        )
    return result


def _normalise_ipa(value: Any, *, allow_empty: bool = False) -> str:
    result = _clean_text(value)
    if allow_empty and not result:
        return ""
    if not _IPA_RE.fullmatch(result):
        raise MunicipalSeatReconciliationError(f"invalid IPA code: {result!r}")
    return result


def _normalise_reported_istat(value: Any) -> str:
    result = _clean_text(value)
    if not result:
        return ""
    if re.fullmatch(r"\d{1,6}(?:\.0+)?", result) is None:
        raise MunicipalSeatReconciliationError(
            f"invalid ANNCSU reported ISTAT code: {result!r}"
        )
    return result.split(".", 1)[0].zfill(6)


def _nonnegative_integer(value: Any, label: str) -> int:
    result = _clean_text(value)
    if not result:
        return 0
    if re.fullmatch(r"\d+(?:\.0+)?", result) is None:
        raise MunicipalSeatReconciliationError(f"{label} is not an integer")
    return int(result.split(".", 1)[0])


def _coverage_basis_points(total: int, georeferenced: int) -> int | None:
    if total == 0:
        return None
    # Integer half-up rounding; deterministic and free of binary floats.
    return (georeferenced * 10_000 + total // 2) // total


def _valid_date(value: str, label: str) -> str:
    value = _clean_text(value)
    if not _DATE_RE.fullmatch(value):
        raise MunicipalSeatReconciliationError(f"{label} must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise MunicipalSeatReconciliationError(f"{label} is not a valid date") from error
    if parsed.isoformat() != value:
        raise MunicipalSeatReconciliationError(f"{label} is not canonical")
    return value


def _validate_catalog_identity(
    catalog: Mapping[str, Any], expected_count: int
) -> tuple[dict[str, Any], ...]:
    municipalities = catalog.get("municipalities")
    if not isinstance(municipalities, list) or len(municipalities) != expected_count:
        raise MunicipalSeatReconciliationError(
            f"catalog must contain {expected_count} municipalities"
        )
    expected_catalog_hash = catalog.get("catalog_sha256")
    if not isinstance(expected_catalog_hash, str) or not _SHA256_RE.fullmatch(
        expected_catalog_hash
    ):
        raise MunicipalSeatReconciliationError("catalog SHA-256 is invalid")
    content = dict(catalog)
    content.pop("catalog_sha256", None)
    if _sha256(canonical_json_bytes(content)) != expected_catalog_hash:
        raise MunicipalSeatReconciliationError("catalog SHA-256 mismatch")

    output: list[dict[str, Any]] = []
    seen_istat: set[str] = set()
    seen_cadastral: set[str] = set()
    for item in municipalities:
        if not isinstance(item, Mapping):
            raise MunicipalSeatReconciliationError("catalog municipality is invalid")
        istat_code = _clean_text(item.get("istat_code"))
        cadastral_code = _normalise_cadastral(item.get("cadastral_code"))
        name = _clean_text(item.get("name"))
        province = _clean_text(item.get("province_abbreviation"))
        region_iso = _clean_text(item.get("region_iso"))
        if (
            not _ISTAT_RE.fullmatch(istat_code)
            or not name
            or not province
            or not re.fullmatch(r"IT-\d{2}", region_iso)
            or istat_code in seen_istat
            or cadastral_code in seen_cadastral
        ):
            raise MunicipalSeatReconciliationError(
                "catalog municipality identity is incomplete or duplicated"
            )
        seen_istat.add(istat_code)
        seen_cadastral.add(cadastral_code)
        output.append(
            {
                "istat_code": istat_code,
                "cadastral_code": cadastral_code,
                "name": name,
                "province_abbreviation": province,
                "region_iso": region_iso,
            }
        )
    return tuple(sorted(output, key=lambda item: item["istat_code"]))


def source_provenance(
    *,
    catalog: Mapping[str, Any],
    catalog_file_sha256: str,
    anncsu_file_sha256: str,
    anncsu_reference_date: str,
    ipa_file_sha256: str,
    ipa_reference_date: str,
) -> dict[str, Any]:
    for digest in (catalog_file_sha256, anncsu_file_sha256, ipa_file_sha256):
        if not _SHA256_RE.fullmatch(digest):
            raise MunicipalSeatReconciliationError("source SHA-256 is invalid")
    return {
        "anncsu_georeferencing": {
            "dataset": ANNCSU_DATASET,
            "reference_date": _valid_date(
                anncsu_reference_date, "ANNCSU reference date"
            ),
            "sha256": anncsu_file_sha256,
            "url": ANNCSU_SOURCE_URL,
        },
        "catalog": {
            "catalog_sha256": catalog["catalog_sha256"],
            "file_sha256": catalog_file_sha256,
            "kind": catalog.get("kind", ""),
            "version": catalog.get("catalog_version", ""),
        },
        "ipa_entities": {
            "dataset": IPA_DATASET,
            "reference_date": _valid_date(ipa_reference_date, "IPA reference date"),
            "sha256": ipa_file_sha256,
            "url": IPA_SOURCE_URL,
        },
    }


def _anncsu_record(row: Mapping[str, Any], municipality: Mapping[str, Any]) -> dict[str, Any]:
    access_count = _nonnegative_integer(row.get("accessi_in_anncsu"), "ANNCSU access count")
    georeferenced = _nonnegative_integer(
        row.get("di_cui_con_coordinate"), "ANNCSU georeferenced access count"
    )
    if georeferenced > access_count:
        raise MunicipalSeatReconciliationError(
            "ANNCSU georeferenced access count exceeds total accesses"
        )
    reported_istat = _normalise_reported_istat(row.get("codice_istat"))
    return {
        "access_count": access_count,
        "administrative_code": _normalise_cadastral(row.get("codice_amministrativo")),
        "coordinate_coverage_basis_points": _coverage_basis_points(
            access_count, georeferenced
        ),
        "georeferenced_access_count": georeferenced,
        "ipa_code": _normalise_ipa(row.get("codice_ipa"), allow_empty=True),
        "reported_istat_code": reported_istat,
        "reported_istat_matches_catalog": reported_istat
        == municipality["istat_code"],
        "reported_municipality_name": _clean_text(row.get("comune")),
        "reported_province": _clean_text(row.get("provincia_amministrativa")),
        "reported_region": _clean_text(row.get("regione")),
    }


def _ipa_record(row: Mapping[str, Any], municipality: Mapping[str, Any]) -> dict[str, Any]:
    cadastral = _normalise_cadastral(
        row.get("codice_catastale_comune"), allow_empty=True
    )
    return {
        "address": _clean_text(row.get("indirizzo")),
        "denomination": _clean_text(row.get("denominazione_ente")),
        "ipa_code": _normalise_ipa(row.get("codice_ipa")),
        "municipality_cadastral_code": cadastral,
        "municipality_cadastral_matches_catalog": cadastral
        == municipality["cadastral_code"],
        "postal_code": _clean_text(row.get("cap")),
        "updated_at": _clean_text(row.get("data_aggiornamento")),
    }


def _point(status: str, reason: str) -> dict[str, Any]:
    return {
        "latitude": None,
        "longitude": None,
        "method": None,
        "reason_code": reason,
        "status": status,
    }


def build_reconciliation_audit(
    catalog: Mapping[str, Any],
    anncsu_rows: Sequence[Mapping[str, Any]],
    ipa_rows: Sequence[Mapping[str, Any]],
    *,
    sources: Mapping[str, Any],
    expected_count: int = EXPECTED_MUNICIPALITY_COUNT,
) -> dict[str, Any]:
    """Build the deterministic all-municipality reconciliation document."""

    municipalities = _validate_catalog_identity(catalog, expected_count)
    anncsu_by_administrative: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in anncsu_rows:
        code = _normalise_cadastral(row.get("codice_amministrativo"))
        anncsu_by_administrative[code].append(row)

    ipa_by_code: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in ipa_rows:
        code = _normalise_ipa(row.get("codice_ipa"))
        ipa_by_code[code.casefold()].append(row)

    records: list[dict[str, Any]] = []
    for municipality in municipalities:
        anncsu: dict[str, Any] | None = None
        ipa_seat: dict[str, Any] | None = None
        matches = anncsu_by_administrative.get(municipality["cadastral_code"], [])
        if not matches:
            reason = "anncsu_municipality_missing"
            point = _point("unresolved", reason)
        elif len(matches) != 1:
            reason = "anncsu_duplicate_administrative_code"
            point = _point("unresolved", reason)
        else:
            anncsu = _anncsu_record(matches[0], municipality)
            if not anncsu["ipa_code"]:
                reason = "anncsu_ipa_code_missing"
                point = _point("unresolved", reason)
            else:
                ipa_matches = ipa_by_code.get(anncsu["ipa_code"].casefold(), [])
                if not ipa_matches:
                    reason = "ipa_entity_missing"
                    point = _point("unresolved", reason)
                elif len(ipa_matches) != 1:
                    reason = "ipa_duplicate_code"
                    point = _point("unresolved", reason)
                else:
                    ipa_seat = _ipa_record(ipa_matches[0], municipality)
                    if not ipa_seat["municipality_cadastral_matches_catalog"]:
                        reason = "ipa_municipality_cadastral_mismatch"
                        point = _point("unresolved", reason)
                    elif not ipa_seat["address"]:
                        reason = "ipa_seat_address_missing"
                        point = _point("unresolved", reason)
                    else:
                        reason = "seat_access_resolution_pending"
                        point = _point("pending", reason)
        records.append(
            {
                "anncsu": anncsu,
                "cadastral_code": municipality["cadastral_code"],
                "ipa_seat": ipa_seat,
                "istat_code": municipality["istat_code"],
                "name": municipality["name"],
                "point_resolution": point,
                "province_abbreviation": municipality["province_abbreviation"],
                "region_iso": municipality["region_iso"],
            }
        )

    summary = _summary(records)
    records_sha256 = _sha256(canonical_json_bytes(records))
    document: dict[str, Any] = {
        "catalog_sha256": catalog["catalog_sha256"],
        "kind": AUDIT_KIND,
        "municipality_codes_sha256": _sha256(
            canonical_json_bytes(sorted(item["istat_code"] for item in records))
        ),
        "municipality_count": len(records),
        "records": records,
        "records_sha256": records_sha256,
        "schema_version": AUDIT_SCHEMA_VERSION,
        "sources": dict(sources),
        "summary": summary,
    }
    document["audit_sha256"] = _sha256(canonical_json_bytes(document))
    validate_reconciliation_audit(
        document, catalog=catalog, expected_count=expected_count
    )
    return document


def _summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    reason_counts = Counter(
        item["point_resolution"]["reason_code"] for item in records
    )
    coverage = Counter()
    for item in records:
        anncsu = item.get("anncsu")
        if not isinstance(anncsu, Mapping):
            continue
        total = anncsu["access_count"]
        covered = anncsu["georeferenced_access_count"]
        if total == 0:
            coverage["no_accesses"] += 1
        elif covered == 0:
            coverage["zero"] += 1
        elif covered == total:
            coverage["complete"] += 1
        else:
            coverage["partial"] += 1
    return {
        "anncsu_coordinate_coverage": {
            "complete": coverage["complete"],
            "no_accesses": coverage["no_accesses"],
            "partial": coverage["partial"],
            "zero": coverage["zero"],
        },
        "pending": reason_counts["seat_access_resolution_pending"],
        "unresolved": sum(
            count
            for reason, count in reason_counts.items()
            if reason != "seat_access_resolution_pending"
        ),
        "unresolved_reasons": {
            reason: reason_counts[reason]
            for reason in sorted(_UNRESOLVED_REASONS)
            if reason_counts[reason]
        },
    }


def _require_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    if frozenset(value) != expected:
        raise MunicipalSeatReconciliationError(f"{label} keys are invalid")


def validate_reconciliation_audit(
    document: Mapping[str, Any],
    *,
    catalog: Mapping[str, Any] | None = None,
    expected_count: int = EXPECTED_MUNICIPALITY_COUNT,
) -> None:
    """Strictly validate hashes, shape, ordering and fail-closed semantics."""

    expected_top = frozenset(
        {
            "audit_sha256",
            "catalog_sha256",
            "kind",
            "municipality_codes_sha256",
            "municipality_count",
            "records",
            "records_sha256",
            "schema_version",
            "sources",
            "summary",
        }
    )
    _require_keys(document, expected_top, "audit")
    if document.get("kind") != AUDIT_KIND or document.get("schema_version") != 1:
        raise MunicipalSeatReconciliationError("audit contract identity is invalid")
    if document.get("municipality_count") != expected_count:
        raise MunicipalSeatReconciliationError("audit municipality count is invalid")
    records = document.get("records")
    if not isinstance(records, list) or len(records) != expected_count:
        raise MunicipalSeatReconciliationError("audit records are incomplete")
    for field in (
        "audit_sha256",
        "catalog_sha256",
        "municipality_codes_sha256",
        "records_sha256",
    ):
        if not isinstance(document.get(field), str) or not _SHA256_RE.fullmatch(
            document[field]
        ):
            raise MunicipalSeatReconciliationError(f"audit {field} is invalid")

    if _sha256(canonical_json_bytes(records)) != document["records_sha256"]:
        raise MunicipalSeatReconciliationError("audit records hash mismatch")
    content = dict(document)
    expected_audit_hash = content.pop("audit_sha256")
    if _sha256(canonical_json_bytes(content)) != expected_audit_hash:
        raise MunicipalSeatReconciliationError("audit hash mismatch")

    codes: list[str] = []
    previous = ""
    catalog_by_istat: dict[str, Mapping[str, Any]] = {}
    if catalog is not None:
        catalog_by_istat = {
            item["istat_code"]: item
            for item in _validate_catalog_identity(catalog, expected_count)
        }
        if document["catalog_sha256"] != catalog["catalog_sha256"]:
            raise MunicipalSeatReconciliationError("audit catalog binding mismatch")

    for record in records:
        if not isinstance(record, Mapping):
            raise MunicipalSeatReconciliationError("audit record is invalid")
        _require_keys(record, _RECORD_KEYS, "audit record")
        istat = record.get("istat_code")
        cadastral = record.get("cadastral_code")
        if not isinstance(istat, str) or not _ISTAT_RE.fullmatch(istat):
            raise MunicipalSeatReconciliationError("record ISTAT code is invalid")
        if istat <= previous:
            raise MunicipalSeatReconciliationError("audit records are not uniquely sorted")
        previous = istat
        codes.append(istat)
        if not isinstance(cadastral, str) or not _CADASTRAL_RE.fullmatch(cadastral):
            raise MunicipalSeatReconciliationError("record cadastral code is invalid")
        if not isinstance(record.get("name"), str) or not record["name"]:
            raise MunicipalSeatReconciliationError("record municipality name is invalid")
        if (
            not isinstance(record.get("province_abbreviation"), str)
            or not record["province_abbreviation"]
            or not isinstance(record.get("region_iso"), str)
            or re.fullmatch(r"IT-\d{2}", record["region_iso"]) is None
        ):
            raise MunicipalSeatReconciliationError(
                "record province or region identity is invalid"
            )
        if catalog_by_istat:
            expected = catalog_by_istat.get(istat)
            identity = {
                key: record[key]
                for key in (
                    "istat_code",
                    "cadastral_code",
                    "name",
                    "province_abbreviation",
                    "region_iso",
                )
            }
            if expected is None or identity != expected:
                raise MunicipalSeatReconciliationError(
                    "record identity differs from the bound catalog"
                )

        anncsu = record.get("anncsu")
        if anncsu is not None:
            if not isinstance(anncsu, Mapping):
                raise MunicipalSeatReconciliationError("ANNCSU evidence is invalid")
            _require_keys(anncsu, _ANNCSU_KEYS, "ANNCSU evidence")
            if anncsu["administrative_code"] != cadastral:
                raise MunicipalSeatReconciliationError("ANNCSU join key mismatch")
            if (
                not isinstance(anncsu["ipa_code"], str)
                or (
                    anncsu["ipa_code"]
                    and _IPA_RE.fullmatch(anncsu["ipa_code"]) is None
                )
                or any(
                    not isinstance(anncsu[field], str)
                    for field in (
                        "reported_istat_code",
                        "reported_municipality_name",
                        "reported_province",
                        "reported_region",
                    )
                )
            ):
                raise MunicipalSeatReconciliationError("ANNCSU evidence text is invalid")
            total = anncsu["access_count"]
            covered = anncsu["georeferenced_access_count"]
            if (
                not isinstance(total, int)
                or isinstance(total, bool)
                or not isinstance(covered, int)
                or isinstance(covered, bool)
                or total < 0
                or covered < 0
                or covered > total
                or anncsu["coordinate_coverage_basis_points"]
                != _coverage_basis_points(total, covered)
            ):
                raise MunicipalSeatReconciliationError(
                    "ANNCSU coordinate coverage is invalid"
                )
            reported = anncsu["reported_istat_code"]
            if reported and not _ISTAT_RE.fullmatch(reported):
                raise MunicipalSeatReconciliationError("ANNCSU ISTAT evidence is invalid")
            if anncsu["reported_istat_matches_catalog"] != (reported == istat):
                raise MunicipalSeatReconciliationError(
                    "ANNCSU ISTAT comparison is inconsistent"
                )

        ipa = record.get("ipa_seat")
        if ipa is not None:
            if not isinstance(ipa, Mapping):
                raise MunicipalSeatReconciliationError("IPA evidence is invalid")
            _require_keys(ipa, _IPA_KEYS, "IPA evidence")
            if (
                not isinstance(ipa["ipa_code"], str)
                or _IPA_RE.fullmatch(ipa["ipa_code"]) is None
                or not isinstance(ipa["municipality_cadastral_code"], str)
                or (
                    ipa["municipality_cadastral_code"]
                    and _CADASTRAL_RE.fullmatch(
                        ipa["municipality_cadastral_code"]
                    )
                    is None
                )
                or any(
                    not isinstance(ipa[field], str)
                    for field in (
                        "address",
                        "denomination",
                        "postal_code",
                        "updated_at",
                    )
                )
            ):
                raise MunicipalSeatReconciliationError("IPA evidence text is invalid")
            if (
                anncsu is None
                or ipa["ipa_code"].casefold() != anncsu["ipa_code"].casefold()
            ):
                raise MunicipalSeatReconciliationError("IPA join key mismatch")
            matches = ipa["municipality_cadastral_code"] == cadastral
            if ipa["municipality_cadastral_matches_catalog"] != matches:
                raise MunicipalSeatReconciliationError(
                    "IPA cadastral comparison is inconsistent"
                )

        point = record.get("point_resolution")
        if not isinstance(point, Mapping):
            raise MunicipalSeatReconciliationError("point resolution is invalid")
        _require_keys(point, _POINT_KEYS, "point resolution")
        if any(point[field] is not None for field in ("latitude", "longitude", "method")):
            raise MunicipalSeatReconciliationError(
                "reconciliation audit must not contain forecast coordinates"
            )
        status, reason = point.get("status"), point.get("reason_code")
        if status == "pending":
            if (
                reason != "seat_access_resolution_pending"
                or anncsu is None
                or ipa is None
                or not ipa["municipality_cadastral_matches_catalog"]
                or not ipa["address"]
            ):
                raise MunicipalSeatReconciliationError("pending point is not justified")
        elif status == "unresolved":
            if reason not in _UNRESOLVED_REASONS:
                raise MunicipalSeatReconciliationError("unresolved reason is invalid")
            reason_shape_is_valid = {
                "anncsu_municipality_missing": anncsu is None and ipa is None,
                "anncsu_duplicate_administrative_code": anncsu is None
                and ipa is None,
                "anncsu_ipa_code_missing": anncsu is not None
                and not anncsu["ipa_code"]
                and ipa is None,
                "ipa_entity_missing": anncsu is not None
                and bool(anncsu["ipa_code"])
                and ipa is None,
                "ipa_duplicate_code": anncsu is not None
                and bool(anncsu["ipa_code"])
                and ipa is None,
                "ipa_municipality_cadastral_mismatch": anncsu is not None
                and ipa is not None
                and not ipa["municipality_cadastral_matches_catalog"],
                "ipa_seat_address_missing": anncsu is not None
                and ipa is not None
                and ipa["municipality_cadastral_matches_catalog"]
                and not ipa["address"],
            }[reason]
            if not reason_shape_is_valid:
                raise MunicipalSeatReconciliationError(
                    "unresolved reason does not match its evidence"
                )
        else:
            raise MunicipalSeatReconciliationError("point status is invalid")

    if _sha256(canonical_json_bytes(codes)) != document["municipality_codes_sha256"]:
        raise MunicipalSeatReconciliationError("municipality code hash mismatch")
    if document.get("summary") != _summary(records):
        raise MunicipalSeatReconciliationError("audit summary mismatch")
    sources = document.get("sources")
    if not isinstance(sources, Mapping) or frozenset(sources) != frozenset(
        {"anncsu_georeferencing", "catalog", "ipa_entities"}
    ):
        raise MunicipalSeatReconciliationError("audit source provenance is invalid")
    catalog_source = sources["catalog"]
    if not isinstance(catalog_source, Mapping) or frozenset(catalog_source) != frozenset(
        {"catalog_sha256", "file_sha256", "kind", "version"}
    ):
        raise MunicipalSeatReconciliationError("catalog source descriptor is invalid")
    if catalog_source.get("catalog_sha256") != document["catalog_sha256"]:
        raise MunicipalSeatReconciliationError("source catalog binding mismatch")
    for source_name in ("anncsu_georeferencing", "ipa_entities"):
        source = sources[source_name]
        if (
            not isinstance(source, Mapping)
            or frozenset(source)
            != frozenset({"dataset", "reference_date", "sha256", "url"})
            or not _SHA256_RE.fullmatch(str(source.get("sha256", "")))
            or not _DATE_RE.fullmatch(str(source.get("reference_date", "")))
            or not source.get("dataset")
            or not source.get("url")
        ):
            raise MunicipalSeatReconciliationError("source descriptor is invalid")
    if (
        not _SHA256_RE.fullmatch(str(catalog_source.get("file_sha256", "")))
        or not isinstance(catalog_source.get("kind"), str)
        or not catalog_source["kind"]
        or not isinstance(catalog_source.get("version"), str)
        or not catalog_source["version"]
    ):
        raise MunicipalSeatReconciliationError("catalog source hash is invalid")


def load_reconciliation_audit(
    path: str | Path,
    *,
    catalog: Mapping[str, Any] | None = None,
    expected_count: int = EXPECTED_MUNICIPALITY_COUNT,
) -> dict[str, Any]:
    raw = Path(path).read_bytes()
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MunicipalSeatReconciliationError("audit JSON is unreadable") from error
    if not isinstance(document, dict) or canonical_json_bytes(document) != raw:
        raise MunicipalSeatReconciliationError("audit is not canonical JSON")
    validate_reconciliation_audit(
        document, catalog=catalog, expected_count=expected_count
    )
    return document


def write_create_only(path: str | Path, content: bytes) -> None:
    """Create ``path`` atomically with respect to pre-existing output."""

    output = Path(path)
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        created = True
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise MunicipalSeatReconciliationError(
            f"output already exists (create-only): {output}"
        ) from error
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        if created:
            try:
                output.unlink()
            except OSError:
                pass
        raise


def build_from_paths(
    *,
    catalog_path: str | Path,
    anncsu_path: str | Path,
    ipa_path: str | Path,
    expected_anncsu_sha256: str,
    expected_ipa_sha256: str,
    anncsu_reference_date: str,
    ipa_reference_date: str,
    expected_count: int = EXPECTED_MUNICIPALITY_COUNT,
) -> dict[str, Any]:
    expected_anncsu_sha256 = _required_sha256(
        expected_anncsu_sha256, "ANNCSU source"
    )
    expected_ipa_sha256 = _required_sha256(expected_ipa_sha256, "IPA source")
    # Snapshot every input exactly once.  Provenance hashes and parsers below
    # consume these same immutable bytes, so a concurrent file replacement
    # cannot bind the audit to content different from the parsed content.
    catalog_raw = _read_file_snapshot(catalog_path)
    anncsu_raw = _read_file_snapshot(anncsu_path)
    ipa_raw = _read_file_snapshot(ipa_path)
    anncsu_sha256 = _sha256(anncsu_raw)
    ipa_sha256 = _sha256(ipa_raw)
    if anncsu_sha256 != expected_anncsu_sha256:
        raise MunicipalSeatReconciliationError("ANNCSU source SHA-256 mismatch")
    if ipa_sha256 != expected_ipa_sha256:
        raise MunicipalSeatReconciliationError("IPA source SHA-256 mismatch")
    try:
        catalog = json.loads(catalog_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MunicipalSeatReconciliationError("catalog JSON is unreadable") from error
    catalog_canonical = canonical_json_bytes(catalog) if isinstance(catalog, dict) else b""
    # The checked-in national catalog follows the repository writer contract:
    # canonical JSON followed by exactly one LF.  Accept both transport forms
    # while hashing the exact reviewed source bytes for provenance.
    if not isinstance(catalog, dict) or catalog_raw not in (
        catalog_canonical,
        catalog_canonical + b"\n",
    ):
        raise MunicipalSeatReconciliationError("catalog is not canonical JSON")
    if expected_count == EXPECTED_MUNICIPALITY_COUNT:
        try:
            validate_catalog(catalog)
        except NationalCatalogError as error:
            raise MunicipalSeatReconciliationError("national catalog is invalid") from error
    sources = source_provenance(
        catalog=catalog,
        catalog_file_sha256=_sha256(catalog_raw),
        anncsu_file_sha256=anncsu_sha256,
        anncsu_reference_date=anncsu_reference_date,
        ipa_file_sha256=ipa_sha256,
        ipa_reference_date=ipa_reference_date,
    )
    return build_reconciliation_audit(
        catalog,
        read_anncsu_workbook_bytes(anncsu_raw),
        read_ipa_entities_workbook_bytes(ipa_raw),
        sources=sources,
        expected_count=expected_count,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the create-only national municipal-seat reconciliation audit."
    )
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--anncsu", required=True, type=Path)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--expected-anncsu-sha256", required=True)
    parser.add_argument("--expected-ipa-sha256", required=True)
    parser.add_argument("--anncsu-reference-date", required=True)
    parser.add_argument("--ipa-reference-date", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        document = build_from_paths(
            catalog_path=arguments.catalog,
            anncsu_path=arguments.anncsu,
            ipa_path=arguments.ipa,
            expected_anncsu_sha256=arguments.expected_anncsu_sha256,
            expected_ipa_sha256=arguments.expected_ipa_sha256,
            anncsu_reference_date=arguments.anncsu_reference_date,
            ipa_reference_date=arguments.ipa_reference_date,
        )
        encoded = canonical_json_bytes(document)
        write_create_only(arguments.output, encoded)
        # Read back exact canonical bytes before declaring success.
        load_reconciliation_audit(arguments.output)
    except (MunicipalSeatReconciliationError, OSError) as error:
        print(canonical_json_bytes({"error": str(error), "status": "failed"}).decode())
        return 2
    print(
        canonical_json_bytes(
            {
                "audit_sha256": document["audit_sha256"],
                "municipality_count": document["municipality_count"],
                "output": str(arguments.output),
                "status": "created",
                "summary": document["summary"],
            }
        ).decode()
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
