import json
from pathlib import Path
from unittest import TestCase


class ProductionRuntimeContractTests(TestCase):
    def test_cams_uses_official_reader_and_durable_recovery_slots(self):
        config = json.loads((Path(__file__).parent / 'production-runtime.json').read_text())
        self.assertEqual(config['project'], 'meteo-friul')
        self.assertEqual(config['region'], 'europe-west1')
        self.assertEqual(
            config['public_reader_base_url'],
            'https://meteofriul-weather-49007668366.europe-west1.run.app',
        )
        cams = config['jobs']['cams']
        self.assertEqual(cams['cloud_run_job'], 'meteofriul-cams')
        self.assertEqual(cams['cloud_scheduler_job'], 'meteofriul-cams-refresh')
        self.assertEqual(cams['environment_file'], 'production-cams.env.yaml')
        # ADS advertises full horizon at 08:30 UTC; ECMWF guarantees it by
        # 10 UTC. Probe at 09, retry at 10/11, preserve both UV windows.
        from cams_runtime import (SCHEDULE_HOURS_UTC, TASK_TIMEOUT_SECONDS,
            RECOVERY_BUDGET_SECONDS, ADS_WAIT_SECONDS, REGIONAL_PASS_RESERVE_SECONDS,
            UV_PASS_RESERVE_SECONDS)
        self.assertEqual(cams['schedule'], '0 ' + ','.join(map(str, SCHEDULE_HOURS_UTC)) + ' * * *')
        self.assertEqual(SCHEDULE_HOURS_UTC, (9, 10, 11, 15, 20))
        self.assertEqual(cams['task_timeout_seconds'], TASK_TIMEOUT_SECONDS)
        self.assertEqual(cams['recovery_budget_seconds'], RECOVERY_BUDGET_SECONDS)
        self.assertEqual(cams['ads_wait_seconds'], ADS_WAIT_SECONDS)
        self.assertEqual(cams['regional_pass_reserve_seconds'], REGIONAL_PASS_RESERVE_SECONDS)
        self.assertEqual(cams['uv_pass_reserve_seconds'], UV_PASS_RESERVE_SECONDS)
        self.assertGreaterEqual(TASK_TIMEOUT_SECONDS - RECOVERY_BUDGET_SECONDS, 300)
        self.assertGreaterEqual(REGIONAL_PASS_RESERVE_SECONDS - ADS_WAIT_SECONDS, 300)
        self.assertLess(TASK_TIMEOUT_SECONDS, 3600)
        self.assertEqual(cams['max_retries'], 0)
        self.assertEqual(cams['scheduler_retry_count'], 0)
        self.assertEqual(cams['time_zone'], 'Etc/UTC')
        self.assertEqual(
            cams['environment']['WEATHER_PUBLIC_BASE_URL'],
            config['public_reader_base_url'],
        )
        self.assertEqual(cams['environment']['WEATHER_UV_UTC_HOURS'], '15,20')
        environment = (Path(__file__).parent / cams['environment_file']).read_text()
        for line in (
            'GOOGLE_CLOUD_PROJECT: meteo-friul',
            'WEATHER_CLOUD_PROJECT: meteo-friul',
            'WEATHER_DATA_BUCKET: meteo-friul-weather-data',
            'WEATHER_STATE_BUCKET: meteo-friul-weather-state',
            'WEATHER_OBJECT_PREFIX: pilot',
            'WEATHER_PROVIDER: cams',
            "WEATHER_UV_ENABLED: '1'",
            "WEATHER_STATE_MIGRATED: '1'",
            'WEATHER_PUBLIC_BASE_URL: https://meteofriul-weather-49007668366.europe-west1.run.app',
            "WEATHER_UV_UTC_HOURS: '15,20'",
        ):
            self.assertIn(line, environment)
