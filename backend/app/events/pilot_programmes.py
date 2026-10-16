"""Explicit programme editions and their compact catalogue projection.

Programme sources may keep the individual sessions for audit and future detail
views.  The public list deliberately exposes one lightweight umbrella record per
reviewed edition.  Membership is explicit: source adapters attach the metadata
below and the small legacy URL registry only covers records already reviewed.
"""
from copy import deepcopy
from datetime import date
from urllib.parse import urlsplit


PORDENONELEGGE_2026 = {
    "series_id": "pordenonelegge",
    "programme_id": "pordenonelegge-2026",
    "edition_id": "2026",
    "programme_title": "Pordenonelegge 2026",
    "programme_url": "https://www.pordenonelegge.it/programma?giorno=tutto",
    "programme_start_date": "2026-09-16",
    "programme_end_date": "2026-09-20",
    "programme_city": "Pordenone",
    "programme_place_label": "Pordenone e territorio",
    "programme_is_multi_place": True,
    "programme_is_multi_venue": True,
    "programme_source": "Pordenonelegge",
    "programme_display_mode": "umbrella",
}

PORDENONE_PENSA_2026 = {
    "series_id": "pordenone-pensa-in-giallo",
    "programme_id": "pordenone-pensa-in-giallo-2026",
    "edition_id": "2026",
    "programme_title": "Pordenone Pensa in Giallo 2026",
    "programme_url": "https://www.pnpensa.it/pnpensa-giallo-settembre-2026-pordenone/",
    "programme_start_date": "2026-09-05",
    "programme_end_date": "2026-09-07",
    "programme_city": "Pordenone",
    "programme_place_label": "Pordenone",
    "programme_is_multi_place": False,
    "programme_is_multi_venue": True,
    "programme_source": "Pordenone Pensa",
    "programme_display_mode": "umbrella",
}

CINEMA_MUTO_TURISMO_2026 = "https://www.turismofvg.it/eventi/45-le-giornate-del-cinema-muto"
MESS_LABORATORI_URL = "https://mess.regione.fvg.it/it/didattica-museale-171043"
MESS_ME_FRIUL_TURISMO_2026 = "https://www.turismofvg.it/eventi/mess-laboratori-cose-cos-e-498424"
MESS_REGIONAL_UMBRELLA_2026 = 'https://www.turismofvg.it/eventi/mess-laboratori-cose-cos-e-2026'
MESS_REGIONAL_MUSEUMS_2026 = {
    'https://www.turismofvg.it/eventi/laboratori-cose-cos-e-498433':
        ('2026-10-10', '2026-10-10', 'Tolmezzo', 38555,
         'Museo Carnico delle arti popolari "Michele Gortani"',
         '2026-10-10', '2026-12-19'),
    'https://www.turismofvg.it/eventi/laboratori-cose-cos-e-498434':
        ('2026-12-19', '2026-12-19', 'Tolmezzo', 38555,
         'Museo Carnico delle arti popolari "Michele Gortani"',
         '2026-10-10', '2026-12-19'),
    'https://www.turismofvg.it/eventi/mess-laboratori-cose-cos-e-2026-501368':
        ('2026-10-17', '2026-11-14', "Farra d'Isonzo", 38558,
         'Museo di documentazione della civiltà contadina friulana',
         '2026-10-17', '2026-11-14'),
    'https://www.turismofvg.it/eventi/mess-viaggio-nei-musei-etnografici-e-storici-del-friuli-venezia-giulia':
        ('2026-10-18', '2026-10-18', 'Trieste', 38550, 'Museo della Bora',
         '2026-10-18', '2026-11-15'),
    'https://www.turismofvg.it/eventi/mess-viaggio-nei-musei-etnografici-e-storici-del-friuli-venezia-giulia-498420':
        ('2026-11-15', '2026-11-15', 'Trieste', 38550, 'Museo della Bora',
         '2026-10-18', '2026-11-15'),
    'https://www.turismofvg.it/eventi/cose-cos-e-in-viaggio-nei-musei-etnografici-e-storici-del-friuli-venezia-giulia-i-cercacose-e-i-cesti':
        ('2026-10-25', '2026-10-25', 'Buttrio', 38556,
         'Museo della Civiltà del Vino del Friuli Venezia Giulia',
         '2026-10-04', '2026-10-25'),
    'https://www.turismofvg.it/eventi/tra-percorsi-nascosti-in-belle-giornate':
        ('2026-10-24', '2026-10-24', 'Ronchi dei Legionari', 38552,
         'Musei del Consorzio Culturale del Monfalconese',
         '2026-10-24', '2026-12-12'),
    'https://www.turismofvg.it/eventi/cose-cos-e-raccoglie-parole-con-sguardo-sorpreso':
        ('2026-11-22', '2026-11-22', 'San Pietro al Natisone', 38545,
         'SMO Slovensko multimedialno okno', '2026-11-22', '2026-11-29'),
    MESS_ME_FRIUL_TURISMO_2026:
        ('2026-11-28', '2026-11-28', 'Udine', 38546,
         'Museo Etnografico del Friuli', '2026-08-29', '2026-11-28'),
    'https://www.turismofvg.it/eventi/cose-cos-e-i-cercacose-e-il-canto':
        ('2026-11-29', '2026-11-29', 'San Pietro al Natisone', 38545,
         'SMO Slovensko multimedialno okno', '2026-11-22', '2026-11-29'),
    'https://www.turismofvg.it/eventi/cose-cos-e-in-viaggio-nei-musei-etnografici-e-storici-del-friuli-venezia-giulia':
        ('2026-12-06', '2026-12-13', 'Maniago', 38559,
         "Museo dell'Arte Fabbrile e delle Coltellerie",
         '2026-12-06', '2026-12-13'),
}


