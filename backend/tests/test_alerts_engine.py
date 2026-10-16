import json
import socket
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import requests

from app.weather import alerts_engine


INACTIVE_WIDGET = """/**/pcrfvgit_widget_setup({
  "alerts": [
    {
      "type": "METEO",
      "title": "NESSUNA ALLERTA",
      "description": "Nessuna criticita prevista in regione.",
      "zone": "FVG-A",
      "dt_start": "2026-08-09T08:00:00+02:00",
      "dt_end": "2026-08-10T08:00:00+02:00",
      "level": 0,
      "file_url": "https://example.test/no-alert.pdf"
    }
  ]
});"""

ACTIVE_WIDGET = INACTIVE_WIDGET.replace(
    '"title": "NESSUNA ALLERTA"',
    '"title": "ALLERTA REGIONALE"',
).replace(
    '"description": "Nessuna criticita prevista in regione."',
    '"description": "Allerta gialla idrogeologica per temporali."',
).replace('"level": 0', '"level": 1')


def mixed_green_yellow_widget():
    alerts = [
        {
            "type": "METEO",
            "title": "ALLERTA REGIONALE 29 DEL 2026",
            "description": (
                "DALLE 00:00 DEL 08 ALLE 06:00 DEL 09 ALLERTA GIALLA "
                "PER TEMPORALI FORTI E CRITICITA' IDROGEOLOGICA "
                "SU FVG-C E FVG-D; CRITICITA' IDROGEOLOGICA SU FVG-B."
            ),
            "zone": zone,
            "dt_start": "2026-10-07T22:00:00Z",
            "dt_end": "2026-10-09T04:00:00Z",
            "level": level,
            "file_url": "https://pianiemergenza.protezionecivile.fvg.it/alerts/29_2026.pdf",
        }
        for zone, level in zip(("FVG-A", "FVG-B", "FVG-C", "FVG-D"), (0, 1, 1, 1))
    ]
    return f"pcrfvgit_widget_setup({json.dumps({'alerts': alerts})});"

INACTIVE_HTML = """
<html><body>
  <div class="allerte view view-allerte">
    <div class="view-empty"><p>Nessuna allerta in corso</p></div>
  </div>
</body></html>
"""


