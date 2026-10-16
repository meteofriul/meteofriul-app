import itertools
import unittest
from datetime import datetime, timezone

from app.contracts.live import (
    CommunityReportConfirmationCreate,
    CommunityReportCreate,
    CommunityReportDelete,
    CommunityReputationRequest,
)
from app.repositories.community import (
    REPUTATION_RETENTION_SECONDS,
    CommunityRepository,
)
from app.services.community import (
    COMMUNITY_GUIDELINES_POLICY_VERSION,
    REPUTATION_DAILY_AWARD_LIMIT,
    CommunityService,
)


NOW = 1786269600.0


class MutableClock:
    def __init__(self, value=NOW):
        self.value = float(value)

    def __call__(self):
        return self.value


class CommunityReputationTests(unittest.TestCase):
    def create_service(self, clock=None):
        ids = itertools.count(1)
        return CommunityService(
            repository=CommunityRepository(),
            now=clock or (lambda: NOW),
            report_id_factory=lambda: f"reputation-report-{next(ids)}",
        )

    @staticmethod
    def report(client_id, *, type_id="rain", place="Pordenone"):
        coordinates = {
            "Pordenone": (45.95689, 12.66051),
            "Cordenons": (45.9836, 12.70038),
        }
        lat, lon = coordinates[place]
        return CommunityReportCreate(
            type_id=type_id,
            lat=lat,
            lon=lon,
            selected_place=place,
            client_id=client_id,
            accepted_terms=True,
            policy_version=COMMUNITY_GUIDELINES_POLICY_VERSION,
        )

    @staticmethod
    def vote(client_id, vote="yes"):
        return CommunityReportConfirmationCreate(
            vote=vote,
            client_id=client_id,
            accepted_terms=True,
            policy_version=COMMUNITY_GUIDELINES_POLICY_VERSION,
        )

    @staticmethod
    def reputation(service, client_id):
        return service.get_reputation(
            CommunityReputationRequest(client_id=client_id),
            client_host="test",
        )

    def test_new_report_is_pending_and_withdrawal_before_validation_scores_zero(self):
        service = self.create_service()
        created = service.create_report(
            self.report("author"),
            client_host="test",
        )

        pending = self.reputation(service, "author")
        self.assertEqual(
            (pending.points, pending.validated_reports, pending.total_reports),
            (0, 0, 1),
        )
        self.assertEqual(pending.pending_reports, 1)

        service.delete_report(
            created.report.id,
            command=CommunityReportDelete(client_id="author"),
            client_host="test",
        )
        withdrawn = self.reputation(service, "author")
        self.assertEqual(
            (withdrawn.points, withdrawn.pending_reports, withdrawn.total_reports),
            (0, 0, 1),
        )

    def test_independent_yes_awards_only_author_once_and_later_no_does_not_revoke(self):
        service = self.create_service()
        created = service.create_report(self.report("author"), client_host="test")
        group_id = created.report.groupId

        service.confirm_report(group_id, self.vote("witness"), client_host="test")
        service.confirm_report(group_id, self.vote("witness"), client_host="test")
        service.confirm_report(
            group_id,
            self.vote("cessation-witness", "no"),
            client_host="test",
        )

        author = self.reputation(service, "author")
        witness = self.reputation(service, "witness")
        self.assertEqual((author.points, author.validated_reports), (1, 1))
        self.assertEqual(witness.points, 0)
        state = service.repository.get_confirmation(group_id)
        self.assertEqual(state["validity_status"], "verified")
        self.assertEqual(state["temporal_status"], "ceased")

    def test_no_before_validation_closes_pending_without_awarding_later(self):
        service = self.create_service()
        created = service.create_report(self.report("author"), client_host="test")
        group_id = created.report.groupId

        service.confirm_report(
            group_id,
            self.vote("cessation-witness", "no"),
            client_host="test",
        )
        closed = self.reputation(service, "author")
        self.assertEqual(
            (closed.points, closed.validated_reports, closed.pending_reports),
            (0, 0, 0),
        )

        service.confirm_report(
            group_id,
            self.vote("late-positive-witness", "yes"),
            client_host="test",
        )
        still_closed = self.reputation(service, "author")
        self.assertEqual((still_closed.points, still_closed.validated_reports), (0, 0))
        state = service.repository.get_confirmation(group_id)
        self.assertTrue(state["closed_unverified"])
        self.assertEqual(state["validity_status"], "unverified")

    def test_second_independent_report_awards_both_authors_once(self):
        service = self.create_service()
        first = service.create_report(self.report("author-a"), client_host="test")
        second = service.create_report(self.report("author-b"), client_host="test")

        self.assertEqual(first.report.groupId, second.report.groupId)
        for client_id in ("author-a", "author-b"):
            summary = self.reputation(service, client_id)
            self.assertEqual((summary.points, summary.validated_reports), (1, 1))
            self.assertEqual(summary.pending_reports, 0)

        # A later positive signal repairs/replays idempotently, never duplicating.
        service.confirm_report(
            first.report.groupId,
            self.vote("third-witness"),
            client_host="test",
        )
        self.assertEqual(self.reputation(service, "author-a").points, 1)

    def test_quiet_reports_are_neither_pending_nor_ranked(self):
        service = self.create_service()
        created = service.create_report(
            self.report("quiet-author", type_id="quiet"),
            client_host="test",
        )
        service.confirm_report(
            created.report.groupId,
            self.vote("quiet-witness"),
            client_host="test",
        )

        summary = self.reputation(service, "quiet-author")
        self.assertEqual(
            (
                summary.points,
                summary.validated_reports,
                summary.pending_reports,
                summary.total_reports,
            ),
            (0, 0, 0, 1),
        )

    def test_daily_cap_counts_validations_but_awards_only_three_points(self):
        clock = MutableClock()
        service = self.create_service(clock)
        for index in range(REPUTATION_DAILY_AWARD_LIMIT + 1):
            created = service.create_report(
                self.report("daily-author"),
                client_host="test",
            )
            service.confirm_report(
                created.report.groupId,
                self.vote(f"daily-witness-{index}"),
                client_host="test",
            )
            clock.value += 3601

        summary = self.reputation(service, "daily-author")
        self.assertEqual(summary.points, REPUTATION_DAILY_AWARD_LIMIT)
        self.assertEqual(
            summary.validated_reports,
            REPUTATION_DAILY_AWARD_LIMIT + 1,
        )
        self.assertEqual(
            summary.total_reports,
            REPUTATION_DAILY_AWARD_LIMIT + 1,
        )

    def test_revocation_is_idempotent_and_preserves_a_new_days_cap_counter(self):
        clock = MutableClock()
        service = self.create_service(clock)
        first = service.create_report(self.report("author"), client_host="test")
        service.confirm_report(
            first.report.groupId,
            self.vote("witness-one"),
            client_host="test",
        )

        clock.value += 24 * 60 * 60
        second = service.create_report(
            self.report("author", place="Cordenons"),
            client_host="test",
        )
        service.confirm_report(
            second.report.groupId,
            self.vote("witness-two"),
            client_host="test",
        )
        owner_key = service._client_key("community-report", "author")
        reputation_id = next(iter(service.repository._reputations))
        current_day = service._reputation_award_day(clock.value)
        self.assertEqual(
            service.repository._reputations[reputation_id]["daily_award_day"],
            current_day,
        )
        self.assertEqual(
            service.repository._reputations[reputation_id]["daily_awards"],
            1,
        )

        revoked = service.repository.revoke_group_reputation_memory(
            first.report.groupId,
            now=clock.value,
            reason="administrative_moderation",
        )
        repeated = service.repository.revoke_group_reputation_memory(
            first.report.groupId,
            now=clock.value,
            reason="administrative_moderation",
        )

        self.assertEqual((revoked, repeated), (1, 0))
        summary = self.reputation(service, "author")
        self.assertEqual((summary.points, summary.validated_reports), (1, 1))
        stored = service.repository._reputations[reputation_id]
        self.assertEqual(stored["daily_award_day"], current_day)
        self.assertEqual(stored["daily_awards"], 1)
        self.assertNotIn(first.report.groupId, str(service.repository._reputation_awards))
        self.assertTrue(owner_key)

    def test_reputation_documents_expire_and_reads_ignore_stale_totals(self):
        clock = MutableClock()
        service = self.create_service(clock)
        created = service.create_report(self.report("author"), client_host="test")
        service.confirm_report(
            created.report.groupId,
            self.vote("witness"),
            client_host="test",
        )

        summary_document = next(iter(service.repository._reputations.values()))
        award_document = next(iter(service.repository._reputation_awards.values()))
        expected_expiry = datetime.fromtimestamp(
            clock.value + REPUTATION_RETENTION_SECONDS,
            timezone.utc,
        )
        self.assertEqual(summary_document["expires_at_timestamp"], expected_expiry)
        self.assertEqual(award_document["expires_at_timestamp"], expected_expiry)

        clock.value += REPUTATION_RETENTION_SECONDS + 1
        expired = self.reputation(service, "author")
        self.assertEqual(
            (expired.points, expired.validated_reports, expired.total_reports),
            (0, 0, 0),
        )
        self.assertEqual(expired.retention_seconds, REPUTATION_RETENTION_SECONDS)

        owner_key = service._client_key("community-report", "author")
        service.repository.apply_group_reputation_memory(
            created.report.groupId,
            reports=[{
                "id": "replacement-validation",
                "group_id": created.report.groupId,
                "type_id": "rain",
                "owner_key": owner_key,
            }],
            confirmation_state={"yes": 1, "no": 0, "votes": {}},
            report_added=False,
            award_day=service._reputation_award_day(clock.value),
            daily_limit=REPUTATION_DAILY_AWARD_LIMIT,
            now=clock.value,
        )
        reusable = self.reputation(service, "author")
        self.assertEqual((reusable.points, reusable.validated_reports), (1, 1))

    def test_daily_cap_rolls_over_at_europe_rome_midnight(self):
        clock = MutableClock()
        service = self.create_service(clock)
        owner_key = service._client_key("community-report", "author")
        before_midnight = (
            datetime(2026, 9, 18, 19, 0, tzinfo=timezone.utc).timestamp(),
            datetime(2026, 9, 18, 20, 1, tzinfo=timezone.utc).timestamp(),
            datetime(2026, 9, 18, 21, 2, tzinfo=timezone.utc).timestamp(),
        )
        for index, instant in enumerate(before_midnight):
            service.repository.apply_group_reputation_memory(
                f"pre-midnight-{index}",
                reports=[{
                    "id": f"pre-midnight-report-{index}",
                    "group_id": f"pre-midnight-{index}",
                    "type_id": "rain",
                    "owner_key": owner_key,
                }],
                confirmation_state={"yes": 1, "no": 0, "votes": {}},
                report_added=False,
                award_day=service._reputation_award_day(instant),
                daily_limit=REPUTATION_DAILY_AWARD_LIMIT,
                now=instant,
            )

        after_midnight = datetime(
            2026,
            9,
            18,
            22,
            1,
            tzinfo=timezone.utc,
        ).timestamp()
        service.repository.apply_group_reputation_memory(
            "post-midnight",
            reports=[{
                "id": "post-midnight-report",
                "group_id": "post-midnight",
                "type_id": "rain",
                "owner_key": owner_key,
            }],
            confirmation_state={"yes": 1, "no": 0, "votes": {}},
            report_added=False,
            award_day=service._reputation_award_day(after_midnight),
            daily_limit=REPUTATION_DAILY_AWARD_LIMIT,
            now=after_midnight,
        )

        stored = next(iter(service.repository._reputations.values()))
        self.assertEqual(stored["points"], 4)
        self.assertEqual(stored["validated_reports"], 4)
        self.assertEqual(stored["daily_award_day"], "2026-09-19")
        self.assertEqual(stored["daily_awards"], 1)

    def test_rank_thresholds_use_validated_points(self):
        novice = CommunityService._reputation_rank(4)
        lookout = CommunityService._reputation_rank(5)
        lookout_max = CommunityService._reputation_rank(19)
        sentinel = CommunityService._reputation_rank(20)

        self.assertEqual((novice.id, novice.label), ("novice", "Osservadôr dal Cîl"))
        self.assertEqual((lookout.id, lookout.label), ("lookout", "Vuaite dal Timp"))
        self.assertEqual((lookout_max.id, lookout_max.label), ("lookout", "Vuaite dal Timp"))
        self.assertEqual(
            (sentinel.id, sentinel.label),
            ("sentinel", "Sentinele dal Teritori"),
        )


if __name__ == "__main__":
    unittest.main()
