import json
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).parent


class RecoveryPlanContractTests(TestCase):
    def setUp(self):
        self.plan = json.loads((ROOT / 'icon-recovery-plan.json').read_text(encoding='utf-8'))

    def test_scheduled_hours_match_worker_policy_and_bounded_offsets(self):
        from local_pipeline.icon_recovery import (
            BASE_HOURS_UTC, RECOVERY_OFFSETS_HOURS, SCHEDULE_HOURS_UTC,
            FEATURE_FLAG, MAX_DISCOVERY_ATTEMPTS,
        )
        schedule = self.plan['schedule']
        self.assertEqual(schedule['time_zone'], 'Etc/UTC')
        self.assertEqual(tuple(schedule['base_hours_utc']), BASE_HOURS_UTC)
        self.assertEqual(tuple(schedule['offsets_hours']), RECOVERY_OFFSETS_HOURS)
        expected_hours = tuple(base + delay for base in BASE_HOURS_UTC for delay in RECOVERY_OFFSETS_HOURS)
        self.assertEqual(expected_hours, SCHEDULE_HOURS_UTC)
        self.assertEqual(tuple(schedule['hours_utc']), expected_hours)
        self.assertEqual(schedule['proposed_cron'], '0 ' + ','.join(map(str, expected_hours)) + ' * * *')
        self.assertEqual(self.plan['feature']['environment_variable'], FEATURE_FLAG)
        self.assertEqual(self.plan['budget']['max_discovery_attempts_per_ticket'], MAX_DISCOVERY_ATTEMPTS)
        self.assertEqual(len(RECOVERY_OFFSETS_HOURS) - 1, 3)
        self.assertEqual(max(RECOVERY_OFFSETS_HOURS), 4)

    def test_budget_counts_task_retries_separately_from_scheduler_starts(self):
        schedule = self.plan['schedule']
        products = self.plan['products']
        budget = self.plan['budget']
        hours = len(schedule['hours_utc'])
        self.assertEqual(budget['proposed_scheduled_starts_per_day'], hours * len(products))
        self.assertEqual(budget['current_scheduled_starts_per_day'], len(schedule['base_hours_utc']) * len(products))
        self.assertEqual(budget['additional_scheduled_starts_per_day'],
                         budget['proposed_scheduled_starts_per_day'] - budget['current_scheduled_starts_per_day'])
        self.assertEqual(budget['max_scheduled_task_attempts_per_day_including_platform_retries'],
                         sum(hours * (p['cloud_run_max_retries'] + 1) for p in products))
        self.assertEqual(schedule['scheduler_retry_count'], 0)
        self.assertFalse(budget['monetary_cost_measured'])

    def test_activation_is_explicit_and_preserves_existing_jobs_and_state(self):
        self.assertEqual(self.plan['status'], 'LOCAL_REVIEW_ONLY_NOT_APPLIED')
        self.assertFalse(self.plan['feature']['default_enabled'])
        self.assertFalse(self.plan['cloud_changes_applied'])
        self.assertFalse(self.plan['app_build_required'])
        self.assertEqual({p['cloud_run_job'] for p in self.plan['products']},
                         {'meteofriul-icon', 'meteofriul-national-icon'})
        activation = self.plan['activation']
        self.assertTrue(activation['requires_separate_owner_authorization'])
        self.assertTrue(activation['quiescent_legacy_executions_required'])
        self.assertFalse(activation['mixed_old_new_workers_allowed'])
        self.assertFalse(activation['legacy_claim_deletion_allowed'])
        self.assertFalse(activation['automatic_claim_takeover_allowed'])
        self.assertEqual(activation['approved_steps'], [])
        for product in self.plan['products']:
            self.assertTrue((ROOT / product['build_definition']).is_file())
