import unittest
from copy import deepcopy
from datetime import date, datetime, timedelta
from app.events.pilot_pordenonelegge import collect_pordenonelegge, parse_programme
from app.events.pilot_catalog import merge_collection, query_catalog, PILOT_PROJECT
from app.events.pilot_source_policy import gate_batch


def card(hour="09:00", city="Sacile", day="2026-09-16"):
    return f'''<div class="festival-programme-event" data-giornoevento="{day}" id="42">
    <h4 class="festival-programme-event-hour">{hour}</h4>
    <a class="festival-programme-event-place">{city}, Teatro</a>
    <h3 class="festival-programme-event-title"><a href="/eventi/prova">Un <b>incontro</b> &amp; libri</a></h3>
    <p class="light-notice">Riservato alle scuole</p><img src="unused"></div>'''


def page(cards, *, year=2026, days=("2026-09-16",)):
    weekdays = ("lun", "mar", "mer", "gio", "ven", "sab", "dom")
    tabs = ''.join(
        f'<a class="festival-programme-tab day" href="/programma?giorno={weekdays[date.fromisoformat(day).weekday()]}">'
        f'{weekdays[date.fromisoformat(day).weekday()]} {date.fromisoformat(day).day}</a>'
        for day in days)
    return (f'<h1>Programma completo {year}</h1>{tabs}'
            '<a class="festival-programme-tab day" href="/programma?giorno=tutto">tutto</a>'
            + cards)


