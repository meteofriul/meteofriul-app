"""Freeze a local, ordered patch kit. No commit, network, build or deployment.

The temporary Git index checks each intermediate tree without touching the real
index or checkout. Reader-stage Python sources are exported for offline checks.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = "8497e773b1613312bb952236d72c074e22a7b1c6"
STAGES = (
    ("01-readers", (
        "frontend/src/services/iconAccumulationQuality.js",
        "frontend/src/services/weatherV1Client.js",
        "frontend/src/services/weatherV1Client.test.js",
        "experiments/weather_autonomy/local_pipeline/accumulation_tolerance.py",
        "experiments/weather_autonomy/local_pipeline/contract_v1.py",
        "experiments/weather_autonomy/local_pipeline/icon_checkpoint.py",
        "experiments/weather_autonomy/local_pipeline/icon_quality.py",
        "experiments/weather_autonomy/test_icon_quality.py",
        "experiments/weather_autonomy/local_pipeline/icon_accumulation_sidecar.py",
        "experiments/weather_autonomy/local_pipeline/contract_publisher.py",
        "experiments/weather_autonomy/local_pipeline/published_runs_reader.py",
        "experiments/weather_autonomy/local_pipeline/http_data_plane.py",
        "experiments/weather_autonomy/test_icon_accumulation_sidecar.py",
    )),
    ("02-notice-consumer", (
        "backend/app/repositories/local_notice_shadow.py",
        "backend/app/services/evening_forecast_delivery.py",
        "backend/app/services/local_notice_delivery.py",
        "backend/app/services/local_notice_shadow.py",
        "backend/app/services/morning_forecast_delivery.py",
        "backend/app/weather/local_notice_shadow.py",
        "backend/app/weather/local_notice_source.py",
        "backend/app/weather/local_notice_sidecar.py",
        "backend/tests/test_local_notice_sidecar.py",
        "backend/app/weather/local_notice_quality.py",
        "backend/app/weather/local_notice_tolerance.py",
        "backend/app/weather/local_notice_thresholds.py",
        "backend/tests/test_local_notice_delivery_service.py",
        "backend/tests/test_local_notice_shadow.py",
        "backend/tests/test_local_notice_missing_data.py",
        "backend/tests/test_local_notice_per_phenomenon.py",
        "backend/tests/test_local_notice_tolerance.py",
        "backend/tests/fixtures/icon_fontanafredda_missing_accumulation.json",
        "experiments/weather_autonomy/fixtures/ciampac-snow-tolerance-20261019.json",
    )),
    ("03-producer", (
        "experiments/weather_autonomy/cloud_worker.py",
        "experiments/weather_autonomy/run_pilot.py",
        "experiments/weather_autonomy/local_pipeline/snapshot_materializer.py",
        "experiments/weather_autonomy/local_pipeline/operational_diagnostics.py",
        "experiments/weather_autonomy/test_cloud_worker.py",
        "experiments/weather_autonomy/test_run_pilot.py",
        "experiments/weather_autonomy/test_accumulation_tolerance.py",
        "experiments/weather_autonomy/test_operational_diagnostics.py",
        "experiments/weather_autonomy/probe_snow_tolerance.py",
        "experiments/weather_autonomy/test_probe_snow_tolerance.py",
    )),
)
WRITERS = (
    "experiments/weather_autonomy/cloud_worker.py",
    "experiments/weather_autonomy/run_pilot.py",
    "experiments/weather_autonomy/local_pipeline/snapshot_materializer.py",
)


def git(*args, env=None):
    result = subprocess.run(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
        cwd=ROOT, env=env, capture_output=True,
    )
    if result.returncode:
        raise SystemExit(result.stderr.decode("utf-8", errors="replace"))
    return result.stdout


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if git("rev-parse", "main").decode().strip() != BASE:
        raise SystemExit("Local main changed: review/rebase the rollout stages first.")
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Use a new output directory; existing kits are immutable.")
    base_paths = set(git("ls-tree", "-r", "--name-only", BASE).decode().splitlines())
    all_paths = [p for _, paths in STAGES for p in paths]
    if len(all_paths) != len(set(all_paths)):
        raise SystemExit("A path belongs to multiple stages.")
    patches, inventory = [], []
    for stage, paths in STAGES:
        sections, files = [], []
        for path in paths:
            before_bytes = git("show", f"{BASE}:{path}") if path in base_paths else b""
            after_bytes = (ROOT / path).read_bytes()
            before = before_bytes.decode("utf-8").replace("\r\n", "\n")
            after = after_bytes.decode("utf-8").replace("\r\n", "\n")
            diff = "".join(difflib.unified_diff(
                before.splitlines(keepends=True), after.splitlines(keepends=True),
                fromfile=f"a/{path}" if path in base_paths else "/dev/null", tofile=f"b/{path}",
            ))
            if not diff:
                raise SystemExit(f"Stage inventory includes an unchanged path: {path}")
            sections.append(diff)
            files.append({"path": path, "source_sha256": sha(after_bytes), "patch_content_sha256": sha(after.encode())})
        patch = "".join(sections).encode("utf-8")
        patches.append((stage, patch))
        inventory.append({"stage": stage, "patch": stage + ".patch", "sha256": sha(patch), "files": files})
    output.mkdir(parents=True)
    for stage, patch in patches:
        (output / (stage + ".patch")).write_bytes(patch)
    with tempfile.TemporaryDirectory(prefix="icon-tolerance-index-") as scratch:
        objects = Path(scratch) / "objects"
        objects.mkdir()
        common = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip())
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(scratch) / "index"),
                   GIT_OBJECT_DIRECTORY=str(objects), GIT_ALTERNATE_OBJECT_DIRECTORIES=str(common / "objects"))
        git("read-tree", BASE, env=env)
        for stage, _ in patches:
            patch_path = str(output / (stage + ".patch"))
            git("apply", "--cached", "--check", patch_path, env=env)
            git("apply", "--cached", patch_path, env=env)
            if stage == "01-readers":
                # Runtime writer bytes must still be exactly the old baseline.
                for path in WRITERS:
                    if git("show", f":{path}", env=env) != git("show", f"{BASE}:{path}"):
                        raise SystemExit(f"Reader stage accidentally changed a writer: {path}")
                export = output / "reader-stage"
                paths = git("ls-files", env=env).decode().splitlines()
                for path in paths:
                    if (path.startswith("experiments/weather_autonomy/") and path.endswith(".py")) or path in {
                        "backend/app/data/fvg_municipalities.json", "backend/app/data/fvg_geography.json",
                    }:
                        destination = export / path
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(git("show", f":{path}", env=env))
        for item in inventory:
            for entry in item["files"]:
                if sha(git("show", f":{entry['path']}", env=env)) != entry["patch_content_sha256"]:
                    raise SystemExit(f"Final staged bytes differ: {entry['path']}")
    manifest = {
        "schema_version": 1, "base_commit": BASE, "source_branch": git("branch", "--show-current").decode().strip(),
        "status": "prepared_locally_not_authorized_for_deployment",
        "source_head": git("rev-parse", "HEAD").decode().strip(),
        "selected_sources_match_head": not bool(git("status", "--porcelain", "--", *all_paths).strip()),
        "ordered_patches_apply": True, "reader_stage_acquisition_files_unchanged": True,
        "real_git_index_untouched": True, "stages": inventory,
        "test_app": {"require_service_parity_with_release": True, "weather_mode": "real_cloud_services",
                     "android_variant": "fullTest", "android_package": "com.meteofriul.app.localpilot",
                     "localpilot_profile_is_equivalent": False,
                     "owner_accepted_exclusions": ["native push notifications", "background weather", "real Community writes (simulation accepted for this workstream)"],
                     "community_backend": "isolated QA; no production reports",
                     "required_services": ["regional and national weather", "CAMS and UV", "events", "maps and location",
                                           "Community UI with explicitly simulated reports if enabled"],
                     "synthetic_data_scope": "offline software checks and isolated Community QA only; weather/events are real reads",
                     "cloud_data_shared": True, "runtime_verified_by_this_command": False, "apk_built_by_this_command": False},
        "release_gates_pending": ["new-format real-run validation; TEST .5 has only exercised the existing published format", "public v1 remains compatible; sidecar HTTP reader deployed before producer",
                                  "separate dry-run consumer and monitoring review", "checkpoint-compatible rollback image",
                                  "new source run after coordinated writer activation", "explicit release authorization"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "stages": len(inventory), "files": len(all_paths),
                      "ordered_patches_apply": True, "reader_stage_acquisition_files_unchanged": True}))


if __name__ == "__main__":
    main()
