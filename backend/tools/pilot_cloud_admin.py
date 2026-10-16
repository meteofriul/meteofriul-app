"""Explicit owner-only pilot import/enrollment; no credentials in stdout/files.

Uses the already signed-in gcloud account in memory. Never changes its default
project, writes an ADC key, clears Android data, or touches the beta package.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

PROJECT = "meteofriul-pilot-20260906"
PACKAGE = "com.meteofriul.app.localpilot"
API_BASE = "https://pilot-community-335641913741.europe-west1.run.app/api"
MAX_DEVICE_FILE_BYTES = 4096
BINDING_PATH = "no_backup/pilot-community-installation.json"
AUTH_PATH = "no_backup/pilot-community-cloud-auth.json"


def _device(command, args, *, payload=None):
    """Never let subprocess stdout/stderr or the input credential escape."""
    try:
        return subprocess.run(command + args, input=payload, capture_output=True, timeout=30)
    except Exception:
        raise RuntimeError("pilot_device_command_failed") from None


def _read_private_device_file(command, path):
    if path not in {BINDING_PATH, AUTH_PATH}:
        raise ValueError("invalid_pilot_private_path")
    # The app-private parent and target must be real files/directories, never
    # symlinks. Bound the read even if a damaged private file is unexpectedly big.
    script = f"test -d no_backup && test ! -L no_backup && test -f {path} && test ! -L {path} && head -c 4097 {path}"
    # exec-out preserves this argv element; shell -T below instead needs its
    # command protected from adb's remote shell parsing. Do not quote both alike.
    result = _device(command, ["exec-out", "run-as", PACKAGE, "sh", "-c", script])
    if result.returncode != 0 or not 2 <= len(result.stdout) <= MAX_DEVICE_FILE_BYTES:
        raise RuntimeError("pilot_private_device_file_unavailable")
    try:
        value = json.loads(result.stdout)
    except (ValueError, UnicodeDecodeError):
        # Some adb exec-out versions report shell failures in stdout with status
        # zero. Require a JSON object before treating any output as file bytes.
        raise RuntimeError("pilot_private_device_file_unavailable") from None
    if not isinstance(value, dict):
        raise RuntimeError("pilot_private_device_file_unavailable")
    return result.stdout


def clients():
    sdk = Path(os.environ["LOCALAPPDATA"]) / "Google/Cloud SDK/google-cloud-sdk/lib/gcloud.py"
    command = [sys.executable, str(sdk)]
    account = subprocess.check_output(command + ["auth", "list", "--filter=status:ACTIVE", "--format=value(account)"], text=True).strip()
    if account != "meteofriul@gmail.com":
        raise RuntimeError("unexpected_pilot_admin_account")
    token = subprocess.check_output(command + ["auth", "print-access-token", "--account=meteofriul@gmail.com", f"--project={PROJECT}"], text=True).strip()
    from google.oauth2.credentials import Credentials
    from google.cloud import firestore, storage
    credential = Credentials(token=token, quota_project_id=PROJECT)
    return firestore.Client(project=PROJECT, credentials=credential), storage.Client(project=PROJECT, credentials=credential)


def seed(path):
    from app.repositories.pilot_community_cloud import PilotCloudCommunityRepository, read_sqlite_seed, serialize_state
    firestore, storage = clients()
    state = read_sqlite_seed(path)
    before = serialize_state(state)
    result = PilotCloudCommunityRepository.seed(firestore_client=firestore, storage_client=storage, state=state)
    repository = PilotCloudCommunityRepository(firestore_client=firestore, storage_client=storage)
    if serialize_state(repository._snapshot_state()) != before:
        raise RuntimeError("pilot_import_readback_mismatch")
    result["verified"] = True
    result["field_counts"] = {k: len(v) for k, v in state.items()}
    print(json.dumps(result))


def enroll(serial):
    adb = Path(os.environ["LOCALAPPDATA"]) / "Android/Sdk/platform-tools/adb.exe"
    command = [str(adb), "-s", serial]
    binding_raw = _read_private_device_file(command, BINDING_PATH)
    try:
        binding = json.loads(binding_raw)
    except (ValueError, UnicodeDecodeError):
        raise RuntimeError("pilot_binding_missing_or_invalid") from None
    if (not isinstance(binding, dict) or set(binding) != {"version", "client_id_sha256", "api_base"}
            or type(binding["version"]) is not int or binding["version"] != 1
            or binding["api_base"] != API_BASE):
        raise RuntimeError("pilot_binding_missing_or_invalid")
    digest = binding["client_id_sha256"]
    import re
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise RuntimeError("pilot_binding_missing_or_invalid")
    check_script = (
        "test -d no_backup && test ! -L no_backup || exit 3; "
        f"if test -L {AUTH_PATH}; then exit 3; fi; "
        f"if test -e {AUTH_PATH}; then test -f {AUTH_PATH} || exit 3; printf PRESENT; else printf ABSENT; fi"
    )
    exists = _device(command, ["shell", "-T", "run-as", PACKAGE, "sh", "-c", "'" + check_script + "'"])
    if exists.returncode != 0:
        raise RuntimeError("pilot_credential_file_check_failed")
    if exists.stdout == b"PRESENT":
        raise RuntimeError("pilot_already_provisioned_do_not_overwrite")
    if exists.stdout != b"ABSENT":
        raise RuntimeError("pilot_credential_file_check_failed")
    firestore, _ = clients()
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(days=30)
    registry = firestore.collection("pilot_community_installations").document(token_hash)
    payload = json.dumps({"version": 1, "client_id_sha256": digest, "token": token, "api_base": API_BASE}).encode()
    # Stream directly into app-private, backup-excluded storage. No shared temp,
    # command-line token, clipboard, Web storage, terminal echo or adb logcat.
    # POSIX noclobber performs exclusive creation; a concurrent provisioner or
    # existing file cannot be overwritten after the earlier read-only check.
    write_script = (
        "umask 077; set -C; test -d no_backup && test ! -L no_backup || exit 3; "
        f"test ! -e {AUTH_PATH} && test ! -L {AUTH_PATH} || exit 3; cat > {AUTH_PATH}"
    )
    try:
        registry.create({"project": PROJECT, "active": True, "client_id_sha256": digest,
                         "created_at": datetime.now(timezone.utc), "expires_at": expires}, timeout=15, retry=None)
        result = _device(command, ["shell", "-T", "run-as", PACKAGE, "sh", "-c", "'" + write_script + "'"], payload=payload)
        if result.returncode:
            raise RuntimeError("pilot_provision_write_failed")
        readback = _read_private_device_file(command, AUTH_PATH)
        if hashlib.sha256(readback).digest() != hashlib.sha256(payload).digest():
            raise RuntimeError("pilot_provision_readback_failed")
    except Exception:
        # Includes transport/readback exceptions and an unknown create result.
        # Do not expose the failing command's stdout/stderr or chained exception.
        try:
            registry.update({"active": False}, timeout=15, retry=None)
        except Exception:
            raise RuntimeError("pilot_provision_failed_revocation_unconfirmed") from None
        raise RuntimeError("pilot_provision_failed_enrollment_revoked") from None
    print(json.dumps({"project": PROJECT, "package": PACKAGE, "enrolled": True,
                      "expires_at": expires.isoformat(), "credential_exposed": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, choices=[PROJECT])
    sub = parser.add_subparsers(dest="operation", required=True)
    importer = sub.add_parser("seed")
    importer.add_argument("--sqlite-state", type=Path, required=True)
    phone = sub.add_parser("enroll-phone")
    phone.add_argument("--serial", required=True)
    args = parser.parse_args()
    if args.operation == "seed":
        seed(args.sqlite_state)
    else:
        enroll(args.serial)


if __name__ == "__main__":
    main()
