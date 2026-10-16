import os
import unittest
from unittest.mock import patch

from app.infrastructure.open_meteo_policy import (
    LOCAL_WEATHER_PILOT_ENV,
    OPEN_METEO_ENABLED_ENV,
    OpenMeteoDisabled,
    ProviderPolicyConfigurationError,
    is_loopback_hostname,
    local_weather_pilot_ready,
    open_meteo_enabled,
    provider_policy_status,
    require_open_meteo_enabled,
)


class OpenMeteoPolicyTests(unittest.TestCase):
    def test_unconfigured_production_default_keeps_open_meteo_disabled(self):
        with patch.dict(os.environ, {}, clear=False):
            with patch.dict(
                os.environ,
                {
                    LOCAL_WEATHER_PILOT_ENV: "",
                    OPEN_METEO_ENABLED_ENV: "",
                },
            ):
                self.assertFalse(open_meteo_enabled())
                self.assertFalse(local_weather_pilot_ready())

    def test_local_pilot_requires_explicit_pilot_and_provider_switches(self):
        with patch.dict(
            os.environ,
            {
                LOCAL_WEATHER_PILOT_ENV: "1",
                OPEN_METEO_ENABLED_ENV: "0",
            },
        ):
            self.assertTrue(local_weather_pilot_ready())
            self.assertEqual(
                provider_policy_status(),
                {
                    "valid": True,
                    "error": None,
                    "local_weather_pilot_requested": True,
                    "open_meteo_enabled": False,
                    "local_weather_pilot_ready": True,
                },
            )
            with self.assertRaisesRegex(OpenMeteoDisabled, "open_meteo_disabled:forecast"):
                require_open_meteo_enabled("forecast")

    def test_invalid_switch_is_not_interpreted_as_enabled(self):
        with patch.dict(
            os.environ,
            {OPEN_METEO_ENABLED_ENV: "maybe"},
        ):
            with self.assertRaises(ProviderPolicyConfigurationError):
                open_meteo_enabled()
            status = provider_policy_status()

        self.assertFalse(status["valid"])
        self.assertFalse(status["open_meteo_enabled"])
        self.assertFalse(status["local_weather_pilot_ready"])

    def test_loopback_check_accepts_only_literal_loopback_hosts(self):
        self.assertTrue(is_loopback_hostname("127.0.0.1"))
        self.assertTrue(is_loopback_hostname("::1"))
        self.assertTrue(is_loopback_hostname("localhost."))
        self.assertFalse(is_loopback_hostname("pilot.example.test"))
        self.assertFalse(is_loopback_hostname("127.0.0.1.example.test"))


if __name__ == "__main__":
    unittest.main()
