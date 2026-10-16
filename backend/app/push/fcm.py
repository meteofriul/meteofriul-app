from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable

from app.infrastructure.firebase import FirebaseInitializationError, get_firebase_app


DEFAULT_ANDROID_NOTIFICATION_CHANNEL = "mf_official_alerts_v1"
DEFAULT_ANDROID_NATIONAL_ALERT_CHANNEL = "mf_national_official_alerts_v1"
DEFAULT_ANDROID_LOCAL_NOTICE_CHANNEL = "mf_weather_notices_v1"
DEFAULT_WEB_NOTIFICATION_ICON = (
    "/branding/web-notification-icon_mf-r4-20260927-192.png"
)
DEFAULT_WEB_APP_URL = "https://meteofriul.app"
FCM_MAX_BATCH_MESSAGES = 500


class FcmSendError(RuntimeError):
    """Base class for sanitized FCM delivery failures."""


class FcmTokenInvalid(FcmSendError):
    """The registered FCM token or Firebase installation is no longer valid."""


class FcmSenderUnavailable(FcmSendError):
    """The server could not make a reliable FCM delivery attempt."""


class FcmConfigurationError(FcmSendError):
    """Firebase/IAM configuration prevents delivery until it is corrected."""


@dataclass(frozen=True)
class FcmOfficialAlertMessage:
    title: str
    body: str
    data: dict[str, str]
    ttl_seconds: int
    target_kind: str = "fcm_token"
    target_value: str = ""
    platform: str = "android"
    token: str = ""
    channel_id: str = DEFAULT_ANDROID_NOTIFICATION_CHANNEL
    collapse_key: str = "mf-official-alerts"
    notification_tag: str = "mf-official-alerts"
    web_link: str = f"{DEFAULT_WEB_APP_URL}/?tab=bulletin"


@dataclass(frozen=True)
class FcmBatchOutcome:
    message_id: str = ""
    error_code: str = ""

    @property
    def success(self) -> bool:
        return bool(self.message_id) and not self.error_code


