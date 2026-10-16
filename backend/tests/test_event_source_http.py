import unittest
from unittest.mock import Mock

import requests

from app.events import http_client


class EventSourceHttpTests(unittest.TestCase):
    @staticmethod
    def http_error_response(status_code: int):
        response = Mock(status_code=status_code)
        response.raise_for_status.side_effect = requests.HTTPError(
            f"HTTP {status_code}", response=response
        )
        return response

    def test_retries_each_supported_transient_http_status_once(self):
        for status_code in sorted(http_client.EVENT_SOURCE_TRANSIENT_STATUS_CODES):
            with self.subTest(status_code=status_code):
                success = Mock()
                get = Mock(
                    side_effect=[self.http_error_response(status_code), success]
                )
                sleep = Mock()

                result = http_client.get_with_single_transient_retry(
                    get, "https://example.test/events", sleep=sleep, timeout=10
                )

                self.assertIs(result, success)
                self.assertEqual(get.call_count, 2)
                sleep.assert_called_once_with(
                    http_client.EVENT_SOURCE_RETRY_DELAY_SECONDS
                )

    def test_retries_timeout_and_connection_failure_once(self):
        for error in (
            requests.ReadTimeout("timeout"),
            requests.ConnectionError("offline"),
        ):
            with self.subTest(error=type(error).__name__):
                success = Mock()
                get = Mock(side_effect=[error, success])
                sleep = Mock()

                result = http_client.get_with_single_transient_retry(
                    get, "https://example.test/events", sleep=sleep
                )

                self.assertIs(result, success)
                self.assertEqual(get.call_count, 2)
                sleep.assert_called_once()

    def test_second_transient_failure_is_raised_fail_closed(self):
        get = Mock(
            side_effect=[
                requests.ReadTimeout("first"),
                requests.ReadTimeout("second"),
            ]
        )
        sleep = Mock()

        with self.assertRaisesRegex(requests.ReadTimeout, "second"):
            http_client.get_with_single_transient_retry(
                get, "https://example.test/events", sleep=sleep
            )

        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once()

    def test_non_transient_http_status_is_not_retried(self):
        for status_code in (400, 401, 403, 404, 422):
            with self.subTest(status_code=status_code):
                get = Mock(return_value=self.http_error_response(status_code))
                sleep = Mock()

                with self.assertRaises(requests.HTTPError):
                    http_client.get_with_single_transient_retry(
                        get, "https://example.test/events", sleep=sleep
                    )

                get.assert_called_once()
                sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
