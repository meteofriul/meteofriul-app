"""Offline regressions: public widget capture + explicitly synthetic PCR panels."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
import json

from app.services import official_alert_sources as sources
from app.services.push import _prepare_official_state
from app.weather import alerts_engine
from tests.test_official_alert_sources import (
    structured_observations, structured_pcr_panel,
)

NOW = datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)
FIXTURE = Path(__file__).parent / "fixtures/official_alerts/widget_30_2026.jsonp"


def observed(zone_values=None):
    widget = alerts_engine.extract_jsonp_payload(FIXTURE.read_text(encoding="utf-8"))
    if zone_values:
        for row, level in zip(widget["alerts"], zone_values):
            row["level"] = level
    alerts = alerts_engine.parse_civil_protection_widget_alerts(
        f"pcrfvgit_widget_setup({json.dumps(widget)});"
    )
    value = structured_observations(
        alerts=alerts,
        panels=[structured_pcr_panel(
            number=30, levels=zone_values or [2, 2, 1, 0],
            start_time="00:00", start_weekday="mercoledì",
            end_time="06:00", end_weekday="giovedì",
        )],
    )
    value["fetched_at"] = NOW.isoformat()
    value["arpa_pcr"]["source_timing"]["http_date"] = NOW.isoformat()
    return value


class MixedWidgetRegressionTests(unittest.TestCase):
    def test_real_widget_preserves_levels_without_rejecting_or_flattening(self):
        alert = observed()["widget"]["alerts"][0]
        self.assertEqual(alert["zone_levels"], {
            "FVG-A": "arancione", "FVG-B": "arancione",
            "FVG-C": "gialla", "FVG-D": "verde",
        })
        self.assertEqual(alert["zones"], ["FVG-A", "FVG-B", "FVG-C"])
        self.assertTrue(alert["mixed_levels"])
        self.assertEqual(alert["area"], "")
        self.assertIn("Allerta arancione. zona FVG-A, zona FVG-B.", alert["push_body"])
        self.assertIn("Allerta gialla. zona FVG-C.", alert["push_body"])
        self.assertIn("Alerte naranç. zone FVG-A, zone FVG-B.",
                      alert["push_body_i18n"]["fur"])
        self.assertIn("Alerte zale. zone FVG-C.", alert["push_body_i18n"]["fur"])
        for body in alert["push_body_i18n"].values():
            self.assertNotIn("FVG-D", body)
        self.assertEqual(alert["valid_from"], "2026-10-21T00:00:00+02:00")
        self.assertEqual(alert["valid_to"], "2026-10-22T06:00:00+02:00")

    def test_exact_two_source_agreement_activates_one_event(self):
        result = sources.reconcile_official_alert_observations(None, observed(), now=NOW)
        self.assertTrue(result["active"])
        self.assertEqual(len(result["alerts"]), 1)
        alert = result["alerts"][0]
        self.assertEqual(alert["event_id"], "allerta-regionale-30-2026")
        self.assertEqual(alert["zone_levels"]["FVG-C"], "gialla")
        self.assertEqual(alert["corroboration"]["revision_hash_schema"], "runtime-v3")
        self.assertEqual(sources._persisted_structured_corroboration_kind(alert, now=NOW), "current")

    def test_wrong_level_missing_zone_wrong_document_or_window_stays_unavailable(self):
        mutations = (
            lambda panel: panel["zone_levels"][2].update(level=2),
            lambda panel: panel["zone_levels"].pop(),
            lambda panel: panel.update(document_urls=["https://pianiemergenza.protezionecivile.fvg.it/alerts/29_2026.pdf"]),
            lambda panel: panel.update(end_time="07:00"),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                value = observed()
                mutate(value["arpa_pcr"]["pcr"]["alerts"][0])
                result = sources.reconcile_official_alert_observations(None, value, now=NOW)
                self.assertEqual(result.get("error"), "official_alerts_unavailable")

    def test_map_is_bound_to_persisted_proof_and_old_v2_remains_readable(self):
        alert = sources.reconcile_official_alert_observations(None, observed(), now=NOW)["alerts"][0]
        tampered = deepcopy(alert)
        tampered["zone_levels"]["FVG-C"] = "arancione"
        self.assertIsNone(sources._persisted_structured_corroboration_kind(tampered, now=NOW))
        # Reproduce the existing uniform v2 record, not a mixed map under v2.
        value = structured_observations()
        at = datetime.fromisoformat(value["fetched_at"])
        old = sources.reconcile_official_alert_observations(None, value, now=at)["alerts"][0]
        old["corroboration"]["revision_hash_schema"] = "runtime-v2"
        old["revision_hash"] = sources._structured_corroboration_revision_hash(
            old, identity=(2026, 24), pcr_revision=old["corroboration"]["pcr_revision"], schema="runtime-v2",
        )
        self.assertEqual(sources._persisted_structured_corroboration_kind(old, now=at), "current")
        old["zone_levels"] = {"FVG-A": "rossa"}
        self.assertIsNone(sources._persisted_structured_corroboration_kind(old, now=at))

    def test_repeat_deduplicates_but_zone_redistribution_changes_signature(self):
        first = sources.reconcile_official_alert_observations(None, observed(), now=NOW)
        state, reason = _prepare_official_state(first, now=NOW)
        self.assertEqual(reason, "ready")
        later = NOW + timedelta(minutes=5)
        refresh = observed()
        refresh["fetched_at"] = later.isoformat()
        refresh["arpa_pcr"]["source_timing"]["http_date"] = later.isoformat()
        refreshed = sources.reconcile_official_alert_observations(first, refresh, now=later)
        again, reason = _prepare_official_state(refreshed, now=later)
        self.assertEqual(reason, "ready")
        self.assertEqual(state.signature, again.signature)
        changed = sources.reconcile_official_alert_observations(
            None, observed([2, 1, 2, 0]), now=NOW,
        )
        changed_state, reason = _prepare_official_state(changed, now=NOW)
        self.assertEqual(reason, "ready")
        self.assertNotEqual(state.signature, changed_state.signature)


if __name__ == "__main__":
    unittest.main()
