from __future__ import annotations

import hashlib
import json
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import requests

from app.services.official_alert_sources import (
    ARPA_PCR_SOURCE_MODE,
    OFFICIAL_PAGE_ARPA_CORROBORATED_SOURCE_MODE,
    OFFICIAL_VALIDITY_EXPIRED_SOURCE_MODE,
    TELEGRAM_ARPA_CORROBORATED_SOURCE_MODE,
    TELEGRAM_VERIFIED_SOURCE_MODE,
    WIDGET_ARPA_CORROBORATED_SOURCE_MODE,
    fetch_official_alert_observations,
    reconcile_official_alert_observations,
)
from app.services.official_alerts import OfficialAlertsStateService
from app.weather import alerts_engine
from app.weather.arpa_osmer_risks import ArpaOsmerRisksUnavailable
from app.weather.official_telegram_alerts import OfficialTelegramParserError


NOW = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
STRUCTURED_NOW = datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc)

ACTIVE_OFFICIAL_PAGE_29 = """
<div class="view view-allerte"><div class="view-content">
  <h2>ALLERTA REGIONALE 29 DEL 2026</h2>
  <p>da 08/10/2026 - 00:00</p>
  <p>a 09/10/2026 - 06:00</p>
  <p>DALLE 00:00 DEL 08 ALLE 06:00 DEL 09 ALLERTA GIALLA PER TEMPORALI FORTI E CRITICITA' IDROGEOLOGICA SU FVG-C E FVG-D; CRITICITA' IDROGEOLOGICA SU FVG-B.</p>
  <a href="https://www.protezionecivile.fvg.it/sites/default/files/allerta/allerta_regionale_29_del_2026.pdf">PDF</a>
</div></div>
"""


class _StaticArpaSource:
    def __init__(self, observation):
        self.observation = observation

    def fetch_pcr(self):
        return deepcopy(self.observation)


def telegram_alert(
    *,
    published_at=None,
    valid_to=None,
    revision="a" * 64,
    pdf_sha256="b" * 64,
    post_id=900,
):
    return {
        "id": "allerta-regionale-23-2026",
        "alert_number": 23,
        "alert_year": 2026,
        "level": "gialla",
        "risks": ["temporali"],
        "zones": ["FVG-A", "FVG-C"],
        "area": "zona FVG-A, zona FVG-C",
        "valid_from": (NOW + timedelta(hours=1)).isoformat(),
        "valid_to": (valid_to or NOW + timedelta(hours=8)).isoformat(),
        "official_text": "Allerta gialla per temporali sulle zone FVG-A e FVG-C.",
        "pdf_url": (
            "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
            "Allerta_regionale_23-2026.pdf"
        ),
        "pdf_sha256": pdf_sha256,
        "pdf_size_bytes": 4096,
        "pdf_verified_at": NOW.isoformat(),
        "telegram_post_id": post_id,
        "telegram_post_url": f"https://t.me/ProtCivileFVG/{post_id}",
        "published_at": (published_at or NOW - timedelta(hours=2)).isoformat(),
        "revision_hash": revision,
    }


def observations(
    at: datetime,
    *,
    telegram=True,
    pcr_status="inactive",
    cache_max_age=3600,
    pcr_http_date=None,
    pcr_age=0,
    failures=None,
):
    return {
        "fetched_at": at.isoformat(),
        "telegram": (
            {
                "source_mode": "official_telegram_positive_only",
                "alerts": [telegram_alert()],
                "can_confirm_inactive": False,
            }
            if telegram
            else None
        ),
        "arpa_pcr": (
            {
                "status": "available",
                "source_mode": "raw_official_page",
                "source_timing": {
                    "cache_max_age_seconds": cache_max_age,
                    "http_date": (pcr_http_date or at).isoformat(),
                    "age_seconds": pcr_age,
                },
                "pcr": {
                    "status": pcr_status,
                    "revision": f"pcr-{pcr_status}",
                    "can_confirm_inactive": pcr_status == "inactive",
                    "alerts": (
                        [{"document_urls": [telegram_alert()["pdf_url"]]}]
                        if pcr_status == "active"
                        else []
                    ),
                },
            }
            if pcr_status
            else None
        ),
        "failures": list(failures or []),
    }


def set_pcr_documents(value, *urls):
    value["arpa_pcr"]["pcr"]["alerts"] = [{"document_urls": list(urls)}]
    return value


def structured_widget_alert(
    *,
    number=24,
    level="arancione",
    zones=None,
    valid_from="2026-08-20T18:00:00+02:00",
    valid_to="2026-08-21T23:59:00+02:00",
    official_text="Allerta arancione per temporali su tutta la regione.",
):
    return {
        "id": f"allerta-regionale-{number}-del-2026",
        "title": f"ALLERTA REGIONALE {number} DEL 2026",
        "level": level,
        "risks": ["temporali"],
        "zones": list(zones or ["FVG-A", "FVG-B", "FVG-C", "FVG-D"]),
        "area": "Tutta la regione",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "official_text": official_text,
        "pdf_url": (
            "https://pianiemergenza.protezionecivile.fvg.it/"
            f"alerts/{number}_2026.pdf"
        ),
        "push_title": "Meteo Friûl",
        "push_body_i18n": {
            "it": "Allerta arancione per temporali in tutta la regione.",
            "fur": "Alerte narançade par temporâi in dute la regjon.",
        },
    }


def structured_pcr_panel(
    *,
    number=24,
    levels=None,
    start_time="18:00",
    start_weekday="giovedì",
    end_time="23:59",
    end_weekday="venerdì",
    revision="d" * 64,
):
    values = list(levels or [2, 2, 2, 2])
    return {
        "headline": (
            f"PCR - Allerta dalle ore {start_time} di {start_weekday} "
            f"alle ore {end_time} di {end_weekday}"
        ),
        "start_time": start_time,
        "start_weekday": start_weekday,
        "end_time": end_time,
        "end_weekday": end_weekday,
        "zone_levels": [
            {"zone": zone, "level": value}
            for zone, value in zip(
                ("FVG-A", "FVG-B", "FVG-C", "FVG-D"), values
            )
        ],
        "document_urls": [
            "https://pianiemergenza.protezionecivile.fvg.it/"
            f"alerts/{number}_2026.pdf"
        ],
        "revision": revision,
    }


def structured_telegram_alert(
    *,
    number=24,
    level="arancione",
    valid_from="2026-08-20T18:00:00+02:00",
    valid_to="2026-08-21T23:59:00+02:00",
):
    return {
        "id": f"allerta-regionale-{number}-2026",
        "alert_number": number,
        "alert_year": 2026,
        "level": level,
        "risks": ["temporali"],
        "zones": ["FVG-A", "FVG-B", "FVG-C", "FVG-D"],
        "area": "Tutta la regione",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "official_text": "Allerta ufficiale per temporali su tutta la regione.",
        "pdf_url": (
            "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
            f"Allerta_regionale_{number}-2026.pdf"
        ),
        "published_at": "2026-08-20T09:36:00+00:00",
        "telegram_post_id": 900 + number,
        "telegram_post_url": f"https://t.me/ProtCivileFVG/{900 + number}",
        "revision_hash": "a" * 64,
    }


def structured_observations(*, alerts=None, panels=None, pcr_status="active"):
    selected_alerts = (
        [structured_widget_alert()] if alerts is None else deepcopy(alerts)
    )
    selected_panels = (
        [structured_pcr_panel()] if panels is None else deepcopy(panels)
    )
    return {
        "fetched_at": STRUCTURED_NOW.isoformat(),
        "widget": {
            "source_mode": "official_widget",
            "alerts": selected_alerts,
            "can_confirm_inactive": not any(
                str(alert.get("level") or "").lower() != "verde"
                for alert in selected_alerts
            ),
        },
        "telegram": None,
        "arpa_pcr": {
            "status": "available",
            "source_mode": "raw_official_page",
            "source_timing": {
                "cache_max_age_seconds": 900,
                "http_date": STRUCTURED_NOW.isoformat(),
                "age_seconds": 0,
            },
            "pcr": {
                "status": pcr_status,
                "revision": "c" * 64,
                "can_confirm_inactive": pcr_status == "inactive",
                "alerts": selected_panels if pcr_status == "active" else [],
            },
        },
        "failures": [],
    }


