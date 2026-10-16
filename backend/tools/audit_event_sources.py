from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.events import engine  # noqa: E402
from app.events.audit import render_event_source_audit_markdown  # noqa: E402
from app.events.source_pipeline import (  # noqa: E402
    build_live_event_source_audit,
    collect_active_catalog,
    normalize_visible_event,
    source_fetchers,
)


# Compatibility names kept for focused tests and existing local tooling.
_normalize_visible_event = normalize_visible_event
_source_fetchers = source_fetchers


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("la data deve essere YYYY-MM-DD") from exc


def run_audit(*, as_of: date, output_dir: Path, active_limit: int = 100) -> dict:
    json_path = output_dir / "event-source-audit.json"
    markdown_path = output_dir / "event-source-audit.md"
    if json_path.exists() or markdown_path.exists():
        raise FileExistsError(
            f"la cartella audit contiene già un report e non verrà sovrascritta: {output_dir}"
        )

    report = build_live_event_source_audit(
        as_of=as_of,
        active_limit=active_limit,
        progress=lambda message: print(f"[audit] {message}...", flush=True),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_event_source_audit_markdown(report),
        encoding="utf-8",
    )
    print(f"[audit] JSON: {json_path}", flush=True)
    print(f"[audit] report: {markdown_path}", flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit locale, fail-closed e non pubblicante per Villa Manin ed ERPAC."
    )
    parser.add_argument("--as-of", type=_parse_date, default=date.today())
    parser.add_argument("--active-limit", type=int, default=100)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=WORKSPACE_ROOT
        / "tmp"
        / "event-source-audit"
        / datetime.now().strftime("%Y%m%d-%H%M%S"),
    )
    args = parser.parse_args()
    if not 1 <= args.active_limit <= 100:
        parser.error("--active-limit deve essere compreso tra 1 e 100")

    report = run_audit(
        as_of=args.as_of,
        output_dir=args.output_dir.resolve(),
        active_limit=args.active_limit,
    )
    print(
        "[audit] esito: "
        f"{report['status']}; candidati={report['counts']['shadow_candidates']}; "
        f"decisioni={report['counts']['decisions']}",
        flush=True,
    )
    return 0 if report["status"] == "ready_for_manual_review" else 2


if __name__ == "__main__":
    raise SystemExit(main())
