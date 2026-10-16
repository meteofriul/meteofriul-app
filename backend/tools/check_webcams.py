from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import requests


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parent
DEFAULT_ACTIVE_MANIFEST = BACKEND_ROOT / "app" / "data" / "webcams_active.json"
DEFAULT_ASSET_ROOT = WORKSPACE_ROOT / "frontend" / "public"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.webcam_health import check_webcam_health  # noqa: E402
from app.services.webcams import (  # noqa: E402
    WebcamManifestValidationError,
    load_shadow_webcam_manifest,
    validate_webcam_manifest,
)


def _load_active_manifest(path: Path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        raise WebcamManifestValidationError([]) from exc
    return validate_webcam_manifest(payload)


def run_health_check(
    *,
    manifest_path: Path,
    shadow: bool,
    asset_root: Path = DEFAULT_ASSET_ROOT,
    session: requests.Session | None = None,
    timeout_seconds: float = 6.0,
) -> dict[str, Any]:
    catalog = (
        load_shadow_webcam_manifest(manifest_path)
        if shadow
        else _load_active_manifest(manifest_path)
    )
    return check_webcam_health(
        catalog.records,
        mode=catalog.mode,
        asset_root=asset_root,
        session=session,
        timeout_seconds=timeout_seconds,
    )


def _validation_report(
    error: WebcamManifestValidationError,
    *,
    path: Path,
    shadow: bool,
) -> dict[str, Any]:
    issues = [issue.as_dict() for issue in error.issues]
    if not issues:
        issues = [
            {
                "code": "manifest_unreadable",
                "path": str(path),
                "message": "manifest non leggibile",
            }
        ]
    return {
        "schema_version": "webcam-health.v1",
        "mode": "shadow" if shadow else "active",
        "publish": False,
        "status": "invalid_manifest",
        "counts": {"total": 0, "ok": 0, "degraded": 0, "failed": 0},
        "issues": issues,
        "results": [],
    }


def _render_report(report: dict[str, Any], output: Path | None) -> None:
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if output is None:
        print(serialized)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized + "\n", encoding="utf-8")
    print(f"[webcam-check] report: {output}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Controllo locale e non pubblicante di manifest, asset e raggiungibilita' delle pagine webcam. "
            "Non certifica aggiornamento dei fotogrammi, punto di ripresa o diritto di incorporamento."
        )
    )
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--manifest", type=Path, help="manifest attivo da controllare")
    inputs.add_argument(
        "--candidates",
        type=Path,
        help="manifest candidati esplicitamente shadow (mai letto dall'API)",
    )
    parser.add_argument("--asset-root", type=Path, default=DEFAULT_ASSET_ROOT)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout deve essere maggiore di zero")

    shadow = args.candidates is not None
    manifest_path = (args.candidates or args.manifest or DEFAULT_ACTIVE_MANIFEST).resolve()
    try:
        report = run_health_check(
            manifest_path=manifest_path,
            shadow=shadow,
            asset_root=args.asset_root.resolve(),
            timeout_seconds=args.timeout,
        )
    except WebcamManifestValidationError as error:
        report = _validation_report(error, path=manifest_path, shadow=shadow)

    _render_report(report, args.output.resolve() if args.output else None)
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
