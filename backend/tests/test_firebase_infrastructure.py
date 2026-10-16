import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

import firebase_admin
from firebase_admin import app_check, firestore

from app.infrastructure.app_check import verify_firebase_app_check_token
from app.infrastructure.firebase import (
    FirebaseInitializationError,
    get_firebase_app,
    get_firestore_client,
    reset_firestore_client_for_tests,
)


class FirebaseInfrastructureTests(unittest.TestCase):
    def setUp(self):
        reset_firestore_client_for_tests()

    def tearDown(self):
        reset_firestore_client_for_tests()

    def test_concurrent_callers_initialize_one_shared_firebase_app(self):
        firebase_app = SimpleNamespace(project_id="meteo-friul")
        credential = object()

        def initialize_app(_credential, _options):
            time.sleep(0.01)
            return firebase_app

        with (
            patch.object(firebase_admin, "get_app", side_effect=ValueError),
            patch.object(
                firebase_admin,
                "initialize_app",
                side_effect=initialize_app,
            ) as initialize,
            patch(
                "app.infrastructure.firebase._build_credential",
                return_value=credential,
            ),
            patch.dict(os.environ, {"FIREBASE_PROJECT_ID": "meteo-friul"}),
            ThreadPoolExecutor(max_workers=8) as executor,
        ):
            apps = list(executor.map(lambda _: get_firebase_app(), range(16)))

        self.assertTrue(all(app is firebase_app for app in apps))
        initialize.assert_called_once_with(
            credential,
            {"projectId": "meteo-friul"},
        )

    def test_initialization_failure_does_not_poison_later_retry(self):
        firebase_app = SimpleNamespace(project_id="meteo-friul")

        with (
            patch.object(firebase_admin, "get_app", side_effect=ValueError),
            patch.object(
                firebase_admin,
                "initialize_app",
                side_effect=[OSError("temporary"), firebase_app],
            ) as initialize,
            patch(
                "app.infrastructure.firebase._build_credential",
                return_value=object(),
            ),
        ):
            with self.assertRaises(FirebaseInitializationError):
                get_firebase_app()
            recovered_app = get_firebase_app()

        self.assertIs(recovered_app, firebase_app)
        self.assertEqual(initialize.call_count, 2)

    def test_firestore_client_failure_can_retry_without_reinitializing_app(self):
        firebase_app = SimpleNamespace(project_id="meteo-friul")
        firestore_client = object()
        environment = {
            "COMMUNITY_STORAGE": "firestore",
            "FIREBASE_PROJECT_ID": "meteo-friul",
        }

        with (
            patch.object(
                firebase_admin,
                "get_app",
                return_value=firebase_app,
            ) as get_app,
            patch.object(
                firestore,
                "client",
                side_effect=[OSError("temporary"), firestore_client],
            ) as create_client,
            patch.dict(os.environ, environment),
        ):
            self.assertIsNone(get_firestore_client())
            recovered_client = get_firestore_client()

        self.assertIs(recovered_client, firestore_client)
        get_app.assert_called_once_with()
        self.assertEqual(create_client.call_count, 2)

    def test_firestore_and_app_check_reuse_the_same_initialized_app(self):
        firebase_app = SimpleNamespace(project_id="meteo-friul")
        firestore_client = object()
        claims = {"app_id": "1:1234567890:android:abcdef"}
        environment = {
            "COMMUNITY_STORAGE": "firestore",
            "FIREBASE_PROJECT_ID": "meteo-friul",
        }

        with (
            patch.object(
                firebase_admin,
                "get_app",
                return_value=firebase_app,
            ) as get_app,
            patch.object(
                firestore,
                "client",
                return_value=firestore_client,
            ) as create_client,
            patch.object(
                app_check,
                "verify_token",
                return_value=claims,
            ) as verify_token,
            patch.dict(os.environ, environment),
        ):
            actual_firestore_client = get_firestore_client()
            actual_claims = verify_firebase_app_check_token("pilot-token")

        self.assertIs(actual_firestore_client, firestore_client)
        self.assertEqual(actual_claims, claims)
        get_app.assert_called_once_with()
        create_client.assert_called_once_with(firebase_app)
        verify_token.assert_called_once_with("pilot-token", app=firebase_app)


if __name__ == "__main__":
    unittest.main()
