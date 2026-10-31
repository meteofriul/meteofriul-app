"""Independent offline checks for lost acknowledgements at durable boundaries.

The object store commits real SQLite transactions before simulating the lost
GCS response. No Cloud SDK, network, sleep or credentials are required.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import Mock

from local_pipeline.contract_v1 import canonical_json_bytes
from local_pipeline.gcs_object_store import RemoteObjectStoreError
from local_pipeline.icon_recovery import FenceLost, Recovery, result
from local_pipeline.sqlite_object_store import SQLiteObjectStore


NOW = datetime(2026, 10, 31, 6, tzinfo=timezone.utc)
RUN = "20261031T000000Z"
SLOT = "20261031-am"


class LostAcknowledgementStore(SQLiteObjectStore):
    def __init__(self, path, target, *, competing_owner=False):
        super().__init__(path)
        self.target = target
        self.competing_owner = competing_owner
        self.losses = 0
        self.winner = None

    def _after_commit(self, key, body, head):
        document = json.loads(body)
        matches = (
            self.target == "cycle_claim" and key.endswith("/acquisition.json")
            or self.target == "execution_binding" and "/executions/" in key
            or self.target == "ready_poll" and "/polls/" in key and document.get("status") == "ready"
            or key.endswith("/active.json") and self.target == "active_" + document.get("phase", "")
        )
        if self.losses or not matches:
            return head
        self.losses += 1
        if self.competing_owner:
            self.winner = {**document, "execution": "concurrent-owner", "fence": "f" * 32}
            # A second real CAS wins before the first caller sees its response.
            SQLiteObjectStore.compare_and_swap(
                self, key, canonical_json_bytes(self.winner), expected_etag=head.etag,
                content_type="application/json",
            )
        raise RemoteObjectStoreError(
            "response lost after commit", original_type="ServiceUnavailable",
            http_status=503, operation="upload", object_key=key, retryable=True,
        )

    def put(self, key, body, **kwargs):
        head = super().put(key, body, **kwargs)
        return self._after_commit(key, body, head)

    def compare_and_swap(self, key, body, **kwargs):
        head = super().compare_and_swap(key, body, **kwargs)
        return self._after_commit(key, body, head)


class RecoveryAcknowledgementTests(TestCase):
    def scenario(self, state, product):
        controller = Recovery(state, product)
        checkpoints = {}
        published = set()

        def freeze(cycle, slot):
            frozen = {"cycle": cycle}
            checkpoints[(cycle, slot)] = frozen
            return frozen

        def commit(frozen):
            published.add(frozen["cycle"])
            return result("published", "publication_committed", frozen["cycle"])

        acquire = Mock(side_effect=freeze)
        publish = Mock(side_effect=commit)
        discover = Mock(return_value="2026103100")

        def run(execution="original-owner"):
            water = max(published) if published else None
            return controller.run(
                now=NOW, execution=execution, high_water=water, verified_run=water,
                discover=discover, checkpoint=lambda cycle, slot: checkpoints.get((cycle, slot)),
                acquire=acquire, publish=publish, verify=lambda cycle: cycle in published,
            )

        return controller, run, acquire, publish, discover

    def assert_lost_success_reconciles(self, target):
        for product in ("fvg", "national"):
            with self.subTest(product=product, target=target), TemporaryDirectory() as directory:
                state = LostAcknowledgementStore(Path(directory) / "state.sqlite", target)
                controller, run, acquire, publish, discover = self.scenario(state, product)
                self.assertEqual(run()["status"], "published")
                self.assertEqual(state.losses, 1, "The simulated response loss must be exercised")
                self.assertEqual(controller.active().record["phase"], "completed")
                self.assertEqual(run("later-owner")["reason"], "publication_already_verified")
                acquire.assert_called_once_with(RUN, SLOT)
                publish.assert_called_once()
                discover.assert_called_once()
                self.assertEqual(len(state.list_keys(controller.prefix + "runs/")), 1)

    def test_lost_producer_claim_success_does_not_strand_unstarted_acquisition(self):
        self.assert_lost_success_reconciles("active_acquiring")

    def test_lost_cycle_claim_success_does_not_download_again(self):
        self.assert_lost_success_reconciles("cycle_claim")

    def test_lost_checkpoint_transition_success_uses_durable_checkpoint(self):
        self.assert_lost_success_reconciles("active_checkpointed")

    def test_lost_completion_transition_success_is_reconciled(self):
        self.assert_lost_success_reconciles("active_completed")

    def test_lost_execution_binding_success_keeps_one_probe_budget(self):
        self.assert_lost_success_reconciles("execution_binding")

    def test_lost_ready_poll_success_does_not_probe_twice(self):
        self.assert_lost_success_reconciles("ready_poll")

    def test_concurrent_winner_is_not_accepted_as_own_lost_response(self):
        with TemporaryDirectory() as directory:
            state = LostAcknowledgementStore(
                Path(directory) / "state.sqlite", "active_acquiring", competing_owner=True,
            )
            controller, run, acquire, publish, _discover = self.scenario(state, "fvg")
            with self.assertRaises(FenceLost):
                run()
            self.assertEqual(state.losses, 1)
            self.assertEqual(controller.active().record, state.winner)
            acquire.assert_not_called()
            publish.assert_not_called()

    def test_existing_different_cycle_claim_is_preserved_and_blocks_download(self):
        with TemporaryDirectory() as directory:
            state = SQLiteObjectStore(Path(directory) / "state.sqlite")
            controller, run, acquire, publish, _discover = self.scenario(state, "national")
            key = controller.prefix + f"runs/{RUN}/acquisition.json"
            other = canonical_json_bytes({
                "schema_version": 1, "product": "national", "phase": "acquiring",
                "source_run_id": RUN, "slot": SLOT, "execution": "previous-owner", "fence": "a" * 32,
            })
            state.put(key, other, content_type="application/json")
            with self.assertRaises((ValueError, FenceLost)):
                run()
            self.assertEqual(state.get(key).body, other)
            self.assertEqual(controller.active().record["phase"], "manual_review")
            acquire.assert_not_called()
            publish.assert_not_called()


if __name__ == "__main__":
    main()
