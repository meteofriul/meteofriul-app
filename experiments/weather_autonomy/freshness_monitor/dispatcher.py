"""Private ASGI relay: Scheduler source time -> explicit Cloud Run Job args.

Authentication is enforced by Cloud Run IAM, not by Scheduler headers. Deploy
only as a private service with the dedicated Scheduler principal as sole invoker.
Imports, --help, and the default image command never acquire credentials.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os

from .collect import Budget, Unavailable
from .core import stamp
from .google import transports
from .schedule import (PROJECT, JOB, JOB_RESOURCE, DISPATCHER, SCHEDULER, ExpiredSlot,
                       scheduler_slot, require_delivery, job_overrides)

RUN_URL = "https://run.googleapis.com/v2/" + JOB_RESOURCE + ":run"


def emit(record):
    print(json.dumps(record, sort_keys=True, allow_nan=False), flush=True)


class JobLauncher:
    """One launch attempt per delivery; no retry after an uncertain POST."""
    def __init__(self, transport, *, owns_transport=False):
        self.transport, self.owns_transport = transport, owns_transport

    def launch(self, planned, source_time):
        try:
            status, body, _ = self.transport.request("POST", RUN_URL, Budget(10),
                maximum=65536, json=job_overrides(planned, source_time))
        finally:
            if self.owns_transport:
                self.transport.close()
        if status != 200:
            raise Unavailable("job launch rejected or uncertain")
        try:
            operation = json.loads(body)
            name = operation["name"]
            prefix = f"projects/{PROJECT}/locations/europe-west1/operations/"
            if not isinstance(name, str) or not name.startswith(prefix) or operation.get("error"):
                raise ValueError("invalid launch acknowledgement")
        except (ValueError, KeyError, TypeError):
            raise Unavailable("job launch acknowledgement invalid or uncertain") from None
        return name


def cloud_launcher():
    auth, _ = transports()
    return JobLauncher(auth, owns_transport=True)


class Application:
    def __init__(self, launcher_factory, *, now=None, log=emit):
        self.launcher_factory = launcher_factory
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.log = log

    def dispatch(self, headers):
        record = {"event": "icon2i_freshness_dispatch", "received_at": stamp(self.now())}
        validation_stage = "scheduler_identity"
        try:
            # HTTP delivery uses the short job ID in production. Accept only
            # that exact ID or its canonical resource; IAM authenticates callers.
            if (headers.get("x-cloudscheduler") != "true"
                    or headers.get("x-cloudscheduler-jobname") not in (JOB, SCHEDULER)):
                raise ValueError("unexpected scheduler identity")
            validation_stage = "scheduler_time"
            source = headers.get("x-cloudscheduler-scheduletime")
            planned = scheduler_slot(source)
            record.update(scheduler_job=SCHEDULER, scheduler_job_received=headers["x-cloudscheduler-jobname"],
                          scheduler_schedule_time=source,
                          scheduled_slot_utc=stamp(planned), basis="scheduler_header")
            validation_stage = "delivery_window"
            require_delivery(planned, source, self.now())
        except ExpiredSlot:
            # Acknowledge an obsolete delivery, but do not start work or emit a heartbeat.
            self.log({**record, "outcome": "expired_before_dispatch", "severity": "WARNING"})
            return 204, b""
        except ValueError:
            # Only bounded scheduling metadata; never Authorization or all headers.
            received = {name: headers.get(name, "")[:limit] for name, limit in (
                ("x-cloudscheduler", 16), ("x-cloudscheduler-jobname", 200),
                ("x-cloudscheduler-scheduletime", 64))}
            self.log({**record, "outcome": "invalid_delivery", "severity": "ERROR",
                      "validation_stage": validation_stage, "scheduler_headers": received})
            return 400, b'{"error":"invalid_scheduler_delivery"}'
        try:
            launcher = self.launcher_factory()
            # Factory/credential setup can itself consume the remaining slot.
            require_delivery(planned, source, self.now())
            operation = launcher.launch(planned, source)
        except ExpiredSlot:
            self.log({**record, "outcome": "expired_before_launch", "severity": "WARNING"})
            return 204, b""
        except Exception as error:
            # Do not log tokens, underlying HTTP exceptions or a false success.
            self.log({**record, "outcome": "launch_uncertain", "error_type": type(error).__name__,
                      "severity": "ERROR"})
            return 503, b'{"error":"launch_uncertain"}'
        self.log({**record, "outcome": "launch_accepted", "operation": operation, "severity": "INFO"})
        return 202, b'{"status":"launch_accepted"}'

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            raise ValueError("HTTP only; run ASGI lifespan off")
        status, body = 400, b'{"error":"invalid_request"}'
        if scope.get("path") != "/dispatch" or scope.get("query_string"):
            status, body = 404, b'{"error":"not_found"}'
        elif scope.get("method") != "POST":
            status, body = 405, b'{"error":"method_not_allowed"}'
        else:
            try:
                headers = {}
                wanted = {"x-cloudscheduler", "x-cloudscheduler-jobname", "x-cloudscheduler-scheduletime"}
                for key, value in scope.get("headers", []):
                    name = key.decode("ascii").lower()
                    if name in wanted:
                        if name in headers:
                            raise ValueError("duplicate scheduler header")
                        headers[name] = value.decode("ascii")
                async def read_body():
                    content = b""
                    while True:
                        part = await receive()
                        if part["type"] != "http.request":
                            raise ValueError("disconnected")
                        content += part.get("body", b"")
                        if len(content) > 1024:
                            raise ValueError("request too large")
                        if not part.get("more_body"):
                            return content
                content = await asyncio.wait_for(read_body(), timeout=5)
                if content and json.loads(content) != {}:
                    raise ValueError("body cannot supply slot or job overrides")
            except (ValueError, UnicodeError, TimeoutError):
                self.log({"event": "icon2i_freshness_dispatch", "outcome": "invalid_request",
                          "severity": "ERROR", "received_at": stamp(self.now())})
            else:
                status, body = await asyncio.to_thread(self.dispatch, headers)
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": body})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--cloud", action="store_true")
    args = parser.parse_args(argv)
    if (not args.serve or not args.cloud or os.environ.get("ICON2I_MONITOR_ALLOW_CLOUD") != "1"
            or os.environ.get("GOOGLE_CLOUD_PROJECT") != PROJECT
            or os.environ.get("K_SERVICE") != DISPATCHER):
        parser.error("private cloud dispatcher is disabled; explicit project/service opt-in required")
    import uvicorn
    uvicorn.run(Application(cloud_launcher), host="0.0.0.0", port=int(os.environ.get("PORT", "8080")),
                lifespan="off", ws="none", access_log=False, proxy_headers=False, timeout_keep_alive=5)


if __name__ == "__main__":
    main()
