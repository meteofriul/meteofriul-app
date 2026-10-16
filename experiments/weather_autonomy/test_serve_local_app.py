"""Offline/local-only bridge tests; no provider requests or real credentials."""
from contextlib import contextmanager
import json
import threading
import unittest
from unittest.mock import Mock

import requests

from serve_local_app import OfficialReader, PREFIX, UPSTREAM, make_server, merge_official, query_location


class Adapter:
    def current(self, city, lat, lon):
        if city == "Expired":
            raise RuntimeError("snapshot expired")
        return {"city": city, "temperature": 20, "rain": None, "primary_source": "icon2i_local_pilot",
                "data_quality": {"run_utc": "2026-09-03T00:00:00Z"}}

    def forecast(self, city, lat, lon):
        return {"city": city, "forecast": [{"date": "2026-09-03", "max_temp": 25}], "data_quality": {}}


@contextmanager
def bridge():
    getter = Mock(return_value=None)
    server = make_server(Adapter(), 0, OfficialReader(getter))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", getter
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class BridgeTests(unittest.TestCase):
    def test_query_rejects_duplicates_unknowns_nonfinite_out_of_range(self):
        for query in ("", "city=A&city=B", "city=A&url=https://example.com", "city=A&lat=nan",
                      "city=A&lat=91", "city=A&lon=inf", "city=A&lon=abc"):
            with self.subTest(query=query), self.assertRaises(ValueError):
                query_location(query)
        self.assertEqual(("Pordenone", 45.95, 12.66), query_location("city=Pordenone&lat=45.95&lon=12.66&_=123"))

    def test_alert_merge_does_not_replace_numbers_or_native_forecast(self):
        current = Adapter().current("Udine", None, None)
        forecast = Adapter().forecast("Udine", None, None)
        result = merge_official(current, forecast, None)
        self.assertEqual(20, result["current"]["temperature"])
        self.assertIsNone(result["current"]["rain"])
        self.assertEqual(25, result["forecast"]["forecast"][0]["max_temp"])
        self.assertNotIn("daily", result["forecast"])
        self.assertIsNone(result["current"]["official"])
        self.assertEqual("separate_app_route", result["current"]["data_quality"]["official_bulletin_status"])
        self.assertNotIn("official", current)
        self.assertEqual("unavailable", result["official_alerts"]["cache"]["status"])
        self.assertEqual("official_alerts_unavailable", result["official_alerts"]["error"])

    def test_official_alert_response_preserved_and_input_immutable(self):
        alerts = {"active": True, "count": 1, "alerts": [{"id": "official"}], "source_mode": "official_page"}
        result = merge_official(Adapter().current("Udine", None, None), {}, alerts)
        self.assertEqual(alerts, result["official_alerts"])
        result["official_alerts"]["alerts"].clear()
        self.assertEqual(1, len(alerts["alerts"]))

    def test_reader_uses_only_local_whitelist_and_caches(self):
        getter = Mock(return_value={"active": False, "alerts": []})
        reader = OfficialReader(getter)
        reader.read("official-alerts", "Comune & testo")
        reader.read("official-alerts", "Altro Comune")
        self.assertEqual(1, getter.call_count)
        self.assertEqual(UPSTREAM + "/weather/official-alerts", getter.call_args.args[0])
        with self.assertRaises(ValueError):
            reader.read("../tokens", "Udine")
        self.assertEqual(1, getter.call_count)

    def test_reader_network_failure_is_unavailable_and_retries_bounded(self):
        getter = Mock(side_effect=requests.ConnectionError("synthetic error"))
        reader = OfficialReader(getter)
        self.assertIsNone(reader.read("official-alerts", "Udine"))
        self.assertIsNone(reader.read("official-alerts", "Trieste"))
        self.assertEqual(1, getter.call_count)

    def test_current_local_only_no_upstream_and_no_store(self):
        with bridge() as (base, getter):
            response = requests.get(base + PREFIX + "/weather/current?city=Udine", timeout=3)
            self.assertEqual(200, response.status_code)
            self.assertEqual(20, response.json()["temperature"])
            self.assertIn("no-store", response.headers["Cache-Control"])
            self.assertNotIn("Access-Control-Allow-Origin", response.headers)
            getter.assert_not_called()

    def test_bootstrap_uses_only_official_alert_route_and_preserves_unknown_state(self):
        with bridge() as (base, getter):
            response = requests.get(base + PREFIX + "/weather/bootstrap?city=Udine", timeout=3)
            self.assertEqual(200, response.status_code)
            self.assertEqual("icon2i_local_pilot", response.json()["current"]["primary_source"])
            self.assertEqual("unavailable", response.json()["official_alerts"]["cache"]["status"])
            self.assertEqual([UPSTREAM + "/weather/official-alerts"],
                             [call.args[0] for call in getter.call_args_list])

    def test_expired_snapshot_has_no_fallback(self):
        with bridge() as (base, getter):
            response = requests.get(base + PREFIX + "/weather/bootstrap?city=Expired", timeout=3)
            self.assertEqual(503, response.status_code)
            getter.assert_not_called()

    def test_wrong_host_origin_paths_and_mutations_rejected(self):
        with bridge() as (base, getter):
            route = base + PREFIX + "/weather/current?city=Udine"
            for headers in ({"Host": "attacker.test"}, {"Origin": "https://attacker.test"}):
                self.assertEqual(403, requests.get(route, headers=headers, timeout=3).status_code)
            for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
                self.assertEqual(405, requests.request(method, route, timeout=3).status_code)
            for path in ("/api/weather/forecast", "/source.grib", "/../.cdsapirc", PREFIX + "/anything"):
                self.assertEqual(404, requests.get(base + path, timeout=3).status_code)
            getter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
