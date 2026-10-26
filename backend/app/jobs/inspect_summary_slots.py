"""Inspect saved summary evidence locally; never acquires credentials or sends."""
import argparse
from datetime import date
import json
from pathlib import Path

from app.services.summary_slot_monitor import evaluate_slot, expected_slot, latest_slots


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--local-date", type=date.fromisoformat,
                        help="Inspect this exact civil date; default: latest due slot per summary")
    args = parser.parse_args(argv)
    try:
        if args.evidence.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("evidence file exceeds 4 MiB")
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        now = evidence["observed_at"]
        slots = ([expected_slot(kind, args.local_date) for kind in ("morning", "evening")]
                 if args.local_date else latest_slots(now))
        results = [evaluate_slot(slot, evidence, now=now) for slot in slots]
    except (OSError, ValueError, KeyError, TypeError):
        parser.error("invalid local evidence; no external action performed")
    print(json.dumps({"mode": "offline", "evaluations": results}, ensure_ascii=True, allow_nan=False))
    return int(any(item["attention"] for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