def cinema_muto_edition(start, end, main_start, main_end):
    """Keep the announced festival dates distinct from pre-opening and replay."""
    if (not all(isinstance(value, date) for value in (start, end, main_start, main_end))
            or not start <= main_start <= main_end <= end
            or len({value.year for value in (start, end, main_start, main_end)}) != 1):
        raise ValueError("invalid Cinema Muto edition dates")
    year = str(main_start.year)
    return {"series_id": "giornate-del-cinema-muto",
            "programme_id": f"giornate-del-cinema-muto-{year}",
            "edition_id": year,
            "programme_title": f"Le Giornate del Cinema Muto {year}",
            "programme_url": "https://www.giornatedelcinemamuto.it/",
            "programme_start_date": start.isoformat(),
            "programme_end_date": end.isoformat(),
            "programme_main_start_date": main_start.isoformat(),
            "programme_main_end_date": main_end.isoformat(),
            "programme_city": "Pordenone",
            "programme_place_label": "Pordenone e territorio",
            "programme_is_multi_place": True,
            "programme_is_multi_venue": True,
            "programme_source": "Le Giornate del Cinema Muto",
            "programme_display_mode": "umbrella",
            "category": "cultura"}


def _declared_cinema_muto(event):
    if (event.get("source") != "Le Giornate del Cinema Muto"
            or event.get("series_id") != "giornate-del-cinema-muto"):
        return None
    try:
        dates = [date.fromisoformat(event[key]) for key in (
            "programme_start_date", "programme_end_date",
            "programme_main_start_date", "programme_main_end_date")]
        expected = cinema_muto_edition(*dates)
    except (KeyError, TypeError, ValueError):
        return None
    if any(event.get(key) != expected[key] for key in (
            "programme_id", "edition_id", "programme_title", "programme_url")):
        return None
    return {**expected, "programme_role": event.get("programme_role") or "session"}


def pordenonelegge_edition(start, end):
    """Build edition identity from the official programme's verified dates."""
    if not isinstance(start, date) or not isinstance(end, date) or start > end or start.year != end.year:
        raise ValueError("invalid Pordenonelegge edition dates")
    year = str(start.year)
    return {**PORDENONELEGGE_2026,
            "programme_id": f"pordenonelegge-{year}", "edition_id": year,
            "programme_title": f"Pordenonelegge {year}",
            "programme_start_date": start.isoformat(),
            "programme_end_date": end.isoformat()}


def _declared_pordenonelegge(event):
    if event.get("source") != "Pordenonelegge" or event.get("series_id") != "pordenonelegge":
        return None
    try:
        start = date.fromisoformat(event["programme_start_date"])
        end = date.fromisoformat(event["programme_end_date"])
        expected = pordenonelegge_edition(start, end)
    except (KeyError, TypeError, ValueError):
        return None
    if (event.get("programme_id") != expected["programme_id"]
            or event.get("edition_id") != expected["edition_id"]
            or event.get("programme_title") != expected["programme_title"]
            or urlsplit(event.get("programme_url") or "").hostname != "www.pordenonelegge.it"):
        return None
    return {**expected, "programme_role": event.get("programme_role") or "session"}


