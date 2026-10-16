"""Run the same Palazzo Attems audit used by the pilot events job locally."""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.events.pilot_attems_audit import main  # noqa: E402


if __name__ == '__main__':
    raise SystemExit(main())
