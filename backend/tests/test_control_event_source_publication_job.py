import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.jobs.control_event_source_publication import (
    CONFIRMATION,
    PublicationControlConfig,
    PublicationControlError,
    run_publication_control,
)
from app.repositories.event_sources import EVENT_SOURCE_STATE_SCHEMA


NOW = datetime(2026, 8, 20, 14, 30, tzinfo=timezone.utc)


class FakeRepository:
    def __init__(self, state):
        self.state = deepcopy(state)
        self.save_count = 0

    def load(self):
        return deepcopy(self.state), "firestore"

    def save(self, state):
        self.state = deepcopy(state)
        self.save_count += 1
        return "firestore"


def state(**overrides):
    value = {
        "schema_version": EVENT_SOURCE_STATE_SCHEMA,
        "mode": "shadow",
        "publication_enabled": False,
        "updated_at": NOW.isoformat(timespec="seconds"),
        "audit_status": "ready_for_manual_review",
        "approved": [{"key": f"event-{index}"} for index in range(6)],
        "pending": [],
        "quarantine": [{"expected": True}],
        "incident": {"active": False},
    }
    value.update(overrides)
    return value


class PublicationControlTests(unittest.TestCase):
    def test_environment_requires_explicit_confirmation_and_count(self):
        with patch.dict(
            "os.environ",
            {"EVENT_SOURCE_PUBLICATION_ACTION": "enable"},
            clear=True,
        ):
            with self.assertRaisesRegex(PublicationControlError, "confirmation_missing"):
                PublicationControlConfig.from_environment()

        with patch.dict(
            "os.environ",
            {
                "EVENT_SOURCE_PUBLICATION_ACTION": "enable",
                "EVENT_SOURCE_PUBLICATION_CONFIRM": CONFIRMATION,
                "EVENT_SOURCE_PUBLICATION_EXPECTED_APPROVED": "6",
            },
            clear=True,
        ):
            config = PublicationControlConfig.from_environment()
        self.assertEqual(config, PublicationControlConfig("enable", 6))

    def test_status_is_read_only(self):
        repository = FakeRepository(state())
        result = run_publication_control(
            repository,
            PublicationControlConfig("status", None),
            now=lambda: NOW,
        )
        self.assertFalse(result["publication_enabled"])
        self.assertEqual(repository.save_count, 0)

    def test_enable_and_disable_are_explicit_and_idempotent(self):
        repository = FakeRepository(state())
        enabled = run_publication_control(
            repository,
            PublicationControlConfig("enable", 6),
            now=lambda: NOW,
        )
        self.assertTrue(enabled["publication_enabled"])

        disabled = run_publication_control(
            repository,
            PublicationControlConfig("disable", None),
            now=lambda: NOW,
        )
        self.assertFalse(disabled["publication_enabled"])

    def test_enable_fails_closed_on_every_operational_guard(self):
        cases = (
            (state(updated_at=(NOW - timedelta(days=2)).isoformat()), "state_stale"),
            (state(pending=[{"key": "pending"}]), "candidates_pending"),
            (state(incident={"active": True}), "incident_active"),
            (state(quarantine=[{"expected": False}]), "unexpected_quarantine"),
            (state(approved=[]), "approved_count_mismatch"),
        )
        for candidate, code in cases:
            with self.subTest(code=code):
                with self.assertRaisesRegex(PublicationControlError, code):
                    run_publication_control(
                        FakeRepository(candidate),
                        PublicationControlConfig("enable", 6),
                        now=lambda: NOW,
                    )


if __name__ == "__main__":
    unittest.main()

