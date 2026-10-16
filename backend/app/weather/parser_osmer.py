import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from xml.etree import ElementTree as ET


PARSER_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

REQUIRED_AREA_NODES = ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9")
REQUIRED_FASCE = ("F1", "F2", "F3", "F4")

FASCIA_ALIAS = {
    "Z1": "F1",
    "Z2": "F2",
    "Z3": "F3",
    "Z4": "F4",
}

CODE_MAPS = {
    "cielo": {
        0: {"id": "sun", "label": "sereno"},
        1: {"id": "mostly_sunny", "label": "poco nuvoloso"},
        2: {"id": "variable", "label": "variabile"},
        3: {"id": "cloudy", "label": "nuvoloso"},
        4: {"id": "overcast", "label": "coperto"},
        5: {"id": "sun_fog", "label": "sole/nebbia"},
    },
    "pioggia": {
        100: {"id": "none", "label": ""},
        6: {"id": "light_rain", "label": "debole"},
        7: {"id": "moderate_rain", "label": "moderata"},
        8: {"id": "heavy_rain", "label": "abbondante"},
        9: {"id": "intense_rain", "label": "intensa"},
        36: {"id": "extreme_rain", "label": "molto intensa"},
    },
    "neve": {
        100: {"id": "none", "label": ""},
        10: {"id": "moderate_snow", "label": "moderata"},
        11: {"id": "heavy_snow", "label": "abbondante"},
        12: {"id": "intense_snow", "label": "intensa"},
    },
    "temporale": {
        100: {"id": "none", "label": ""},
        13: {"id": "storm", "label": "temporale"},
    },
    "nebbia": {
        100: {"id": "none", "label": ""},
        14: {"id": "fog", "label": "nebbia"},
        15: {"id": "mist", "label": "foschia"},
    },
    "vento": {
        100: {"id": "none", "label": ""},
        16: {"id": "north_moderate", "direction": "N", "intensity": "moderate"},
        17: {"id": "north_east_moderate", "direction": "NE", "intensity": "moderate"},
        18: {"id": "east_north_east_moderate", "direction": "ENE", "intensity": "moderate"},
        19: {"id": "east_moderate", "direction": "E", "intensity": "moderate"},
        20: {"id": "south_east_moderate", "direction": "SE", "intensity": "moderate"},
        21: {"id": "south_moderate", "direction": "S", "intensity": "moderate"},
        22: {"id": "south_west_moderate", "direction": "SW", "intensity": "moderate"},
        23: {"id": "west_moderate", "direction": "W", "intensity": "moderate"},
        24: {"id": "north_west_moderate", "direction": "NW", "intensity": "moderate"},
        25: {"id": "north_strong", "direction": "N", "intensity": "strong"},
        26: {"id": "north_east_strong", "direction": "NE", "intensity": "strong"},
        27: {"id": "east_north_east_strong", "direction": "ENE", "intensity": "strong"},
        28: {"id": "east_strong", "direction": "E", "intensity": "strong"},
        29: {"id": "south_east_strong", "direction": "SE", "intensity": "strong"},
        30: {"id": "south_strong", "direction": "S", "intensity": "strong"},
        31: {"id": "south_west_strong", "direction": "SW", "intensity": "strong"},
        32: {"id": "west_strong", "direction": "W", "intensity": "strong"},
        33: {"id": "north_west_strong", "direction": "NW", "intensity": "strong"},
        34: {"id": "east_north_east_very_strong", "direction": "ENE", "intensity": "very_strong"},
        35: {"id": "breeze", "direction": None, "intensity": "breeze"},
    },
    "evoluzione": {
        0: {"id": "sun", "label": "sereno"},
        1: {"id": "variable", "label": "variabile"},
        2: {"id": "overcast", "label": "coperto"},
        3: {"id": "variable_moderate_rain", "label": "variabile con piogge moderate"},
        4: {"id": "variable_heavy_rain", "label": "variabile con piogge abbondanti"},
        5: {"id": "variable_heavy_rain_storm", "label": "variabile con piogge abbondanti e temporali"},
        6: {"id": "variable_storm", "label": "variabile con temporali"},
        7: {"id": "variable_moderate_rain_snow", "label": "variabile con piogge moderate e nevicate"},
        8: {"id": "variable_snow", "label": "variabile con nevicate"},
        9: {"id": "overcast_moderate_rain", "label": "coperto con piogge moderate"},
        10: {"id": "overcast_heavy_rain", "label": "coperto con piogge abbondanti"},
        11: {"id": "overcast_intense_rain", "label": "coperto con piogge intense"},
        12: {"id": "overcast_heavy_rain_storm", "label": "coperto con piogge abbondanti e temporali"},
        13: {"id": "overcast_storm", "label": "coperto con temporali"},
        14: {"id": "overcast_heavy_rain_snow", "label": "coperto con piogge abbondanti e nevicate"},
        15: {"id": "overcast_snow", "label": "coperto con nevicate"},
    },
}