def _declared_mess_laboratories(event):
    if (event.get('source') != 'MESS'
            or event.get('series_id') != 'mess-laboratori'
            or event.get('programme_role') != 'session'):
        return None
    try:
        start = date.fromisoformat(event['programme_start_date'])
        end = date.fromisoformat(event['programme_end_date'])
        session = date.fromisoformat(event['start_date'])
        museum_id = int(event['programme_id'].rsplit('-', 1)[-1])
    except (KeyError, TypeError, ValueError):
        return None
    year = str(start.year)
    if (start > session or session > end or start.year != end.year
            or event.get('programme_id') != f'mess-laboratori-{year}-{museum_id}'
            or event.get('edition_id') != year
            or event.get('programme_url') != MESS_LABORATORI_URL
            or event.get('url') != MESS_LABORATORI_URL
            or event.get('programme_title') != 'Laboratori MESS · ' + event.get('venue', '')
            or event.get('programme_city') != event.get('event_city')
            or event.get('programme_source') != 'MESS'):
        return None
    return {key: event[key] for key in (
        'series_id', 'programme_id', 'edition_id', 'programme_title',
        'programme_url', 'programme_start_date', 'programme_end_date',
        'programme_city', 'programme_place_label', 'programme_is_multi_place',
        'programme_is_multi_venue', 'programme_source',
        'programme_display_mode', 'programme_role')}

# These TurismoFVG pages were manually verified as the edition card or as
# sessions belonging to Pordenonelegge 2026.  This intentionally is not a title
# or URL-prefix heuristic: new pages require explicit review before inclusion.
_PORDENONELEGGE_TURISMO_URL_ROLES = {
    "https://www.turismofvg.it/eventi/pordenonelegge-2026": "umbrella",
    "https://www.turismofvg.it/eventi/pordenonelegge-scimmia-sapiens": "session_reference",
    "https://www.turismofvg.it/eventi/pordenonelegge-non-e-mai-troppo-tardi-la-salute-e-una-scelta-quotidiana": "session_reference",
    "https://www.turismofvg.it/eventi/pordenonelegge-csaba-dalla-zorza-presenta-il-tempo-per-un-altra-vita": "session_reference",
    "https://www.turismofvg.it/eventi/pordenonelegge-502757": "session_reference",
}


def programme_session_metadata(programme):
    """Return an isolated copy suitable for attaching to one parsed session."""
    return {**deepcopy(programme), "programme_role": "session"}


