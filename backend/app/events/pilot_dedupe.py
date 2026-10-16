"""Conservative cross-source identity; ambiguous sessions stay separate."""
from difflib import SequenceMatcher
from datetime import date
import re
import unicodedata

from . import engine
from .pilot_excerpt import EXCERPT_FIELDS

DIRECT = {"Pordenonelegge", "Barcolana", "Azalea", "CSS Udine", "Teatro Verdi Pordenone",
          "Teatro Verdi Trieste", "Pordenone Pensa", "Villa Manin",
          "Magazzino delle Idee", "MESS", "Galleria Spazzapan"}
SAGRA_PAIR = {"Paesi in Festa", "SagreFVG"}
TITLE_FILLER = {"sagra", "sagre", "festa", "festeggiamenti", "del", "della",
                "delle", "di", "da", "las", "la", "il", "perdon", "ed", "edizione"}
GENERIC_TITLES = {"concerto", "evento", "laboratorio", "spettacolo",
                  "visita guidata", "domenica al museo", "ingresso gratuito"}
REVIEWED_PREFERRED_URLS = {
    frozenset({
        'https://paesiinfesta.com/friuli-venezia-giulia/pordenone/sagra-di-rauscedo-di-gan-giorgio-della-richinvelda/',
        'https://sagrefvg.it/sagre/rauscedo-di-san-giorgio-della-richinvelda-pn-le-radici-del-vino-duplicate-1/',
    }): 'https://paesiinfesta.com/friuli-venezia-giulia/pordenone/sagra-di-rauscedo-di-gan-giorgio-della-richinvelda/',
    frozenset({
        'https://paesiinfesta.com/friuli-venezia-giulia/pordenone/sagra-di-rauscedo-di-gan-giorgio-della-richinvelda/',
        'https://www.turismofvg.it/eventi/le-radici-del-vino-505985',
    }): 'https://paesiinfesta.com/friuli-venezia-giulia/pordenone/sagra-di-rauscedo-di-gan-giorgio-della-richinvelda/',
}
REVIEWED_PERIOD_REPLACEMENTS = (
    ('https://paesiinfesta.com/friuli-venezia-giulia/udine/campoformido/',
     '2026-10-09', '2026-10-11', (
         ('https://www.turismofvg.it/eventi/un-giorno-con-napoleone-466090',
          '2026-10-10', '2026-10-11'),
         ('https://www.turismofvg.it/eventi/un-giorno-con-napoleone-504752',
          '2026-10-10', '2026-10-11'))),
    ('https://www.turismofvg.it/eventi/32-festa-delle-zucche',
     '2026-10-18', '2026-10-25', (
         ('https://paesiinfesta.com/friuli-venezia-giulia/pordenone/sagra-di-cordenons-inverno/',
          '2026-10-24', '2026-10-25'),)),
)
REVIEWED_MESS_NEWS_PAIRS = {
    frozenset({
        'https://mess.regione.fvg.it/it/not-173804',
        'https://www.turismofvg.it/eventi/sulla-soglia-simboli-e-rituali-della-morte-in-friuli-con-le-fotografie-di-carlo-innocenti',
    }),
    frozenset({
        'https://mess.regione.fvg.it/it/not-173318/no-173328',
        'https://www.turismofvg.it/eventi/mostra-victor-oriecuia-spiriti-amuleti-e-memorie-ancestrali',
    }),
    frozenset({
        'https://mess.regione.fvg.it/it/not-169209',
        'https://www.turismofvg.it/eventi/storie-di-erbe-un-percorso-tra-magia-miti-focolare-e-credenze',
    }),
}
REVIEWED_SPAZZAPAN_PAIR = frozenset({
    'https://galleriaspazzapan.regione.fvg.it/it/fvg7002-eventi-collaterali-di-ottobre-172985',
    'https://www.turismofvg.it/eventi/mostra-fvg70-02-nuovi-modelli-di-ricerca',
})
BARCOLANA_REGIONAL_CARD = 'https://www.turismofvg.it/eventi/58a-ed-barcolana'
REVIEWED_BARCOLANA_SESSIONS = {
    'https://www.turismofvg.it/eventi/barcolana58-concerto-les-babettes':
        ('2026-10-09', 'CONCERTO LES BABETTES'),
    'https://www.turismofvg.it/eventi/barcolana58-m2o-night':
        ('2026-10-10', 'M2O NIGHT'),
    'https://www.turismofvg.it/events20/details/377881':
        ('2026-10-09', "L'incanto dei castelli d'acqua: Miramare e Duino protagonisti della riviera triestina"),
    'https://www.turismofvg.it/eventi/barcolana-58-le-frontiere-che-uniscono-storie-di-popoli-viaggi-identita':
        ('2026-10-10', 'Le frontiere che uniscono: storie di popoli, viaggi, identità'),
    'https://www.turismofvg.it/eventi/barcolana-ski-coppa-d-autunno-il-10-ottobre-la-sfida-ad-aurisina':
        ('2026-10-10', "BARCOLANA SKI - COPPA D'AUTUNNO"),
}
REVIEWED_BARCOLANA_PERIODS = {
    'https://www.turismofvg.it/eventi/barcolana-58-le-rotte-in-liberta':
        ('2026-10-07', '2026-10-11', 'rotte in liberta'),
    'https://www.turismofvg.it/eventi/barcolana-all-museo-della-scienza':
        ('2026-10-04', '2026-10-11', 'barcolana al museo della scienza'),
    'https://www.turismofvg.it/eventi/la-contrada-ragazzi-barcolana-58-storie-di-pirati-e-sirene':
        ('2026-10-06', '2026-10-09', 'storie di pirati e di sirene'),
    'https://www.turismofvg.it/eventi/per-barcolana-la-lanterna-apre-alla-citta':
        ('2026-10-07', '2026-10-10', 'la lanterna aperta alla citta'),
}