def _clean_text(value):
    if value is None:
        return None
    text = value.strip()
    for _ in range(3):
        decoded = unescape(text)
        if decoded == text:
            break
        text = decoded
    return re.sub(r"\s+", " ", text).strip()


def _text(node, tag):
    child = node.find(tag)
    if child is None:
        return None
    return _clean_text(child.text)


def _int_text(node, tag):
    value = _text(node, tag)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_number(value):
    if value in (None, "", "-"):
        return None
    normalized = str(value).replace(",", ".").strip()
    try:
        parsed = float(normalized)
    except ValueError:
        return None
    return int(parsed) if parsed.is_integer() else parsed


def _parse_percent_value(value):
    value = _clean_text(value)
    if value in (None, "", "-"):
        return None
    if value.startswith("<"):
        return {"operator": "<", "value": _parse_number(value[1:]), "raw": value}
    number = _parse_number(value)
    return {"operator": "=", "value": number, "raw": value} if number is not None else {"raw": value}


def _parse_range(value):
    value = _clean_text(value)
    if value in (None, "", "-"):
        return None
    if "/" in value:
        parts = [_parse_number(part) for part in value.split("/", 1)]
        return {"min": parts[0], "max": parts[1], "raw": value}
    number = _parse_number(value)
    return {"value": number, "raw": value} if number is not None else {"raw": value}


def _parse_osmer_datetime(value):
    value = _clean_text(value)
    if not value:
        return None
    normalized = value.replace("UTC", "").strip()
    try:
        parsed = datetime.strptime(normalized, "%d-%m-%Y %H:%M:%S")
    except ValueError:
        return value
    return parsed.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_osmer_date(value):
    value = _clean_text(value)
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%d-%m-%Y")
    except ValueError:
        return value
    return parsed.date().isoformat()


def _source_date_from_id(source_id):
    match = re.search(r"(?:PW|NW)(\d{8})", source_id or "")
    if not match:
        return None
    try:
        parsed = datetime.strptime(match.group(1), "%Y%m%d")
    except ValueError:
        return None
    return parsed.date().isoformat()


def _code_detail(kind, code, description=None):
    details = dict(CODE_MAPS.get(kind, {}).get(code, {"id": "unknown", "label": description or ""}))
    details["code"] = code
    if description:
        details["description"] = description
    return details


def _read_symbol(node, kind, tag_prefix):
    code = _int_text(node, f"{tag_prefix}_SIMBOLO")
    description = _text(node, f"{tag_prefix}_DESCRIZIONE")
    return _code_detail(kind, code, description)


def _dominant_condition(symbols):
    if symbols["temporale"]["id"] != "none":
        return "storm"
    if symbols["neve"]["id"] != "none":
        return symbols["neve"]["id"]
    if symbols["pioggia"]["id"] != "none":
        return symbols["pioggia"]["id"]
    if symbols["nebbia"]["id"] != "none":
        return symbols["nebbia"]["id"]
    return symbols["cielo"]["id"]


def _evolution_from_zone(zone):
    evolution = []
    for hour in ("00", "12", "24"):
        code = _int_text(zone, f"EVOLUZIONE{hour}_SIMBOLO")
        description = _text(zone, f"EVOLUZIONE{hour}_DESCRIZIONE")
        if code is None and not description:
            continue
        detail = _code_detail("evoluzione", code, description)
        detail["hour"] = int(hour)
        evolution.append(detail)
    return evolution


