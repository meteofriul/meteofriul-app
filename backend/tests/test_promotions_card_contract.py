"""Synthetic API fixtures shared with the current and frozen Android 0.1.14 clients."""
import copy
from datetime import datetime
import itertools
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.api.promotions import get_promotion_service
from app.main import create_app
from app.services.promotions import (
    PromotionRepository, PromotionService, PromotionValidationError,
    build_public_catalog, sanitize_admin_state,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures/promotions_card_contract.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(FIXTURE["now"])
FIELDS = {"businessName": "title", "category": "category", "address": "businessAddress",
          "city": "location", "title": "headline", "description": "text"}


class PromotionCardContractTests(unittest.TestCase):
    def test_admin_roundtrip_and_public_api_match_shared_client_fixtures(self):
        for case in FIXTURE["cases"]:
            with self.subTest(case=case["name"]):
                state = copy.deepcopy(FIXTURE["adminState"])
                if "selection" in case:
                    state["campaigns"][0]["cardVisibleFields"] = case["selection"]
                if case.get("emptyHiddenText"):
                    state["campaigns"][0].update(title="", description="")
                service = PromotionService(PromotionRepository(lambda: None))
                app = create_app()
                app.dependency_overrides[get_promotion_service] = lambda: service
                with TestClient(app) as client, patch.dict(os.environ, {
                    "ADS_ADMIN_AUTH_MODE": "local", "ADS_ADMIN_LOCAL_TOKEN": "synthetic-test-token",
                    "K_SERVICE": "",
                }), patch("app.services.promotions.datetime") as clock:
                    clock.now.return_value = NOW
                    clock.strptime = datetime.strptime
                    saved = client.put("/api/admin/promotions/state", json={"expectedRevision": 0, "state": state},
                                       headers={"Authorization": "Bearer synthetic-test-token"})
                    self.assertEqual(saved.status_code, 200)
                    self.assertEqual(saved.json()["state"]["campaigns"][0]["internalNotes"], "SYNTHETIC-PRIVATE-NOTE")
                    response = client.get("/api/promotions/catalog")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.headers["etag"], '\"promotions-1\"')
                    self.assertEqual(response.headers["cache-control"], "public, max-age=60, must-revalidate")
                    self.assertEqual(response.json(), case["catalog"])
                    for private in ("SYNTHETIC-PRIVATE-NOTE", "SYNTHETIC-PRIVATE-INVOICE", "private-contact@example.test"):
                        self.assertNotIn(private, response.text)
                    self.assertEqual(client.get("/api/admin/promotions/state").status_code, 401)

    def test_every_field_combination_masks_hidden_text_and_preserves_campaign_identity(self):
        identities = set()
        for size in range(1, len(FIELDS) + 1):
            for selection in itertools.combinations(FIELDS, size):
                with self.subTest(selection=selection):
                    state = copy.deepcopy(FIXTURE["adminState"])
                    state["campaigns"][0]["cardVisibleFields"] = list(selection)
                    catalog = build_public_catalog(sanitize_admin_state(state), revision=1, now=NOW)
                    public = catalog["campaigns"][0]
                    identities.add((public["id"], public["advertiserId"]))
                    self.assertEqual(public["visibleFields"], list(selection))
                    for selected, field in FIELDS.items():
                        self.assertEqual(bool(public[field]), selected in selection)
                    self.assertEqual(public["placements"], ["home", "events", "discover"])
        self.assertEqual(len(identities), 1)

    def test_selection_is_allowlisted_deduplicated_and_cannot_enable_empty_active_card(self):
        state = copy.deepcopy(FIXTURE["adminState"])
        campaign = state["campaigns"][0]
        campaign["cardVisibleFields"] = ["businessName", "invoiceNumber", " businessName "]
        self.assertEqual(sanitize_admin_state(state)["campaigns"][0]["cardVisibleFields"], ["businessName"])
        for selection in ([], ["invoiceNumber"]):
            campaign["cardVisibleFields"] = selection
            with self.assertRaises(PromotionValidationError):
                sanitize_admin_state(state)
