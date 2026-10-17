"""Explicitly gated Cloud Run job entrypoint; --help never uses credentials."""
import argparse
from datetime import datetime, timezone
import json
import os

from .collect import Budget, Collector
from .core import stamp
from .google import WeatherData, PublicHTTP, MonitorState, Metrics, transports
from .schedule import PROJECT, JOB, forwarded_slot, require_delivery
from .runner import Runner
from .http import PUBLIC_TIMEOUT_SECONDS, API_TIMEOUT_SECONDS, PUBLIC_DOCUMENT_BYTES, timeout_value

def emit(record):
    print(json.dumps(record, sort_keys=True, allow_nan=False), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cloud", action="store_true", help="Requires explicit environment opt-in; writes monitor state/metrics")
    parser.add_argument("--scheduled-slot", help="Explicit UTC :10/:40 slot passed by the dispatcher or an authorized operator")
    parser.add_argument("--scheduler-schedule-time", help="Original Scheduler header; must agree with the explicit slot")
    parser.add_argument("--fvg-grace-seconds", type=int, default=60)
    parser.add_argument("--national-grace-seconds", type=int, default=60)
    parser.add_argument("--public-http-timeout-seconds", type=float, default=os.environ.get("ICON2I_PUBLIC_HTTP_TIMEOUT_SECONDS", PUBLIC_TIMEOUT_SECONDS),
                        help="Absolute public request limit, 1..15s; default 15s for observed cold starts")
    parser.add_argument("--api-http-timeout-seconds", type=float, default=os.environ.get("ICON2I_API_HTTP_TIMEOUT_SECONDS", API_TIMEOUT_SECONDS),
                        help="Absolute Google request limit, 1..5s, including credential refresh")
    args = parser.parse_args(argv)
    try:
        timeout_value(args.public_http_timeout_seconds, PUBLIC_TIMEOUT_SECONDS)
        timeout_value(args.api_http_timeout_seconds, API_TIMEOUT_SECONDS)
    except ValueError as error:
        parser.error(str(error))
    if not args.cloud or os.environ.get("ICON2I_MONITOR_ALLOW_CLOUD") != "1":
        parser.error("cloud mode is disabled; run the offline unit tests instead")
    if os.environ.get("GOOGLE_CLOUD_PROJECT") != PROJECT or os.environ.get("CLOUD_RUN_JOB") != JOB:
        parser.error("unexpected project/job")
    if os.environ.get("CLOUD_RUN_TASK_COUNT") != "1" or os.environ.get("CLOUD_RUN_TASK_ATTEMPT", "0") != "0":
        parser.error("one task, no automatic retry required")
    if not args.scheduled_slot:
        parser.error("explicit scheduled slot required; execution timestamps are not slot identities")
    now = lambda: datetime.now(timezone.utc)
    try:
        planned = forwarded_slot(args.scheduled_slot, args.scheduler_schedule_time)
        require_delivery(planned, args.scheduler_schedule_time, now())
    except ValueError as error:
        parser.error(str(error))
    # Reject old/future/inconsistent invocations before obtaining credentials.
    emit({"event": "icon2i_freshness_slot", "scheduled_slot_utc": stamp(planned),
          "scheduler_schedule_time": args.scheduler_schedule_time,
          "basis": "scheduler_header" if args.scheduler_schedule_time else "manual_explicit"})
    budget = Budget(110)
    auth, public = transports(api_timeout_seconds=args.api_http_timeout_seconds)
    try:
        collection_budget = budget.child(75, reserve=35)
        emit({"event": "icon2i_freshness_runtime_limits", "public_http_timeout_seconds": args.public_http_timeout_seconds,
              "api_http_timeout_seconds": args.api_http_timeout_seconds, "public_document_bytes": PUBLIC_DOCUMENT_BYTES,
              "collection_budget_seconds": 75, "telemetry_reserve_seconds": 35,
              "per_product_budget_seconds": 35, "application_budget_seconds": 110})
        collector = Collector(WeatherData(auth), PublicHTTP(public, timeout_seconds=args.public_http_timeout_seconds),
                              now=now, budget=collection_budget,
                              grace={"fvg": args.fvg_grace_seconds, "national": args.national_grace_seconds})
        results = Runner(MonitorState(auth), Metrics(auth), collector,
                         now=now, budget=budget, collection_budget=collection_budget, emit=emit).run(planned)
        return int(any(not state or any(p["status"] != "confirmed" for p in state["outbox"].values())
                       for state in results.values()))
    finally:
        public.close()
        auth.close()


if __name__ == "__main__":
    raise SystemExit(main())