def _parse_area_node(zone):
    symbols = {
        "cielo": _read_symbol(zone, "cielo", "CIELO"),
        "pioggia": _read_symbol(zone, "pioggia", "PIOGGIA"),
        "neve": _read_symbol(zone, "neve", "NEVE"),
        "temporale": _read_symbol(zone, "temporale", "TEMPORALE"),
        "nebbia": _read_symbol(zone, "nebbia", "NEBBIA"),
        "vento": _read_symbol(zone, "vento", "VENTO"),
    }
    node_id = zone.attrib.get("nome")

    return {
        "id": node_id,
        "name": (zone.attrib.get("descrizione") or node_id).replace("_", " "),
        "attendibilita": _parse_percent_value(_text(zone, "ATTENDIBILITA")),
        "text": _text(zone, "TESTO") or "",
        "precipitation_probability": _parse_percent_value(_text(zone, "PROBABILITAPRECIPITAZIONI")),
        "storm_probability": _parse_percent_value(_text(zone, "PROBABILITATEMPORALI")),
        "snow_level": _parse_range(_text(zone, "QUOTANEVICATA")),
        "mountain": {
            "wind_2000_direction": _text(zone, "VENTO2000_DIREZIONE"),
            "wind_3000_direction": _text(zone, "VENTO3000_DIREZIONE"),
            "wind_2000_intensity_ms": _parse_number(_text(zone, "VENTO2000_INTENSITA")),
            "wind_3000_intensity_ms": _parse_number(_text(zone, "VENTO3000_INTENSITA")),
            "temperature_1000": _parse_number(_text(zone, "TMED1000")),
            "temperature_2000": _parse_number(_text(zone, "TMED2000")),
            "freezing_level_m": _parse_number(_text(zone, "ZEROTERMICO")),
        },
        "symbols": symbols,
        "dominant_condition": _dominant_condition(symbols),
    }


def _merge_fascia(existing, zone):
    data = dict(existing or {})
    zone_name = zone.attrib.get("nome")
    fascia_id = FASCIA_ALIAS.get(zone_name, zone_name)

    data.setdefault("id", fascia_id)
    data.setdefault("name", (zone.attrib.get("descrizione") or fascia_id).replace("_", " "))

    updates = {
        "attendibilita": _parse_percent_value(_text(zone, "ATTENDIBILITA")),
        "text": _text(zone, "TESTO"),
        "precipitation_probability": _parse_percent_value(_text(zone, "PROBABILITAPRECIPITAZIONI")),
        "storm_probability": _parse_percent_value(_text(zone, "PROBABILITATEMPORALI")),
        "snow_level": _parse_range(_text(zone, "QUOTANEVICATA")),
        "temperature_min": _parse_range(_text(zone, "TMIN")),
        "temperature_max": _parse_range(_text(zone, "TMAX")),
        "temperature_1000": _parse_number(_text(zone, "TMED1000")),
        "temperature_2000": _parse_number(_text(zone, "TMED2000")),
        "freezing_level_m": _parse_number(_text(zone, "ZEROTERMICO")),
    }

    for key, value in updates.items():
        if value not in (None, ""):
            data[key] = value

    evolution = _evolution_from_zone(zone)
    if evolution:
        data["evolution"] = evolution

    return data


def _parse_region_zone(zone):
    if zone is None:
        return None
    return {
        "attendibilita": _parse_percent_value(_text(zone, "ATTENDIBILITA")),
        "text": _text(zone, "TESTO") or "",
        "evolution": _evolution_from_zone(zone),
    }