def as_legacy_structured_snapshot(payload):
    """Rewrite a generated fixture exactly as the deployed pre-v2 record."""

    snapshot = deepcopy(payload)
    alert = snapshot["alerts"][0]
    identity = (int(alert["alert_year"]), int(alert["alert_number"]))
    pcr_revision = alert["corroboration"]["pcr_revision"]
    alert["corroboration"].pop("revision_hash_schema", None)
    alert["revision_hash"] = hashlib.sha256(
        json.dumps(
            {
                "identity": list(identity),
                "level": alert.get("level"),
                "zones": sorted(alert.get("zones") or []),
                "valid_from": alert.get("valid_from"),
                "valid_to": alert.get("valid_to"),
                "pdf_url": alert.get("pdf_url"),
                "official_text": alert.get("official_text"),
                "pcr_revision": pcr_revision,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return snapshot


class OfficialAlertReconciliationTests(unittest.TestCase):
    def test_official_page_fallback_corrobates_only_the_yellow_zones(self):
        observed_at = datetime(2026, 10, 7, 20, 0, tzinfo=timezone.utc)
        pcr = structured_observations(
            alerts=[],
            panels=[
                structured_pcr_panel(
                    number=29,
                    levels=[0, 1, 1, 1],
                    start_time="00:00",
                    start_weekday="giovedì",
                    end_time="06:00",
                    end_weekday="venerdì",
                )
            ],
        )["arpa_pcr"]
        pcr["source_timing"]["http_date"] = observed_at.isoformat()

        def timed_out_widget():
            raise requests.ReadTimeout("private widget details")

        observed = fetch_official_alert_observations(
            widget_fetcher=timed_out_widget,
            html_fetcher=lambda: ACTIVE_OFFICIAL_PAGE_29,
            telegram_fetcher=lambda: {"alerts": [], "can_confirm_inactive": False},
            arpa_source=_StaticArpaSource(pcr),
            now=lambda: observed_at,
        )
        result = reconcile_official_alert_observations(
            None, observed, now=observed_at
        )

        self.assertTrue(result["active"])
        self.assertEqual(
            result["source_mode"], OFFICIAL_PAGE_ARPA_CORROBORATED_SOURCE_MODE
        )
        alert = result["alerts"][0]
        self.assertEqual(alert["level"], "gialla")
        self.assertEqual(alert["zones"], ["FVG-B", "FVG-C", "FVG-D"])
        self.assertEqual(alert["corroboration"]["method"], "official_fvg_page_arpa")
        self.assertIn("pianiemergenza.", alert["pdf_url"])
        self.assertIn("www.protezionecivile.", alert["metadata_document_url"])
        self.assertNotIn("private", repr(result))

        mismatched = deepcopy(observed)
        mismatched["arpa_pcr"]["pcr"]["alerts"][0]["zone_levels"][1]["level"] = 2
        blocked = reconcile_official_alert_observations(
            None, mismatched, now=observed_at
        )
        self.assertEqual(blocked.get("error"), "official_alerts_unavailable")

        later = observed_at + timedelta(minutes=10)
        follow_up = deepcopy(observed)
        follow_up["fetched_at"] = later.isoformat()
        follow_up["html"] = None
        follow_up["arpa_pcr"]["source_timing"]["http_date"] = later.isoformat()
        retained = reconcile_official_alert_observations(
            result, follow_up, now=later
        )
        self.assertTrue(retained["active"])
        self.assertEqual(
            retained["source_mode"], OFFICIAL_PAGE_ARPA_CORROBORATED_SOURCE_MODE
        )

    def test_official_page_fallback_rejects_wrong_pdf_identity(self):
        observed_at = datetime(2026, 10, 7, 20, 0, tzinfo=timezone.utc)

        def timed_out_widget():
            raise requests.ReadTimeout("private widget details")

        observed = fetch_official_alert_observations(
            widget_fetcher=timed_out_widget,
            html_fetcher=lambda: ACTIVE_OFFICIAL_PAGE_29.replace(
                "allerta_regionale_29_del_2026.pdf",
                "allerta_regionale_30_del_2026.pdf",
            ),
            telegram_fetcher=lambda: {"alerts": [], "can_confirm_inactive": False},
            arpa_source=_StaticArpaSource(
                structured_observations(alerts=[])["arpa_pcr"]
            ),
            now=lambda: observed_at,
        )

        self.assertIsNone(observed["html"])
        self.assertIn(
            {"source": "html", "category": "parser"}, observed["failures"]
        )
        result = reconcile_official_alert_observations(
            None, observed, now=observed_at
        )
        self.assertEqual(result.get("error"), "official_alerts_unavailable")

    def test_expired_html_alert_does_not_override_fresh_inactive_arpa(self):
        observed_at = datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc)
        pcr = structured_observations(alerts=[], pcr_status="inactive")["arpa_pcr"]
        pcr["source_timing"]["http_date"] = observed_at.isoformat()

        def timed_out_widget():
            raise requests.ReadTimeout("private widget details")

        observed = fetch_official_alert_observations(
            widget_fetcher=timed_out_widget,
            html_fetcher=lambda: ACTIVE_OFFICIAL_PAGE_29,
            telegram_fetcher=lambda: {"alerts": [], "can_confirm_inactive": False},
            arpa_source=_StaticArpaSource(pcr),
            now=lambda: observed_at,
        )
        result = reconcile_official_alert_observations(
            None, observed, now=observed_at
        )

        self.assertFalse(result["active"])
        self.assertEqual(result["source_mode"], ARPA_PCR_SOURCE_MODE)
        self.assertNotIn("error", result)

    def test_structured_widget_and_arpa_activate_without_downloading_the_pdf(self):
        result = reconcile_official_alert_observations(
            None,
            structured_observations(),
            now=STRUCTURED_NOW,
        )

        self.assertTrue(result["active"])
        self.assertEqual(
            result["source_mode"], WIDGET_ARPA_CORROBORATED_SOURCE_MODE
        )
        self.assertEqual(result["count"], 1)
        alert = result["alerts"][0]
        self.assertEqual(alert["alert_number"], 24)
        self.assertEqual(alert["corroboration"]["identity"], "2026:24")
        self.assertNotIn("pdf_sha256", alert)

    def test_telegram_metadata_and_arpa_are_used_when_widget_times_out(self):
        observed = structured_observations()
        observed["widget"] = None
        observed["telegram"] = {
            "source_mode": "official_telegram_positive_only",
            "alerts": [structured_telegram_alert()],
            "can_confirm_inactive": False,
        }
        observed["failures"] = [{"source": "widget", "category": "timeout"}]

        result = reconcile_official_alert_observations(
            None,
            observed,
            now=STRUCTURED_NOW,
        )

        self.assertTrue(result["active"])
        self.assertEqual(
            result["source_mode"], TELEGRAM_ARPA_CORROBORATED_SOURCE_MODE
        )
        alert = result["alerts"][0]
        self.assertTrue(alert["pdf_url"].endswith("/alerts/24_2026.pdf"))
        self.assertIn("cfd.protezionecivile.fvg.it", alert["metadata_document_url"])
        self.assertEqual(alert["corroboration"]["method"], "official_telegram_arpa")
        self.assertNotIn("pdf_sha256", alert)

    def test_end_of_day_2359_and_midnight_are_semantically_equivalent(self):
        observed = structured_observations(
            alerts=[],
            panels=[
                structured_pcr_panel(
                    number=23,
                    levels=[1, 1, 1, 1],
                    start_time="12:00",
                )
            ],
        )
        observed["widget"] = None
        observed["telegram"] = {
            "source_mode": "official_telegram_positive_only",
            "alerts": [
                structured_telegram_alert(
                    number=23,
                    level="gialla",
                    valid_from="2026-08-20T12:00:00+02:00",
                    valid_to="2026-08-22T00:00:00+02:00",
                )
            ],
            "can_confirm_inactive": False,
        }

        result = reconcile_official_alert_observations(
            None,
            observed,
            now=STRUCTURED_NOW,
        )

        self.assertTrue(result["active"])
        self.assertEqual(result["alerts"][0]["alert_number"], 23)

    def test_structured_corroboration_ignores_text_and_zone_order_differences(self):
        alert = structured_widget_alert(
            zones=["FVG-D", "FVG-B", "FVG-A", "FVG-C"],
            official_text="Testo editoriale ufficiale formulato in modo diverso.",
        )

        result = reconcile_official_alert_observations(
            None,
            structured_observations(alerts=[alert]),
            now=STRUCTURED_NOW,
        )

        self.assertTrue(result["active"])
        self.assertEqual(
            result["source_mode"], WIDGET_ARPA_CORROBORATED_SOURCE_MODE
        )

    def test_structured_critical_disagreements_block_activation(self):
        cases = {
            "identity": lambda value: value["widget"]["alerts"][0].update(
                title="ALLERTA REGIONALE 25 DEL 2026"
            ),
            "severity": lambda value: value["arpa_pcr"]["pcr"]["alerts"][0].update(
                zone_levels=[
                    {"zone": zone, "level": 1}
                    for zone in ("FVG-A", "FVG-B", "FVG-C", "FVG-D")
                ]
            ),
            "zones": lambda value: value["widget"]["alerts"][0].update(
                zones=["FVG-A", "FVG-B", "FVG-C"]
            ),
            "validity": lambda value: value["arpa_pcr"]["pcr"]["alerts"][0].update(
                start_time="19:00"
            ),
        }

        for name, mutate in cases.items():
            with self.subTest(name=name):
                observed = structured_observations()
                mutate(observed)

                result = reconcile_official_alert_observations(
                    None,
                    observed,
                    now=STRUCTURED_NOW,
                )

                self.assertEqual(result.get("error"), "official_alerts_unavailable")
                self.assertEqual(result["cache"]["status"], "unavailable")

    def test_mixed_level_27_is_not_flattened_into_false_structured_agreement(self):
        alert = structured_telegram_alert(number=27)
        alert.update(
            level="arancione",
            levels=["arancione", "gialla"],
            mixed_levels=True,
            zones=["FVG-A", "FVG-C", "FVG-D"],
            area="zone FVG-A, FVG-C e FVG-D",
        )
        observed = structured_observations(
            alerts=[],
            panels=[
                structured_pcr_panel(
                    number=27,
                    levels=[1, 0, 2, 2],
                )
            ],
        )
        observed["widget"] = None
        observed["telegram"] = {
            "source_mode": "official_telegram_positive_only",
            "alerts": [alert],
            "can_confirm_inactive": False,
        }

        result = reconcile_official_alert_observations(
            None,
            observed,
            now=STRUCTURED_NOW,
        )

        self.assertEqual(result.get("error"), "official_alerts_unavailable")
        self.assertEqual(
            result.get("cache", {}).get("reason"),
            "official_structured_sources_disagree",
        )

    def test_green_and_yellow_widget_zones_match_structured_pcr(self):
        observed_at = datetime(2026, 10, 7, 20, 0, tzinfo=timezone.utc)
        widget_items = [
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
        widget_alerts = alerts_engine.parse_civil_protection_widget_alerts(
            f"pcrfvgit_widget_setup({json.dumps({'alerts': widget_items})});"
        )
        observed = structured_observations(
            alerts=widget_alerts,
            panels=[
                structured_pcr_panel(
                    number=29,
                    levels=[0, 1, 1, 1],
                    start_time="00:00",
                    start_weekday="giovedì",
                    end_time="06:00",
                    end_weekday="venerdì",
                )
            ],
        )
        observed["fetched_at"] = observed_at.isoformat()
        observed["arpa_pcr"]["source_timing"]["http_date"] = observed_at.isoformat()

        result = reconcile_official_alert_observations(
            None, observed, now=observed_at
        )

        self.assertTrue(result["active"])
        self.assertEqual(result["source_mode"], WIDGET_ARPA_CORROBORATED_SOURCE_MODE)
        self.assertEqual(result["alerts"][0]["level"], "gialla")
        self.assertEqual(result["alerts"][0]["zones"], ["FVG-B", "FVG-C", "FVG-D"])
        self.assertNotIn("FVG-A", result["alerts"][0]["area"])

    def test_only_an_older_lower_arpa_panel_can_coexist(self):
        older_yellow = structured_pcr_panel(
            number=23,
            levels=[1, 1, 1, 1],
            start_time="12:00",
            revision="e" * 64,
        )
        current_orange = structured_pcr_panel()

        accepted = reconcile_official_alert_observations(
            None,
            structured_observations(panels=[older_yellow, current_orange]),
            now=STRUCTURED_NOW,
        )
        blocked = reconcile_official_alert_observations(
            None,
            structured_observations(
                panels=[
                    current_orange,
                    structured_pcr_panel(number=25, revision="f" * 64),
                ]
            ),
            now=STRUCTURED_NOW,
        )
        newer_lower = reconcile_official_alert_observations(
            None,
            structured_observations(
                panels=[
                    current_orange,
                    structured_pcr_panel(
                        number=25,
                        levels=[1, 1, 1, 1],
                        revision="1" * 64,
                    ),
                ]
            ),
            now=STRUCTURED_NOW,
        )

        self.assertTrue(accepted["active"])
        self.assertEqual(blocked.get("error"), "official_alerts_unavailable")
        self.assertEqual(newer_lower.get("error"), "official_alerts_unavailable")

    def test_both_structured_sources_must_explicitly_confirm_inactive(self):
        inactive = structured_observations(alerts=[], panels=[], pcr_status="inactive")

        result = reconcile_official_alert_observations(
            None,
            inactive,
            now=STRUCTURED_NOW,
        )

        self.assertFalse(result["active"])
        self.assertEqual(result["source_mode"], ARPA_PCR_SOURCE_MODE)

    def test_telegram_alert_activates_immediately_despite_first_inactive_mirror(self):
        result = reconcile_official_alert_observations(
            None, observations(NOW), now=NOW
        )

        self.assertTrue(result["active"])
        self.assertEqual(result["source_mode"], TELEGRAM_VERIFIED_SOURCE_MODE)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["alerts"][0]["push_title"], "Meteo Friûl")
        self.assertTrue(result["alerts"][0]["push_body_i18n"]["it"])
        self.assertTrue(result["alerts"][0]["push_body_i18n"]["fur"])
        self.assertEqual(
            result["cache"]["verification"]["arpa_pcr"]["status"], "inactive"
        )

    def test_one_cached_inactive_observation_never_clears_a_newer_alert(self):
        first = reconcile_official_alert_observations(
            None, observations(NOW), now=NOW
        )
        second_at = NOW + timedelta(minutes=30)

        second = reconcile_official_alert_observations(
            first, observations(second_at), now=second_at
        )

        self.assertTrue(second["active"])
        self.assertEqual(second["source_mode"], TELEGRAM_VERIFIED_SOURCE_MODE)

    def test_two_inactive_observations_beyond_cache_window_clear_the_alert(self):
        first = reconcile_official_alert_observations(
            None, observations(NOW), now=NOW
        )
        second_at = NOW + timedelta(minutes=66)

        second = reconcile_official_alert_observations(
            first, observations(second_at), now=second_at
        )

        self.assertFalse(second["active"])
        self.assertEqual(second["source_mode"], ARPA_PCR_SOURCE_MODE)
        self.assertEqual(second["alerts"], [])

    def test_observed_arpa_active_then_inactive_clears_without_waiting_an_hour(self):
        active_observation = observations(NOW, pcr_status="active")
        previous = reconcile_official_alert_observations(
            None, active_observation, now=NOW
        )
        inactive_at = NOW + timedelta(minutes=10)

        cleared = reconcile_official_alert_observations(
            previous, observations(inactive_at), now=inactive_at
        )

        self.assertFalse(cleared["active"])
        self.assertEqual(cleared["source_mode"], ARPA_PCR_SOURCE_MODE)

    def test_positive_only_telegram_absence_does_not_clear_previous_active_state(self):
        previous = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status=None), now=NOW
        )
        later = NOW + timedelta(minutes=10)

        retained = reconcile_official_alert_observations(
            previous,
            observations(later, telegram=False, pcr_status="inactive"),
            now=later,
        )

        self.assertTrue(retained["active"])
        self.assertEqual(retained["alerts"], previous["alerts"])

    def test_source_failure_is_unavailable_and_does_not_clear_previous(self):
        previous = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        later = NOW + timedelta(minutes=10)
        failed = observations(
            later,
            telegram=False,
            pcr_status=None,
            failures=[
                {"source": "telegram", "category": "timeout"},
                {"source": "arpa_pcr", "category": "connection"},
            ],
        )

        result = reconcile_official_alert_observations(previous, failed, now=later)

        self.assertEqual(result["error"], "official_alerts_unavailable")
        self.assertEqual(result["cache"]["status"], "unavailable")
        self.assertEqual(len(result["cache"]["upstream_failure"]["attempts"]), 2)

    def test_official_validity_deadline_clears_even_when_sources_fail(self):
        previous = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        expired = deepcopy(previous)
        expired["alerts"][0]["valid_to"] = (NOW - timedelta(minutes=1)).isoformat()
        expired["expires_at"] = expired["alerts"][0]["valid_to"]
        later = NOW + timedelta(minutes=1)

        result = reconcile_official_alert_observations(
            expired,
            observations(later, telegram=False, pcr_status=None),
            now=later,
        )

        self.assertFalse(result["active"])
        self.assertEqual(result["source_mode"], OFFICIAL_VALIDITY_EXPIRED_SOURCE_MODE)

    def test_expired_structured_corroboration_is_persisted_as_fresh_inactive(self):
        initial = structured_observations()
        initial["widget"] = None
        initial["telegram"] = {
            "source_mode": "official_telegram_positive_only",
            "alerts": [structured_telegram_alert()],
            "can_confirm_inactive": False,
        }
        initial["failures"] = [{"source": "widget", "category": "timeout"}]
        previous = reconcile_official_alert_observations(
            None,
            initial,
            now=STRUCTURED_NOW,
        )
        self.assertEqual(
            previous["source_mode"], TELEGRAM_ARPA_CORROBORATED_SOURCE_MODE
        )
        self.assertNotIn("pdf_verified_at", previous["alerts"][0])

        expired_at = datetime(2026, 8, 21, 22, 5, tzinfo=timezone.utc)
        observed = structured_observations(
            alerts=[], panels=[], pcr_status="inactive"
        )
        observed["fetched_at"] = expired_at.isoformat()
        observed["widget"] = None
        observed["telegram"] = {
            "source_mode": "official_telegram_positive_only",
            "alerts": [],
            "can_confirm_inactive": False,
        }
        observed["arpa_pcr"]["source_timing"]["http_date"] = (
            expired_at.isoformat()
        )
        observed["failures"] = [{"source": "widget", "category": "timeout"}]

        class Repository:
            def __init__(self, payload):
                self.payload = deepcopy(payload)
                self.saved = []

            def load(self):
                return deepcopy(self.payload), "firestore"

            def save(self, payload):
                self.payload = deepcopy(payload)
                self.saved.append(deepcopy(payload))
                return "firestore"

        repository = Repository(previous)
        service = OfficialAlertsStateService(
            repository=repository,
            loader=lambda **_kwargs: deepcopy(observed),
            reconciler=reconcile_official_alert_observations,
            now=lambda: expired_at,
        )

        result = service.refresh()

        self.assertTrue(result.refreshed)
        self.assertEqual(result.stored_in, "firestore")
        self.assertFalse(result.payload["active"])
        self.assertNotIn("error", result.payload)
        self.assertEqual(
            result.payload["source_mode"], OFFICIAL_VALIDITY_EXPIRED_SOURCE_MODE
        )
        self.assertEqual(result.payload["cache"]["status"], "fresh")
        self.assertEqual(repository.saved, [result.payload])

    def test_tampered_structured_corroboration_cannot_unlock_expiry(self):
        initial = structured_observations()
        initial["widget"] = None
        initial["telegram"] = {
            "source_mode": "official_telegram_positive_only",
            "alerts": [structured_telegram_alert()],
            "can_confirm_inactive": False,
        }
        previous = reconcile_official_alert_observations(
            None,
            initial,
            now=STRUCTURED_NOW,
        )
        previous["alerts"][0]["valid_to"] = "2026-08-21T21:59:00+00:00"

        expired_at = datetime(2026, 8, 21, 22, 5, tzinfo=timezone.utc)
        observed = structured_observations(
            alerts=[], panels=[], pcr_status="inactive"
        )
        observed["fetched_at"] = expired_at.isoformat()
        observed["widget"] = None
        observed["telegram"] = {
            "source_mode": "official_telegram_positive_only",
            "alerts": [],
            "can_confirm_inactive": False,
        }
        observed["arpa_pcr"]["source_timing"]["http_date"] = (
            expired_at.isoformat()
        )

        result = reconcile_official_alert_observations(
            previous,
            observed,
            now=expired_at,
        )

        self.assertEqual(result.get("error"), "official_alerts_unavailable")
        self.assertEqual(
            result.get("cache", {}).get("reason"),
            "official_previous_alert_unverified",
        )

    def test_runtime_v2_structured_hash_binds_ordering_and_alert_semantics(self):
        initial = structured_observations()
        initial["widget"] = None
        initial["telegram"] = {
            "source_mode": "official_telegram_positive_only",
            "alerts": [structured_telegram_alert()],
            "can_confirm_inactive": False,
        }
        previous = reconcile_official_alert_observations(
            None,
            initial,
            now=STRUCTURED_NOW,
        )
        self.assertEqual(
            previous["alerts"][0]["corroboration"]["revision_hash_schema"],
            "runtime-v3",
        )

        expired_at = datetime(2026, 8, 21, 22, 5, tzinfo=timezone.utc)
        observed = structured_observations(
            alerts=[], panels=[], pcr_status="inactive"
        )
        observed["fetched_at"] = expired_at.isoformat()
        observed["widget"] = None
        observed["telegram"] = {
            "source_mode": "official_telegram_positive_only",
            "alerts": [],
            "can_confirm_inactive": False,
        }
        observed["arpa_pcr"]["source_timing"]["http_date"] = (
            expired_at.isoformat()
        )

        mutations = {
            "published_at": "2026-08-21T21:30:00+00:00",
            "telegram_post_id": 999999,
            "telegram_post_url": "https://t.me/ProtCivileFVG/999999",
            "levels": ["gialla", "arancione"],
            "mixed_levels": True,
            "risks": ["vento"],
            "area": "Zona FVG-A",
            "push_body_i18n": {
                "it": "Messaggio alterato.",
                "fur": "Messaç alterât.",
            },
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                tampered = deepcopy(previous)
                tampered["alerts"][0][field] = value

                result = reconcile_official_alert_observations(
                    tampered,
                    deepcopy(observed),
                    now=expired_at,
                )

                self.assertEqual(result.get("error"), "official_alerts_unavailable")
                self.assertEqual(
                    result.get("cache", {}).get("reason"),
                    "official_previous_alert_unverified",
                )

    def test_legacy_structured_snapshot_can_only_retire_its_exact_expired_revision(self):
        initial = structured_observations()
        initial["widget"] = None
        initial["telegram"] = {
            "source_mode": "official_telegram_positive_only",
            "alerts": [structured_telegram_alert()],
            "can_confirm_inactive": False,
        }
        legacy = as_legacy_structured_snapshot(
            reconcile_official_alert_observations(
                None,
                initial,
                now=STRUCTURED_NOW,
            )
        )
        # These fields were not covered by the legacy revision hash.  They must
        # not become a publication-order floor in the generated clearance.
        legacy["alerts"][0]["published_at"] = "2026-08-21T22:04:00+00:00"
        legacy["alerts"][0]["telegram_post_id"] = 999999
        legacy["alerts"][0]["risks"] = ["vento"]

        expired_at = datetime(2026, 8, 21, 22, 5, tzinfo=timezone.utc)
        observed = structured_observations(
            alerts=[], panels=[], pcr_status="inactive"
        )
        observed["fetched_at"] = expired_at.isoformat()
        observed["widget"] = None
        observed["telegram"] = {
            "source_mode": "official_telegram_positive_only",
            "alerts": [],
            "can_confirm_inactive": False,
        }
        observed["arpa_pcr"]["source_timing"]["http_date"] = (
            expired_at.isoformat()
        )

        retired = reconcile_official_alert_observations(
            legacy,
            deepcopy(observed),
            now=expired_at,
        )

        self.assertFalse(retired["active"])
        self.assertEqual(
            retired["source_mode"], OFFICIAL_VALIDITY_EXPIRED_SOURCE_MODE
        )
        clearance = retired["cache"]["verification"]["cleared_alerts"][0]
        self.assertTrue(clearance["exact_revision_only"])
        self.assertEqual(clearance["published_at"], "")
        self.assertIsNone(clearance["telegram_post_id"])

        newer = structured_telegram_alert(
            valid_from="2026-08-21T22:00:00+00:00",
            valid_to="2026-08-22T08:00:00+00:00",
        )
        newer.update(
            published_at="2026-08-21T21:00:00+00:00",
            telegram_post_id=925,
            telegram_post_url="https://t.me/ProtCivileFVG/925",
            pdf_sha256="e" * 64,
            pdf_size_bytes=4096,
            pdf_verified_at="2026-08-21T21:30:00+00:00",
            revision_hash="f" * 64,
        )
        next_observed = deepcopy(observed)
        next_observed["telegram"] = {
            "source_mode": "official_telegram_positive_only",
            "alerts": [newer],
            "can_confirm_inactive": False,
        }

        adopted = reconcile_official_alert_observations(
            retired,
            next_observed,
            now=expired_at,
        )

        self.assertTrue(adopted["active"])
        self.assertEqual(adopted["alerts"][0]["pdf_sha256"], "e" * 64)

    def test_unexpired_legacy_structured_snapshot_is_never_presented_or_retained(self):
        initial = structured_observations()
        previous = as_legacy_structured_snapshot(
            reconcile_official_alert_observations(
                None,
                initial,
                now=STRUCTURED_NOW,
            )
        )
        observed = {
            "fetched_at": (STRUCTURED_NOW + timedelta(minutes=5)).isoformat(),
            "widget": None,
            "telegram": None,
            "arpa_pcr": None,
            "failures": [{"source": "widget", "category": "timeout"}],
        }

        result = reconcile_official_alert_observations(
            previous,
            observed,
            now=STRUCTURED_NOW + timedelta(minutes=5),
        )

        self.assertEqual(result.get("error"), "official_alerts_unavailable")
        self.assertEqual(
            result.get("cache", {}).get("reason"),
            "official_previous_alert_unverified",
        )

    def test_explicit_arpa_inactive_establishes_an_inactive_baseline(self):
        result = reconcile_official_alert_observations(
            None,
            observations(NOW, telegram=False, pcr_status="inactive"),
            now=NOW,
        )

        self.assertFalse(result["active"])
        self.assertEqual(result["source_mode"], ARPA_PCR_SOURCE_MODE)

    def test_stale_or_future_arpa_response_cannot_confirm_inactive(self):
        for source_time in (
            NOW - timedelta(days=1),
            NOW + timedelta(minutes=10),
        ):
            with self.subTest(source_time=source_time):
                result = reconcile_official_alert_observations(
                    None,
                    observations(
                        NOW,
                        telegram=False,
                        pcr_status="inactive",
                        pcr_http_date=source_time,
                    ),
                    now=NOW,
                )

                self.assertEqual(result.get("error"), "official_alerts_unavailable")
                self.assertEqual(result.get("cache", {}).get("status"), "unavailable")

    def test_repeated_copy_of_pre_telegram_arpa_cache_cannot_clear(self):
        published_at = NOW - timedelta(hours=2)
        cached_at = published_at - timedelta(minutes=10)
        first = reconcile_official_alert_observations(
            None,
            observations(NOW, pcr_http_date=cached_at),
            now=NOW,
        )
        second_at = NOW + timedelta(hours=2)

        second = reconcile_official_alert_observations(
            first,
            observations(second_at, pcr_http_date=cached_at),
            now=second_at,
        )

        self.assertTrue(second["active"])

    def test_clearance_tombstone_blocks_reactivation_on_arpa_timeout(self):
        active = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        cleared_at = NOW + timedelta(minutes=10)
        cleared = reconcile_official_alert_observations(
            active, observations(cleared_at), now=cleared_at
        )
        timeout_at = cleared_at + timedelta(minutes=15)

        after_timeout = reconcile_official_alert_observations(
            cleared,
            observations(
                timeout_at,
                pcr_status=None,
                failures=[{"source": "arpa_pcr", "category": "timeout"}],
            ),
            now=timeout_at,
        )

        self.assertFalse(cleared["active"])
        self.assertFalse(after_timeout["active"])
        self.assertEqual(after_timeout["source_mode"], ARPA_PCR_SOURCE_MODE)

    def test_expired_record_is_removed_while_other_active_record_is_retained(self):
        previous = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        expired = deepcopy(previous["alerts"][0])
        expired.update(
            id="older-red",
            event_id="older-red",
            level="rossa",
            pdf_url=(
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_22-2026.pdf"
            ),
            valid_to=(NOW - timedelta(minutes=1)).isoformat(),
        )
        previous["alerts"] = [expired, previous["alerts"][0]]
        previous["count"] = 2
        later = NOW + timedelta(minutes=1)

        retained = reconcile_official_alert_observations(
            previous,
            observations(later, telegram=False, pcr_status="active"),
            now=later,
        )

        self.assertTrue(retained["active"])
        self.assertEqual(retained["count"], 1)
        self.assertEqual([item["id"] for item in retained["alerts"]], [
            "allerta-regionale-23-2026"
        ])

    def test_partially_expired_revision_cannot_return_with_extended_validity(self):
        alert_a = telegram_alert(
            valid_to=NOW + timedelta(minutes=30),
            pdf_sha256="a" * 64,
        )
        alert_b = {
            **telegram_alert(pdf_sha256="b" * 64, post_id=901),
            "id": "allerta-regionale-24-2026",
            "event_id": "allerta-regionale-24-2026",
            "alert_number": 24,
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026.pdf"
            ),
        }
        initial = observations(NOW, telegram=False, pcr_status="active")
        initial["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(initial, alert_a["pdf_url"], alert_b["pdf_url"])
        previous = reconcile_official_alert_observations(None, initial, now=NOW)
        original_signature = previous["cache"]["verification"]["telegram"][
            "event_signature"
        ]
        later = NOW + timedelta(hours=1)
        stale_extension = {
            **alert_a,
            "valid_to": (later + timedelta(hours=4)).isoformat(),
        }
        observed = observations(later, telegram=False, pcr_status="active")
        observed["telegram"] = {"alerts": [stale_extension]}
        set_pcr_documents(observed, alert_b["pdf_url"])

        retained = reconcile_official_alert_observations(
            previous, observed, now=later
        )

        self.assertTrue(retained["active"])
        self.assertEqual([item["id"] for item in retained["alerts"]], [alert_b["id"]])
        cleared = retained["cache"]["verification"]["cleared_alerts"]
        self.assertTrue(any(item["pdf_sha256"] == "a" * 64 for item in cleared))
        retained_signature = retained["cache"]["verification"]["telegram"][
            "event_signature"
        ]
        self.assertNotEqual(retained_signature, original_signature)
        self.assertEqual(
            retained["cache"]["verification"]["arpa_pcr"][
                "matched_event_signature"
            ],
            retained_signature,
        )

    def test_active_pcr_document_transition_removes_only_the_missing_alert(self):
        alert_a = telegram_alert(pdf_sha256="a" * 64)
        alert_b = {
            **telegram_alert(pdf_sha256="b" * 64, post_id=901),
            "id": "allerta-regionale-24-2026",
            "event_id": "allerta-regionale-24-2026",
            "alert_number": 24,
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026.pdf"
            ),
        }
        initial = observations(NOW, telegram=False, pcr_status="active")
        initial["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(initial, alert_a["pdf_url"], alert_b["pdf_url"])
        previous = reconcile_official_alert_observations(None, initial, now=NOW)
        later = NOW + timedelta(minutes=10)
        changed = observations(later, telegram=False, pcr_status="active")
        changed["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(changed, alert_b["pdf_url"])

        result = reconcile_official_alert_observations(previous, changed, now=later)

        self.assertTrue(result["active"])
        self.assertEqual([item["id"] for item in result["alerts"]], [alert_b["id"]])
        verification = result["cache"]["verification"]
        self.assertNotIn("clearance", verification)
        self.assertTrue(
            any(
                item.get("pdf_sha256") == "a" * 64
                and item.get("reason") == "arpa_pcr_document_removed"
                for item in verification["cleared_alerts"]
            )
        )

    def test_incomplete_multi_panel_pcr_cannot_remove_a_document(self):
        alert_a = telegram_alert(pdf_sha256="a" * 64)
        alert_b = {
            **telegram_alert(pdf_sha256="b" * 64, post_id=901),
            "id": "allerta-regionale-24-2026",
            "event_id": "allerta-regionale-24-2026",
            "alert_number": 24,
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026.pdf"
            ),
        }
        initial = observations(NOW, telegram=False, pcr_status="active")
        initial["telegram"] = {"alerts": [alert_a, alert_b]}
        initial["arpa_pcr"]["pcr"]["alerts"] = [
            {"document_urls": [alert_a["pdf_url"]]},
            {"document_urls": [alert_b["pdf_url"]]},
        ]
        previous = reconcile_official_alert_observations(None, initial, now=NOW)
        later = NOW + timedelta(minutes=10)
        incomplete = observations(later, telegram=False, pcr_status="active")
        incomplete["telegram"] = {"alerts": [alert_a, alert_b]}
        incomplete["arpa_pcr"]["pcr"]["alerts"] = [
            {"document_urls": []},
            {"document_urls": [alert_b["pdf_url"]]},
        ]

        result = reconcile_official_alert_observations(
            previous, incomplete, now=later
        )

        self.assertTrue(result["active"])
        self.assertEqual(
            {item["id"] for item in result["alerts"]},
            {alert_a["id"], alert_b["id"]},
        )

    def test_incomplete_multi_panel_pcr_blocks_partial_expiry_inference(self):
        alert_a = telegram_alert(
            valid_to=NOW + timedelta(minutes=30), pdf_sha256="a" * 64
        )
        alert_b = {
            **telegram_alert(pdf_sha256="b" * 64, post_id=901),
            "id": "allerta-regionale-24-2026",
            "event_id": "allerta-regionale-24-2026",
            "alert_number": 24,
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026.pdf"
            ),
        }
        initial = observations(NOW, telegram=False, pcr_status="active")
        initial["telegram"] = {"alerts": [alert_a, alert_b]}
        initial["arpa_pcr"]["pcr"]["alerts"] = [
            {"document_urls": [alert_a["pdf_url"]]},
            {"document_urls": [alert_b["pdf_url"]]},
        ]
        previous = reconcile_official_alert_observations(None, initial, now=NOW)
        later = NOW + timedelta(hours=1)
        incomplete = observations(later, telegram=False, pcr_status="active")
        incomplete["arpa_pcr"]["pcr"]["alerts"] = [
            {"document_urls": []},
            {"document_urls": [alert_b["pdf_url"]]},
        ]

        result = reconcile_official_alert_observations(
            previous, incomplete, now=later
        )

        self.assertEqual(result.get("error"), "official_alerts_unavailable")

    def test_two_source_distinct_document_absences_are_required_without_baseline(self):
        alert_a = telegram_alert(pdf_sha256="a" * 64)
        alert_b = {
            **telegram_alert(pdf_sha256="b" * 64, post_id=901),
            "id": "allerta-regionale-24-2026",
            "event_id": "allerta-regionale-24-2026",
            "alert_number": 24,
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026.pdf"
            ),
        }
        initial = observations(NOW, telegram=False, pcr_status=None)
        initial["telegram"] = {"alerts": [alert_a, alert_b]}
        previous = reconcile_official_alert_observations(None, initial, now=NOW)

        first_at = NOW + timedelta(minutes=10)
        first = observations(first_at, telegram=False, pcr_status="active")
        first["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(first, alert_b["pdf_url"])
        after_first = reconcile_official_alert_observations(previous, first, now=first_at)
        self.assertEqual(len(after_first["alerts"]), 2)

        early_at = first_at + timedelta(minutes=30)
        early = observations(early_at, telegram=False, pcr_status="active")
        early["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(early, alert_b["pdf_url"])
        after_early = reconcile_official_alert_observations(
            after_first, early, now=early_at
        )
        self.assertEqual(len(after_early["alerts"]), 2)

        mature_at = first_at + timedelta(minutes=66)
        mature = observations(mature_at, telegram=False, pcr_status="active")
        mature["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(mature, alert_b["pdf_url"])
        after_mature = reconcile_official_alert_observations(
            after_early, mature, now=mature_at
        )
        self.assertEqual([item["id"] for item in after_mature["alerts"]], [alert_b["id"]])

    def test_repeated_cached_document_absence_cannot_remove_an_alert(self):
        alert_a = telegram_alert(pdf_sha256="a" * 64)
        alert_b = {
            **telegram_alert(pdf_sha256="b" * 64, post_id=901),
            "id": "allerta-regionale-24-2026",
            "event_id": "allerta-regionale-24-2026",
            "alert_number": 24,
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026.pdf"
            ),
        }
        baseline = observations(NOW, telegram=False, pcr_status=None)
        baseline["telegram"] = {"alerts": [alert_a, alert_b]}
        previous = reconcile_official_alert_observations(None, baseline, now=NOW)
        source_time = NOW + timedelta(minutes=10)
        first = observations(
            source_time,
            telegram=False,
            pcr_status="active",
            pcr_http_date=source_time,
        )
        first["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(first, alert_b["pdf_url"])
        after_first = reconcile_official_alert_observations(
            previous, first, now=source_time
        )
        later = source_time + timedelta(minutes=90)
        cached = observations(
            later,
            telegram=False,
            pcr_status="active",
            pcr_http_date=source_time,
        )
        cached["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(cached, alert_b["pdf_url"])

        result = reconcile_official_alert_observations(after_first, cached, now=later)

        self.assertEqual(len(result["alerts"]), 2)

    def test_new_revision_on_the_same_url_resets_the_missing_baseline(self):
        alert_a = telegram_alert(pdf_sha256="a" * 64)
        alert_b = {
            **telegram_alert(pdf_sha256="b" * 64, post_id=901),
            "id": "allerta-regionale-24-2026",
            "event_id": "allerta-regionale-24-2026",
            "alert_number": 24,
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026.pdf"
            ),
        }
        baseline = observations(NOW, telegram=False, pcr_status=None)
        baseline["telegram"] = {"alerts": [alert_a, alert_b]}
        previous = reconcile_official_alert_observations(None, baseline, now=NOW)
        first_at = NOW + timedelta(minutes=10)
        first = observations(first_at, telegram=False, pcr_status="active")
        first["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(first, alert_b["pdf_url"])
        after_first = reconcile_official_alert_observations(
            previous, first, now=first_at
        )
        later = first_at + timedelta(minutes=80)
        revised_a = {
            **telegram_alert(
                published_at=first_at + timedelta(minutes=5),
                pdf_sha256="e" * 64,
                post_id=902,
            ),
            "pdf_verified_at": (first_at + timedelta(minutes=6)).isoformat(),
        }
        revised = observations(later, telegram=False, pcr_status="active")
        revised["telegram"] = {"alerts": [revised_a, alert_b]}
        set_pcr_documents(revised, alert_b["pdf_url"])

        result = reconcile_official_alert_observations(after_first, revised, now=later)

        self.assertEqual(len(result["alerts"]), 2)
        self.assertEqual(
            next(item for item in result["alerts"] if item["id"] == alert_a["id"])[
                "pdf_sha256"
            ],
            "e" * 64,
        )

    def test_partial_removal_then_inactive_pcr_clears_the_remaining_alert(self):
        alert_a = telegram_alert(pdf_sha256="a" * 64)
        alert_b = {
            **telegram_alert(pdf_sha256="b" * 64, post_id=901),
            "id": "allerta-regionale-24-2026",
            "event_id": "allerta-regionale-24-2026",
            "alert_number": 24,
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026.pdf"
            ),
        }
        initial = observations(NOW, telegram=False, pcr_status="active")
        initial["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(initial, alert_a["pdf_url"], alert_b["pdf_url"])
        previous = reconcile_official_alert_observations(None, initial, now=NOW)
        partial_at = NOW + timedelta(minutes=10)
        partial = observations(partial_at, telegram=False, pcr_status="active")
        partial["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(partial, alert_b["pdf_url"])
        only_b = reconcile_official_alert_observations(
            previous, partial, now=partial_at
        )
        inactive_at = partial_at + timedelta(minutes=10)

        result = reconcile_official_alert_observations(
            only_b,
            observations(inactive_at, telegram=False, pcr_status="inactive"),
            now=inactive_at,
        )

        self.assertFalse(result["active"])
        self.assertEqual(result["source_mode"], ARPA_PCR_SOURCE_MODE)

    def test_first_large_cache_window_controls_partial_document_clearance(self):
        alert_a = telegram_alert(pdf_sha256="a" * 64)
        alert_b = {
            **telegram_alert(pdf_sha256="b" * 64, post_id=901),
            "id": "allerta-regionale-24-2026",
            "event_id": "allerta-regionale-24-2026",
            "alert_number": 24,
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026.pdf"
            ),
        }
        baseline = observations(NOW, telegram=False, pcr_status=None)
        baseline["telegram"] = {"alerts": [alert_a, alert_b]}
        previous = reconcile_official_alert_observations(None, baseline, now=NOW)
        first_at = NOW + timedelta(minutes=10)
        first = observations(
            first_at, telegram=False, pcr_status="active", cache_max_age=7200
        )
        first["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(first, alert_b["pdf_url"])
        after_first = reconcile_official_alert_observations(
            previous, first, now=first_at
        )
        too_early_at = first_at + timedelta(minutes=80)
        too_early = observations(
            too_early_at, telegram=False, pcr_status="active", cache_max_age=0
        )
        too_early["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(too_early, alert_b["pdf_url"])

        result = reconcile_official_alert_observations(
            after_first, too_early, now=too_early_at
        )

        self.assertEqual(len(result["alerts"]), 2)

    def test_unknown_active_pcr_document_makes_the_state_unavailable(self):
        known = telegram_alert()
        unknown_url = (
            "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
            "Allerta_regionale_99-2026.pdf"
        )
        observed = observations(NOW, telegram=False, pcr_status="active")
        observed["telegram"] = {"alerts": [known]}
        set_pcr_documents(observed, known["pdf_url"], unknown_url)

        result = reconcile_official_alert_observations(None, observed, now=NOW)

        self.assertEqual(result.get("error"), "official_alerts_unavailable")
        self.assertEqual(result.get("cache", {}).get("status"), "unavailable")

    def test_new_arpa_mirror_url_matches_verified_telegram_alert_by_identity(self):
        known = telegram_alert()
        observed = observations(NOW, telegram=False, pcr_status="active")
        observed["telegram"] = {"alerts": [known]}
        set_pcr_documents(
            observed,
            "https://pianiemergenza.protezionecivile.fvg.it/alerts/23_2026.pdf",
        )

        result = reconcile_official_alert_observations(None, observed, now=NOW)

        self.assertTrue(result["active"])
        verification = result["cache"]["verification"]
        self.assertEqual(
            verification["arpa_pcr"]["matched_event_signature"],
            verification["telegram"]["event_signature"],
        )
        self.assertNotIn("missing_documents", verification["arpa_pcr"])

    def test_new_arpa_mirror_url_with_other_alert_number_is_unmapped(self):
        known = telegram_alert()
        observed = observations(NOW, telegram=False, pcr_status="active")
        observed["telegram"] = {"alerts": [known]}
        set_pcr_documents(
            observed,
            "https://pianiemergenza.protezionecivile.fvg.it/alerts/24_2026.pdf",
        )

        result = reconcile_official_alert_observations(None, observed, now=NOW)

        self.assertEqual(result.get("error"), "official_alerts_unavailable")

    def test_new_arpa_mirror_identity_preserves_partial_clearance_safety(self):
        alert_a = telegram_alert(pdf_sha256="a" * 64)
        alert_b = {
            **telegram_alert(pdf_sha256="b" * 64, post_id=901),
            "id": "allerta-regionale-24-2026",
            "event_id": "allerta-regionale-24-2026",
            "alert_number": 24,
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026_20082026-11_36.pdf"
            ),
        }
        initial = observations(NOW, telegram=False, pcr_status="active")
        initial["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(
            initial,
            "https://pianiemergenza.protezionecivile.fvg.it/alerts/23_2026.pdf",
            "https://pianiemergenza.protezionecivile.fvg.it/alerts/24_2026.pdf",
        )
        previous = reconcile_official_alert_observations(None, initial, now=NOW)
        later = NOW + timedelta(minutes=10)
        changed = observations(later, telegram=False, pcr_status="active")
        changed["telegram"] = {"alerts": [alert_a, alert_b]}
        set_pcr_documents(
            changed,
            "https://pianiemergenza.protezionecivile.fvg.it/alerts/24_2026.pdf",
        )

        result = reconcile_official_alert_observations(previous, changed, now=later)

        self.assertTrue(result["active"])
        self.assertEqual([item["id"] for item in result["alerts"]], [alert_b["id"]])

    def test_new_revision_issued_after_old_expiry_but_before_poll_is_accepted(self):
        old = telegram_alert(
            published_at=NOW - timedelta(hours=2),
            valid_to=NOW + timedelta(minutes=30),
            pdf_sha256="a" * 64,
            post_id=900,
        )
        initial = observations(NOW, telegram=False, pcr_status="active")
        initial["telegram"] = {"alerts": [old]}
        previous = reconcile_official_alert_observations(None, initial, now=NOW)
        issued_at = NOW + timedelta(minutes=30, seconds=10)
        revised = {
            **telegram_alert(
                published_at=issued_at,
                valid_to=NOW + timedelta(hours=6),
                pdf_sha256="e" * 64,
                post_id=901,
            ),
            "pdf_verified_at": (issued_at + timedelta(seconds=10)).isoformat(),
        }
        poll_at = NOW + timedelta(minutes=31)
        observed = observations(
            poll_at,
            telegram=False,
            pcr_status=None,
            failures=[{"source": "arpa_pcr", "category": "timeout"}],
        )
        observed["telegram"] = {"alerts": [revised]}

        result = reconcile_official_alert_observations(
            previous, observed, now=poll_at
        )

        self.assertTrue(result["active"])
        self.assertEqual(result["alerts"][0]["pdf_sha256"], "e" * 64)

    def test_arpa_active_blocks_expiry_clear_when_new_details_are_missing(self):
        previous = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        previous["alerts"][0]["valid_to"] = (NOW - timedelta(minutes=1)).isoformat()
        previous["expires_at"] = previous["alerts"][0]["valid_to"]
        later = NOW + timedelta(minutes=1)

        result = reconcile_official_alert_observations(
            previous,
            observations(later, telegram=False, pcr_status="active"),
            now=later,
        )

        self.assertEqual(result.get("error"), "official_alerts_unavailable")
        self.assertEqual(result.get("cache", {}).get("status"), "unavailable")

    def test_clearance_is_per_alert_and_does_not_hide_a_new_alert(self):
        active = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        cleared_at = NOW + timedelta(minutes=10)
        cleared = reconcile_official_alert_observations(
            active, observations(cleared_at), now=cleared_at
        )
        alert_a = telegram_alert()
        alert_b = {
            **telegram_alert(
                published_at=cleared_at + timedelta(minutes=1),
                pdf_sha256="c" * 64,
            ),
            "id": "allerta-regionale-24-2026",
            "alert_number": 24,
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026.pdf"
            ),
            "pdf_verified_at": (cleared_at + timedelta(minutes=2)).isoformat(),
        }
        later = cleared_at + timedelta(minutes=3)
        mixed = observations(
            later,
            telegram=False,
            pcr_status=None,
            failures=[{"source": "arpa_pcr", "category": "timeout"}],
        )
        mixed["telegram"] = {"alerts": [alert_a, alert_b]}

        result = reconcile_official_alert_observations(cleared, mixed, now=later)

        self.assertTrue(result["active"])
        self.assertEqual([item["id"] for item in result["alerts"]], [alert_b["id"]])

    def test_same_pdf_copy_edit_does_not_resurrect_a_cleared_alert(self):
        active = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        cleared_at = NOW + timedelta(minutes=10)
        cleared = reconcile_official_alert_observations(
            active, observations(cleared_at), now=cleared_at
        )
        later = cleared_at + timedelta(minutes=15)
        edited = observations(later, pcr_status=None)
        edited["telegram"]["alerts"] = [telegram_alert(revision="d" * 64)]

        result = reconcile_official_alert_observations(cleared, edited, now=later)

        self.assertFalse(result["active"])

    def test_new_verified_pdf_revision_can_reactivate_same_alert_number(self):
        active = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        cleared_at = NOW + timedelta(minutes=10)
        cleared = reconcile_official_alert_observations(
            active, observations(cleared_at), now=cleared_at
        )
        later = cleared_at + timedelta(minutes=15)
        revised = observations(later, pcr_status=None)
        revised["telegram"]["alerts"] = [
            {
                **telegram_alert(
                    published_at=cleared_at + timedelta(minutes=1),
                    pdf_sha256="e" * 64,
                ),
                "pdf_verified_at": (cleared_at + timedelta(minutes=2)).isoformat(),
            }
        ]

        result = reconcile_official_alert_observations(cleared, revised, now=later)

        self.assertTrue(result["active"])

    def test_revision_after_arpa_source_change_but_before_poll_can_reactivate(self):
        active = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        source_changed_at = NOW + timedelta(minutes=5)
        cleared_at = NOW + timedelta(minutes=10)
        cleared_observation = observations(
            cleared_at,
            pcr_status="inactive",
            pcr_http_date=source_changed_at,
        )
        cleared = reconcile_official_alert_observations(
            active, cleared_observation, now=cleared_at
        )
        issued_at = NOW + timedelta(minutes=7)
        later = NOW + timedelta(minutes=11)
        revised = observations(later, telegram=False, pcr_status=None)
        revised["telegram"] = {
            "alerts": [
                {
                    **telegram_alert(
                        published_at=issued_at,
                        pdf_sha256="e" * 64,
                        post_id=901,
                    ),
                    "pdf_verified_at": (issued_at + timedelta(minutes=1)).isoformat(),
                }
            ]
        }

        result = reconcile_official_alert_observations(cleared, revised, now=later)

        self.assertTrue(result["active"])
        self.assertEqual(result["alerts"][0]["pdf_sha256"], "e" * 64)

    def test_cleared_new_revision_cannot_roll_back_to_an_older_pdf(self):
        newest = observations(NOW, telegram=False, pcr_status="active")
        newest["telegram"] = {
            "alerts": [
                telegram_alert(
                    published_at=NOW - timedelta(hours=1),
                    pdf_sha256="e" * 64,
                    post_id=901,
                )
            ]
        }
        active = reconcile_official_alert_observations(None, newest, now=NOW)
        cleared_at = NOW + timedelta(minutes=10)
        cleared = reconcile_official_alert_observations(
            active, observations(cleared_at), now=cleared_at
        )
        later = cleared_at + timedelta(minutes=15)
        rollback = observations(later, telegram=False, pcr_status=None)
        rollback["telegram"] = {
            "alerts": [
                telegram_alert(
                    published_at=NOW - timedelta(hours=2),
                    pdf_sha256="b" * 64,
                    post_id=900,
                )
            ]
        }

        result = reconcile_official_alert_observations(cleared, rollback, now=later)

        self.assertFalse(result["active"])
        self.assertEqual(result["source_mode"], ARPA_PCR_SOURCE_MODE)

    def test_cached_relist_cannot_bypass_a_newer_same_event_clearance(self):
        alert_a = telegram_alert()
        first = observations(NOW, telegram=False, pcr_status="active")
        first["telegram"] = {"alerts": [alert_a]}
        set_pcr_documents(first, alert_a["pdf_url"])
        active_a = reconcile_official_alert_observations(None, first, now=NOW)

        a_cleared_at = NOW + timedelta(minutes=10)
        clear_a = observations(a_cleared_at, telegram=False, pcr_status="inactive")
        clear_a["telegram"] = {"alerts": [alert_a]}
        cleared_a = reconcile_official_alert_observations(
            active_a, clear_a, now=a_cleared_at
        )

        b_published_at = a_cleared_at + timedelta(minutes=1)
        alert_b = {
            **telegram_alert(
                published_at=b_published_at,
                pdf_sha256="e" * 64,
                post_id=901,
            ),
            # The authority may overwrite the same document URL with a revision.
            "pdf_url": alert_a["pdf_url"],
            "pdf_verified_at": (b_published_at + timedelta(minutes=1)).isoformat(),
        }
        b_active_at = a_cleared_at + timedelta(minutes=3)
        activate_b = observations(b_active_at, telegram=False, pcr_status="active")
        activate_b["telegram"] = {"alerts": [alert_b]}
        set_pcr_documents(activate_b, alert_b["pdf_url"])
        active_b = reconcile_official_alert_observations(
            cleared_a, activate_b, now=b_active_at
        )

        b_cleared_at = NOW + timedelta(minutes=20)
        clear_b = observations(b_cleared_at, telegram=False, pcr_status="inactive")
        clear_b["telegram"] = {"alerts": [alert_b]}
        cleared_b = reconcile_official_alert_observations(
            active_b, clear_b, now=b_cleared_at
        )
        retained_clearances = (
            cleared_b.get("cache", {})
            .get("verification", {})
            .get("cleared_alerts", [])
        )
        self.assertEqual(
            {item.get("pdf_sha256") for item in retained_clearances},
            {"b" * 64, "e" * 64},
        )

        rollback_at = NOW + timedelta(minutes=25)
        rollback_relist = observations(
            rollback_at,
            telegram=False,
            pcr_status="active",
            pcr_http_date=rollback_at,
        )
        rollback_relist["telegram"] = {"alerts": [alert_a]}
        set_pcr_documents(rollback_relist, alert_a["pdf_url"])

        result = reconcile_official_alert_observations(
            cleared_b, rollback_relist, now=rollback_at
        )

        self.assertFalse(result.get("active", False))
        self.assertNotEqual(result.get("source_mode"), TELEGRAM_VERIFIED_SOURCE_MODE)
        self.assertEqual(
            {
                item.get("pdf_sha256")
                for item in (
                    cleared_b.get("cache", {})
                    .get("verification", {})
                    .get("cleared_alerts", [])
                )
            },
            {"b" * 64, "e" * 64},
        )

    def test_new_pdf_confirmed_by_newer_pcr_can_precede_the_clearance_poll(self):
        alert_a = telegram_alert()
        first = observations(NOW, telegram=False, pcr_status="active")
        first["telegram"] = {"alerts": [alert_a]}
        set_pcr_documents(first, alert_a["pdf_url"])
        active_a = reconcile_official_alert_observations(None, first, now=NOW)

        cleared_at = NOW + timedelta(minutes=10)
        cleared_a = reconcile_official_alert_observations(
            active_a,
            observations(
                cleared_at,
                telegram=False,
                pcr_status="inactive",
                pcr_http_date=cleared_at,
                failures=[{"source": "official_telegram", "category": "timeout"}],
            ),
            now=cleared_at,
        )

        alert_b = {
            **telegram_alert(
                published_at=NOW + timedelta(minutes=5),
                pdf_sha256="e" * 64,
                post_id=901,
            ),
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_23-2026-rev2.pdf"
            ),
            "pdf_verified_at": (NOW + timedelta(minutes=6)).isoformat(),
        }
        observed_at = NOW + timedelta(minutes=20)
        confirmed_b = observations(
            observed_at,
            telegram=False,
            pcr_status="active",
            pcr_http_date=observed_at,
        )
        confirmed_b["telegram"] = {"alerts": [alert_b]}
        set_pcr_documents(confirmed_b, alert_b["pdf_url"])

        result = reconcile_official_alert_observations(
            cleared_a, confirmed_b, now=observed_at
        )

        self.assertTrue(result["active"])
        self.assertEqual(result["source_mode"], TELEGRAM_VERIFIED_SOURCE_MODE)
        self.assertEqual(result["alerts"][0]["pdf_sha256"], "e" * 64)

    def test_clearance_survives_the_old_validity_deadline_for_the_same_revision(self):
        initial = observations(NOW, telegram=False, pcr_status="active")
        initial["telegram"] = {
            "alerts": [telegram_alert(valid_to=NOW + timedelta(minutes=30))]
        }
        active = reconcile_official_alert_observations(None, initial, now=NOW)
        cleared_at = NOW + timedelta(minutes=10)
        cleared = reconcile_official_alert_observations(
            active,
            observations(cleared_at, telegram=False, pcr_status="inactive"),
            now=cleared_at,
        )
        later = NOW + timedelta(hours=1)
        edited = observations(later, pcr_status=None)
        edited["telegram"]["alerts"] = [
            telegram_alert(valid_to=later + timedelta(hours=4))
        ]

        result = reconcile_official_alert_observations(cleared, edited, now=later)

        self.assertFalse(result["active"])
        self.assertEqual(result["source_mode"], ARPA_PCR_SOURCE_MODE)

    def test_cached_active_pcr_cannot_restore_a_tombstoned_telegram_post(self):
        active = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        cleared_at = NOW + timedelta(minutes=10)
        cleared = reconcile_official_alert_observations(
            active, observations(cleared_at), now=cleared_at
        )
        later = cleared_at + timedelta(minutes=15)

        result = reconcile_official_alert_observations(
            cleared,
            observations(
                later,
                pcr_status="active",
                pcr_http_date=cleared_at,
            ),
            now=later,
        )

        self.assertEqual(result.get("error"), "official_alerts_unavailable")
        self.assertEqual(result.get("cache", {}).get("status"), "unavailable")

    def test_newer_active_pcr_and_telegram_restore_the_same_valid_revision(self):
        active = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        cleared_at = NOW + timedelta(minutes=10)
        cleared = reconcile_official_alert_observations(
            active, observations(cleared_at), now=cleared_at
        )
        later = cleared_at + timedelta(minutes=15)

        result = reconcile_official_alert_observations(
            cleared,
            observations(later, pcr_status="active"),
            now=later,
        )

        self.assertTrue(result["active"])
        self.assertEqual(result["alerts"][0]["pdf_sha256"], "b" * 64)
        self.assertNotIn("cleared_alerts", result["cache"]["verification"])

    def test_clearance_survives_a_poll_where_telegram_omits_the_post(self):
        active = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        cleared_at = NOW + timedelta(minutes=10)
        cleared = reconcile_official_alert_observations(
            active, observations(cleared_at), now=cleared_at
        )
        absent_at = cleared_at + timedelta(minutes=15)
        absent = reconcile_official_alert_observations(
            cleared,
            observations(absent_at, telegram=False, pcr_status="inactive"),
            now=absent_at,
        )
        returns_at = absent_at + timedelta(minutes=15)

        returned = reconcile_official_alert_observations(
            absent,
            observations(returns_at, pcr_status=None),
            now=returns_at,
        )

        self.assertFalse(returned["active"])

    def test_old_tombstoned_post_cannot_hide_a_new_active_alert(self):
        active_a = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        cleared_at = NOW + timedelta(minutes=10)
        cleared_a = reconcile_official_alert_observations(
            active_a, observations(cleared_at), now=cleared_at
        )
        alert_b = {
            **telegram_alert(
                published_at=cleared_at + timedelta(minutes=1),
                pdf_sha256="c" * 64,
            ),
            "id": "allerta-regionale-24-2026",
            "alert_number": 24,
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026.pdf"
            ),
            "pdf_verified_at": (cleared_at + timedelta(minutes=2)).isoformat(),
        }
        b_at = cleared_at + timedelta(minutes=3)
        b_observation = observations(b_at, telegram=False, pcr_status=None)
        b_observation["telegram"] = {"alerts": [telegram_alert(), alert_b]}
        active_b = reconcile_official_alert_observations(
            cleared_a, b_observation, now=b_at
        )
        rollback_at = b_at + timedelta(minutes=15)
        rollback = observations(
            rollback_at,
            pcr_status=None,
            failures=[{"source": "arpa_pcr", "category": "timeout"}],
        )

        retained = reconcile_official_alert_observations(
            active_b, rollback, now=rollback_at
        )

        self.assertEqual(retained.get("error"), "official_alerts_unavailable")
        self.assertNotIn(
            retained.get("source_mode"),
            {ARPA_PCR_SOURCE_MODE, OFFICIAL_VALIDITY_EXPIRED_SOURCE_MODE},
        )

    def test_positive_only_telegram_omission_cannot_remove_a_previous_alert(self):
        alert_a = telegram_alert(pdf_sha256="a" * 64)
        alert_b = {
            **telegram_alert(pdf_sha256="b" * 64),
            "id": "allerta-regionale-24-2026",
            "alert_number": 24,
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026.pdf"
            ),
        }
        initial = observations(NOW, telegram=False, pcr_status="active")
        initial["telegram"] = {"alerts": [alert_a, alert_b]}
        previous = reconcile_official_alert_observations(None, initial, now=NOW)
        later = NOW + timedelta(minutes=15)
        partial = observations(
            later,
            telegram=False,
            pcr_status=None,
            failures=[{"source": "arpa_pcr", "category": "timeout"}],
        )
        partial["telegram"] = {"alerts": [alert_b]}

        retained = reconcile_official_alert_observations(
            previous, partial, now=later
        )

        self.assertTrue(retained["active"])
        self.assertEqual(
            {item["id"] for item in retained["alerts"]},
            {alert_a["id"], alert_b["id"]},
        )

    def test_older_same_identity_observation_cannot_replace_a_newer_revision(self):
        newer = telegram_alert(
            published_at=NOW - timedelta(hours=1),
            pdf_sha256="e" * 64,
            post_id=901,
        )
        initial = observations(NOW, telegram=False, pcr_status="active")
        initial["telegram"] = {"alerts": [newer]}
        previous = reconcile_official_alert_observations(None, initial, now=NOW)
        later = NOW + timedelta(minutes=15)
        rollback = observations(
            later,
            telegram=False,
            pcr_status=None,
            failures=[{"source": "arpa_pcr", "category": "timeout"}],
        )
        rollback["telegram"] = {
            "alerts": [
                telegram_alert(
                    published_at=NOW - timedelta(hours=2),
                    pdf_sha256="b" * 64,
                    post_id=900,
                )
            ]
        }

        retained = reconcile_official_alert_observations(previous, rollback, now=later)

        self.assertTrue(retained["active"])
        self.assertEqual(retained["alerts"][0]["pdf_sha256"], "e" * 64)
        self.assertEqual(retained["alerts"][0]["telegram_post_id"], 901)

    def test_equal_order_different_pdf_cannot_replace_persisted_revision(self):
        published_at = NOW - timedelta(hours=1)
        newer = telegram_alert(
            published_at=published_at,
            pdf_sha256="e" * 64,
            post_id=901,
        )
        initial = observations(NOW, telegram=False, pcr_status="active")
        initial["telegram"] = {"alerts": [newer]}
        previous = reconcile_official_alert_observations(None, initial, now=NOW)
        later = NOW + timedelta(minutes=15)
        rollback = observations(later, telegram=False, pcr_status=None)
        rollback["telegram"] = {
            "alerts": [
                telegram_alert(
                    published_at=published_at,
                    pdf_sha256="b" * 64,
                    post_id=901,
                )
            ]
        }

        retained = reconcile_official_alert_observations(previous, rollback, now=later)

        self.assertTrue(retained["active"])
        self.assertEqual(retained["alerts"][0]["pdf_sha256"], "e" * 64)

    def test_newer_active_pcr_can_restore_old_post_after_new_alert_expires(self):
        active_a = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        cleared_at = NOW + timedelta(minutes=10)
        cleared_a = reconcile_official_alert_observations(
            active_a, observations(cleared_at), now=cleared_at
        )
        alert_b = {
            **telegram_alert(
                published_at=cleared_at + timedelta(minutes=1),
                pdf_sha256="c" * 64,
                post_id=901,
            ),
            "id": "allerta-regionale-24-2026",
            "event_id": "allerta-regionale-24-2026",
            "alert_number": 24,
            "pdf_url": (
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026.pdf"
            ),
            "pdf_verified_at": (cleared_at + timedelta(minutes=2)).isoformat(),
        }
        b_at = cleared_at + timedelta(minutes=3)
        b_observation = observations(b_at, telegram=False, pcr_status=None)
        b_observation["telegram"] = {"alerts": [telegram_alert(), alert_b]}
        active_b = reconcile_official_alert_observations(
            cleared_a, b_observation, now=b_at
        )
        later = b_at + timedelta(minutes=15)
        active_b["alerts"][0]["valid_to"] = (later - timedelta(minutes=1)).isoformat()
        active_b["expires_at"] = active_b["alerts"][0]["valid_to"]
        rollback = observations(later, pcr_status="active")

        result = reconcile_official_alert_observations(active_b, rollback, now=later)

        self.assertTrue(result["active"])
        self.assertEqual(
            [item["id"] for item in result["alerts"]],
            ["allerta-regionale-23-2026"],
        )

    def test_larger_first_cache_window_controls_double_inactive_clearance(self):
        first = reconcile_official_alert_observations(
            None,
            observations(NOW, cache_max_age=7200),
            now=NOW,
        )
        second_at = NOW + timedelta(minutes=66)

        second = reconcile_official_alert_observations(
            first,
            observations(second_at, cache_max_age=0),
            now=second_at,
        )

        self.assertTrue(second["active"])

    def test_unverified_telegram_candidate_never_activates(self):
        raw = observations(NOW, pcr_status=None)
        raw["telegram"]["alerts"][0].pop("pdf_sha256")

        result = reconcile_official_alert_observations(None, raw, now=NOW)

        self.assertEqual(result.get("error"), "official_alerts_unavailable")

    def test_mixed_zone_levels_do_not_assign_the_maximum_level_to_every_zone(self):
        mixed = observations(NOW, pcr_status=None)
        mixed_alert = mixed["telegram"]["alerts"][0]
        mixed_alert.update(
            level="arancione",
            levels=["arancione", "gialla"],
            mixed_levels=True,
            zones=["FVG-A", "FVG-B", "FVG-C"],
            area="zona FVG-A, zona FVG-B, zona FVG-C",
        )

        result = reconcile_official_alert_observations(None, mixed, now=NOW)

        self.assertTrue(result["active"])
        self.assertEqual(result["alerts"][0]["level"], "arancione")
        self.assertEqual(result["alerts"][0]["area"], "")
        self.assertNotIn("zona FVG", result["alerts"][0]["push_body"])

    def test_legacy_active_without_validity_is_not_refreshed_forever(self):
        previous = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        previous["alerts"][0].pop("valid_to")
        previous["expires_at"] = ""
        later = NOW + timedelta(minutes=10)

        result = reconcile_official_alert_observations(
            previous,
            observations(later, telegram=False, pcr_status="inactive"),
            now=later,
        )

        self.assertEqual(result.get("error"), "official_alerts_unavailable")

    def test_legacy_active_without_verified_pdf_cannot_be_republished(self):
        previous = reconcile_official_alert_observations(
            None, observations(NOW, pcr_status="active"), now=NOW
        )
        previous["source_mode"] = "official_page"
        previous["alerts"][0].pop("pdf_sha256")
        previous["alerts"][0].pop("pdf_size_bytes")
        previous["alerts"][0].pop("pdf_verified_at")
        later = NOW + timedelta(minutes=10)

        result = reconcile_official_alert_observations(
            previous,
            observations(later, telegram=False, pcr_status="active"),
            now=later,
        )

        self.assertEqual(result.get("error"), "official_alerts_unavailable")
        self.assertEqual(result.get("cache", {}).get("status"), "unavailable")


class _FailingArpaSource:
    def fetch_pcr(self):
        raise ArpaOsmerRisksUnavailable("source_timeout")


class OfficialAlertObservationFetchTests(unittest.TestCase):
    def test_widget_timeout_phase_is_safe_to_log(self):
        for error, phase in (
            (requests.ConnectTimeout("private host and token"), "connect"),
            (requests.ReadTimeout("private host and token"), "read"),
        ):
            with self.subTest(phase=phase):
                def broken_widget():
                    raise error

                result = fetch_official_alert_observations(
                    telegram_fetcher=lambda: {"alerts": [], "can_confirm_inactive": False},
                    widget_fetcher=broken_widget,
                    html_fetcher=None,
                    arpa_source=_FailingArpaSource(),
                    now=lambda: NOW,
                )
                sanitized = alerts_engine.sanitize_official_alerts_upstream_failure(
                    {"attempts": result["failures"]}
                )

                self.assertEqual(
                    sanitized["attempts"][0],
                    {"source": "widget", "category": "timeout", "phase": phase},
                )
                self.assertNotIn("private", repr(sanitized))

    def test_fetch_failures_are_sanitized_and_do_not_include_exception_text(self):
        def broken_telegram():
            raise OfficialTelegramParserError("sensitive parser detail")

        result = fetch_official_alert_observations(
            telegram_fetcher=broken_telegram,
            widget_fetcher=lambda: (
                'pcrfvgit_widget_setup({"alerts":['
                '{"title":"NESSUNA ALLERTA","description":"Nessuna allerta",'
                '"level":0,"zone":"FVG-A"}]})'
            ),
            arpa_source=_FailingArpaSource(),
            now=lambda: NOW,
        )

        self.assertIsNone(result["telegram"])
        self.assertIsNone(result["arpa_pcr"])
        self.assertEqual(
            result["failures"],
            [
                {"source": "telegram", "category": "parser"},
                {"source": "arpa_pcr", "category": "timeout"},
            ],
        )
        self.assertNotIn("sensitive", repr(result))

    def test_http_status_is_the_only_http_error_detail_retained(self):
        response = requests.Response()
        response.status_code = 503

        def broken_telegram():
            raise requests.HTTPError("private upstream body", response=response)

        result = fetch_official_alert_observations(
            telegram_fetcher=broken_telegram,
            widget_fetcher=lambda: (
                'pcrfvgit_widget_setup({"alerts":['
                '{"title":"NESSUNA ALLERTA","description":"Nessuna allerta",'
                '"level":0,"zone":"FVG-A"}]})'
            ),
            arpa_source=_FailingArpaSource(),
            now=lambda: NOW,
        )

        self.assertEqual(
            result["failures"][0],
            {"source": "telegram", "category": "http", "status_code": 503},
        )
        self.assertNotIn("private", repr(result))


if __name__ == "__main__":
    unittest.main()