class OfficialAlertsEngineTests(unittest.TestCase):
    def setUp(self):
        alerts_engine.reset_official_alerts_cache_for_tests()

    def tearDown(self):
        alerts_engine.reset_official_alerts_cache_for_tests()

    def test_friulian_push_copy_uses_standard_weather_spelling(self):
        body = alerts_engine.build_official_alert_push_body(
            "gialla",
            ["temporali", "neve"],
            "10:00 14/08-18:00 14/08",
            "zona FVG-A",
            "fur",
        )

        self.assertEqual(
            body,
            "Des 10:00 dai 14/08 aes 18:00 dai 14/08. "
            "Alerte zale par temporâi e par nêf. zone FVG-A.",
        )

    def test_html_alert_dates_use_the_fvg_timezone(self):
        self.assertEqual(
            alerts_engine.parse_civil_protection_datetime("da 08/10/2026 - 00:00"),
            "2026-10-08T00:00:00+02:00",
        )
        self.assertEqual(
            alerts_engine.parse_civil_protection_datetime("da 08/01/2027 - 00:00"),
            "2027-01-08T00:00:00+01:00",
        )

    @patch.object(alerts_engine, "fetch_civil_protection_widget_alerts_jsonp")
    def test_green_widget_is_confirmed_inactive(self, fetch_widget):
        fetch_widget.return_value = INACTIVE_WIDGET

        payload = alerts_engine.fetch_official_alerts()

        self.assertFalse(payload["active"])
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["source_mode"], "official_widget")
        self.assertEqual(payload["cache"]["status"], "fresh")

    @patch.object(alerts_engine, "fetch_civil_protection_widget_alerts_jsonp")
    def test_yellow_widget_keeps_actionable_alert(self, fetch_widget):
        fetch_widget.return_value = ACTIVE_WIDGET

        payload = alerts_engine.fetch_official_alerts()

        self.assertTrue(payload["active"])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["alerts"][0]["level"], "gialla")

    def test_mixed_green_yellow_widget_only_reports_yellow_zones(self):
        alerts = alerts_engine.parse_civil_protection_widget_alerts(
            mixed_green_yellow_widget()
        )

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["level"], "gialla")
        self.assertEqual(alerts[0]["zones"], ["FVG-B", "FVG-C", "FVG-D"])
        self.assertEqual(
            alerts[0]["area"], "zona FVG-B, zona FVG-C, zona FVG-D"
        )
        self.assertIn("gialla", alerts[0]["push_body"].lower())

    def test_mixed_positive_zone_levels_are_not_flattened(self):
        payload = mixed_green_yellow_widget()
        data = json.loads(payload[payload.index("(") + 1 : -2])
        data["alerts"][2]["level"] = 2

        with self.assertRaises(alerts_engine.OfficialAlertsParserError):
            alerts_engine.parse_civil_protection_widget_alerts(
                f"pcrfvgit_widget_setup({json.dumps(data)});"
            )

    def test_conflicting_or_incomplete_zone_metadata_fails_closed(self):
        payload = mixed_green_yellow_widget()
        original = json.loads(payload[payload.index("(") + 1 : -2])
        cases = {
            "duplicate zone": lambda alerts: alerts[1].update(zone="FVG-A"),
            "different window": lambda alerts: alerts[1].update(
                dt_end="2026-10-09T05:00:00Z"
            ),
        }

        for name, mutate in cases.items():
            with self.subTest(name=name):
                data = json.loads(json.dumps(original))
                mutate(data["alerts"])
                with self.assertRaises(alerts_engine.OfficialAlertsParserError):
                    alerts_engine.parse_civil_protection_widget_alerts(
                        f"pcrfvgit_widget_setup({json.dumps(data)});"
                    )

    def test_malformed_empty_and_unrecognized_widget_payloads_are_rejected(self):
        payloads = (
            "not-jsonp",
            "callback({});",
            'callback({"alerts": []});',
            'callback({"alerts": [{"title": "Stato", "level": "unknown"}]});',
            'callback({"alerts": [{"title": "Stato", "level": false}]});',
            'callback({"alerts": [{"title": "Stato", "level": 0.5}]});',
        )

        for payload in payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(alerts_engine.OfficialAlertsParserError):
                    alerts_engine.parse_civil_protection_widget_alerts(payload)

    @patch.object(alerts_engine, "fetch_civil_protection_alerts_html")
    @patch.object(alerts_engine, "fetch_civil_protection_widget_alerts_jsonp")
    def test_malformed_widget_falls_back_to_confirmed_html_state(
        self,
        fetch_widget,
        fetch_html,
    ):
        fetch_widget.return_value = "not-jsonp"
        fetch_html.return_value = INACTIVE_HTML

        payload = alerts_engine.fetch_official_alerts(force=True)

        self.assertFalse(payload["active"])
        self.assertEqual(payload["source_mode"], "official_page")
        self.assertEqual(payload["cache"]["status"], "fresh")
        fetch_html.assert_called_once_with()

    @patch.object(alerts_engine, "fetch_civil_protection_alerts_html")
    @patch.object(alerts_engine, "fetch_civil_protection_widget_alerts_jsonp")
    def test_widget_timeout_falls_back_to_confirmed_html_state(
        self,
        fetch_widget,
        fetch_html,
    ):
        fetch_widget.side_effect = requests.ReadTimeout("private timeout detail")
        fetch_html.return_value = INACTIVE_HTML

        payload = alerts_engine.fetch_official_alerts(force=True)

        self.assertEqual(payload["source_mode"], "official_page")
        self.assertNotIn("upstream_failure", payload["cache"])

    @patch.object(alerts_engine, "fetch_civil_protection_alerts_html")
    @patch.object(alerts_engine, "fetch_civil_protection_widget_alerts_jsonp")
    def test_http_and_dns_failures_are_reported_without_raw_details(
        self,
        fetch_widget,
        fetch_html,
    ):
        response = requests.Response()
        response.status_code = 503
        fetch_widget.side_effect = requests.HTTPError(
            "private response body https://secret.test/?token=secret",
            response=response,
        )
        dns_error = requests.ConnectionError("private DNS host detail")
        dns_error.__cause__ = socket.gaierror(-2, "private resolver detail")
        fetch_html.side_effect = dns_error

        payload = alerts_engine.fetch_official_alerts(force=True)

        self.assertEqual(payload["cache"]["status"], "unavailable")
        self.assertEqual(
            payload["cache"]["upstream_failure"],
            {
                "attempts": [
                    {"source": "widget", "category": "http", "status_code": 503},
                    {"source": "html", "category": "dns"},
                ]
            },
        )
        serialized = json.dumps(payload)
        self.assertNotIn("secret.test", serialized)
        self.assertNotIn("private", serialized)
        self.assertNotIn("token", serialized)

    @patch.object(alerts_engine, "fetch_civil_protection_alerts_html")
    @patch.object(alerts_engine, "fetch_civil_protection_widget_alerts_jsonp")
    def test_unclassified_responses_fail_closed_as_parser_errors(
        self,
        fetch_widget,
        fetch_html,
    ):
        fetch_widget.return_value = "not-jsonp"
        fetch_html.return_value = "<html><body>Manutenzione</body></html>"

        payload = alerts_engine.fetch_official_alerts(force=True)

        self.assertEqual(payload["cache"]["status"], "unavailable")
        self.assertEqual(
            payload["cache"]["upstream_failure"],
            {
                "attempts": [
                    {"source": "widget", "category": "parser"},
                    {"source": "html", "category": "parser"},
                ]
            },
        )

    @patch.object(alerts_engine, "fetch_civil_protection_alerts_html")
    @patch.object(alerts_engine, "fetch_civil_protection_widget_alerts_jsonp")
    def test_incidental_no_alert_copy_does_not_confirm_inactive_html(
        self,
        fetch_widget,
        fetch_html,
    ):
        fetch_widget.return_value = "not-jsonp"
        fetch_html.return_value = """
            <div class="view view-allerte">
              <div class="new-active-alert-markup">
                <article>Avviso meteo con markup non riconosciuto</article>
              </div>
              <template><div class="view-empty">Nessuna allerta in corso</div></template>
            </div>
        """

        payload = alerts_engine.fetch_official_alerts(force=True)

        self.assertEqual(payload["cache"]["status"], "unavailable")
        self.assertEqual(
            payload["cache"]["upstream_failure"]["attempts"][-1],
            {"source": "html", "category": "parser"},
        )

    @patch.object(alerts_engine, "fetch_civil_protection_alerts_html")
    @patch.object(alerts_engine, "fetch_civil_protection_widget_alerts_jsonp")
    def test_timeout_and_parser_failures_remain_distinguishable(
        self,
        fetch_widget,
        fetch_html,
    ):
        fetch_widget.side_effect = requests.ConnectTimeout("private timeout detail")
        fetch_html.return_value = "<html><body>Manutenzione</body></html>"

        payload = alerts_engine.fetch_official_alerts(force=True)

        self.assertEqual(
            payload["cache"]["upstream_failure"],
            {
                "attempts": [
                    {"source": "widget", "category": "timeout"},
                    {"source": "html", "category": "parser"},
                ]
            },
        )

    @patch.object(alerts_engine.time, "sleep")
    @patch.object(alerts_engine.requests, "get")
    def test_html_fetch_retries_with_the_configured_timeout(self, get, sleep):
        response = MagicMock()
        response.text = INACTIVE_HTML
        get.side_effect = [requests.ReadTimeout("private detail"), response]

        html = alerts_engine.fetch_civil_protection_alerts_html()

        self.assertEqual(html, INACTIVE_HTML)
        self.assertEqual(get.call_count, 2)
        self.assertTrue(
            all(
                call.kwargs["timeout"] == alerts_engine.PROTEZIONE_CIVILE_ALERTS_TIMEOUT
                for call in get.call_args_list
            )
        )
        sleep.assert_called_once_with(0.5)

    @patch.object(alerts_engine, "_fetch_confirmed_alerts")
    def test_refresh_failure_preserves_active_cache(self, fetch_confirmed):
        active_payload = alerts_engine._build_alerts_payload(
            alerts_engine.parse_civil_protection_widget_alerts(ACTIVE_WIDGET),
            "official_widget",
        )
        valid_to = (
            datetime.now(alerts_engine.get_fvg_timezone()) + timedelta(hours=2)
        ).isoformat()
        active_payload["alerts"][0]["valid_to"] = valid_to
        active_payload["expires_at"] = valid_to
        fetch_confirmed.return_value = active_payload
        self.assertTrue(alerts_engine.fetch_official_alerts()["active"])

        fetch_confirmed.side_effect = requests.RequestException("offline")
        payload = alerts_engine.fetch_official_alerts(force=True)

        self.assertTrue(payload["active"])
        self.assertEqual(payload["cache"]["status"], "stale")
        self.assertEqual(
            payload["cache"]["upstream_failure"],
            {"attempts": [{"source": "unknown", "category": "connection"}]},
        )

    @patch.object(alerts_engine, "_fetch_confirmed_alerts")
    def test_refresh_failure_never_turns_stale_inactive_into_confirmation(
        self,
        fetch_confirmed,
    ):
        fetch_confirmed.return_value = alerts_engine._build_alerts_payload(
            alerts_engine.parse_civil_protection_widget_alerts(INACTIVE_WIDGET),
            "official_widget",
        )
        self.assertFalse(alerts_engine.fetch_official_alerts()["active"])

        fetch_confirmed.side_effect = requests.RequestException("offline")
        payload = alerts_engine.fetch_official_alerts(force=True)

        self.assertFalse(payload["active"])
        self.assertEqual(payload["cache"]["status"], "unavailable")
        self.assertEqual(payload["error"], "official_alerts_unavailable")


if __name__ == "__main__":
    unittest.main()
