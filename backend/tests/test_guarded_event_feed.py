import unittest
from copy import deepcopy
from unittest.mock import patch

from app.events import guarded_feed
from app.repositories.event_sources import (
    EVENT_SOURCE_STATE_SCHEMA,
    EventSourceStateRepositoryUnavailable,
)


EVENT = {
    "title": "FVG Settanta",
    "source": "ERPAC FVG",
    "start_date": "2026-08-20",
    "end_date": "2026-09-20",
    "event_city": "Gradisca d'Isonzo",
}


class FakeRepository:
    def __init__(self, state=None, error=None):
        self.state = deepcopy(state)
        self.error = error
        self.load_count = 0

    def load(self):
        self.load_count += 1
        if self.error:
            raise self.error
        return deepcopy(self.state), "fake"


def state(publication_enabled=False):
    return {
        "schema_version": EVENT_SOURCE_STATE_SCHEMA,
        "publication_enabled": publication_enabled,
        "approved": [{"key": "event", "event": deepcopy(EVENT)}],
    }


class GuardedEventFeedTests(unittest.TestCase):
    def setUp(self):
        guarded_feed.reset_guarded_event_feed_cache()

    def test_off_mode_does_not_read_state(self):
        repository = FakeRepository(state())
        with patch.dict("os.environ", {"EVENT_SOURCE_FEED_MODE": "off"}, clear=True), patch(
            "app.events.guarded_feed._repository",
            return_value=repository,
        ):
            events = guarded_feed.load_guarded_official_events()

        self.assertEqual(events, [])
        self.assertEqual(repository.load_count, 0)

    def test_local_preview_can_read_approved_shadow_state(self):
        repository = FakeRepository(state(publication_enabled=False))
        with patch.dict(
            "os.environ",
            {"EVENT_SOURCE_FEED_MODE": "preview"},
            clear=True,
        ), patch("app.events.guarded_feed._repository", return_value=repository):
            events = guarded_feed.load_guarded_official_events()

        self.assertEqual(events, [EVENT])

    def test_cloud_run_disables_preview_mode(self):
        repository = FakeRepository(state())
        with patch.dict(
            "os.environ",
            {"EVENT_SOURCE_FEED_MODE": "preview", "K_SERVICE": "api"},
            clear=True,
        ), patch("app.events.guarded_feed._repository", return_value=repository):
            events = guarded_feed.load_guarded_official_events()

        self.assertEqual(events, [])
        self.assertEqual(repository.load_count, 0)

    def test_active_mode_requires_explicit_publication_gate(self):
        unpublished = FakeRepository(state(publication_enabled=False))
        published = FakeRepository(state(publication_enabled=True))
        with patch.dict(
            "os.environ",
            {"EVENT_SOURCE_FEED_MODE": "active"},
            clear=True,
        ), patch("app.events.guarded_feed._repository", return_value=unpublished):
            self.assertEqual(guarded_feed.load_guarded_official_events(), [])

        guarded_feed.reset_guarded_event_feed_cache()
        with patch.dict(
            "os.environ",
            {"EVENT_SOURCE_FEED_MODE": "active"},
            clear=True,
        ), patch("app.events.guarded_feed._repository", return_value=published):
            self.assertEqual(guarded_feed.load_guarded_official_events(), [EVENT])

    def test_storage_failure_returns_no_events(self):
        repository = FakeRepository(
            error=EventSourceStateRepositoryUnavailable("storage failed")
        )
        with patch.dict(
            "os.environ",
            {"EVENT_SOURCE_FEED_MODE": "active"},
            clear=True,
        ), patch("app.events.guarded_feed._repository", return_value=repository):
            events = guarded_feed.load_guarded_official_events()

        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
