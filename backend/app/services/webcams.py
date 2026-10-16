from __future__ import annotations

import json
import math
import os
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Callable
from urllib.parse import urlsplit

import requests

from app.contracts.live import WebcamManifestResponse, WebcamRecord
DEFAULT_MANIFEST_CACHE_SECONDS = 10 * 60
ALLOWED_WEBCAM_GROUPS = frozenset({"coast", "mountain", "plain"})
WEBCAM_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DEDICATED_WEBCAM_ROOT_HOSTS = frozenset({
    "cervignanometeo.org",
    "www.cervignanometeo.org",
})
APPROVED_IFRAME_PLAYER_URLS = frozenset({
    "https://fornidisopra.panomax.com/",
    "https://sandanieledelfriuli.panomax.com/",
    "https://stream-meteoproject.eu/weathercam-player.php?code=18",
})


@dataclass(frozen=True)
class WebcamManifestValidationIssue:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


class WebcamManifestValidationError(ValueError):
    def __init__(self, issues: list[WebcamManifestValidationIssue]) -> None:
        self.issues = tuple(issues)
        summary = "; ".join(f"{issue.path}: {issue.message}" for issue in issues)
        super().__init__(summary or "webcam_manifest_invalid")


@dataclass(frozen=True)
class ValidatedWebcamManifest:
    version: int
    source_updated_at: str | None
    generated_at: str | None
    records: tuple[WebcamRecord, ...]
    mode: str


def _issue(
    issues: list[WebcamManifestValidationIssue],
    code: str,
    path: str,
    message: str,
) -> None:
    issues.append(WebcamManifestValidationIssue(code=code, path=path, message=message))


def _alias_value(
    item: Mapping[str, Any],
    canonical: str,
    aliases: tuple[str, ...],
    *,
    path: str,
    issues: list[WebcamManifestValidationIssue],
) -> Any:
    present = [(key, item[key]) for key in (canonical, *aliases) if key in item]
    if not present:
        return None
    value = present[0][1]
    for key, candidate in present[1:]:
        if candidate != value:
            _issue(
                issues,
                "alias_conflict",
                f"{path}.{key}",
                f"conflitto con {present[0][0]}",
            )
    return value


def _text(
    value: Any,
    *,
    path: str,
    issues: list[WebcamManifestValidationIssue],
    required: bool = False,
) -> str | None:
    if value is None:
        if required:
            _issue(issues, "required", path, "campo obbligatorio")
        return None
    if not isinstance(value, str):
        _issue(issues, "invalid_text", path, "deve essere una stringa")
        return None
    normalized = value.strip()
    if not normalized:
        if required:
            _issue(issues, "required", path, "non può essere vuoto")
        elif value:
            _issue(issues, "invalid_text", path, "non può contenere solo spazi")
        return None
    return normalized