class PordenoneleggeTests(unittest.TestCase):
    def test_official_home_redirect_closes_only_a_verified_past_edition(self):
        days = tuple((date(2026, 9, 16) + timedelta(days=index)).isoformat()
                     for index in range(5))
        prior = parse_programme(page(''.join(card(day=day) for day in days),
                                     days=days))
        class Redirect:
            status_code = 302
            headers = {'Location': '/'}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def raise_for_status(self):
                return None
        get = lambda *args, **kwargs: Redirect()
        today = date(2026, 10, 13)
        closed = collect_pordenonelegge(
            get=get, today=today, previous_batch={'verification': prior['verification']})
        self.assertEqual(gate_batch(
            'Pordenonelegge', closed, today=today,
            previous_batch={'verification': prior['verification']})['status'], 'ok')
        self.assertEqual(closed['events'], [])
        again = collect_pordenonelegge(
            get=get, today=today, previous_batch={'verification': closed['verification']})
        self.assertEqual(gate_batch(
            'Pordenonelegge', again, today=today,
            previous_batch={'verification': closed['verification']})['status'], 'ok')
        with self.assertRaises(ValueError):
            collect_pordenonelegge(get=get, today=today)
    def test_facts_and_access_preserved(self):
        event = parse_programme(page(card()))["events"][0]
        self.assertEqual(event["title"], "Un incontro & libri")
        self.assertEqual(event["event_city"], "Sacile")
        self.assertEqual(event["time"], "09:00")
        self.assertEqual(event["access_notes"], "Riservato alle scuole")
        self.assertEqual(event["location_confidence"], "municipality")
        self.assertEqual(event["programme_id"], "pordenonelegge-2026")
        self.assertEqual(event["programme_role"], "session")

    def test_duplicate_removed_but_second_time_kept(self):
        self.assertEqual(len(parse_programme(page(card()*2 + card("11:00")))["events"]), 2)

    def test_unknown_place_not_assigned_to_pordenone(self):
        batch = parse_programme(page(card(city="Sede ignota")))
        self.assertEqual(batch["events"], [])
        self.assertEqual(batch["review_required"][0]["reason"],
                         "municipality_not_resolved")

    def test_invalid_date_and_time_rejected(self):
        for html in (card(day=""), card(day="2026-02-30"), card(day="2027-09-16")):
            with self.assertRaises(ValueError):
                parse_programme(page(html))
        invalid_time = parse_programme(page(card(hour="25:00")))
        self.assertEqual(invalid_time["status"], "error")
        self.assertEqual(invalid_time["review_required"][0]["reason"],
                         "invalid_programme_time")

    def test_bad_link_rejected(self):
        with self.assertRaises(ValueError):
            parse_programme(page(card().replace("/eventi/prova", "https://example.org/eventi/prova")))

    def test_empty_and_truncated_rejected(self):
        for html in ("<p>Non ci sono eventi</p>", page(card()[:-6])):
            with self.assertRaises(ValueError):
                parse_programme(html)

    def test_catalog_projects_sessions_as_one_programme_with_ordered_entries(self):
        batch = parse_programme(page(card("11:00") + card("09:00")))
        catalog = merge_collection(PILOT_PROJECT, None, {"Pordenonelegge": batch}, "2026-09-06T18:00:00Z")
        event = batch["events"][0]
        result = query_catalog(catalog, event["lat"], event["lon"], now=datetime.fromisoformat("2026-09-06T18:00:00Z"))
        self.assertEqual(len(result["events"]), 1)
        programme = result["events"][0]
        self.assertEqual(programme["title"], "Pordenonelegge 2026")
        self.assertEqual(programme["display_mode"], "umbrella")
        self.assertEqual(programme["active_session_count"], 2)
        self.assertNotIn("session_count", programme)
        self.assertEqual(programme["venue"], "Più sedi")
        self.assertEqual([item["time"] for item in programme["programme_sessions"]],
                         ["09:00", "11:00"])
        self.assertEqual(programme["programme_sessions"][0]["url"],
                         "https://www.pordenonelegge.it/eventi/prova")
        self.assertEqual(programme["programme_sessions"][0]["access_notes"],
                         "Riservato alle scuole")

    def test_next_edition_is_derived_from_header_tabs_and_cards(self):
        days = tuple((date(2027, 9, 15) + timedelta(days=index)).isoformat()
                     for index in range(5))
        batch = parse_programme(page(''.join(card(day=day) for day in days),
                                     year=2027, days=days))
        self.assertEqual(batch["verification"]["edition_id"], "2027")
        self.assertEqual(batch["verification"]["tab_dates"], list(days))
        self.assertEqual({event["programme_id"] for event in batch["events"]},
                         {"pordenonelegge-2027"})
        self.assertEqual(batch["events"][0]["programme_start_date"], days[0])
        self.assertEqual(batch["events"][0]["programme_end_date"], days[-1])
        gated = gate_batch("Pordenonelegge", batch, today=date(2027, 9, 14))
        self.assertEqual(gated["status"], "ok")
        catalog = merge_collection(PILOT_PROJECT, None, {"Pordenonelegge": gated},
                                   "2027-09-14T12:00:00Z")
        event = batch["events"][0]
        result = query_catalog(catalog, event["lat"], event["lon"],
                               now=datetime.fromisoformat("2027-09-14T12:00:00Z"))
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["events"][0]["title"], "Pordenonelegge 2027")

    def test_automatic_gate_rejects_missing_cards_and_schedule_notices(self):
        days = tuple((date(2026, 9, 16) + timedelta(days=index)).isoformat()
                     for index in range(5))
        batch = parse_programme(page(''.join(card(day=day) for day in days), days=days))
        damaged = deepcopy(batch)
        damaged['events'].pop()
        self.assertEqual(gate_batch('Pordenonelegge', damaged,
                                    today=date(2026, 9, 15))['error_type'],
                         'source_verification_failed')
        changed = parse_programme(page(
            card(day=days[0]).replace('Riservato alle scuole', 'Incontro annullato')
            + ''.join(card(day=day) for day in days[1:]), days=days))
        self.assertEqual(gate_batch('Pordenonelegge', changed,
                                    today=date(2026, 9, 15))['status'], 'partial')
        wrong_day = deepcopy(batch)
        wrong_day['events'][0]['start_date'] = days[1]
        self.assertEqual(gate_batch('Pordenonelegge', wrong_day,
                                    today=date(2026, 9, 15))['error_type'],
                         'source_verification_failed')

    def test_same_edition_large_count_drop_is_rejected_but_new_year_resets_baseline(self):
        days = tuple((date(2026, 9, 16) + timedelta(days=index)).isoformat()
                     for index in range(5))
        batch = parse_programme(page(''.join(card(day=day) for day in days), days=days))
        previous = {'verification': {'edition_id': '2026', 'tab_dates': list(days),
                                     'records_scanned': 6}}
        failed = gate_batch('Pordenonelegge', batch, today=date(2026, 9, 15),
                            previous_batch=previous)
        self.assertEqual(failed['error_type'], 'source_verification_failed')
        previous['verification']['edition_id'] = '2025'
        accepted = gate_batch('Pordenonelegge', batch, today=date(2026, 9, 15),
                              previous_batch=previous)
        self.assertEqual(accepted['status'], 'ok')
        previous['verification']['edition_id'] = '2027'
        self.assertEqual(gate_batch('Pordenonelegge', batch, today=date(2026, 9, 15),
                                    previous_batch=previous)['status'], 'error')

    def test_missing_day_or_mismatched_year_fails_closed(self):
        days = ("2026-09-16", "2026-09-17")
        for html in (
            page(card(), days=days),
            page(card(day=days[0]) + card(day=days[1]), year=2027, days=days),
            page(card()).replace("giorno=tutto", "giorno=mer"),
        ):
            with self.assertRaises(ValueError):
                parse_programme(html)