class FirebaseCloudMessagingSender:
    """Small Firebase Admin seam that never logs or returns a device token."""

    def __init__(
        self,
        *,
        firebase_app_provider: Callable[[], Any] = get_firebase_app,
    ) -> None:
        self._firebase_app_provider = firebase_app_provider

    @staticmethod
    def _build_message(payload: FcmOfficialAlertMessage, messaging: Any) -> Any:
        target_value = str(payload.target_value or payload.token)
        valid_android = (
            payload.platform == "android" and payload.target_kind == "fcm_token"
        )
        valid_web = (
            payload.platform == "web"
            and payload.target_kind == "firebase_installation_id"
        )
        if not target_value or not (valid_android or valid_web):
            raise FcmConfigurationError("fcm_target_configuration_error")
        if valid_web and not payload.web_link.startswith("https://"):
            raise FcmConfigurationError("fcm_web_link_configuration_error")

        ttl_seconds = max(60, int(payload.ttl_seconds))
        message_arguments: dict[str, Any] = {
            "data": {
                str(key): str(value) for key, value in payload.data.items()
            },
        }
        if valid_android:
            message_arguments.update(
                token=target_value,
                notification=messaging.Notification(
                    title=payload.title,
                    body=payload.body,
                ),
                android=messaging.AndroidConfig(
                    collapse_key=payload.collapse_key,
                    priority="high",
                    ttl=timedelta(seconds=ttl_seconds),
                    notification=messaging.AndroidNotification(
                        channel_id=payload.channel_id,
                        tag=payload.notification_tag,
                    ),
                ),
            )
        else:
            message_arguments.update(
                fid=target_value,
                webpush=messaging.WebpushConfig(
                    headers={"TTL": str(ttl_seconds), "Urgency": "high"},
                    notification=messaging.WebpushNotification(
                        title=payload.title,
                        body=payload.body,
                        icon=DEFAULT_WEB_NOTIFICATION_ICON,
                        tag=payload.notification_tag,
                    ),
                    fcm_options=messaging.WebpushFCMOptions(
                        link=payload.web_link,
                    ),
                ),
            )
        return messaging.Message(**message_arguments)

    @staticmethod
    def _error_code(
        error: BaseException | None,
        *,
        firebase_exceptions: Any,
        messaging: Any,
    ) -> str:
        if isinstance(
            error,
            (messaging.UnregisteredError, messaging.SenderIdMismatchError),
        ):
            return "fcm_token_invalid"
        if isinstance(
            error,
            (
                firebase_exceptions.FailedPreconditionError,
                firebase_exceptions.InvalidArgumentError,
                firebase_exceptions.PermissionDeniedError,
                firebase_exceptions.UnauthenticatedError,
                messaging.ThirdPartyAuthError,
            ),
        ):
            return "fcm_configuration_error"
        return "fcm_sender_unavailable"

    def send(self, payload: FcmOfficialAlertMessage) -> str:

        try:
            from firebase_admin import exceptions as firebase_exceptions
            from firebase_admin import messaging

            firebase_app = self._firebase_app_provider()
            message = self._build_message(payload, messaging)
            return str(messaging.send(message, app=firebase_app))
        except (FirebaseInitializationError, ImportError) as error:
            raise FcmConfigurationError("fcm_configuration_error") from error
        except FcmSendError:
            raise
        except (
            messaging.UnregisteredError,
            messaging.SenderIdMismatchError,
        ) as error:
            raise FcmTokenInvalid("fcm_token_invalid") from error
        except (
            firebase_exceptions.FailedPreconditionError,
            firebase_exceptions.InvalidArgumentError,
            firebase_exceptions.PermissionDeniedError,
            firebase_exceptions.UnauthenticatedError,
            messaging.ThirdPartyAuthError,
        ) as error:
            raise FcmConfigurationError("fcm_configuration_error") from error
        except (
            messaging.QuotaExceededError,
            firebase_exceptions.AbortedError,
            firebase_exceptions.CancelledError,
            firebase_exceptions.DeadlineExceededError,
            firebase_exceptions.InternalError,
            firebase_exceptions.ResourceExhaustedError,
            firebase_exceptions.UnavailableError,
        ) as error:
            raise FcmSenderUnavailable("fcm_sender_unavailable") from error
        except Exception as error:
            raise FcmSenderUnavailable("fcm_sender_unavailable") from error

    def send_batch(
        self,
        payloads: list[FcmOfficialAlertMessage],
    ) -> list[FcmBatchOutcome]:
        if not payloads:
            return []
        if len(payloads) > FCM_MAX_BATCH_MESSAGES:
            raise FcmConfigurationError("fcm_batch_size_invalid")
        try:
            from firebase_admin import exceptions as firebase_exceptions
            from firebase_admin import messaging

            firebase_app = self._firebase_app_provider()
            messages = [
                self._build_message(payload, messaging) for payload in payloads
            ]
            response = messaging.send_each(messages, app=firebase_app)
            responses = list(getattr(response, "responses", ()))
            if len(responses) != len(messages):
                raise FcmSenderUnavailable("fcm_batch_response_invalid")
            return [
                FcmBatchOutcome(message_id=str(item.message_id or ""))
                if bool(getattr(item, "success", False))
                else FcmBatchOutcome(
                    error_code=self._error_code(
                        getattr(item, "exception", None),
                        firebase_exceptions=firebase_exceptions,
                        messaging=messaging,
                    )
                )
                for item in responses
            ]
        except (FirebaseInitializationError, ImportError) as error:
            raise FcmConfigurationError("fcm_configuration_error") from error
        except FcmSendError:
            raise
        except (
            firebase_exceptions.FailedPreconditionError,
            firebase_exceptions.InvalidArgumentError,
            firebase_exceptions.PermissionDeniedError,
            firebase_exceptions.UnauthenticatedError,
            messaging.ThirdPartyAuthError,
        ) as error:
            raise FcmConfigurationError("fcm_configuration_error") from error
        except (
            messaging.QuotaExceededError,
            firebase_exceptions.AbortedError,
            firebase_exceptions.CancelledError,
            firebase_exceptions.DeadlineExceededError,
            firebase_exceptions.InternalError,
            firebase_exceptions.ResourceExhaustedError,
            firebase_exceptions.UnavailableError,
        ) as error:
            raise FcmSenderUnavailable("fcm_sender_unavailable") from error
        except Exception as error:
            raise FcmSenderUnavailable("fcm_sender_unavailable") from error