def _parse_day(scadenza):
    areas9 = {}
    fasce4 = {}
    region = None

    for zone in scadenza.findall("./zone/zona"):
        zone_name = zone.attrib.get("nome")
        if zone_name == "REGIONE":
            region = _parse_region_zone(zone)
        elif zone_name in REQUIRED_AREA_NODES:
            areas9[zone_name] = _parse_area_node(zone)
        elif zone_name in REQUIRED_FASCE or zone_name in FASCIA_ALIAS:
            fascia_id = FASCIA_ALIAS.get(zone_name, zone_name)
            fasce4[fascia_id] = _merge_fascia(fasce4.get(fascia_id), zone)

    missing_nodes = [node_id for node_id in REQUIRED_AREA_NODES if node_id not in areas9]
    missing_fasce = [fascia_id for fascia_id in REQUIRED_FASCE if fascia_id not in fasce4]
    confidence = "alta" if not missing_nodes else "media"

    return {
        "id": scadenza.attrib.get("id"),
        "valid_date": _parse_osmer_date(scadenza.attrib.get("data_validita")),
        "day_label": scadenza.attrib.get("giorno"),
        "regional": region,
        "areas9": areas9,
        "fasce4": fasce4,
        "quality": {
            "all_nodes_present": not missing_nodes,
            "missing_nodes": missing_nodes,
            "all_fasce_present": not missing_fasce,
            "missing_fasce": missing_fasce,
            "confidence": confidence,
        },
    }


def parse_osmer_xml(raw_xml, *, source_url=None, source_id=None, requested_date=None):
    if isinstance(raw_xml, bytes):
        raw_text = raw_xml.decode("utf-8")
        raw_bytes = raw_xml
    else:
        raw_text = str(raw_xml)
        raw_bytes = raw_text.encode("utf-8")

    root = ET.fromstring(raw_text)
    previsioni = root.find("previsioni")
    if previsioni is None:
        raise ValueError("OSMER XML without previsioni node")

    emissione = _text(previsioni, "emissione")
    source_id = source_id or _source_id_from_emission(emissione) or "unknown"
    source_date = _source_date_from_id(source_id)

    days = [_parse_day(scadenza) for scadenza in previsioni.findall("./scadenze/scadenza")]
    incomplete_days = [
        day["valid_date"]
        for day in days
        if not day["quality"]["all_nodes_present"] or not day["quality"]["all_fasce_present"]
    ]

    return {
        "id_emissione": source_id,
        "language": _text(root, "lingua"),
        "author": _text(root, "autore"),
        "author_url": _text(root, "autore_url"),
        "source_url": source_url,
        "source_date": source_date,
        "requested_date": requested_date,
        "data_emissione": _parse_osmer_datetime(emissione),
        "published_at": _parse_osmer_datetime(emissione),
        "updated_at": _parse_osmer_datetime(_text(root, "ultimo_aggiornamento")),
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_status": "local_fixture",
        "raw_hash": hashlib.sha256(raw_bytes).hexdigest(),
        "parser_version": PARSER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "fonte": "structured_xml",
        "is_stale": False,
        "stale_reason": None,
        "testo_ufficiale": {
            "situazione_generale": _text(previsioni, "SITUAZIONEGENERALE_TESTO") or "",
            "tendenza": _text(previsioni, "TENDENZA_TESTO") or "",
        },
        "days": days,
        "quality": {
            "xml_valid": True,
            "days_count": len(days),
            "all_days_complete": not incomplete_days,
            "incomplete_days": incomplete_days,
            "confidence": "alta" if days and not incomplete_days else "media",
        },
    }


def _source_id_from_emission(emissione):
    emissione = _clean_text(emissione)
    if not emissione:
        return None
    match = re.match(r"(\d{2})-(\d{2})-(\d{4})", emissione)
    if not match:
        return None
    day, month, year = match.groups()
    return f"PW{year}{month}{day}"


def parse_osmer_xml_file(path, *, source_url=None, requested_date=None):
    file_path = Path(path)
    raw = file_path.read_bytes()
    return parse_osmer_xml(
        raw,
        source_url=source_url,
        source_id=file_path.stem,
        requested_date=requested_date,
    )


def main():
    parser = argparse.ArgumentParser(description="Parse an OSMER ARPA FVG forecast XML into the Meteo Friul structured map schema.")
    parser.add_argument("xml_file", help="Path to a PWYYYYMMDD.xml file")
    parser.add_argument("--output", "-o", help="Optional JSON output path")
    parser.add_argument("--source-url", help="Original XML URL")
    parser.add_argument("--requested-date", help="Requested date in YYYY-MM-DD format")
    args = parser.parse_args()

    result = parse_osmer_xml_file(
        args.xml_file,
        source_url=args.source_url,
        requested_date=args.requested_date,
    )
    serialized = json.dumps(result, indent=2, sort_keys=True)

    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)


if __name__ == "__main__":
    main()
