import unittest
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch

from app.events.audit import (
    DECISION_BLOCKED,
    DECISION_DUPLICATE,
    DECISION_READY,
)
from app.services.event_sources import (
    EXPECTED_QUARANTINE_URLS,
    EventSourceAutomationConfig,
    EventSourceAutomationConfigurationError,
    EventSourceAutomationService,
)


NOW = datetime(2026, 8, 20, 8, 0, tzinfo=timezone.utc)


class FakeRepository:
    def __init__(self, state=None):
        self.state = deepcopy(state)
        self.save_count = 0

    def load(self):
        return deepcopy(self.state), "fake"

    def save(self, state):
        self.state = deepcopy(state)
        self.save_count += 1
        return "fake"


def config(**overrides):
    values = {
        "mode": "shadow",
        "local_state_path": None,
        "confirmations_required": 2,
        "alert_failure_threshold": 2,
        "alert_email_to": "info@meteofriul.it",
        "active_limit": 100,
    }
    values.update(overrides)
    return EventSourceAutomationConfig(**values)


def record(**overrides):
    values = {
        "source": "Villa Manin",
        "title": "Lo scrigno del Doge",
        "url": "https://www.villamanin.it/evento/lo-scrigno-del-doge/",
        "date": "20 settembre 2026",
        "start_date": "2026-09-20",
        "end_date": "2026-09-20",
        "occurrences": [],
        "event_city": "Codroipo",
        "venue": "Villa Manin",
        "place": "Villa Manin - Codroipo",
        "description": "Visita tematica ufficiale.",
        "image": "https://www.villamanin.it/scrigno.jpg",
        "provider_categories": "Cultura",
    }
    values.update(overrides)
    return values


def report(*candidate_items, source_status="ready_for_review", complete=True):
    return {
        "status": "ready_for_manual_review" if complete else "blocked",
        "visible_catalog": {"complete": complete},
        "source_summaries": [
            {
                "source": "Villa Manin",
                "status": source_status,
                "structure_errors": [],
            },
            {
                "source": "ERPAC FVG",
                "status": "ready_for_review",
                "structure_errors": [],
            },
        ],
        "candidates": list(candidate_items),
    }


def candidate(decision=DECISION_READY, event=None, blockers=None):
    return {
        "decision": decision,
        "source_record": deepcopy(event or record()),
        "blockers": list(blockers or []),
    }


