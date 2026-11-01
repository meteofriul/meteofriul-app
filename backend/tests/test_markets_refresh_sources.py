import json
from datetime import date
import unittest
from unittest.mock import patch

from app.markets.refresh_sources import (collect_market, _url, _public_addresses,
                                         MAX_SOURCES, SourceError)


URL = "https://official.example/market"
MARKET = {"id": "M1", "name": "Mercatino di prova", "comune": "Udine", "url": URL}


def event(**updates):
    return {"@type": "Event", "@id": URL + "#edition", "name": "Mercatino di prova", "url": URL,
            "startDate": "2026-11-15T09:00:00+01:00", "endDate": "2026-11-15T18:00:00+01:00",
            "location": {"@type": "Place", "name": "Piazza Libertà", "address": {
                "@type": "PostalAddress", "addressLocality": "Udine", "streetAddress": "Piazza Libertà"}},
            **updates}


def html(data):
    return '<html><script type="application/ld+json">' + json.dumps(data) + '</script></html>'


def collect(body, market=None, **kwargs):
    return collect_market(market or MARKET, [], [], as_of=date(2026, 11, 1), fetch=lambda _: body, **kwargs)


class MarketRefreshSourcesTests(unittest.TestCase):
    def test_explicit_single_edition_and_venue_preserve_source_evidence(self):
        result = collect(html(event(dateModified="2026-10-31")))
        self.assertEqual(result["issues"], [])
        observation = result["observations"][0]
        self.assertEqual(observation["fields"], {})
        self.assertNotIn("validThrough", observation)
        self.assertEqual(observation["sourceUpdatedAt"], "2026-10-31")
        self.assertEqual(len(observation["contentHash"]), 64)
        edition = observation["editions"][0]
        self.assertEqual(edition["date"], "2026-11-15")
        self.assertEqual(edition["sourceKey"], URL + "#edition")
        self.assertEqual(edition["venue"]["place"], "Piazza Libertà")
        self.assertIn("Piazza Libertà", observation["evidence"][0]["excerpt"])
        self.assertEqual(observation["evidence"][0]["value"], edition)

    def test_unrelated_name_or_municipality_or_source_url_not_matched(self):
        for entry in [event(name="Concerto"), event(url="https://other.example/event"),
                      event(location={"address": {"addressLocality": "Pordenone"}})]:
            with self.subTest(entry=entry):
                self.assertEqual(collect(html(entry))["observations"], [])

    def test_date_range_never_expands_to_calendar(self):
        result = collect(html(event(endDate="2026-11-19")))
        self.assertEqual(result["observations"], [])
        self.assertIn("multi_day_event_requires_explicit_editions", result["issues"])

    def test_historical_or_future_modified_event_rejected(self):
        for entry in [event(startDate="2025-11-15", endDate="2025-11-15"),
                      event(dateModified="2028-01-01")]:
            self.assertEqual(collect(html(entry))["observations"], [])

    def test_reschedule_preserves_previous_date_and_key(self):
        observation = collect(html(event(eventStatus="https://schema.org/EventRescheduled",
                                         previousStartDate="2026-11-08")))["observations"][0]
        self.assertEqual(observation["editions"][0]["previousDate"], "2026-11-08")
        self.assertEqual(observation["editions"][0]["status"], "published")
        result = collect(html(event(eventStatus="https://schema.org/EventRescheduled")))
        self.assertEqual(result["observations"], [])

    def test_cancellation_is_explicit_and_no_other_dates_deleted(self):
        observation = collect(html(event(eventStatus="https://schema.org/EventCancelled")))["observations"][0]
        self.assertEqual(observation["editions"][0]["status"], "cancelled")
        self.assertFalse(observation["completeCalendar"])

    def test_duplicate_graph_reference_deduplicated_and_conflict_rejected(self):
        self.assertEqual(len(collect(html({"@graph": [event(), event()]}))["observations"]), 1)
        result = collect(html([event(), event(startDate="2026-11-22", endDate="2026-11-22")]))
        self.assertEqual(result["observations"], [])
        self.assertIn("ambiguous_event_identity", result["issues"])

    def test_empty_or_invalid_html_and_script_cannot_produce_dates(self):
        for body in ["<p>Updated 2026-11-12</p>", '<script type="application/ld+json">{</script>',
                     '<script>2026-11-12 EventCancelled</script>']:
            self.assertEqual(collect(body)["observations"], [])

    def test_prosacile_only_explicit_dates_and_caveats_preserved(self):
        market = {**MARKET, "name": "Sacellum – la piazza delle antichità", "comune": "Sacile",
                  "url": "https://www.prosacile.it/antiquariato"}
        body = '''<p>Domande dal 23 novembre 2025 al 28 dicembre 2025.</p>
        <p>Il mercatino si svolge nelle seguenti date:</p>
        <p>- 25 gennaio 2026</p><p>- 22 novembre 2026 (*)</p>
        <p>- 27 dic embre 2026 (*) (**)</p>
        <p>* Si avverte che potrebbero esserci modifiche alla planimetria.</p>
        <p>** Si avverte che la data potrebbe cambiare per esigenze Comunali.</p>
        <p>Disponibile per la consultazione il regolamento comunale.</p><p>1 gennaio 2027</p>'''
        result = collect(body, market)
        observation = result["observations"][0]
        self.assertEqual([item["date"] for item in observation["editions"]], ["2026-01-25", "2026-11-22"])
        self.assertIn("provisional_calendar_date", result["issues"])
        self.assertIn("potrebbe cambiare", observation["evidence"][-1]["excerpt"])
        self.assertEqual(observation["evidence"][0]["value"], observation["editions"][0])
        self.assertEqual(observation["fields"], {})

    def test_prosacile_does_not_parse_unlabelled_list_or_wrong_market(self):
        self.assertEqual(collect("<p>25 gennaio 2026</p>")["observations"], [])
        market = {**MARKET, "url": "https://www.prosacile.it/antiquariato", "comune": "Sacile"}
        self.assertEqual(collect("<p>Il mercatino nelle seguenti date:</p><p>25 gennaio 2026</p>", market)["observations"], [])

    def test_sources_are_deduplicated_and_bounded(self):
        calls = []
        result = collect_market(MARKET, [{"source": URL}], [{"url": f"https://official.example/{i}"}
                                for i in range(10)], as_of=date(2026, 11, 1),
                                fetch=lambda url: calls.append(url) or "<p>No calendar</p>")
        self.assertEqual(len(calls), MAX_SOURCES)
        self.assertIn("source_limit_reached", result["issues"])

    def test_many_events_share_one_observation_and_all_considerations_survive(self):
        first = event(description="Sede temporanea per lavori", dateModified="2026-10-30")
        second = event(**{"@id": URL + "#second", "startDate": "2026-11-22", "endDate": "2026-11-22",
                          "description": "Orario festivo diverso", "dateModified": "2026-10-31"})
        result = collect(html([first, second]))
        self.assertEqual(len(result["observations"]), 1)
        observation = result["observations"][0]
        self.assertEqual(len(observation["editions"]), 2)
        self.assertEqual(observation["sourceUpdatedAt"], "2026-10-30")
        excerpts = [item["excerpt"] for item in observation["evidence"]]
        self.assertIn("Sede temporanea per lavori", excerpts)
        self.assertIn("Orario festivo diverso", excerpts)
        for edition in observation["editions"]:
            self.assertTrue(any(proof["field"] == "editions" and proof["value"] == edition
                                for proof in observation["evidence"]))

    def test_one_failed_source_does_not_discard_another_source(self):
        def fetch(url):
            if url == URL:
                raise TimeoutError()
            return html(event(url=url))
        result = collect_market(MARKET, [], [{"url": "https://official.example/other"}],
                                as_of=date(2026, 11, 1), fetch=fetch)
        self.assertEqual(len(result["observations"]), 1)
        self.assertIn("source_unavailable", result["issues"])

    def test_unsafe_urls_and_private_dns_rejected(self):
        for url in ["http://official.example/", "https://127.0.0.1/", "https://169.254.169.254/",
                    "https://localhost/", "https://foo.local/", "https://user:pass@official.example/",
                    "https://official.example:444/", "https://official.example/\r\nHeader: value"]:
            with self.subTest(url=url), self.assertRaises(SourceError):
                _url(url)
        with patch("app.markets.refresh_sources.socket.getaddrinfo", return_value=[
                (2, 1, 6, "", ("127.0.0.1", 443))]), self.assertRaises(SourceError):
            _public_addresses("official.example")

    def test_cross_host_redirect_rejected_even_with_injected_transport(self):
        result = collect({"url": "https://other.example/", "html": html(event())})
        self.assertEqual(result["observations"], [])
        self.assertIn("cross_host_redirect", result["issues"])

    def test_proloco_labelled_calendar_keeps_explicit_year_and_source_address(self):
        market = {**MARKET, "name": "Lo Scrigno del Doge", "comune": "Codroipo", "validThrough": "2026-12-31",
                  "url": "https://prolocoregionefvg.it/eventi-delle-associate/lo-scrigno/"}
        body = '''<ul><li><strong>Città</strong></li><li>Codroipo</li></ul>
        <ul><li><strong>Indirizzo</strong></li><li>Esedra<br>Villa Manin - Passariano</li></ul>
        <ul><li><strong>Quando</strong></li><li>08/12/2025</li><li>08/12/2026</li><li>06/01/2027</li></ul>
        <h2 class="event-title">Lo scrigno del Doge in Villa Manin - Mercatino</h2>
        <footer><ul><li>10/02/2027</li><li>Via dell'organizzatore 1</li></ul></footer>'''
        result = collect(body, market)
        self.assertEqual(result["issues"], [])
        observation = result["observations"][0]
        self.assertEqual([entry["date"] for entry in observation["editions"]], ["2026-12-08", "2027-01-06"])
        self.assertEqual(observation["fields"]["place"], "Esedra, Villa Manin - Passariano")
        self.assertEqual(observation["fields"]["validThrough"], "2027-01-06")
        self.assertNotIn("scheduleNote", observation["fields"])
        for edition in observation["editions"]:
            self.assertEqual(edition["venue"]["place"], observation["fields"]["place"])
            self.assertTrue(any(proof["field"] == "editions" and proof["value"] == edition
                                for proof in observation["evidence"]))

    def test_proloco_range_and_missing_year_are_not_expanded(self):
        market = {**MARKET, "url": "https://prolocoregionefvg.it/eventi-delle-associate/prova/"}
        body = '''<h2 class="event-title">Mercatino di prova</h2>
        <ul><li>Città</li><li>Udine</li></ul><ul><li>Quando</li>
        <li>01/11/2026 - 08/12/2026</li><li>06/01</li><li>15/11/2026</li></ul>'''
        result = collect(body, market)
        self.assertEqual([entry["date"] for entry in result["observations"][0]["editions"]], ["2026-11-15"])
        self.assertIn("calendar_entry_requires_explicit_date", result["issues"])
        self.assertTrue(any("01/11/2026 - 08/12/2026" in entry["excerpt"]
                            for entry in result["observations"][0]["evidence"]))

    def test_proloco_identity_mismatch_or_duplicate_metadata_fails_closed(self):
        market = {**MARKET, "url": "https://prolocoregionefvg.it/eventi-delle-associate/prova/"}
        base = '<h2 class="event-title">Mercatino di prova</h2><ul><li>Città</li><li>Udine</li></ul><ul><li>Quando</li><li>15/11/2026</li></ul>'
        for body in [base.replace("Udine", "Pordenone"), base.replace("Mercatino di prova", "Concerto"),
                     base + '<ul><li>Quando</li><li>16/11/2026</li></ul>']:
            self.assertEqual(collect(body, market)["observations"], [])


if __name__ == "__main__":
    unittest.main()
