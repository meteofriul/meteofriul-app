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
        # 10 UTC publishes the regional family. UV is requested only after its
        # observed availability window; 20 UTC remains the recovery pass.
        self.assertEqual(cams['schedule'], '0 10,15,20 * * *')
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