class EventSourceAutomationConfigurationTests(unittest.TestCase):
    def test_defaults_are_disabled_and_target_project_email(self):
        with patch.dict("os.environ", {}, clear=True):
            current = EventSourceAutomationConfig.from_environment()

        self.assertEqual(current.mode, "off")
        self.assertEqual(current.alert_email_to, "info@meteofriul.it")
        self.assertEqual(current.confirmations_required, 2)

    def test_cloud_run_forbids_local_preview_storage(self):
        with patch.dict(
            "os.environ",
            {
                "K_SERVICE": "event-source-job",
                "EVENT_SOURCE_LOCAL_STATE_PATH": "tmp/state.json",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                EventSourceAutomationConfigurationError,
                "event_source_local_state_forbidden_in_cloud_run",
            ):
                EventSourceAutomationConfig.from_environment()


class EventSourceAutomationServiceTests(unittest.TestCase):
    def service(self, repository, reports, **config_overrides):
        queue = iter(deepcopy(reports))
        return EventSourceAutomationService(
            repository=repository,
            config=config(**config_overrides),
            audit_builder=lambda **_kwargs: next(queue),
            now=lambda: NOW,
        )

    def test_disabled_mode_never_reads_or_writes_state(self):
        repository = FakeRepository()
        service = EventSourceAutomationService(
            repository=repository,
            config=config(mode="off"),
            audit_builder=lambda **_kwargs: self.fail("audit must not run"),
            now=lambda: NOW,
        )

        result = service.run()

        self.assertEqual(result.status, "disabled")
        self.assertEqual(repository.save_count, 0)

    def test_candidate_requires_two_identical_observations_before_approval(self):
        repository = FakeRepository()
        healthy = report(candidate())

        first = self.service(repository, [healthy]).run()
        second = self.service(repository, [healthy]).run()

        self.assertEqual((first.pending, first.approved), (1, 0))
        self.assertEqual((second.pending, second.approved), (0, 1))
        self.assertFalse(repository.state["publication_enabled"])
        saved_event = repository.state["approved"][0]["event"]
        self.assertEqual(saved_event["source"], "Villa Manin")
        self.assertEqual(saved_event["event_city"], "Codroipo")
        self.assertIn("lat", saved_event)

    def test_scanner_preserves_but_never_self_enables_manual_publication_gate(self):
        repository = FakeRepository()
        healthy = report(candidate())
        self.service(repository, [healthy]).run()
        self.service(repository, [healthy]).run()

        self.assertFalse(repository.state["publication_enabled"])
        repository.state["publication_enabled"] = True

        result = self.service(repository, [healthy]).run()

        self.assertTrue(repository.state["publication_enabled"])
        self.assertTrue(result.publication_enabled)

    def test_critical_change_is_reconfirmed_while_old_approved_event_is_retained(self):
        repository = FakeRepository()
        original = report(candidate())
        self.service(repository, [original]).run()
        self.service(repository, [original]).run()
        changed = report(
            candidate(
                event=record(
                    start_date="2026-09-21",
                    end_date="2026-09-21",
                    date="21 settembre 2026",
                )
            )
        )

        result = self.service(repository, [changed]).run()

        self.assertEqual((result.approved, result.pending), (1, 1))
        self.assertEqual(
            repository.state["approved"][0]["event"]["start_date"],
            "2026-09-20",
        )
        self.assertEqual(
            repository.state["pending"][0]["event"]["start_date"],
            "2026-09-21",
        )

    def test_noncritical_description_change_updates_approved_event(self):
        repository = FakeRepository()
        original = report(candidate())
        self.service(repository, [original]).run()
        self.service(repository, [original]).run()
        refreshed = report(
            candidate(event=record(description="Descrizione ufficiale aggiornata."))
        )

        result = self.service(repository, [refreshed]).run()

        self.assertEqual((result.approved, result.pending), (1, 0))
        self.assertEqual(
            repository.state["approved"][0]["event"]["description"],
            "Descrizione ufficiale aggiornata.",
        )

    def test_official_cultural_event_is_not_misclassified_by_word_fragment(self):
        repository = FakeRepository()
        dag = report(
            candidate(
                event=record(
                    source="ERPAC FVG",
                    title="DAG - Digital Art Gallery Gorizia",
                    event_city="Gorizia",
                    place="Gorizia",
                    venue="Galleria Bombi",
                    description="Uno degli esempi più interessanti di arte digitale.",
                    provider_categories="evento",
                )
            )
        )

        self.service(repository, [dag]).run()
        self.service(repository, [dag]).run()

        event = repository.state["approved"][0]["event"]
        self.assertEqual(event["category"], "cultura")
        self.assertEqual(event["weather_sensitivity"], "low")

    def test_cena_in_bianco_uses_food_category(self):
        repository = FakeRepository()
        dinner = report(candidate(event=record(title="Cena in bianco")))

        self.service(repository, [dinner]).run()
        self.service(repository, [dinner]).run()

        self.assertEqual(
            repository.state["approved"][0]["event"]["category"],
            "food_wine",
        )

    def test_discrete_schedule_exposes_only_the_next_real_occurrence(self):
        repository = FakeRepository()
        scheduled = report(
            candidate(
                event=record(
                    title="Lo scrigno del Doge in Villa Manin",
                    date=(
                        "25 aprile 2026 · 2 giugno 2026 · 20 settembre 2026 · "
                        "1 novembre 2026"
                    ),
                    start_date="2026-04-25",
                    end_date="2026-11-01",
                    occurrences=[
                        "2026-04-25",
                        "2026-06-02",
                        "2026-09-20",
                        "2026-11-01",
                    ],
                )
            )
        )

        self.service(repository, [scheduled]).run()
        self.service(repository, [scheduled]).run()

        event = repository.state["approved"][0]["event"]
        self.assertEqual(event["date"], "20 settembre 2026")
        self.assertEqual(
            event["occurrences"],
            ["2026-04-25", "2026-06-02", "2026-09-20", "2026-11-01"],
        )

    def test_confirmed_duplicate_is_not_approved(self):
        repository = FakeRepository()
        duplicate = report(candidate(decision=DECISION_DUPLICATE))

        result = self.service(repository, [duplicate]).run()

        self.assertEqual(result.duplicates, 1)
        self.assertEqual(result.approved, 0)
        self.assertEqual(result.pending, 0)

    def test_expected_flowers_404_stays_quarantined_without_incident(self):
        repository = FakeRepository()
        flowers_url = next(iter(EXPECTED_QUARANTINE_URLS))
        blocked = report(
            candidate(
                decision=DECISION_BLOCKED,
                event=record(title="Flowers", url=flowers_url),
                blockers=["detail_not_found"],
            )
        )

        first = self.service(repository, [blocked]).run()
        second = self.service(repository, [blocked]).run()

        self.assertEqual(first.quarantined, 1)
        self.assertEqual(second.quarantined, 1)
        self.assertFalse(second.incident_active)
        self.assertTrue(repository.state["quarantine"][0]["expected"])

    def test_structure_failure_opens_incident_after_two_observations(self):
        repository = FakeRepository()
        failed = report(source_status="blocked")

        first = self.service(repository, [failed]).run()
        second = self.service(repository, [failed]).run()

        self.assertFalse(first.incident_active)
        self.assertTrue(second.incident_active)
        self.assertEqual(second.alert_transition, "opened")
        self.assertEqual(second.status, "incident")

    def test_incomplete_active_catalog_preserves_source_and_city_in_incident_log(self):
        repository = FakeRepository()
        incomplete = report(complete=False)
        incomplete["visible_catalog"]["incomplete_cities"] = ["Codroipo"]
        incomplete["active_catalog_coverage"] = {
            "complete": False,
            "cities": {
                "Codroipo": {
                    "complete": False,
                    "sources": {
                        "TurismoFVG": {"status": "ok", "count": 12},
                        "SagreFVG": {
                            "status": "error",
                            "error": "TimeoutError: upstream timeout",
                        },
                    },
                }
            },
            "warnings": ["Codroipo/SagreFVG: upstream timeout"],
        }

        result = self.service(repository, [incomplete]).run()
        summary = result.summary()

        self.assertIn("visible_catalog_incomplete", result.issues)
        self.assertIn(
            "active_catalog_coverage:Codroipo:SagreFVG:error",
            result.issues,
        )
        self.assertEqual(
            summary["active_catalog_coverage"]["failures"],
            [
                {
                    "city": "Codroipo",
                    "source": "SagreFVG",
                    "status": "error",
                    "error": "TimeoutError: upstream timeout",
                }
            ],
        )
        self.assertIn(
            {
                "type": "active_catalog_coverage",
                "city": "Codroipo",
                "source": "SagreFVG",
                "status": "error",
                "error": "TimeoutError: upstream timeout",
            },
            summary["incident_details"],
        )
        self.assertEqual(
            repository.state["incident"]["active_catalog_coverage"][
                "incomplete_cities"
            ],
            ["Codroipo"],
        )

    def test_candidate_incident_context_contains_source_and_city(self):
        repository = FakeRepository()
        blocked = report(
            candidate(
                decision=DECISION_BLOCKED,
                event=record(event_city="Codroipo"),
                blockers=["missing_date"],
            )
        )

        result = self.service(repository, [blocked]).run()

        detail = next(
            item
            for item in result.incident_details
            if item.get("type") == "candidate"
        )
        self.assertEqual(detail["source"], "Villa Manin")
        self.assertEqual(detail["city"], "Codroipo")
        self.assertEqual(detail["blockers"], ["missing_date"])

    def test_active_incident_stays_active_when_failure_signature_changes(self):
        repository = FakeRepository()
        failed = report(source_status="blocked")
        self.service(repository, [failed]).run()
        self.service(repository, [failed]).run()
        different = report(
            candidate(
                decision=DECISION_BLOCKED,
                event=record(title="Evento inatteso", url="https://example.test/evento"),
                blockers=["missing_date"],
            )
        )

        result = self.service(repository, [different]).run()

        self.assertTrue(result.incident_active)
        self.assertEqual(result.alert_transition, "none")

    def test_recovery_closes_incident(self):
        repository = FakeRepository()
        failed = report(source_status="blocked")
        self.service(repository, [failed]).run()
        self.service(repository, [failed]).run()

        recovered = self.service(repository, [report(candidate())]).run()

        self.assertFalse(recovered.incident_active)
        self.assertEqual(recovered.alert_transition, "recovered")


if __name__ == "__main__":
    unittest.main()