def reviewed_programme_metadata(event):
    """Resolve explicit programme membership, including old pilot snapshots."""
    declared = _declared_pordenonelegge(event)
    if declared:
        return declared
    declared = _declared_cinema_muto(event)
    if declared:
        return declared
    declared = _declared_mess_laboratories(event)
    if declared:
        return declared
    programme_id = event.get("programme_id")
    if event.get("source") == "Le Giornate del Cinema Muto":
        return None
    if (event.get("source") == "TurismoFVG"
            and event.get("url", "").split("?", 1)[0] == CINEMA_MUTO_TURISMO_2026):
        if (event.get("start_date") != "2026-10-03"
                or event.get("end_date") != "2026-10-10"
                or event.get("event_city") != "Pordenone"):
            return None
        expected = cinema_muto_edition(
            date(2026, 10, 2), date(2026, 10, 11),
            date(2026, 10, 3), date(2026, 10, 10))
        if programme_id and programme_id != expected["programme_id"]:
            return None
        return {**expected, "programme_role": "umbrella"}
    regional_mess = (MESS_REGIONAL_MUSEUMS_2026.get(event.get('url', '').split('?', 1)[0])
                     if event.get('source') == 'TurismoFVG' else None)
    if (regional_mess and
            (event.get('start_date'), event.get('end_date'), event.get('event_city'))
                == regional_mess[:3]):
        _, _, city, museum_id, museum_name, first, last = regional_mess
        return {'series_id': 'mess-laboratori',
                'programme_id': f'mess-laboratori-2026-{museum_id}',
                'edition_id': '2026',
                'programme_title': 'Laboratori MESS · ' + museum_name,
                'programme_url': MESS_LABORATORI_URL,
                'programme_start_date': first,
                'programme_end_date': last,
                'programme_city': city,
                'programme_place_label': city,
                'programme_is_multi_place': False,
                'programme_is_multi_venue': False,
                'programme_source': 'MESS',
                'programme_display_mode': 'umbrella',
                'programme_role': 'umbrella'}
    if event.get("source") == "Pordenonelegge" and programme_id:
        return None
    if programme_id and programme_id != PORDENONE_PENSA_2026["programme_id"]:
        # An unknown or inconsistent declared edition must never become 2026.
        if programme_id != PORDENONELEGGE_2026["programme_id"]:
            return None
    if programme_id == PORDENONELEGGE_2026["programme_id"]:
        return {**PORDENONELEGGE_2026,
                "programme_role": event.get("programme_role") or "session"}
    if programme_id == PORDENONE_PENSA_2026["programme_id"]:
        return {**PORDENONE_PENSA_2026,
                "programme_role": event.get("programme_role") or "session"}

    # Backward compatibility for already-published pilot snapshots.  Source
    # identity is explicit because these adapters only cover the reviewed 2026
    # editions; no title similarity is used.
    if event.get("source") == "Pordenonelegge" and not programme_id:
        return {**PORDENONELEGGE_2026, "programme_role": "session"}
    if (event.get("source") == "Pordenone Pensa"
            and event.get("url") == PORDENONE_PENSA_2026["programme_url"]):
        return {**PORDENONE_PENSA_2026, "programme_role": "session"}

    if event.get("source") == "TurismoFVG":
        role = _PORDENONELEGGE_TURISMO_URL_ROLES.get(event.get("url"))
        if role:
            return {**PORDENONELEGGE_2026, "programme_role": role}
    return None


def annotate_reviewed_regional_programme(event):
    """Attach programme metadata to an exact, reviewed regional listing."""
    metadata = reviewed_programme_metadata(event)
    if not metadata or event.get("source") != "TurismoFVG":
        return event
    return {**event, **metadata}


def _unique(values):
    return sorted({str(value).strip() for value in values if str(value or "").strip()})


def _session_identity(event):
    return (event.get("url"), event.get("title"), event.get("start_date"),
            event.get("time"), event.get("place"), event.get("event_city"))


def _programme_sessions(events):
    """Expose the qualifying programme entries, once each, in reading order."""
    unique = {_session_identity(event): event for event in events}
    ordered = sorted(unique.values(), key=lambda event: (
        event.get("start_date") or "", event.get("time") or "",
        event.get("title") or "", event.get("place") or ""))
    fields = ("title", "start_date", "time", "place", "event_city", "url",
              "access_notes")
    return [{key: event[key] for key in fields if event.get(key)} for event in ordered]


