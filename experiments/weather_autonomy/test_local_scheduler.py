from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from local_pipeline.contract_v1 import CAMS_POLLEN_PROVIDER, CAMS_PROVIDER, ICON_PROVIDER
from local_pipeline.job_outcomes import JobKind, JobResult, JobStatus
from local_pipeline.local_scheduler import (
    LocalScheduler,
    ProviderSchedule,
    RetryPolicy,
    ScheduledAttempt,
    SchedulerClockRegression,
    SchedulerLeaseLost,
    SchedulerState,
    SQLiteSchedulerStore,
)


UTC = timezone.utc


class FakeClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value

    def advance(self, *, seconds: int = 0, hours: int = 0) -> None:
        self.value += timedelta(seconds=seconds, hours=hours)


def _schedule(
    job: JobKind, *slots: str
) -> ProviderSchedule:
    return ProviderSchedule(job, tuple(slots or ("12:00:00Z",)))


def _no_op(job: JobKind, reason: str = "already_current", **kwargs: object) -> JobResult:
    return JobResult(job, JobStatus.NO_OP, reason, **kwargs)


def _published(job: JobKind, run_id: str) -> JobResult:
    providers = (
        (ICON_PROVIDER,)
        if job is JobKind.ICON
        else (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER)
    )
    return JobResult(
        job,
        JobStatus.PUBLISHED,
        "published",
        source_run_id=run_id,
        published_providers=providers,
    )


class LocalSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="local-scheduler-test-")
        self.root = Path(self.temporary.name)
        self.path = self.root / "scheduler.sqlite3"
        self.clock = FakeClock(datetime(2026, 9, 5, 12, 30, tzinfo=UTC))
        self.policy = RetryPolicy(
            lease_seconds=10,
            max_attempts=3,
            backoff_base_seconds=5,
            max_backoff_seconds=7,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _controller(
        self,
        *,
        store: SQLiteSchedulerStore | None = None,
        owner: str = "worker-a",
        schedules: tuple[ProviderSchedule, ...] | None = None,
        runners: dict[JobKind, object] | None = None,
    ) -> LocalScheduler:
        selected_schedules = schedules or (_schedule(JobKind.ICON),)
        selected_runners = runners or {JobKind.ICON: lambda attempt: _no_op(attempt.job)}
        return LocalScheduler(
            store or SQLiteSchedulerStore(self.path),
            schedules=selected_schedules,
            runners=selected_runners,  # type: ignore[arg-type]
            owner_id=owner,
            policy=self.policy,
            clock=self.clock,
        )

    def test_two_workers_claim_one_provider_slot_only_once(self):
        store_a = SQLiteSchedulerStore(self.path)
        store_b = SQLiteSchedulerStore(self.path)
        calls: list[ScheduledAttempt] = []
        nested_actions: list[str] = []

        worker_b = self._controller(
            store=store_b,
            owner="worker-b",
            runners={
                JobKind.ICON: lambda attempt: self.fail("second worker ran a live slot")
            },
        )

        def first_runner(attempt: ScheduledAttempt) -> JobResult:
            calls.append(attempt)
            nested_actions.append(worker_b.run_due().outcomes[0].action)
            return _no_op(JobKind.ICON)

        worker_a = self._controller(
            store=store_a,
            runners={JobKind.ICON: first_runner},
        )
        cycle = worker_a.run_due()

        self.assertEqual("completed", cycle.outcomes[0].action)
        self.assertEqual(["lease_held"], nested_actions)
        self.assertEqual(1, len(calls))
        record = store_b.get(JobKind.ICON, "2026-09-05T12:00:00Z")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(SchedulerState.NO_OP, record.state)
        self.assertEqual(1, record.attempt_count)

    def test_crash_is_recovered_at_expiry_and_old_fence_cannot_complete(self):
        interrupted_attempts: list[ScheduledAttempt] = []

        def crash(attempt: ScheduledAttempt) -> JobResult:
            interrupted_attempts.append(attempt)
            raise RuntimeError("private path and credential must not escape")

        store_a = SQLiteSchedulerStore(self.path)
        worker_a = self._controller(store=store_a, runners={JobKind.ICON: crash})
        first = worker_a.run_due()
        self.assertEqual("runner_interrupted", first.outcomes[0].action)

        replacement_calls: list[ScheduledAttempt] = []

        def replacement(attempt: ScheduledAttempt) -> JobResult:
            replacement_calls.append(attempt)
            return _no_op(JobKind.ICON, "recovered")

        store_b = SQLiteSchedulerStore(self.path)
        worker_b = self._controller(
            store=store_b,
            owner="worker-b",
            runners={JobKind.ICON: replacement},
        )
        self.clock.advance(seconds=9)
        self.assertEqual("lease_held", worker_b.run_due().outcomes[0].action)
        self.clock.advance(seconds=1)
        recovered = worker_b.run_due()

        self.assertEqual("completed", recovered.outcomes[0].action)
        self.assertTrue(recovered.outcomes[0].recovered_lease)
        self.assertEqual(2, replacement_calls[0].attempt)
        self.assertEqual(2, replacement_calls[0].fencing_token)
        with self.assertRaises(SchedulerLeaseLost):
            store_a.complete(
                interrupted_attempts[0],
                _no_op(JobKind.ICON),
                policy=self.policy,
                now=self.clock(),
            )

    def test_completion_at_exact_lease_expiry_fails_closed(self):
        store = SQLiteSchedulerStore(self.path)
        claim = store.claim(
            JobKind.ICON,
            "2026-09-05T12:00:00Z",
            owner_id="worker-a",
            policy=self.policy,
            now=self.clock(),
        )
        assert claim.scheduled_attempt is not None
        self.clock.advance(seconds=10)
        with self.assertRaises(SchedulerLeaseLost):
            store.complete(
                claim.scheduled_attempt,
                _no_op(JobKind.ICON),
                policy=self.policy,
                now=self.clock(),
            )

    def test_expired_old_slot_is_superseded_with_a_provider_wide_new_fence(self):
        store = SQLiteSchedulerStore(self.path)
        old = store.claim(
            JobKind.ICON,
            "2026-09-05T12:00:00Z",
            owner_id="crashed-old-worker",
            policy=self.policy,
            now=self.clock(),
        )
        assert old.scheduled_attempt is not None

        self.clock.value = datetime(2026, 9, 5, 18, 0, tzinfo=UTC)
        new_attempts: list[ScheduledAttempt] = []

        def runner(attempt: ScheduledAttempt) -> JobResult:
            new_attempts.append(attempt)
            return _no_op(attempt.job)

        controller = self._controller(
            store=store,
            owner="new-slot-worker",
            schedules=(_schedule(JobKind.ICON, "12:00:00Z", "18:00:00Z"),),
            runners={JobKind.ICON: runner},
        )
        controller.run_due()
        self.assertGreater(
            new_attempts[0].fencing_token, old.scheduled_attempt.fencing_token
        )
        old_record = store.get(JobKind.ICON, "2026-09-05T12:00:00Z")
        assert old_record is not None
        self.assertEqual(SchedulerState.SUPERSEDED, old_record.state)
        with self.assertRaises(SchedulerLeaseLost):
            store.complete(
                old.scheduled_attempt,
                _no_op(JobKind.ICON),
                policy=self.policy,
                now=self.clock(),
            )

    def test_repeated_crashes_end_in_manual_review_at_attempt_bound(self):
        policy = RetryPolicy(
            lease_seconds=10,
            max_attempts=2,
            backoff_base_seconds=1,
            max_backoff_seconds=1,
        )
        calls: list[int] = []

        def crash(attempt: ScheduledAttempt) -> JobResult:
            calls.append(attempt.attempt)
            raise RuntimeError("never serialize this failure")

        store = SQLiteSchedulerStore(self.path)
        controller = LocalScheduler(
            store,
            schedules=(_schedule(JobKind.ICON),),
            runners={JobKind.ICON: crash},
            owner_id="crash-recovery-worker",
            policy=policy,
            clock=self.clock,
        )
        self.assertEqual("runner_interrupted", controller.run_due().outcomes[0].action)
        self.clock.advance(seconds=10)
        self.assertEqual("runner_interrupted", controller.run_due().outcomes[0].action)
        self.clock.advance(seconds=10)
        exhausted = controller.run_due()
        self.assertEqual("lease_recovery_exhausted", exhausted.outcomes[0].action)
        self.assertEqual(SchedulerState.MANUAL_REVIEW, exhausted.outcomes[0].state)
        self.assertEqual(1, exhausted.metrics["terminal_failures"])
        self.assertEqual([1, 2], calls)
        record = store.get(JobKind.ICON, "2026-09-05T12:00:00Z")
        assert record is not None
        self.assertIsNone(record.result_status)
        self.assertEqual("lease_recovery_exhausted", record.reason_code)
        self.clock.advance(seconds=10)
        self.assertEqual("already_terminal", controller.run_due().outcomes[0].action)
        self.assertEqual([1, 2], calls)

    def test_retry_delay_and_attempt_count_are_bounded_without_sleep(self):
        calls: list[int] = []

        def runner(attempt: ScheduledAttempt) -> JobResult:
            calls.append(attempt.attempt)
            if attempt.attempt == 2:
                return JobResult(
                    JobKind.ICON,
                    JobStatus.RETRYABLE_FAILURE,
                    "provider_busy",
                    retry_after_seconds=100,
                )
            return JobResult(
                JobKind.ICON,
                JobStatus.RETRYABLE_FAILURE,
                "temporary_failure",
            )

        controller = self._controller(runners={JobKind.ICON: runner})
        first = controller.run_due()
        self.assertEqual("retry_scheduled", first.outcomes[0].action)
        self.assertEqual("2026-09-05T12:30:05Z", first.outcomes[0].next_attempt_at)

        self.clock.advance(seconds=4)
        self.assertEqual("retry_wait", controller.run_due().outcomes[0].action)
        self.clock.advance(seconds=1)
        second = controller.run_due()
        self.assertEqual("2026-09-05T12:30:12Z", second.outcomes[0].next_attempt_at)

        self.clock.advance(seconds=6)
        self.assertEqual("retry_wait", controller.run_due().outcomes[0].action)
        self.clock.advance(seconds=1)
        third = controller.run_due()
        self.assertEqual("completed", third.outcomes[0].action)
        self.assertEqual(SchedulerState.RETRY_EXHAUSTED, third.outcomes[0].state)
        self.assertEqual([1, 2, 3], calls)
        self.clock.advance(seconds=100)
        self.assertEqual("already_terminal", controller.run_due().outcomes[0].action)
        self.assertEqual([1, 2, 3], calls)

    def test_lowered_attempt_limit_classifies_waiting_retry_without_running_it(self):
        calls: list[int] = []

        def retry(attempt: ScheduledAttempt) -> JobResult:
            calls.append(attempt.attempt)
            return JobResult(
                attempt.job, JobStatus.RETRYABLE_FAILURE, "temporary_failure"
            )

        store = SQLiteSchedulerStore(self.path)
        self._controller(store=store, runners={JobKind.ICON: retry}).run_due()
        self.clock.advance(seconds=5)
        lowered = LocalScheduler(
            SQLiteSchedulerStore(self.path),
            schedules=(_schedule(JobKind.ICON),),
            runners={JobKind.ICON: retry},
            owner_id="worker-lowered-policy",
            policy=RetryPolicy(
                lease_seconds=10,
                max_attempts=1,
                backoff_base_seconds=5,
                max_backoff_seconds=7,
            ),
            clock=self.clock,
        )
        cycle = lowered.run_due()
        self.assertEqual("attempts_exhausted", cycle.outcomes[0].action)
        self.assertEqual(SchedulerState.RETRY_EXHAUSTED, cycle.outcomes[0].state)
        self.assertEqual(1, cycle.metrics["terminal_failures"])
        self.assertEqual([1], calls)

    def test_manual_review_and_permanent_failure_never_retry(self):
        calls = {JobKind.ICON: 0, JobKind.CAMS: 0}

        def icon(attempt: ScheduledAttempt) -> JobResult:
            calls[attempt.job] += 1
            return JobResult(
                attempt.job, JobStatus.MANUAL_REVIEW, "operator_decision_required"
            )

        def cams(attempt: ScheduledAttempt) -> JobResult:
            calls[attempt.job] += 1
            return JobResult(attempt.job, JobStatus.PERMANENT_FAILURE, "invalid_input")

        controller = self._controller(
            schedules=(_schedule(JobKind.ICON), _schedule(JobKind.CAMS)),
            runners={JobKind.ICON: icon, JobKind.CAMS: cams},
        )
        states = {outcome.job: outcome.state for outcome in controller.run_due().outcomes}
        self.assertEqual(SchedulerState.MANUAL_REVIEW, states[JobKind.ICON])
        self.assertEqual(SchedulerState.PERMANENT_FAILURE, states[JobKind.CAMS])
        self.clock.advance(seconds=100)
        controller.run_due()
        self.assertEqual({JobKind.ICON: 1, JobKind.CAMS: 1}, calls)

    def test_latest_only_catch_up_and_later_slot_supersedes_retry(self):
        calls: list[str] = []

        def runner(attempt: ScheduledAttempt) -> JobResult:
            calls.append(attempt.slot_utc)
            if len(calls) == 1:
                return JobResult(
                    attempt.job, JobStatus.RETRYABLE_FAILURE, "temporary_failure"
                )
            return _no_op(attempt.job)

        schedule = _schedule(
            JobKind.ICON,
            "00:00:00Z",
            "06:00:00Z",
            "12:00:00Z",
            "18:00:00Z",
        )
        store = SQLiteSchedulerStore(self.path)
        controller = self._controller(
            store=store,
            schedules=(schedule,),
            runners={JobKind.ICON: runner},
        )
        controller.run_due()
        self.assertEqual(["2026-09-05T12:00:00Z"], calls)
        self.assertIsNone(store.get(JobKind.ICON, "2026-09-05T00:00:00Z"))
        self.assertIsNone(store.get(JobKind.ICON, "2026-09-05T06:00:00Z"))

        self.clock.value = datetime(2026, 9, 5, 18, 0, tzinfo=UTC)
        second = controller.run_due()
        self.assertEqual("completed", second.outcomes[0].action)
        self.assertEqual(2, second.outcomes[0].fencing_token)
        self.assertEqual(
            ["2026-09-05T12:00:00Z", "2026-09-05T18:00:00Z"], calls
        )
        old = store.get(JobKind.ICON, "2026-09-05T12:00:00Z")
        assert old is not None
        self.assertEqual(SchedulerState.SUPERSEDED, old.state)
        controller.run_due()
        self.assertEqual(2, len(calls))

    def test_terminal_result_survives_store_reopen(self):
        calls: list[int] = []

        def runner(attempt: ScheduledAttempt) -> JobResult:
            calls.append(attempt.attempt)
            return _published(JobKind.ICON, "20260905T120000Z")

        self._controller(runners={JobKind.ICON: runner}).run_due()
        reopened = self._controller(
            store=SQLiteSchedulerStore(self.path),
            owner="worker-after-restart",
            runners={JobKind.ICON: runner},
        )
        cycle = reopened.run_due()
        self.assertEqual("already_terminal", cycle.outcomes[0].action)
        self.assertEqual([1], calls)
        self.assertEqual(SchedulerState.PUBLISHED, cycle.outcomes[0].state)

    def test_provider_exception_is_isolated_and_documents_are_redacted(self):
        secret = r"C:\private\token.json?api_key=do-not-log"

        def cams(attempt: ScheduledAttempt) -> JobResult:
            raise RuntimeError(secret)

        def icon(attempt: ScheduledAttempt) -> JobResult:
            return _no_op(
                JobKind.ICON,
                metrics={"diagnostic": secret},
            )

        controller = self._controller(
            schedules=(_schedule(JobKind.ICON), _schedule(JobKind.CAMS)),
            runners={JobKind.ICON: icon, JobKind.CAMS: cams},
        )
        cycle = controller.run_due()
        by_job = {outcome.job: outcome for outcome in cycle.outcomes}
        # CAMS sorts first, so this also proves a crashing first provider does
        # not prevent the next independent provider from completing.
        self.assertEqual("runner_interrupted", by_job[JobKind.CAMS].action)
        self.assertEqual(SchedulerState.NO_OP, by_job[JobKind.ICON].state)
        document = json.dumps(cycle.as_document(), sort_keys=True)
        self.assertNotIn(secret, document)
        self.assertNotIn(str(self.path), document)
        self.assertNotIn("worker-a", document)

    def test_wrong_or_non_result_is_terminal_manual_review(self):
        for name, invalid in (
            ("wrong_job", _no_op(JobKind.CAMS)),
            ("not_a_result", {"status": "published"}),
        ):
            with self.subTest(name=name):
                path = self.root / f"{name}.sqlite3"
                calls: list[object] = []

                def runner(attempt: ScheduledAttempt, value: object = invalid) -> object:
                    calls.append(value)
                    return value

                controller = self._controller(
                    store=SQLiteSchedulerStore(path),
                    runners={JobKind.ICON: runner},  # type: ignore[dict-item]
                )
                outcome = controller.run_due().outcomes[0]
                self.assertEqual(SchedulerState.MANUAL_REVIEW, outcome.state)
                self.assertEqual("invalid_runner_result", outcome.reason_code)
                controller.run_due()
                self.assertEqual(1, len(calls))

    def test_clock_is_canonical_and_regression_is_rejected(self):
        self.clock.value = datetime(2026, 9, 5, 12, 0, 0, 999999, tzinfo=UTC)
        controller = self._controller()
        cycle = controller.run_due()
        self.assertEqual("2026-09-05T12:00:00Z", cycle.observed_at)

        self.clock.value = datetime(2026, 9, 5, 11, 59, 59, tzinfo=UTC)
        with self.assertRaises(SchedulerClockRegression):
            controller.run_due()

        naive_path = self.root / "naive.sqlite3"
        naive = LocalScheduler(
            SQLiteSchedulerStore(naive_path),
            schedules=(_schedule(JobKind.ICON),),
            runners={JobKind.ICON: lambda attempt: _no_op(attempt.job)},
            owner_id="worker-naive",
            policy=self.policy,
            clock=lambda: datetime(2026, 9, 5, 12, 30),
        )
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            naive.run_due()

        far_clock = FakeClock(datetime(3000, 1, 1, 0, 0, 0, 999999, tzinfo=UTC))
        far = LocalScheduler(
            SQLiteSchedulerStore(self.root / "far-clock.sqlite3"),
            schedules=(_schedule(JobKind.ICON, "00:00:00Z"),),
            runners={JobKind.ICON: lambda attempt: _no_op(attempt.job)},
            owner_id="worker-far-clock",
            policy=self.policy,
            clock=far_clock,
        )
        far_cycle = far.run_due()
        self.assertEqual("3000-01-01T00:00:00Z", far_cycle.observed_at)
        self.assertEqual("3000-01-01T00:00:00Z", far_cycle.outcomes[0].slot_utc)

    def test_configuration_and_database_identity_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "sorted and unique"):
            _schedule(JobKind.ICON, "12:00:00Z", "06:00:00Z")
        with self.assertRaisesRegex(ValueError, "canonical"):
            _schedule(JobKind.ICON, "12:00Z")
        with self.assertRaises(ValueError):
            RetryPolicy(max_attempts=0)
        with self.assertRaises(ValueError):
            RetryPolicy(backoff_base_seconds=20, max_backoff_seconds=10)
        with self.assertRaisesRegex(ValueError, "supported range"):
            LocalScheduler(
                SQLiteSchedulerStore(self.root / "old-clock.sqlite3"),
                schedules=(_schedule(JobKind.ICON),),
                runners={JobKind.ICON: lambda attempt: _no_op(attempt.job)},
                owner_id="worker-old-clock",
                policy=self.policy,
                clock=lambda: datetime(1969, 12, 31, 23, 59, 59, tzinfo=UTC),
            ).run_due()

        foreign = self.root / "foreign.sqlite3"
        connection = sqlite3.connect(foreign)
        try:
            connection.execute("CREATE TABLE unrelated (value TEXT)")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaisesRegex(RuntimeError, "not an empty scheduler"):
            SQLiteSchedulerStore(foreign)


if __name__ == "__main__":
    unittest.main()
