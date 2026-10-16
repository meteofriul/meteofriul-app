import os
import unittest
from unittest.mock import patch

from app.contracts.live import WebcamManifestResponse, WebcamRecord
from app.services.webcam_controls import (
    WebcamControlConflict,
    WebcamControlRepository,
    WebcamControlService,
    WebcamControlStorageUnavailable,
    WebcamControlValidationError,
    validate_control_changes,
)


def manifest():
    records = [
        WebcamRecord(
            id="udine-panorama-castello",
            name="Udine - Panorama dal Castello",
            group="plain",
            municipality="Udine",
            area="Specola del Castello",
            imageUrl="https://images.example.test/udine.jpg",
            fallbackImageUrl="/municipalities/photos/030129-photo.webp",
            sourcePage="https://udine.example.test/",
            provider="Comune di Udine",
            mediaType="snapshot",
        ),
        WebcamRecord(
            id="forni-varmost",
            name="Forni di Sopra - Varmost",
            group="mountain",
            municipality="Forni di Sopra",
            playerUrl="https://forni.example.test/player/",
            fallbackImageUrl="/municipalities/photos/030033-photo.webp",
            sourcePage="https://forni.example.test/",
            mediaType="iframe",
        ),
        WebcamRecord(
            id="link-only",
            name="Link esterno",
            group="plain",
            municipality="Udine",
            fallbackImageUrl="/municipalities/photos/030129-photo.webp",
            sourcePage="https://link.example.test/webcam/",
        ),
    ]
    return WebcamManifestResponse(
        ok=True,
        status="ok",
        source="local",
        version=14,
        count=len(records),
        webcams=records,
    )


class FailingRepository:
    def read_state(self):
        raise WebcamControlStorageUnavailable("offline")


class WebcamControlServiceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"K_SERVICE": ""})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.repository = WebcamControlRepository(lambda: None)
        self.service = WebcamControlService(self.repository, cache_seconds=60)

    def test_default_state_keeps_public_contract_unchanged(self):
        original = manifest()

        controlled = self.service.apply_public_controls(original)

        self.assertIs(controlled, original)
        self.assertEqual(controlled.webcams[0].imageUrl, original.webcams[0].imageUrl)
        self.assertEqual(controlled.webcams[1].playerUrl, original.webcams[1].playerUrl)

    def test_disabled_snapshot_keeps_fallback_identity_and_source(self):
        original = manifest()
        response = self.service.update_previews(
            [{
                "webcamId": "udine-panorama-castello",
                "previewEnabled": False,
                "reason": "Verifica della fonte in corso",
            }],
            manifest=original,
            expected_revision=0,
            actor_uid="owner-1",
            actor_email="owner@example.test",
        )

        controlled = self.service.apply_public_controls(original)
        udine = controlled.webcams[0]
        self.assertEqual(response["revision"], 1)
        self.assertFalse(response["webcams"][0]["previewEnabled"])
        self.assertIsNone(udine.imageUrl)
        self.assertIsNone(udine.mediaType)
        self.assertIsNone(udine.playerUrl)
        self.assertEqual(udine.fallbackImageUrl, original.webcams[0].fallbackImageUrl)
        self.assertEqual(udine.sourcePage, original.webcams[0].sourcePage)
        self.assertEqual(udine.provider, original.webcams[0].provider)
        self.assertEqual(controlled.webcams[1], original.webcams[1])

    def test_reenable_restores_original_media_without_reentering_the_url(self):
        original = manifest()
        self.service.update_previews(
            [{"webcamId": original.webcams[0].id, "previewEnabled": False}],
            manifest=original,
            expected_revision=0,
            actor_uid="owner-1",
            actor_email="owner@example.test",
        )
        enabled = self.service.update_previews(
            [{"webcamId": original.webcams[0].id, "previewEnabled": True}],
            manifest=original,
            expected_revision=1,
            actor_uid="owner-1",
            actor_email="owner@example.test",
        )

        controlled = self.service.apply_public_controls(original)
        self.assertTrue(enabled["webcams"][0]["previewEnabled"])
        self.assertEqual(controlled.webcams[0].imageUrl, original.webcams[0].imageUrl)
        self.assertEqual(controlled.webcams[0].mediaType, "snapshot")

    def test_multi_camera_change_is_atomic_and_tracks_each_operator_change(self):
        original = manifest()
        response = self.service.update_previews(
            [
                {"webcamId": original.webcams[0].id, "previewEnabled": False},
                {"webcamId": original.webcams[1].id, "previewEnabled": False},
            ],
            manifest=original,
            expected_revision=0,
            actor_uid="owner-1",
            actor_email="owner@example.test",
        )

        self.assertEqual(response["revision"], 1)
        self.assertFalse(response["webcams"][0]["previewEnabled"])
        self.assertFalse(response["webcams"][1]["previewEnabled"])
        self.assertEqual(response["webcams"][0]["updatedByEmail"], "owner@example.test")
        controlled = self.service.apply_public_controls(original)
        self.assertIsNone(controlled.webcams[0].imageUrl)
        self.assertIsNone(controlled.webcams[1].playerUrl)

    def test_conflicting_revision_does_not_change_controls(self):
        original = manifest()
        self.service.update_previews(
            [{"webcamId": original.webcams[0].id, "previewEnabled": False}],
            manifest=original,
            expected_revision=0,
            actor_uid="owner-1",
            actor_email="owner@example.test",
        )

        with self.assertRaises(WebcamControlConflict):
            self.service.update_previews(
                [{"webcamId": original.webcams[1].id, "previewEnabled": False}],
                manifest=original,
                expected_revision=0,
                actor_uid="owner-2",
                actor_email="other@example.test",
            )

        state = self.service.admin_state(original)
        self.assertEqual(state["revision"], 1)
        self.assertFalse(state["webcams"][0]["previewEnabled"])
        self.assertTrue(state["webcams"][1]["previewEnabled"])

    def test_unknown_duplicate_and_link_only_changes_are_rejected(self):
        original = manifest()
        invalid_cases = (
            ([{"webcamId": "missing", "previewEnabled": False}], "webcam_control_unknown_id"),
            ([
                {"webcamId": original.webcams[0].id, "previewEnabled": False},
                {"webcamId": original.webcams[0].id, "previewEnabled": True},
            ], "webcam_control_duplicate_id"),
            ([{"webcamId": "link-only", "previewEnabled": False}], "webcam_control_preview_not_available"),
        )
        for changes, code in invalid_cases:
            with self.subTest(code=code), self.assertRaises(WebcamControlValidationError) as error:
                validate_control_changes(changes, manifest=original)
            self.assertEqual(str(error.exception), code)

    def test_unavailable_control_storage_fails_closed_to_fallbacks(self):
        original = manifest()
        service = WebcamControlService(FailingRepository(), cache_seconds=0)

        controlled = service.apply_public_controls(original)

        self.assertIsNone(controlled.webcams[0].imageUrl)
        self.assertIsNone(controlled.webcams[0].mediaType)
        self.assertEqual(controlled.webcams[0].fallbackImageUrl, original.webcams[0].fallbackImageUrl)
        self.assertIsNone(controlled.webcams[1].playerUrl)
        self.assertEqual(controlled.webcams[2], original.webcams[2])


if __name__ == "__main__":
    unittest.main()