def _https_url(
    value: Any,
    *,
    path: str,
    issues: list[WebcamManifestValidationIssue],
    required: bool = False,
    specific_page: bool = False,
    allow_local_asset: bool = False,
) -> str | None:
    normalized = _text(value, path=path, issues=issues, required=required)
    if normalized is None:
        return None

    if allow_local_asset and normalized.startswith("/"):
        parsed_local = urlsplit(normalized)
        path_segments = parsed_local.path.split("/")
        if (
            normalized.startswith("//")
            or "\\" in normalized
            or any(char.isspace() for char in normalized)
            or any(segment in {".", ".."} for segment in path_segments)
            or parsed_local.scheme
            or parsed_local.netloc
        ):
            _issue(
                issues,
                "invalid_local_asset",
                path,
                "il path locale deve iniziare con una sola / e non contenere spazi",
            )
            return None
        return normalized

    try:
        parsed = urlsplit(normalized)
        hostname = parsed.hostname
    except ValueError:
        parsed = None
        hostname = None
    if (
        parsed is None
        or parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        _issue(issues, "invalid_https_url", path, "deve essere un URL HTTPS assoluto")
        return None
    normalized_hostname = hostname.lower()
    dedicated_subdomain = (
        normalized_hostname.endswith(".panomax.com")
        and normalized_hostname not in {"www.panomax.com", "panomax.com"}
    ) or normalized_hostname in DEDICATED_WEBCAM_ROOT_HOSTS
    if (
        specific_page
        and parsed.path in {"", "/"}
        and not parsed.query
        and not dedicated_subdomain
    ):
        _issue(
            issues,
            "source_page_not_specific",
            path,
            "deve puntare a una pagina specifica, non alla sola home del sito",
        )
        return None
    return normalized


def _coordinate(
    value: Any,
    *,
    path: str,
    minimum: float,
    maximum: float,
    issues: list[WebcamManifestValidationIssue],
) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        _issue(issues, "invalid_coordinate", path, "deve essere un numero finito")
        return None
    try:
        coordinate = float(value)
    except (TypeError, ValueError):
        _issue(issues, "invalid_coordinate", path, "deve essere un numero finito")
        return None
    if not math.isfinite(coordinate) or not minimum <= coordinate <= maximum:
        _issue(
            issues,
            "invalid_coordinate",
            path,
            f"deve essere compreso tra {minimum:g} e {maximum:g}",
        )
        return None
    return coordinate


def _manifest_version(
    raw_manifest: Mapping[str, Any],
    issues: list[WebcamManifestValidationIssue],
) -> int:
    value = raw_manifest.get("version", 1)
    if isinstance(value, bool):
        _issue(issues, "invalid_version", "version", "deve essere un intero positivo")
        return 1
    try:
        version = int(value)
    except (TypeError, ValueError):
        _issue(issues, "invalid_version", "version", "deve essere un intero positivo")
        return 1
    if version < 1:
        _issue(issues, "invalid_version", "version", "deve essere un intero positivo")
        return 1
    return version


def validate_webcam_manifest(
    raw_manifest: Mapping[str, Any],
    *,
    shadow: bool = False,
) -> ValidatedWebcamManifest:
    """Validate and normalize an active or explicitly non-publishing manifest.

    Active manifests read ``webcams``. Shadow manifests read ``candidates`` and
    must opt into the safe mode with ``mode: shadow`` and ``publish: false``.
    Snake-case URL aliases and ``latitude``/``longitude`` are accepted, while
    the returned records always use the public camel-case contract.
    """

    if not isinstance(raw_manifest, Mapping):
        raise WebcamManifestValidationError(
            [
                WebcamManifestValidationIssue(
                    code="invalid_manifest",
                    path="$",
                    message="il manifest deve essere un oggetto JSON",
                )
            ]
        )

    issues: list[WebcamManifestValidationIssue] = []
    version = _manifest_version(raw_manifest, issues)
    records_field = "candidates" if shadow else "webcams"
    mode = "shadow" if shadow else "active"

    if shadow:
        if raw_manifest.get("mode") != "shadow":
            _issue(
                issues,
                "shadow_mode_required",
                "mode",
                'deve essere esattamente "shadow"',
            )
        if raw_manifest.get("publish") is not False:
            _issue(
                issues,
                "shadow_publish_must_be_false",
                "publish",
                "deve essere esplicitamente false",
            )
    elif (
        raw_manifest.get("mode") == "shadow"
        or raw_manifest.get("publish") is False
        or "candidates" in raw_manifest
    ):
        _issue(
            issues,
            "shadow_manifest_not_publishable",
            "$",
            "un manifest candidati non può essere caricato come catalogo attivo",
        )

    raw_records = raw_manifest.get(records_field)
    if not isinstance(raw_records, list):
        _issue(
            issues,
            "invalid_records",
            records_field,
            "deve essere un elenco",
        )
        raw_records = []

    normalized_records: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}
    for index, raw_record in enumerate(raw_records):
        path = f"{records_field}[{index}]"
        if not isinstance(raw_record, Mapping):
            _issue(issues, "invalid_record", path, "deve essere un oggetto")
            continue

        webcam_id = _text(
            raw_record.get("id"),
            path=f"{path}.id",
            issues=issues,
            required=True,
        )
        if webcam_id is not None:
            if WEBCAM_ID_PATTERN.fullmatch(webcam_id) is None:
                _issue(
                    issues,
                    "invalid_id",
                    f"{path}.id",
                    "usa solo lettere minuscole, numeri e trattini",
                )
            if webcam_id in seen_ids:
                _issue(
                    issues,
                    "duplicate_id",
                    f"{path}.id",
                    f"duplicato di {records_field}[{seen_ids[webcam_id]}].id",
                )
            else:
                seen_ids[webcam_id] = index

        name = _text(
            raw_record.get("name"),
            path=f"{path}.name",
            issues=issues,
            required=True,
        )
        group = _text(
            raw_record.get("group"),
            path=f"{path}.group",
            issues=issues,
            required=True,
        )
        if group is not None and group not in ALLOWED_WEBCAM_GROUPS:
            _issue(
                issues,
                "invalid_group",
                f"{path}.group",
                f"deve essere uno tra {', '.join(sorted(ALLOWED_WEBCAM_GROUPS))}",
            )

        image_url = _https_url(
            _alias_value(
                raw_record,
                "imageUrl",
                ("image_url",),
                path=path,
                issues=issues,
            ),
            path=f"{path}.imageUrl",
            issues=issues,
        )
        fallback_image_url = _https_url(
            _alias_value(
                raw_record,
                "fallbackImageUrl",
                ("fallback_image_url",),
                path=path,
                issues=issues,
            ),
            path=f"{path}.fallbackImageUrl",
            issues=issues,
            allow_local_asset=True,
        )
        if image_url is None and fallback_image_url is None:
            _issue(
                issues,
                "media_required",
                path,
                "serve imageUrl oppure fallbackImageUrl",
            )

        source_page = _https_url(
            _alias_value(
                raw_record,
                "sourcePage",
                ("source_page",),
                path=path,
                issues=issues,
            ),
            path=f"{path}.sourcePage",
            issues=issues,
            required=True,
            specific_page=True,
        )
        if source_page is not None and source_page in {image_url, fallback_image_url}:
            _issue(
                issues,
                "source_page_is_media",
                f"{path}.sourcePage",
                "deve puntare alla pagina esterna della webcam, non al file immagine",
            )
        source_check_url = _https_url(
            _alias_value(
                raw_record,
                "sourceCheckUrl",
                ("source_check_url",),
                path=path,
                issues=issues,
            ),
            path=f"{path}.sourceCheckUrl",
            issues=issues,
        )
        source_check_expected_id = _text(
            _alias_value(
                raw_record,
                "sourceCheckExpectedId",
                ("source_check_expected_id",),
                path=path,
                issues=issues,
            ),
            path=f"{path}.sourceCheckExpectedId",
            issues=issues,
        )
        if source_check_url is not None and source_check_expected_id is None:
            _issue(
                issues,
                "source_check_expected_id_required",
                f"{path}.sourceCheckExpectedId",
                "serve per verificare che l'API descriva la webcam attesa",
            )
        elif source_check_url is None and source_check_expected_id is not None:
            _issue(
                issues,
                "source_check_expected_id_without_url",
                f"{path}.sourceCheckExpectedId",
                "può essere usato solo insieme a sourceCheckUrl",
            )

        attribution = _text(
            _alias_value(
                raw_record,
                "attribution",
                ("attribution_text",),
                path=path,
                issues=issues,
            ),
            path=f"{path}.attribution",
            issues=issues,
        )
        attribution_url = _https_url(
            _alias_value(
                raw_record,
                "attributionUrl",
                ("attribution_url",),
                path=path,
                issues=issues,
            ),
            path=f"{path}.attributionUrl",
            issues=issues,
        )

        latitude_raw = _alias_value(
            raw_record,
            "lat",
            ("latitude",),
            path=path,
            issues=issues,
        )
        longitude_raw = _alias_value(
            raw_record,
            "lon",
            ("longitude",),
            path=path,
            issues=issues,
        )
        latitude = _coordinate(
            latitude_raw,
            path=f"{path}.lat",
            minimum=-90,
            maximum=90,
            issues=issues,
        )
        longitude = _coordinate(
            longitude_raw,
            path=f"{path}.lon",
            minimum=-180,
            maximum=180,
            issues=issues,
        )
        if (latitude_raw is None) != (longitude_raw is None):
            _issue(
                issues,
                "coordinate_pair_required",
                path,
                "lat e lon devono essere presenti insieme",
            )

        player_url = _https_url(
            _alias_value(
                raw_record,
                "playerUrl",
                ("player_url",),
                path=path,
                issues=issues,
            ),
            path=f"{path}.playerUrl",
            issues=issues,
        )
        media_type = _text(
            _alias_value(
                raw_record,
                "mediaType",
                ("media_type",),
                path=path,
                issues=issues,
            ),
            path=f"{path}.mediaType",
            issues=issues,
        )
        normalized_media_type = media_type.lower() if media_type else None
        if player_url is not None:
            if normalized_media_type != "iframe":
                _issue(
                    issues,
                    "player_media_type_required",
                    f"{path}.mediaType",
                    "un player incorporato richiede mediaType iframe",
                )
            parsed_player = urlsplit(player_url)
            try:
                player_port = parsed_player.port
            except ValueError:
                player_port = -1
            player_is_exactly_approved = (
                parsed_player.scheme == "https"
                and not parsed_player.username
                and not parsed_player.password
                and player_port is None
                and not parsed_player.fragment
                and player_url in APPROVED_IFRAME_PLAYER_URLS
            )
            if not player_is_exactly_approved:
                _issue(
                    issues,
                    "player_host_not_approved",
                    f"{path}.playerUrl",
                    "host player non approvato per l'incorporamento",
                )
        elif normalized_media_type == "iframe":
            _issue(
                issues,
                "iframe_player_url_required",
                f"{path}.playerUrl",
                "mediaType iframe richiede playerUrl",
            )
        if image_url is not None and player_url is not None:
            _issue(
                issues,
                "media_mode_conflict",
                path,
                "imageUrl e playerUrl sono modalità alternative e non possono coesistere",
            )

        sort_order_raw = _alias_value(
            raw_record,
            "sortOrder",
            ("sort_order",),
            path=path,
            issues=issues,
        )
        if sort_order_raw is None:
            sort_order = 999
        elif isinstance(sort_order_raw, bool):
            _issue(
                issues,
                "invalid_sort_order",
                f"{path}.sortOrder",
                "deve essere un intero",
            )
            sort_order = 999
        else:
            try:
                sort_order = int(sort_order_raw)
            except (TypeError, ValueError):
                _issue(
                    issues,
                    "invalid_sort_order",
                    f"{path}.sortOrder",
                    "deve essere un intero",
                )
                sort_order = 999

        map_cluster_id = _text(
            _alias_value(
                raw_record,
                "mapClusterId",
                ("map_cluster_id",),
                path=path,
                issues=issues,
            ),
            path=f"{path}.mapClusterId",
            issues=issues,
        )
        map_cluster_label = _text(
            _alias_value(
                raw_record,
                "mapClusterLabel",
                ("map_cluster_label",),
                path=path,
                issues=issues,
            ),
            path=f"{path}.mapClusterLabel",
            issues=issues,
        )
        if bool(map_cluster_id) != bool(map_cluster_label):
            _issue(
                issues,
                "incomplete_map_cluster",
                f"{path}.mapClusterId",
                "mapClusterId e mapClusterLabel devono essere presenti insieme",
            )
        if map_cluster_id is not None and (
            len(map_cluster_id) > 80
            or WEBCAM_ID_PATTERN.fullmatch(map_cluster_id) is None
        ):
            _issue(
                issues,
                "invalid_map_cluster_id",
                f"{path}.mapClusterId",
                "usa al massimo 80 caratteri tra lettere minuscole, numeri e trattini",
            )
        if map_cluster_label is not None and len(map_cluster_label) > 120:
            _issue(
                issues,
                "invalid_map_cluster_label",
                f"{path}.mapClusterLabel",
                "usa al massimo 120 caratteri",
            )

        normalized_records.append(
            {
                "id": webcam_id or "invalid",
                "name": name or webcam_id or "invalid",
                "group": group or "",
                "category": _text(
                    raw_record.get("category"),
                    path=f"{path}.category",
                    issues=issues,
                )
                or "",
                "area": _text(
                    raw_record.get("area"),
                    path=f"{path}.area",
                    issues=issues,
                )
                or "",
                "municipality": _text(
                    raw_record.get("municipality"),
                    path=f"{path}.municipality",
                    issues=issues,
                ),
                "mapClusterId": map_cluster_id,
                "mapClusterLabel": map_cluster_label,
                "imageUrl": image_url,
                "fallbackImageUrl": fallback_image_url,
                "provider": _text(
                    raw_record.get("provider"),
                    path=f"{path}.provider",
                    issues=issues,
                )
                or "",
                "sourcePage": source_page or "",
                "sourceCheckUrl": source_check_url,
                "sourceCheckExpectedId": source_check_expected_id,
                "attribution": attribution,
                "attributionUrl": attribution_url,
                "lat": latitude,
                "lon": longitude,
                "health": _text(
                    raw_record.get("health"),
                    path=f"{path}.health",
                    issues=issues,
                )
                or "ok",
                "checkedAt": _text(
                    _alias_value(
                        raw_record,
                        "checkedAt",
                        ("checked_at",),
                        path=path,
                        issues=issues,
                    ),
                    path=f"{path}.checkedAt",
                    issues=issues,
                )
                or "",
                "sortOrder": sort_order,
                "playerUrl": player_url,
                "mediaType": normalized_media_type,
            }
        )

    source_updated_at = _text(
        _alias_value(
            raw_manifest,
            "sourceUpdatedAt",
            ("source_updated_at", "updatedAt", "updated_at"),
            path="$",
            issues=issues,
        ),
        path="sourceUpdatedAt",
        issues=issues,
    )
    generated_at = _text(
        _alias_value(
            raw_manifest,
            "generatedAt",
            ("generated_at",),
            path="$",
            issues=issues,
        ),
        path="generatedAt",
        issues=issues,
    )

    if issues:
        raise WebcamManifestValidationError(issues)

    return ValidatedWebcamManifest(
        version=version,
        source_updated_at=source_updated_at,
        generated_at=generated_at,
        records=tuple(WebcamRecord(**record) for record in normalized_records),
        mode=mode,
    )