def _locality_root(value):
    normalized = engine.normalize_for_search(value)
    return re.split(r"\s+(?:di|al)\s+", normalized, maxsplit=1)[0]


def _distinctive_tokens(value):
    normalized = unicodedata.normalize("NFKD", engine.normalize_for_search(value))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return [part for part in re.findall(r"[a-z]+", normalized)
            if part not in TITLE_FILLER and len(part) >= 4]


def same_sagra_across_sources(event, other):
    """Join one named sagra at the same locality, municipality and date range."""
    if {event.get("source"), other.get("source")} != SAGRA_PAIR:
        return False
    if not event.get("place") or not other.get("place"):
        return False
    if _locality_root(event["place"]) != _locality_root(other["place"]):
        return False
    left, right = _distinctive_tokens(event.get("title")), _distinctive_tokens(other.get("title"))
    return bool(left and right and any(
        SequenceMatcher(None, word_a, word_b).ratio() >= 0.86
        for word_a in left for word_b in right))


def same_regional_festival(event, other):
    """Join a named local festival with the matching regional detail."""
    if ({event.get('source'), other.get('source')} not in
            ({'TurismoFVG', 'SagreFVG'}, {'TurismoFVG', 'Paesi in Festa'})
            or event.get('time') or other.get('time')):
        return False
    a = _distinctive_tokens(event.get('title'))
    b = _distinctive_tokens(other.get('title'))
    if not a or not b:
        return False
    smaller, larger = (a, b) if len(a) <= len(b) else (b, a)
    matched = sum(any(SequenceMatcher(None, word, other_word).ratio() >= .86
                      for other_word in larger) for word in smaller)
    return matched >= max(1, (3 * len(smaller) + 3) // 4)


def same_mess_news_exhibition(event, other):
    return ({event.get('source'), other.get('source')} == {'MESS', 'TurismoFVG'}
            and frozenset({event.get('url'), other.get('url')})
                in REVIEWED_MESS_NEWS_PAIRS
            and any(item.get('source') == 'MESS'
                    and item.get('mess_content_kind') == 'news_exhibition'
                    for item in (event, other)))


def same_spazzapan_exhibition(event, other):
    return ({event.get('source'), other.get('source')}
            == {'Galleria Spazzapan', 'TurismoFVG'}
            and frozenset({event.get('url'), other.get('url')})
                == REVIEWED_SPAZZAPAN_PAIR)


def same_villa_manin_across_sources(event, other):
    return ({event.get('source'), other.get('source')} == {'Villa Manin', 'TurismoFVG'}
            and engine.normalize_for_search(event.get('title'))
                == engine.normalize_for_search(other.get('title'))
            and all('villa manin' in engine.normalize_for_search(item.get('venue'))
                    for item in (event, other)))


def same_magazzino_across_sources(event, other):
    return ({event.get('source'), other.get('source')}
            == {'Magazzino delle Idee', 'TurismoFVG'}
            and engine.normalize_for_search(event.get('title'))
                == engine.normalize_for_search(other.get('title'))
            and all('magazzino delle idee' in engine.normalize_for_search(item.get('venue'))
                    for item in (event, other)))


def same_exact_venue_across_sources(event, other):
    """Recognize a shared dated event only when both sources name one venue."""
    if event.get('source') == other.get('source'):
        return False
    if event.get('programme_id') or other.get('programme_id'):
        return False
    if engine.normalize_for_search(event.get('title')) in GENERIC_TITLES:
        return False
    venues = [engine.normalize_for_search(item.get('venue')) for item in (event, other)]
    return bool(venues[0] and venues[0] == venues[1])


def _selection_score(event):
    """Prefer the organiser's detail, then the best verified location and copy."""
    location = {'none': 0, 'city_text': 1, 'municipality': 2,
                'venue': 3, 'exact': 3}
    return (event.get('source') in DIRECT,
            location.get(event.get('location_confidence'), 0),
            bool(event.get('venue')), bool(event.get('address')),
            all(event.get(key) for key in EXCERPT_FIELDS),
            bool(event.get('image')),
            engine.event_preference_score(event, []))


def _title_core(value):
    title = engine.normalize_for_search(value)
    title = re.sub(r'^(?:teatro verdi|anni verdi)(?:\s+20\d{2}/20\d{2})?\s*-\s*', '', title)
    title = re.sub(r'\s*-\s*contatto tig in famiglia 20\d{2}/20\d{2}$', '', title)
    title = title.rsplit(' / ', 1)[-1]
    title = unicodedata.normalize('NFKD', title)
    title = ''.join(char for char in title if not unicodedata.combining(char))
    return ' '.join(re.findall(r'[a-z0-9]+', title))


def _same_stage_title(a, b):
    a, b = _title_core(a), _title_core(b)
    return bool(a and b and a not in GENERIC_TITLES and b not in GENERIC_TITLES and
                (a == b or
                len(a) >= 8 and b.startswith(a + ' ') or
                len(b) >= 8 and a.startswith(b + ' ')))


def _same_stage_venue(direct, regional):
    if direct.get('source') == 'Teatro Verdi Trieste':
        return engine.normalize_for_search(regional.get('title')).startswith('teatro verdi -')
    a = _title_core(direct.get('venue'))
    b = _title_core(regional.get('venue'))
    if direct.get('source') == 'Teatro Verdi Pordenone':
        return 'verdi' in a and 'verdi' in b
    if direct.get('source') == 'CSS Udine':
        return any(token in a and token in b for token in
                   ('palamost', 'pasolini', 'giorgio')) or \
            ('giorgio' in a and 'sab giorgio' in b)
    return False


def _same_source_variant(event, other):
    if (event.get('source') != other.get('source') or
            event.get('source') not in {'TurismoFVG', 'CSS Udine'} or
            (event.get('time') and other.get('time') and
             event['time'] != other['time']) or
            _title_core(event.get('title')) in GENERIC_TITLES or
            not _same_stage_title(event.get('title'), other.get('title'))):
        return False
    a, b = _title_core(event.get('venue')), _title_core(other.get('venue'))
    city = _title_core(event.get('event_city'))
    return bool(a and b and (a == b or a == city or b == city or
                            a.startswith(b + ' ') or b.startswith(a + ' ')))


def _choose_best(event, other):
    if _same_source_variant(event, other):
        if bool(event.get('time')) != bool(other.get('time')):
            return (event, other) if event.get('time') else (other, event)
        city = _title_core(event.get('event_city'))
        if (_title_core(event.get('venue')) == city) != (_title_core(other.get('venue')) == city):
            return (other, event) if _title_core(event.get('venue')) == city else (event, other)
    preferred_url = REVIEWED_PREFERRED_URLS.get(frozenset((event.get('url'), other.get('url'))))
    if (preferred_url and all(item.get('start_date') == '2026-10-09'
                              and item.get('end_date') == '2026-10-11'
                              for item in (event, other))):
        return ((event, other) if event.get('url') == preferred_url else (other, event))
    if _selection_score(event) != _selection_score(other):
        return ((event, other) if _selection_score(event) > _selection_score(other)
                else (other, event))
    # Cross-source ties must not depend on the source iteration order.
    return tuple(sorted((event, other), key=lambda item: (
        str(item.get('source') or ''), str(item.get('url') or ''))))


def _prefer_official_discrete_dates(events):
    """A dated Villa Manin programme replaces its broad TurismoFVG proxy."""
    official = [event for event in events
                if event.get('source') == 'Villa Manin'
                and event.get('schedule_kind') == 'explicit_occurrence'
                and event.get('start_date') == event.get('end_date')]
    suppressed = set()
    for index, regional in enumerate(events):
        if (regional.get('source') != 'TurismoFVG' or regional.get('time')
                or regional.get('programme_id')
                or not regional.get('start_date') or not regional.get('end_date')
                or regional['start_date'] == regional['end_date']):
            continue
        title = engine.normalize_for_search(regional.get('title'))
        city = engine.normalize_for_search(regional.get('event_city'))
        venue = engine.normalize_for_search(regional.get('venue'))
        if not city or 'villa manin' not in venue:
            continue
        grouped = {}
        for event in official:
            name = engine.normalize_for_search(event.get('title'))
            if (name and title.startswith(name)
                    and engine.normalize_for_search(event.get('event_city')) == city
                    and 'villa manin' in engine.normalize_for_search(event.get('venue'))
                    and not event.get('time')
                    and regional['start_date'] <= event['start_date'] <= regional['end_date']):
                grouped.setdefault(event.get('url'), []).append(event)
        matching = next((rows for rows in grouped.values()
                         if len({row['start_date'] for row in rows}) >= 2), None)
        if matching:
            suppressed.add(index)
            for event in matching:
                event['source_urls'] = sorted(set(event.get('source_urls', [])
                                                  + [event['url'], regional['url']]))
    return [event for index, event in enumerate(events) if index not in suppressed]


def _prefer_reviewed_periods(events):
    """Keep the evidenced complete 2026 programme for two conflicting pairs."""
    suppressed = set()
    for preferred_url, first, last, alternatives in REVIEWED_PERIOD_REPLACEMENTS:
        preferred = next((event for event in events
                          if event.get('url') == preferred_url
                          and event.get('start_date') == first
                          and event.get('end_date') == last), None)
        if preferred is None:
            continue
        for url, start, end in alternatives:
            for index, other in enumerate(events):
                if (other.get('url') != url or other.get('start_date') != start
                        or other.get('end_date') != end
                        or engine.normalize_for_search(other.get('event_city')) !=
                           engine.normalize_for_search(preferred.get('event_city'))):
                    continue
                suppressed.add(index)
                preferred['source_urls'] = sorted(set(
                    preferred.get('source_urls', []) + [preferred_url, url]))
                if not preferred.get('image') and other.get('image'):
                    preferred['image'] = other['image']
    return [event for index, event in enumerate(events) if index not in suppressed]


def _prefer_direct_stage_dates(events):
    """Use complete theatre programmes over short regional date ranges."""
    direct_sources = {'CSS Udine', 'Teatro Verdi Pordenone', 'Teatro Verdi Trieste'}
    suppressed = set()
    for index, regional in enumerate(events):
        if (regional.get('source') != 'TurismoFVG' or regional.get('time')
                or regional.get('programme_id')
                or not regional.get('start_date') or not regional.get('end_date')):
            continue
        try:
            span = (date.fromisoformat(regional['end_date']) -
                    date.fromisoformat(regional['start_date'])).days
        except ValueError:
            continue
        if not 0 <= span <= 14:
            continue
        groups = {}
        for event in events:
            if (event.get('source') not in direct_sources
                    or event.get('programme_id')
                    or event.get('start_date') != event.get('end_date')
                    or not regional['start_date'] <= (event.get('start_date') or '') <= regional['end_date']
                    or engine.normalize_for_search(event.get('event_city')) !=
                       engine.normalize_for_search(regional.get('event_city'))
                    or not _same_stage_title(event.get('title'), regional.get('title'))
                    or not _same_stage_venue(event, regional)):
                continue
            groups.setdefault((event['source'], event.get('url')), []).append(event)
        matching = next((rows for rows in groups.values()
                         if (span == 0 or len({row['start_date'] for row in rows}) >= 2)
                         and any(row['start_date'] == regional['end_date'] for row in rows)), None)
        if not matching:
            continue
        suppressed.add(index)
        for event in matching:
            event['source_urls'] = sorted(set(event.get('source_urls', [])
                                              + [event['url'], regional['url']]))
            if not event.get('image') and regional.get('image'):
                event['image'] = regional['image']
            if not event.get('description_excerpt') and all(regional.get(key) for key in EXCERPT_FIELDS):
                for key in EXCERPT_FIELDS:
                    event[key] = regional[key]
    return [event for index, event in enumerate(events) if index not in suppressed]


def _prefer_barcolana_programme(events):
    """Replace only reviewed regional identities present in the official card."""
    official = next((event for event in events
                     if event.get('source') == 'Barcolana'
                     and event.get('title') == 'Barcolana 2026'
                     and event.get('programme_sessions')), None)
    if not official:
        return events
    sessions = {(item.get('start_date'), _title_core(item.get('title')))
                for item in official['programme_sessions']}
    suppressed = set()
    for index, event in enumerate(events):
        if event.get('source') != 'TurismoFVG':
            continue
        url = event.get('url')
        if (engine.normalize_for_search(event.get('event_city')) != 'trieste'
                and url not in REVIEWED_BARCOLANA_SESSIONS):
            continue
        if (url == BARCOLANA_REGIONAL_CARD
                and event.get('start_date') == '2026-10-02'
                and event.get('end_date') == '2026-10-11'):
            suppressed.add(index)
        elif (url in (official.get('regional_mirror_days') or {})
              and event.get('start_date') == event.get('end_date')
              == official['regional_mirror_days'][url]):
            suppressed.add(index)
        elif (url in (official.get('regional_mirror_periods') or {})
              and (event.get('start_date'), event.get('end_date'))
              == tuple(official['regional_mirror_periods'][url])):
            suppressed.add(index)
        elif url in REVIEWED_BARCOLANA_SESSIONS:
            day, title = REVIEWED_BARCOLANA_SESSIONS[url]
            if (event.get('start_date') == event.get('end_date') == day
                    and _title_core(title) in _title_core(event.get('title'))
                    and (day, _title_core(title)) in sessions):
                suppressed.add(index)
        elif url in REVIEWED_BARCOLANA_PERIODS:
            first, last, title_prefix = REVIEWED_BARCOLANA_PERIODS[url]
            if (event.get('start_date') == first and event.get('end_date') == last
                    and any(first <= day <= last and title.startswith(title_prefix)
                            for day, title in sessions)):
                suppressed.add(index)
        if index in suppressed:
            official['source_urls'] = sorted(set(
                official.get('source_urls', []) + [official['url'], url]))
            if event.get('distance_km') is not None and (
                    official.get('distance_km') is None
                    or event['distance_km'] < official['distance_km']):
                official['distance_km'] = event['distance_km']
    return [event for index, event in enumerate(events) if index not in suppressed]


def deduplicate(events):
    events = _prefer_barcolana_programme(_prefer_direct_stage_dates(
        _prefer_reviewed_periods(
            _prefer_official_discrete_dates([dict(event) for event in events]))))
    result = []
    for event in events:
        match = None
        for index, other in enumerate(result):
            # Never collapse a multi-day festival into a single meeting, or two
            # performances when a source omits the time.
            keys = ("start_date", "end_date")
            if any(not event.get(k) or event.get(k) != other.get(k) for k in keys):
                continue
            same_variant = _same_source_variant(event, other)
            if event.get("time") != other.get("time") and not same_variant:
                continue
            if sorted(event.get('occurrences') or []) != sorted(other.get('occurrences') or []):
                continue
            if event.get('end_time') and other.get('end_time') and event['end_time'] != other['end_time']:
                continue
            if not event.get("event_city") or engine.normalize_for_search(event["event_city"]) != engine.normalize_for_search(other.get("event_city")):
                continue
            sagra_pair = same_sagra_across_sources(event, other) if not event.get("time") else False
            festival_pair = same_regional_festival(event, other)
            mess_news_pair = same_mess_news_exhibition(event, other)
            spazzapan_pair = same_spazzapan_exhibition(event, other)
            villa_pair = same_villa_manin_across_sources(event, other) if not event.get('time') else False
            magazzino_pair = same_magazzino_across_sources(event, other) if not event.get('time') else False
            exact_venue_pair = same_exact_venue_across_sources(event, other)
            same_reference = (event.get("url") and event.get("url") == other.get("url")
                              and event.get("source") == other.get("source"))
            if not event.get("time") and not (same_reference or same_variant or sagra_pair or festival_pair or mess_news_pair or spazzapan_pair or villa_pair
                                                or magazzino_pair or exact_venue_pair):
                continue
            if (engine.normalize_for_search(event.get("title"))
                    != engine.normalize_for_search(other.get("title")) and not (sagra_pair or festival_pair or mess_news_pair or spazzapan_pair or same_variant)):
                continue
            if (event.get('source') != other.get('source')
                    and engine.normalize_for_search(event.get('title')) in GENERIC_TITLES
                    and not all(engine.normalize_for_search(item.get('venue')) for item in (event, other))):
                continue
            # Two explicit venues that disagree need review, not a silent merge.
            if (event.get("venue") and other.get("venue")
                    and engine.normalize_for_search(event["venue"])
                        != engine.normalize_for_search(other["venue"])
                    and not (villa_pair or magazzino_pair or festival_pair or mess_news_pair or spazzapan_pair or same_variant)):
                continue
            conflict = False
            for field in ("address", "place"):
                a, b = event.get(field), other.get(field)
                if a and b and engine.normalize_for_search(a) != engine.normalize_for_search(b):
                    if field == "place" and (sagra_pair or festival_pair or mess_news_pair or spazzapan_pair or villa_pair or magazzino_pair or same_variant
                                              or exact_venue_pair):
                        continue
                    # A municipality-only place is not a conflicting venue.
                    city = engine.normalize_for_search(event.get("event_city"))
                    if field != "place" or all(engine.normalize_for_search(v) != city for v in (a, b)):
                        conflict = True
            if conflict:
                continue
            match = index
            break
        if match is None:
            result.append(dict(event))
            continue
        other = result[match]
        primary, secondary = _choose_best(event, other)
        merged = engine.merge_duplicate_event_data(primary, secondary)
        if (not merged.get('description_excerpt')
                and all(secondary.get(key) for key in EXCERPT_FIELDS)):
            for key in EXCERPT_FIELDS:
                if secondary.get(key):
                    merged[key] = secondary[key]
        # Query distances have already been computed. Keep the chosen record's
        # location bundle atomic rather than mixing another point and distance.
        for key in ("lat", "lon", "maps_url", "location_confidence", "distance_km", "distance_is_approximate"):
            if key in primary:
                merged[key] = primary[key]
            else:
                merged.pop(key, None)
        merged["source_urls"] = sorted(set(primary.get("source_urls", []) + secondary.get("source_urls", []) + [u for u in (primary.get("url"), secondary.get("url")) if u]))
        if not merged.get("access_notes") and secondary.get("access_notes"):
            merged["access_notes"] = secondary["access_notes"]
        if not merged.get('end_time') and secondary.get('end_time'):
            merged['end_time'] = secondary['end_time']
        result[match] = merged
    return result
