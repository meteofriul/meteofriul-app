from __future__ import annotations

import base64
import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import Any, Iterator
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import requests


MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_REDIRECTS = 4
REQUEST_TIMEOUT = (4, 10)
USER_AGENT = "MeteoFriul-AdsAdmin/1.0 (+https://meteofriul.app)"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


class SiteImportError(RuntimeError):
    def __init__(self, code: str, status_code: int = 422):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class _SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title: list[str] = []
        self.visible_text: list[str] = []
        self.json_ld: list[Any] = []
        self.telephones: list[str] = []
        self.emails: list[str] = []
        self._in_title = False
        self._json_ld_chunks: list[str] | None = None
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {str(key).lower(): str(value or "").strip() for key, value in attrs}
        tag = tag.lower()
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            content = values.get("content", "")
            if key and content and key not in self.meta:
                self.meta[key] = content
        elif tag == "title":
            self._in_title = True
        elif tag == "script":
            if values.get("type", "").lower().split(";", 1)[0].strip() == "application/ld+json":
                self._json_ld_chunks = []
            else:
                self._hidden_depth += 1
        elif tag in {"style", "noscript", "template"}:
            self._hidden_depth += 1
        elif tag == "a":
            href = values.get("href", "")
            if href.lower().startswith("tel:"):
                self.telephones.append(unquote(href[4:]).strip())
            elif href.lower().startswith("mailto:"):
                self.emails.append(unquote(href[7:].split("?", 1)[0]).strip())

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._json_ld_chunks is not None:
            raw = "".join(self._json_ld_chunks).strip()
            self._json_ld_chunks = None
            if raw:
                try:
                    self.json_ld.append(json.loads(raw))
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass
        elif tag in {"script", "style", "noscript", "template"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._json_ld_chunks is not None:
            self._json_ld_chunks.append(data)
            return
        text = " ".join(str(data).split())
        if not text or self._hidden_depth:
            return
        if self._in_title:
            self.title.append(text)
        self.visible_text.append(text)


def _bounded(value: Any, maximum: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text[:maximum]


def _first_text(value: Any) -> str:
    if isinstance(value, str):
        return _bounded(value, 2000)
    if isinstance(value, list):
        for item in value:
            text = _first_text(item)
            if text:
                return text
        return ""
    if isinstance(value, dict):
        for key in ("@value", "name", "url", "contentUrl"):
            text = _first_text(value.get(key))
            if text:
                return text
    return ""


def _walk_json(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _schema_types(value: Any) -> set[str]:
    raw = value.get("@type", []) if isinstance(value, dict) else []
    items = raw if isinstance(raw, list) else [raw]
    return {str(item).strip().lower() for item in items if str(item).strip()}


def _structured_candidate(documents: list[Any]) -> dict[str, Any]:
    candidates = [item for document in documents for item in _walk_json(document)]
    business_tokens = {
        "localbusiness", "organization", "corporation", "store", "restaurant",
        "foodestablishment", "lodgingbusiness", "professionalservice",
    }
    for candidate in candidates:
        types = _schema_types(candidate)
        if types.intersection(business_tokens) or any(value.endswith("business") for value in types):
            return candidate
    for candidate in candidates:
        if candidate.get("name") and (candidate.get("address") or candidate.get("telephone")):
            return candidate
    return {}


def _category_for(types: set[str], text: str) -> str:
    combined = " ".join([*(value.lower() for value in types), text.lower()])
    mappings = (
        (("hair", "beauty", "spa", "salon", "barber"), "Benessere e persona"),
        (("cafe", "coffee", "bakery", "pasticcer", "caffetter"), "Caffetterie e pasticcerie"),
        (("restaurant", "barorpub", "foodestablishment", "ristor", "trattoria", "pizzeria"), "Bar e ristorazione"),
        (("grocery", "foodstore", "alimentari", "prodotti tipici"), "Alimentari e prodotti tipici"),
        (("lodging", "hotel", "bedandbreakfast", "campground", "ospital"), "Alloggio e ospitalità"),
        (("clothing", "jewelry", "shoe", "fashion", "moda"), "Moda e accessori"),
        (("furniture", "homeandconstruction", "hardware", "arredamento"), "Casa e arredamento"),
        (("medical", "dentist", "pharmacy", "physician", "health"), "Salute e professionisti"),
        (("automotive", "autodealer", "autorepair", "motorcycle", "mobilità"), "Automotive e mobilità"),
        (("sports", "gym", "fitness", "sport"), "Sport e tempo libero"),
        (("theater", "museum", "music", "cinema", "cultura", "spettacolo"), "Cultura e spettacolo"),
        (("photographer", "photography", "fotograf", "videograph", "videoproduzione"), "Fotografia e video"),
        (("advertisingagency", "marketingagency", "marketing", "communication", "comunicazione", "pubblicit", "digitalagency"), "Marketing, comunicazione e media"),
        (("event", "festival", "manifestazione"), "Eventi e manifestazioni"),
        (("government", "ngo", "association", "associazione", "ente"), "Enti e associazioni"),
        (("professionalservice", "legalservice", "financialservice", "service", "servizi"), "Servizi"),
        (("store", "localbusiness", "shop", "negozio", "commercio"), "Commercio"),
    )
    for needles, category in mappings:
        if any(needle in combined for needle in needles):
            return category
    return ""


def _province_code(value: str) -> str:
    normalized = _bounded(value, 80).upper().strip(" .")
    if re.fullmatch(r"[A-Z]{2}", normalized):
        return normalized
    known = {
        "PORDENONE": "PN",
        "UDINE": "UD",
        "GORIZIA": "GO",
        "TRIESTE": "TS",
    }
    return known.get(normalized, "")


def _fiscal_values(text: str, candidate: dict[str, Any]) -> tuple[str, str]:
    vat = re.sub(r"\D", "", _first_text(candidate.get("vatID")))
    tax = re.sub(r"[^A-Z0-9]", "", _first_text(candidate.get("taxID")).upper())
    if len(vat) != 11:
        match = re.search(r"(?:P\.?\s*IVA|PARTITA\s+IVA|VAT)\s*[:\-]?\s*(?:IT\s*)?(\d[\d .-]{9,15}\d)", text, re.I)
        vat = re.sub(r"\D", "", match.group(1)) if match else ""
    if len(vat) != 11:
        vat = ""
    if len(tax) not in {11, 16}:
        match = re.search(r"(?:C\.?\s*F\.?|CODICE\s+FISCALE)\s*[:\-]?\s*([A-Z0-9][A-Z0-9 .-]{9,20}[A-Z0-9])", text, re.I)
        tax = re.sub(r"[^A-Z0-9]", "", match.group(1).upper()) if match else ""
    if len(tax) not in {11, 16}:
        tax = ""
    return vat, tax


def extract_site_fields(html: str, final_url: str) -> dict[str, Any]:
    parser = _SiteParser()
    parser.feed(html)
    candidate = _structured_candidate(parser.json_ld)
    types = _schema_types(candidate)
    visible = " ".join(parser.visible_text)
    address = candidate.get("address", {})
    if isinstance(address, list):
        address = next((item for item in address if isinstance(item, dict)), _first_text(address))
    if not isinstance(address, dict):
        address = {"streetAddress": _first_text(address)}

    name = _first_text(candidate.get("name"))
    # Never infer a fiscal denomination from the public-facing brand name.
    # Populate billing identity only when the site exposes it explicitly.
    legal_name = _first_text(candidate.get("legalName"))
    description = (
        parser.meta.get("og:description")
        or parser.meta.get("twitter:description")
        or parser.meta.get("description")
        or _first_text(candidate.get("description"))
    )
    page_title = (
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or _first_text(candidate.get("headline"))
        or " ".join(parser.title)
        or name
    )
    phone = _first_text(candidate.get("telephone")) or next(iter(parser.telephones), "")
    email = _first_text(candidate.get("email")) or next(iter(parser.emails), "")
    email = re.sub(r"^mailto:", "", email, flags=re.I).split("?", 1)[0].strip()
    vat_number, tax_code = _fiscal_values(visible, candidate)
    street = _first_text(address.get("streetAddress"))
    city = _first_text(address.get("addressLocality"))
    postal_code = re.sub(r"\D", "", _first_text(address.get("postalCode")))[:5]
    province = _province_code(_first_text(address.get("addressRegion")))
    image_url = (
        parser.meta.get("og:image:secure_url")
        or parser.meta.get("og:image")
        or parser.meta.get("twitter:image")
        or _first_text(candidate.get("image"))
        or _first_text(candidate.get("logo"))
    )
    image_url = urljoin(final_url, image_url) if image_url else ""
    category = _category_for(types, " ".join([name, description]))

    fields = {
        "businessName": _bounded(name or page_title, 120),
        "legalName": _bounded(legal_name, 160),
        "businessAddress": _bounded(street, 240),
        "city": _bounded(city, 120),
        "category": category,
        "businessDetails": _bounded(description, 500),
        "contactPhone": _bounded(phone, 60),
        "title": _bounded(page_title, 58),
        "description": _bounded(description, 125),
        "destinationUrl": final_url,
        "vatNumber": vat_number,
        "taxCode": tax_code,
        "billingAddress": _bounded(street, 240),
        "postalCode": postal_code if len(postal_code) == 5 else "",
        "billingCity": _bounded(city, 120),
        "province": province,
        "billingEmail": _bounded(email, 320),
    }
    return {
        "fields": {key: value for key, value in fields.items() if value},
        "imageUrl": image_url,
    }


def _validated_public_url(value: str) -> str:
    raw = str(value or "").strip()
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as error:
        raise SiteImportError("site_import_url_invalid") from error
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise SiteImportError("site_import_url_invalid")
    if parsed.username or parsed.password or parsed.fragment:
        raise SiteImportError("site_import_url_invalid")
    if port is not None and port not in {80, 443}:
        raise SiteImportError("site_import_url_unsafe")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost") or "%" in hostname:
        raise SiteImportError("site_import_url_unsafe")
    try:
        addresses = {
            str(item[4][0]).split("%", 1)[0]
            for item in socket.getaddrinfo(hostname, port or (443 if parsed.scheme.lower() == "https" else 80), type=socket.SOCK_STREAM)
        }
    except (OSError, socket.gaierror) as error:
        raise SiteImportError("site_import_host_unreachable", 502) from error
    if not addresses:
        raise SiteImportError("site_import_host_unreachable", 502)
    try:
        if any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise SiteImportError("site_import_url_unsafe")
    except ValueError as error:
        raise SiteImportError("site_import_url_unsafe") from error
    netloc = hostname if port is None else f"{hostname}:{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, ""))


class SiteImportService:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.session.trust_env = False

    def _download(self, url: str, *, maximum: int, kind: str) -> tuple[str, str, bytes]:
        current = _validated_public_url(url)
        for redirect_index in range(MAX_REDIRECTS + 1):
            try:
                response = self.session.get(
                    current,
                    allow_redirects=False,
                    headers={"Accept": "text/html,application/xhtml+xml,image/*;q=0.8", "User-Agent": USER_AGENT},
                    stream=True,
                    timeout=REQUEST_TIMEOUT,
                )
            except requests.RequestException as error:
                raise SiteImportError(f"site_import_{kind}_unreachable", 502) from error
            try:
                if response.status_code in {301, 302, 303, 307, 308}:
                    if redirect_index >= MAX_REDIRECTS:
                        raise SiteImportError(f"site_import_{kind}_redirects", 422)
                    location = response.headers.get("Location", "")
                    if not location:
                        raise SiteImportError(f"site_import_{kind}_unreachable", 502)
                    current = _validated_public_url(urljoin(current, location))
                    continue
                if response.status_code < 200 or response.status_code >= 300:
                    raise SiteImportError(f"site_import_{kind}_unreachable", 502)
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                declared_length = int(response.headers.get("Content-Length", "0") or 0)
                if declared_length > maximum:
                    raise SiteImportError(f"site_import_{kind}_too_large", 413)
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_content(64 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > maximum:
                        raise SiteImportError(f"site_import_{kind}_too_large", 413)
                    chunks.append(chunk)
                return current, content_type, b"".join(chunks)
            finally:
                response.close()
        raise SiteImportError(f"site_import_{kind}_redirects", 422)

    def import_site(self, url: str) -> dict[str, Any]:
        final_url, content_type, body = self._download(url, maximum=MAX_PAGE_BYTES, kind="page")
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise SiteImportError("site_import_not_html")
        html = body.decode("utf-8", errors="replace")
        extracted = extract_site_fields(html, final_url)
        warnings: list[str] = []
        image: dict[str, str] | None = None
        image_url = str(extracted.pop("imageUrl", "") or "")
        if image_url:
            try:
                resolved_image_url, image_type, image_body = self._download(
                    image_url,
                    maximum=MAX_IMAGE_BYTES,
                    kind="image",
                )
                if image_type not in ALLOWED_IMAGE_TYPES:
                    warnings.append("site_import_image_format_unsupported")
                else:
                    suffix = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[image_type]
                    raw_name = PurePosixPath(urlsplit(resolved_image_url).path).name
                    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_name).strip("-.")[:80]
                    filename = stem if "." in stem else f"immagine-sito.{suffix}"
                    image = {
                        "contentType": image_type,
                        "dataUrl": f"data:{image_type};base64,{base64.b64encode(image_body).decode('ascii')}",
                        "filename": filename,
                        "sourceUrl": resolved_image_url,
                    }
            except SiteImportError as error:
                warnings.append(error.code)
        else:
            warnings.append("site_import_image_not_found")
        fields = extracted["fields"]
        if not fields.get("vatNumber") and not fields.get("taxCode"):
            warnings.append("site_import_fiscal_data_not_found")
        return {
            "sourceUrl": str(url),
            "finalUrl": final_url,
            "fields": fields,
            "image": image,
            "warnings": warnings,
        }
