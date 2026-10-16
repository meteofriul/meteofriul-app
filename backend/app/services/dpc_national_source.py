"""Atomic acquisition of the current national DPC CAP and SHP snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
import re
from typing import Any, Callable
from urllib.parse import urlparse
from zipfile import BadZipFile, ZipFile

import requests

from app.weather.dpc_national_alerts import (
    DpcNationalAlertContractError,
    parse_dpc_national_cap,
)
from app.weather.dpc_national_zone_snapshot import (
    parse_dpc_national_zone_zip,
    reconcile_dpc_cap_and_zone_snapshot,
)


DPC_NATIONAL_BULLETIN_URL = (
    "https://mappe.protezionecivile.gov.it/it/mappe-rischi/"
    "bollettino-di-criticita/index.html"
)
DPC_RAW_BASE = (
    "https://raw.githubusercontent.com/pcm-dpc/"
    "DPC-Bollettini-Criticita-Idrogeologica-Idraulica/master/files"
)
DPC_PAGE_MAX_BYTES = 1024 * 1024
DPC_XML_ZIP_MAX_BYTES = 2 * 1024 * 1024
DPC_SHP_ZIP_MAX_BYTES = 16 * 1024 * 1024
DPC_SOURCE_USER_AGENT = "MeteoFriul/1.0 official-alert-source"

_ASSET = re.compile(
    re.escape(DPC_RAW_BASE)
    + r"/(?P<kind>xml|shp)/(?P<revision>\d{8}_\d{4})"
    + r"(?P<suffix>_shp)?\.zip\Z"
)


class DpcNationalSourceError(RuntimeError):
    """The official source could not produce one coherent safe snapshot."""


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.casefold() != "a":
            return
        for name, value in attrs:
            if name.casefold() == "href" and value:
                self.links.append(str(value).strip())


def discover_dpc_national_assets(html: str) -> dict[str, str]:
    parser = _LinkParser()
    try:
        parser.feed(str(html))
        parser.close()
    except Exception as error:
        raise DpcNationalSourceError("dpc_source_page_invalid") from error
    assets: dict[str, set[tuple[str, str]]] = {"xml": set(), "shp": set()}
    for link in parser.links:
        match = _ASSET.fullmatch(link)
        if match is None:
            continue
        kind = match.group("kind")
        suffix = match.group("suffix")
        if (kind == "shp") != (suffix == "_shp"):
            raise DpcNationalSourceError("dpc_source_asset_name_invalid")
        assets[kind].add((match.group("revision"), link))
    if len(assets["xml"]) != 1 or len(assets["shp"]) != 1:
        raise DpcNationalSourceError("dpc_source_assets_missing_or_ambiguous")
    xml_revision, xml_url = next(iter(assets["xml"]))
    shp_revision, shp_url = next(iter(assets["shp"]))
    if xml_revision != shp_revision:
        raise DpcNationalSourceError("dpc_source_asset_revision_mismatch")
    return {"revision": xml_revision, "xml_url": xml_url, "shp_url": shp_url}


def extract_dpc_cap_xml(payload: bytes, revision: str) -> bytes:
    if not payload or len(payload) > DPC_XML_ZIP_MAX_BYTES:
        raise DpcNationalSourceError("dpc_source_xml_zip_size_invalid")
    cap_name = f"Cap_{revision}.xml"
    allowed = {cap_name, "BCR_testo_DCAT_AP_IT.xml", "README.txt"}
    try:
        with ZipFile(BytesIO(payload)) as archive:
            names = set()
            cap_payload = None
            for info in archive.infolist():
                name = info.filename.replace("\\", "/")
                if (
                    info.is_dir()
                    or "/" in name
                    or name.startswith(".")
                    or name not in allowed
                    or name in names
                    or info.file_size > DPC_XML_ZIP_MAX_BYTES
                    or info.compress_size > DPC_XML_ZIP_MAX_BYTES
                ):
                    raise DpcNationalSourceError("dpc_source_xml_zip_unsafe")
                names.add(name)
                if name == cap_name:
                    cap_payload = archive.read(info)
    except DpcNationalSourceError:
        raise
    except (BadZipFile, OSError, RuntimeError) as error:
        raise DpcNationalSourceError("dpc_source_xml_zip_invalid") from error
    if cap_payload is None:
        raise DpcNationalSourceError("dpc_source_cap_missing")
    return cap_payload


def _validate_fetch_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port:
        raise DpcNationalSourceError("dpc_source_url_invalid")
    if url == DPC_NATIONAL_BULLETIN_URL:
        return
    if _ASSET.fullmatch(url) is None:
        raise DpcNationalSourceError("dpc_source_url_invalid")


def _fetch_bytes(url: str, max_bytes: int) -> bytes:
    _validate_fetch_url(url)
    try:
        with requests.get(
            url,
            headers={"User-Agent": DPC_SOURCE_USER_AGENT},
            timeout=(5, 30),
            allow_redirects=False,
            stream=True,
        ) as response:
            if response.status_code != 200:
                raise DpcNationalSourceError(
                    f"dpc_source_http_{response.status_code}"
                )
            length = response.headers.get("Content-Length")
            if length is not None and int(length) > max_bytes:
                raise DpcNationalSourceError("dpc_source_response_too_large")
            body = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise DpcNationalSourceError("dpc_source_response_too_large")
    except (requests.RequestException, OSError, ValueError) as error:
        raise DpcNationalSourceError("dpc_source_request_failed") from error
    if not body:
        raise DpcNationalSourceError("dpc_source_empty_response")
    return bytes(body)


class DpcNationalSource:
    def __init__(
        self,
        fetcher: Callable[[str, int], bytes] | None = None,
    ) -> None:
        self._fetcher = fetcher or _fetch_bytes

    def fetch(self, *, acquired_at: datetime | None = None) -> dict[str, Any]:
        observed = acquired_at or datetime.now(timezone.utc)
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise DpcNationalSourceError("dpc_source_acquired_at_invalid")
        page = self._fetcher(DPC_NATIONAL_BULLETIN_URL, DPC_PAGE_MAX_BYTES)
        try:
            html = page.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise DpcNationalSourceError("dpc_source_page_encoding_invalid") from error
        assets = discover_dpc_national_assets(html)
        xml_zip = self._fetcher(assets["xml_url"], DPC_XML_ZIP_MAX_BYTES)
        shp_zip = self._fetcher(assets["shp_url"], DPC_SHP_ZIP_MAX_BYTES)
        try:
            cap = parse_dpc_national_cap(
                extract_dpc_cap_xml(xml_zip, assets["revision"])
            )
        except DpcNationalAlertContractError as error:
            if str(error) == "dpc_cap_not_public_actual":
                raise DpcNationalSourceError(
                    "dpc_source_cap_not_public"
                ) from error
            raise DpcNationalSourceError(
                "dpc_source_cap_contract_invalid"
            ) from error
        zones = parse_dpc_national_zone_zip(shp_zip)
        reconciled = reconcile_dpc_cap_and_zone_snapshot(cap, zones)
        if reconciled["revision"]["source_revision"] != assets["revision"]:
            raise DpcNationalSourceError("dpc_source_payload_revision_mismatch")
        reconciled["acquisition"] = {
            "acquired_at": observed.astimezone(timezone.utc).isoformat(),
            "page_url": DPC_NATIONAL_BULLETIN_URL,
            "cap_url": assets["xml_url"],
            "zone_url": assets["shp_url"],
        }
        return reconciled


__all__ = [
    "DPC_NATIONAL_BULLETIN_URL",
    "DpcNationalSource",
    "DpcNationalSourceError",
    "discover_dpc_national_assets",
    "extract_dpc_cap_xml",
]