def _programme_card(events, metadata, today):
    direct_sessions = [event for event in events
                       if reviewed_programme_metadata(event).get("programme_role") == "session"]
    reference_sessions = [event for event in events
                          if reviewed_programme_metadata(event).get("programme_role") == "session_reference"]
    sessions = direct_sessions or reference_sessions
    programme_sessions = _programme_sessions(sessions)
    active_session_count = len(programme_sessions)

    occurrence_dates = _unique(
        occurrence
        for event in (sessions or events)
        for occurrence in ([event.get("start_date")] + list(event.get("occurrences") or []))
        if occurrence and date.fromisoformat(occurrence) >= today
    )
    # The card identifies the edition, so its visible range remains stable even
    # after the first day has passed.  The query has already removed expired or
    # out-of-radius sessions; ``active_session_count`` describes that relevant
    # subset without rewriting the edition dates.
    configured_start = date.fromisoformat(metadata["programme_start_date"])
    configured_end = date.fromisoformat(metadata["programme_end_date"])

    nearest = min(events, key=lambda event: event.get("distance_km", float("inf")))
    cities = _unique(event.get("event_city") for event in sessions or events)
    venues = _unique((event.get("venue") or event.get("place")) for event in sessions or events)
    multiple_places = metadata.get("programme_is_multi_place", len(cities) > 1)
    multiple_venues = metadata.get("programme_is_multi_venue", len(venues) > 1)

    # Preserve useful editorial decoration from the reviewed regional umbrella,
    # but never copy its identity, dates or location over the programme contract.
    rich = next((event for event in events
                 if reviewed_programme_metadata(event).get("programme_role") == "umbrella"
                 and any(event.get(key) for key in ("image", "description", "description_excerpt"))), {})
    optional = {}
    for key in ("image", "category", "categories", "provider_categories",
                "provider_category_list", "audience", "description",
                "description_excerpt", "description_source_name", "description_source_url"):
        value = rich.get(key)
        if value:
            optional[key] = deepcopy(value)
    if metadata.get("series_id") == "giornate-del-cinema-muto":
        official_image = next((event.get("image") for event in direct_sessions
                               if event.get("source") == "Le Giornate del Cinema Muto"
                               and event.get("image")), None)
        if official_image:
            optional["image"] = official_image
    if metadata.get('series_id') == 'mess-laboratori' and direct_sessions:
        next_session = min(direct_sessions, key=lambda event: event['start_date'])
        for key in ('description_excerpt', 'description_source_name',
                    'description_source_url', 'description_checked_at'):
            if next_session.get(key):
                optional[key] = next_session[key]

    updated_values = _unique(event.get("source_updated_at") for event in events)
    sources = _unique(event.get("source") for event in events)
    place = metadata.get("programme_place_label") or metadata["programme_city"]
    card = {
        **optional,
        **metadata,
        "display_mode": "umbrella",
        "programme_role": "umbrella",
        "title": metadata["programme_title"],
        "url": metadata["programme_url"],
        "source": metadata["programme_source"],
        "sources": sources,
        "source_id": metadata["programme_id"],
        "start_date": configured_start.isoformat(),
        "end_date": configured_end.isoformat(),
        "occurrences": occurrence_dates,
        # This projection runs after the date and radius gates. The count and
        # the preview entries describe the same qualifying subset; the full
        # edition is still retained in the source catalog.
        "active_session_count": active_session_count,
        "programme_sessions": programme_sessions,
        "event_city": place,
        "place": place,
        "venue": "Più sedi" if multiple_venues else (venues[0] if venues else place),
        "is_multi_place": multiple_places,
        "is_multi_venue": multiple_venues,
        "active_municipality_count": len(cities),
        "active_venue_count": len(venues),
        "location_label": f"{place} · Più sedi" if multiple_venues else place,
        # The nearest qualifying session decides whether the programme belongs
        # in this radius, but it is not the location of the umbrella itself.
        # Keeping that value separate prevents UI copy such as
        # "Pordenone e territorio · ~0 km" for a satellite-town session.
        "nearest_session_distance_km": nearest.get("distance_km"),
        "location_confidence": "programme_area",
        "source_status": ("fresh" if any(event.get("source_status") == "fresh" for event in events)
                          else nearest.get("source_status")),
        "source_updated_at": updated_values[-1] if updated_values else None,
        "date_evidence_kind": "programme_schedule",
        "date_evidence": f'{configured_start.isoformat()} / {configured_end.isoformat()}',
        "is_real": True,
    }
    return {key: value for key, value in card.items() if value is not None}


def project_programme_editions(events, *, today):
    """Collapse explicit programme sessions after date and radius filtering."""
    regular, groups, metadata_by_group = [], {}, {}
    has_mess_programme = any(
        event.get('source') == 'MESS'
        and _declared_mess_laboratories(event) for event in events)
    for event in events:
        if (has_mess_programme and event.get('source') == 'TurismoFVG'
                and event.get('url', '').split('?', 1)[0] == MESS_REGIONAL_UMBRELLA_2026
                and event.get('start_date') == '2026-08-01'
                and event.get('end_date') == '2026-12-20'
                and event.get('location_confidence') == 'multiple_municipalities'):
            continue
        metadata = reviewed_programme_metadata(event)
        if not metadata:
            regular.append(event)
            continue
        key = metadata["programme_id"]
        groups.setdefault(key, []).append(event)
        if key not in metadata_by_group or event.get("source") in {
                "Pordenonelegge", "Le Giornate del Cinema Muto",
                "MESS"}:
            metadata_by_group[key] = metadata
    regular.extend(_programme_card(group, metadata_by_group[key], today)
                   for key, group in groups.items())
    return regular
