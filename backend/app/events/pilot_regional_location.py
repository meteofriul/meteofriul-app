"""TurismoFVG spellings that refer to an existing FVG municipality.

Hamlets are intentionally absent: a municipal centroid can misplace a nearby
event enough to change radius results.
"""
import re
from html import unescape
from urllib.parse import parse_qs, urlsplit

from . import engine


MUNICIPALITY_ALIASES = {
    'duino-aurisina': 'Duino Aurisina',
    'san dorligo della valle-dolina': 'San Dorligo della Valle',
}

# Numeric point published in TurismoFVG's place page. This locates the
# locality for radius search, not an individual venue or meeting point.
SOURCE_LOCALITY_POINTS = {
    'sistiana': (45.7728922, 13.6391125,
                 'https://www.turismofvg.it/sistiana'),
}


def resolve_turismofvg_locality(source_city):
    return SOURCE_LOCALITY_POINTS.get(engine.normalize_for_search(source_city))


def resolve_turismofvg_municipality(source_city):
    town = engine.fvg_municipality_catalog.match_names(source_city)
    if town:
        return town
    key = re.sub(r'\s*[-–]\s*', '-',
                 engine.normalize_for_search(source_city or ''))
    canonical = MUNICIPALITY_ALIASES.get(key)
    return engine.fvg_municipality_catalog.match_names(canonical) if canonical else None


def resolve_turismofvg_municipalities(source_cities):
    """Keep every municipality named by a multi-place detail, or none."""
    names = [part.strip() for part in (source_cities or '').split(',')]
    if not 2 <= len(names) <= 32 or any(not name for name in names):
        return None
    places, seen = [], set()
    for name in names:
        key = engine.normalize_for_search(name)
        town = resolve_turismofvg_municipality(name)
        if not town or key in seen:
            return None
        seen.add(key)
        places.append({'name': name, 'lat': town.latitude,
                       'lon': town.longitude})
    return places


def source_map_is_single_venue(source_cities, venue):
    """A map may locate one named hamlet within an otherwise municipal list."""
    names = [part.strip() for part in (source_cities or '').split(',')]
    if len(names) < 2 or not venue:
        return False
    unknown = [name for name in names if not resolve_turismofvg_municipality(name)]
    return (len(unknown) == 1
            and engine.normalize_for_search(unknown[0])
            in engine.normalize_for_search(venue))


def extract_turismofvg_map_point(html):
    """Read the source's numeric map point; never geocode free text."""
    for iframe in re.findall(r'<iframe\b[^>]*>', html or '', re.I | re.S):
        if not re.search(r'\bid=["\']gmap_canvas["\']', iframe, re.I):
            continue
        src = re.search(r'\bsrc=["\']([^"\']+)["\']', iframe, re.I)
        if not src:
            continue
        parsed = urlsplit(unescape(src[1]))
        if (parsed.scheme != 'https' or parsed.hostname not in {'www.google.com', 'google.com'}
                or parsed.path != '/maps/embed/v1/place'):
            continue
        query = parse_qs(parsed.query).get('q') or []
        if len(query) != 1:
            continue
        pair = re.fullmatch(r'\s*(\d{2}\.\d+)\s+(-?\d{1,3}\.\d+)\s*', query[0])
        if not pair:
            continue
        lat, lon = float(pair[1]), float(pair[2])
        if 45.5 <= lat <= 47.2 and 12.0 <= lon <= 14.0:
            return lat, lon
    return None
