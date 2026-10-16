"""Build the runtime FVG municipality/locality snapshot from official sources.

This is a release-time tool, not a runtime dependency. It expects:

* the ISTAT 2026 municipality shapefile (EPSG:32632);
* the RAFVG/IRDAT ``DBPRIOR_0411_LOCAL_PUNT`` GeoJSON (EPSG:4326);
* the application's canonical municipality registry.

Install ``pyshp`` and ``pyproj`` only in the environment used to run this tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

import shapefile
from pyproj import Transformer


ISTAT_BOUNDARIES_URL = (
    "https://www.istat.it/storage/cartografia/confini_amministrativi/"
    "non_generalizzati/2026/Limiti01012026.zip"
)
ISTAT_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
IRDAT_METADATA_URL = (
    "https://irdat.regione.fvg.it/consultatore-dati-ambientali-territoriali/"
    "istantSearch.do?identificationId=4981&metadataId=5841"
)
IRDAT_CATALOG_URL = (
    "https://irdat.regione.fvg.it/consultatore-dati-ambientali-territoriali/"
    "home?language=it"
)
IRDAT_WFS_URL = (
    "https://serviziogc.regione.fvg.it/geoserver/NOMI_GEO/wfs?service=WFS&"
    "version=2.0.0&request=GetFeature&"
    "typeNames=NOMI_GEO%3ADBPRIOR_0411_LOCAL_PUNT&"
    "outputFormat=application%2Fjson&srsName=EPSG%3A4326"
)
ALLOWED_LOCALITY_TYPES = {"01", "02", "03"}
MUNICIPAL_SEAT_SUFFIX = re.compile(r"\s*\(SEDE COMUNALE\)\s*$", re.IGNORECASE)
ITALIAN_LOWERCASE_WORDS = {
    "a",
    "al",
    "alla",
    "alle",
    "con",
    "d'",
    "da",
    "dal",
    "dalla",
    "de",
    "dei",
    "del",
    "della",
    "delle",
    "di",
    "e",
    "in",
    "la",
    "le",
    "sul",
    "sulla",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_case(value: Any) -> str:
    source = " ".join(str(value or "").strip().split())
    if not source:
        return ""
    if not source.isupper():
        return source

    words: list[str] = []
    for index, raw_word in enumerate(source.lower().split(" ")):
        pieces = raw_word.split("-")
        rendered_pieces = []
        for piece in pieces:
            if index > 0 and piece in ITALIAN_LOWERCASE_WORDS:
                rendered_pieces.append(piece)
            elif "'" in piece:
                rendered_pieces.append("'".join(
                    segment.capitalize() if segment else segment
                    for segment in piece.split("'")
                ))
            else:
                rendered_pieces.append(piece.capitalize())
        words.append("-".join(rendered_pieces))
    return " ".join(words)


def _transform_coordinates(value: Any, transformer: Transformer) -> Any:
    if (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        longitude, latitude = transformer.transform(float(value[0]), float(value[1]))
        return [round(longitude, 6), round(latitude, 6)]
    if isinstance(value, (list, tuple)):
        return [_transform_coordinates(item, transformer) for item in value]
    raise ValueError("invalid_geometry_coordinates")


def _rings_from_geometry(geometry: dict[str, Any]) -> list[list[list[list[float]]]]:
    geometry_type = str(geometry.get("type") or "")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon":
        return [coordinates]
    if geometry_type == "MultiPolygon":
        return coordinates
    raise ValueError(f"unsupported_municipality_geometry:{geometry_type}")


def _bbox(polygons: list[list[list[list[float]]]]) -> list[float]:
    points = [point for polygon in polygons for ring in polygon for point in ring]
    return [
        round(min(point[0] for point in points), 6),
        round(min(point[1] for point in points), 6),
        round(max(point[0] for point in points), 6),
        round(max(point[1] for point in points), 6),
    ]


def _point_on_segment(
    longitude: float,
    latitude: float,
    first: list[float],
    second: list[float],
    tolerance: float = 1e-10,
) -> bool:
    x1, y1 = first
    x2, y2 = second
    cross = (longitude - x1) * (y2 - y1) - (latitude - y1) * (x2 - x1)
    if abs(cross) > tolerance:
        return False
    return (
        min(x1, x2) - tolerance <= longitude <= max(x1, x2) + tolerance
        and min(y1, y2) - tolerance <= latitude <= max(y1, y2) + tolerance
    )


def _point_in_ring(longitude: float, latitude: float, ring: list[list[float]]) -> bool:
    inside = False
    previous = ring[-1]
    for current in ring:
        if _point_on_segment(longitude, latitude, previous, current):
            return True
        x1, y1 = previous
        x2, y2 = current
        if (y1 > latitude) != (y2 > latitude):
            intersection = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < intersection:
                inside = not inside
        previous = current
    return inside


def _point_in_polygons(
    longitude: float,
    latitude: float,
    polygons: list[list[list[list[float]]]],
) -> bool:
    for polygon in polygons:
        if not polygon or not _point_in_ring(longitude, latitude, polygon[0]):
            continue
        if any(_point_in_ring(longitude, latitude, hole) for hole in polygon[1:]):
            continue
        return True
    return False


def _load_municipalities(
    shapefile_path: Path,
    registry_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
    canonical_by_istat = {
        str(item["istatCode"]): item
        for item in registry_payload.get("municipalities") or []
    }
    transformer = Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)
    reader = shapefile.Reader(str(shapefile_path))
    municipalities: list[dict[str, Any]] = []

    for shape_record in reader.iterShapeRecords():
        record = shape_record.record.as_dict()
        if int(record.get("COD_REG") or 0) != 6:
            continue
        istat_code = str(record.get("PRO_COM_T") or "").zfill(6)
        canonical = canonical_by_istat.get(istat_code)
        if canonical is None:
            raise ValueError(f"istat_boundary_not_in_registry:{istat_code}")
        geometry = dict(shape_record.shape.__geo_interface__)
        geometry["coordinates"] = _transform_coordinates(
            geometry.get("coordinates"),
            transformer,
        )
        polygons = _rings_from_geometry(geometry)
        municipalities.append({
            "istatCode": istat_code,
            "name": canonical["name"],
            "bbox": _bbox(polygons),
            "polygons": polygons,
        })

    municipalities.sort(key=lambda item: item["istatCode"])
    if len(municipalities) != len(canonical_by_istat):
        raise ValueError(
            "municipality_boundary_count_mismatch:"
            f"{len(municipalities)}:{len(canonical_by_istat)}"
        )
    return municipalities, canonical_by_istat


def _matching_municipality(
    latitude: float,
    longitude: float,
    municipalities: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    matches = []
    for municipality in municipalities:
        min_lon, min_lat, max_lon, max_lat = municipality["bbox"]
        if not (min_lon <= longitude <= max_lon and min_lat <= latitude <= max_lat):
            continue
        if _point_in_polygons(longitude, latitude, municipality["polygons"]):
            matches.append(municipality)
    return matches[0] if len(matches) == 1 else None


def _load_localities(
    irdat_path: Path,
    municipalities: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    payload = json.loads(irdat_path.read_text(encoding="utf-8"))
    features = payload.get("features") or []
    localities: list[dict[str, Any]] = []
    stats = {"input": len(features), "filtered": 0, "outside": 0, "included": 0}

    for feature in features:
        properties = feature.get("properties") or {}
        locality_type = str(properties.get("TIPO_TOPON") or "").zfill(2)
        original_name = " ".join(str(properties.get("TOPONIMO") or "").split())
        is_municipal_seat = bool(MUNICIPAL_SEAT_SUFFIX.search(original_name))
        if locality_type not in ALLOWED_LOCALITY_TYPES and not is_municipal_seat:
            stats["filtered"] += 1
            continue
        canonical_name = MUNICIPAL_SEAT_SUFFIX.sub("", original_name).strip()
        if not canonical_name:
            stats["filtered"] += 1
            continue
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2:
            stats["filtered"] += 1
            continue
        longitude = float(coordinates[0])
        latitude = float(coordinates[1])
        if not (math.isfinite(latitude) and math.isfinite(longitude)):
            stats["filtered"] += 1
            continue
        municipality = _matching_municipality(latitude, longitude, municipalities)
        if municipality is None:
            stats["outside"] += 1
            continue

        feature_id = str(feature.get("id") or properties.get("ID_OGG") or "").strip()
        if not feature_id:
            raise ValueError("locality_missing_stable_id")
        localities.append({
            "id": f"irdat-5000:{feature_id}",
            "name": _display_case(canonical_name),
            "kind": "municipal_seat" if is_municipal_seat else "settlement",
            "municipalityIstat": municipality["istatCode"],
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
        })
        stats["included"] += 1

    localities.sort(key=lambda item: (item["municipalityIstat"], item["name"], item["id"]))
    ids = [item["id"] for item in localities]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_locality_id")
    return localities, stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--municipality-shapefile", type=Path, required=True)
    parser.add_argument("--irdat-geojson", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    municipalities, _ = _load_municipalities(
        args.municipality_shapefile,
        args.registry,
    )
    localities, locality_stats = _load_localities(args.irdat_geojson, municipalities)
    output = {
        "schemaVersion": "fvg-geography.v1",
        "sources": {
            "municipalities": {
                "authority": "ISTAT",
                "dataset": "Confini amministrativi non generalizzati 2026",
                "validAt": "2026-01-01",
                "url": ISTAT_BOUNDARIES_URL,
                "license": "CC BY 4.0",
                "licenseUrl": ISTAT_LICENSE_URL,
                "sha256": _sha256(args.municipality_shapefile),
            },
            "localities": {
                "authority": "Regione Autonoma Friuli Venezia Giulia - IRDAT",
                "dataset": "Local place names CTRN 5000",
                "edition": "2006",
                "metadataUrl": IRDAT_METADATA_URL,
                "catalogUrl": IRDAT_CATALOG_URL,
                "license": "IODL 2.0",
                "wfsUrl": IRDAT_WFS_URL,
                "sha256": _sha256(args.irdat_geojson),
                "selection": "TIPO_TOPON 01/02/03 plus '(SEDE COMUNALE)'",
            },
        },
        "municipalityCount": len(municipalities),
        "localityCount": len(localities),
        "localityBuildStats": locality_stats,
        "municipalities": municipalities,
        "localities": localities,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "municipalities": len(municipalities),
        "localities": len(localities),
        "stats": locality_stats,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
