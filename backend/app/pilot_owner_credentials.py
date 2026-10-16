"""Refresh the local pilot owner's gcloud credential in memory, never via ADC.

Only the explicitly started loopback preview imports this module. It is not
part of either public Cloud Run image and never reads phone enrollment files.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock

from app.repositories.pilot_community_cloud import PILOT_PROJECT

PILOT_OWNER = "meteofriul@gmail.com"


class PilotOwnerCredentialUnavailable(RuntimeError):
    def __init__(self):
        super().__init__("pilot_owner_credential_unavailable")


class PilotOwnerTokenRefresher:
    def __init__(self, *, runner=subprocess.run, sdk_path: Path | None = None,
                 now=lambda: datetime.now(timezone.utc)):
        self._runner, self._now = runner, now
        self._sdk_path = sdk_path or Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Cloud SDK/google-cloud-sdk/lib/gcloud.py"
        self._lock = Lock()

    def _run(self, arguments):
        # SDK overrides must not redirect this privileged local-only credential.
        if any(value for key, value in os.environ.items() if
               key.startswith("CLOUDSDK_API_ENDPOINT_OVERRIDES_") or key in {
                   "CLOUDSDK_AUTH_ACCESS_TOKEN", "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
                   "CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT"}):
            raise PilotOwnerCredentialUnavailable()
        if not self._sdk_path.is_file():
            raise PilotOwnerCredentialUnavailable()
        result = self._runner(
            [sys.executable, str(self._sdk_path), *arguments],
            capture_output=True, text=True, timeout=25, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0 or not isinstance(result.stdout, str) or len(result.stdout) > 32768:
            raise PilotOwnerCredentialUnavailable()
        return result.stdout

    def __call__(self, _request=None, scopes=None):
        # Never expose subprocess output, token, stderr, or exception messages.
        try:
            with self._lock:
                active = self._run(["auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
                if active.strip() != PILOT_OWNER:
                    raise PilotOwnerCredentialUnavailable()
                document = json.loads(self._run([
                    "config", "config-helper", f"--account={PILOT_OWNER}",
                    f"--project={PILOT_PROJECT}", "--min-expiry=5m",
                    "--format=json(credential.access_token,credential.token_expiry,configuration.properties.core.account,configuration.properties.core.project,configuration.properties.auth.impersonate_service_account)",
                ]))
                properties = document["configuration"]["properties"]
                if (properties["core"]["account"] != PILOT_OWNER
                        or properties["core"]["project"] != PILOT_PROJECT
                        or properties.get("auth", {}).get("impersonate_service_account")):
                    raise PilotOwnerCredentialUnavailable()
                token = document["credential"]["access_token"]
                expiry = datetime.strptime(document["credential"]["token_expiry"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if (not isinstance(token, str) or not token or len(token) > 16384
                        or any(char.isspace() for char in token)
                        or not self._now() + timedelta(minutes=4) < expiry <= self._now() + timedelta(hours=2)):
                    raise PilotOwnerCredentialUnavailable()
                # google-auth expects naive UTC expiry for its refresh handler.
                return token, expiry.replace(tzinfo=None)
        except Exception:
            raise PilotOwnerCredentialUnavailable() from None


def create_owner_credentials(*, refresher=None):
    from google.oauth2.credentials import Credentials

    credentials = Credentials(token=None, refresh_handler=refresher or PilotOwnerTokenRefresher())
    credentials.refresh(None)
    return credentials