def load_shadow_webcam_manifest(path: Path) -> ValidatedWebcamManifest:
    """Load a candidate-only manifest; this function is never used by the API."""

    try:
        raw_manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        raise WebcamManifestValidationError(
            [
                WebcamManifestValidationIssue(
                    code="shadow_manifest_unreadable",
                    path=str(path),
                    message="manifest candidati non leggibile",
                )
            ]
        ) from exc
    return validate_webcam_manifest(raw_manifest, shadow=True)


class WebcamManifestService:
    def __init__(
        self,
        *,
        local_path: Path | None = None,
        manifest_url: str | None = None,
        now: Callable[[], float] = time.time,
        session: requests.Session | None = None,
        timeout_seconds: float = 4,
    ) -> None:
        self.local_path = local_path or Path(__file__).resolve().parents[1] / "data" / "webcams_active.json"
        self.manifest_url = (
            manifest_url
            if manifest_url is not None
            else os.getenv("LIVE_WEBCAMS_MANIFEST_URL", "").strip()
        )
        self.now = now
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self._cache: tuple[float, WebcamManifestResponse] | None = None
        self._cache_lock = Lock()

    def get_manifest(self) -> WebcamManifestResponse:
        # A single refresh per instance also bounds requests to snapshot sources.
        with self._cache_lock:
            if self._cache and self.now() - self._cache[0] <= DEFAULT_MANIFEST_CACHE_SECONDS:
                return self._cache[1]
            return self._load_manifest()

    def _load_manifest(self) -> WebcamManifestResponse:
        remote_failed = False
        if self.manifest_url:
            try:
                response = self.session.get(
                    self.manifest_url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "Meteo-Friul-App/3.0 (+https://meteofriul.it)",
                    },
                    timeout=self.timeout_seconds,
                    allow_redirects=True,
                )
                response.raise_for_status()
                manifest = self._normalize(response.json(), source="remote", source_url=response.url)
                if manifest.ok:
                    return self._store_cache(manifest)
                remote_failed = True
            except (requests.RequestException, TypeError, ValueError):
                remote_failed = True

        try:
            payload = json.loads(self.local_path.read_text(encoding="utf-8"))
            manifest = self._normalize(payload, source="local", source_url="")
            if remote_failed and manifest.ok:
                manifest = manifest.model_copy(update={"status": "fallback"})
            return self._store_cache(manifest)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return WebcamManifestResponse(
                ok=False,
                status="unavailable",
                source="none",
                count=0,
                webcams=[],
            )

    def _store_cache(self, manifest: WebcamManifestResponse) -> WebcamManifestResponse:
        if manifest.ok:
            # Called under get_manifest's lock; never re-enter the same lock.
            self._cache = (self.now(), manifest)
        return manifest

    @staticmethod
    def _normalize(
        raw_manifest: Mapping[str, Any],
        *,
        source: str,
        source_url: str,
    ) -> WebcamManifestResponse:
        validated = validate_webcam_manifest(raw_manifest)
        webcams = list(validated.records)
        return WebcamManifestResponse(
            ok=bool(webcams),
            status="ok" if webcams else "empty",
            source=source,
            source_url=source_url,
            version=validated.version,
            source_updated_at=validated.source_updated_at,
            generated_at=validated.generated_at,
            count=len(webcams),
            webcams=webcams,
        )
