"""Bounded HTTP worker. No network or credentials in the supervising process."""
import json
import math
import multiprocessing
import os
import time

from .collect import Budget, BudgetExpired, Unavailable
from .contracts import MAX_DOCUMENT

PUBLIC_DOCUMENT_BYTES = 64 * 1024
PUBLIC_TIMEOUT_SECONDS = 15
API_TIMEOUT_SECONDS = 5
CLEANUP_SECONDS = 0.2
SAFE_HEADERS = {"cache-control", "age", "etag", "content-type", "content-encoding",
                "content-length", "vary"}


def timeout_value(value, maximum):
    value = float(value)
    if not math.isfinite(value) or not 1 <= value <= maximum:
        raise ValueError(f"request timeout must be between 1 and {maximum} seconds")
    return value


class SessionTransport:
    """Streaming implementation; production calls run ONLY inside the worker.

    Chunk checks and Requests socket timeouts alone cannot cancel DNS, headers,
    slow-drip bodies or credential refresh. Transport owns that cancellation.
    """
    def __init__(self, session):
        self.session = session

    def request(self, method, url, budget, *, maximum=MAX_DOCUMENT,
                timeout_seconds=API_TIMEOUT_SECONDS, **kwargs):
        budget.remaining()
        try:
            response = self.session.request(method, url, timeout=budget.remaining(timeout_seconds),
                                            allow_redirects=False, stream=True, **kwargs)
            with response:
                budget.remaining()
                declared = response.headers.get("Content-Length", response.headers.get("content-length"))
                if declared is not None and (not str(declared).isdigit() or int(declared) > maximum):
                    raise ValueError("response byte limit exceeded")
                chunks, count = [], 0
                for chunk in response.iter_content(min(4096, maximum + 1)):
                    budget.remaining()
                    count += len(chunk)
                    if count > maximum:
                        raise ValueError("response byte limit exceeded")
                    chunks.append(chunk)
                budget.remaining()
                headers = {k.lower(): v for k, v in response.headers.items() if k.lower() in SAFE_HEADERS}
                if any(len(v) > 16384 for v in headers.values()):
                    raise ValueError("response header limit exceeded")
                return response.status_code, b"".join(chunks), headers
        except (BudgetExpired, ValueError):
            raise
        except Exception as error:
            names = {cls.__name__ for cls in type(error).__mro__}
            kind = ("timeout" if names & {"Timeout", "TimeoutError"}
                    else "connection" if "ConnectionError" in names else "transport")
            raise Unavailable("transport request failed", transient=True, failure_kind=kind) from None

    def read_json(self, url, budget, **kwargs):
        status, body, _ = self.request("GET", url, budget, **kwargs)
        if status != 200:
            raise Unavailable("Google read HTTP " + str(status), transient=status in (408, 429) or status >= 500)
        return json.loads(body)


def _session(kind):
    import requests
    if kind == "public":
        session = requests.Session()
        session.trust_env = False  # No implicit netrc credentials on public readers.
        return session
    if kind != "authorized" or os.environ.get("ICON2I_MONITOR_ALLOW_CLOUD") != "1":
        raise ValueError("authorized HTTP worker is disabled")
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return AuthorizedSession(credentials, max_refresh_attempts=0, refresh_timeout=API_TIMEOUT_SECONDS)


def _worker(connection, kind, session_factory):
    # Session setup/ADC discovery and refresh are inside the killable process.
    session = None
    try:
        session = session_factory() if session_factory else _session(kind)
        transport = SessionTransport(session)
        connection.send(("ready", None))
        while True:
            command = connection.recv()
            method, url, end, maximum, kwargs = command
            try:
                budget = Budget(deadline=end)
                response = transport.request(method, url, budget, maximum=maximum,
                                             timeout_seconds=max(0, end - time.monotonic()), **kwargs)
                result = ("ok", response)
            except BudgetExpired:
                result = ("timeout", None)
            except Unavailable as error:
                result = ("unavailable", (error.transient, error.failure_kind))
            except (ValueError, TypeError, OverflowError):
                result = ("invalid", None)
            except Exception:
                result = ("unavailable", (True, "transport"))
            # All network I/O is finished before a bounded reply is sent.
            connection.send(result)
    except (EOFError, BrokenPipeError, OSError):
        pass
    except Exception:
        try:
            connection.send(("unavailable", (True, "transport")))
        except (EOFError, BrokenPipeError, OSError):
            pass
    finally:
        connection.close()
        if session is not None:
            session.close()


class Transport(SessionTransport):
    """One persistent, serial worker per transport, discarded after a deadline.

    Never retry here: callers own read retry and uncertain-write reconciliation.
    No shared queues/locks are reused after termination. Public and authorized
    sessions are separate. Tests can inject a picklable local session factory.
    """
    def __init__(self, kind="public", *, timeout_seconds=API_TIMEOUT_SECONDS, session_factory=None):
        if kind not in {"public", "authorized"}:
            raise ValueError("invalid transport kind")
        self.kind, self.timeout_seconds, self.session_factory = kind, timeout_seconds, session_factory
        self._process = self._connection = None

    def close(self, allowance=CLEANUP_SECONDS):
        process, connection = self._process, self._connection
        self._process = self._connection = None
        if connection is not None:
            connection.close()
        if process is not None:
            if process.pid is None:
                process.close()
                return
            if process.is_alive():
                process.terminate()
            process.join(timeout=allowance / 2)
            if process.is_alive():
                process.kill()
                process.join(timeout=allowance / 2)
            if not process.is_alive():
                process.close()

    def _receive(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not self._connection.poll(remaining):
            raise TimeoutError()
        result = self._connection.recv()
        if time.monotonic() >= deadline:
            raise TimeoutError()
        return result

    def _start(self, deadline):
        if self._process is None:
            context = multiprocessing.get_context("spawn")
            self._connection, child = context.Pipe()
            self._process = context.Process(target=_worker, args=(child, self.kind, self.session_factory),
                                            name="icon2i-http-" + self.kind, daemon=True)
            try:
                self._process.start()
            finally:
                child.close()
            status, _ = self._receive(deadline)
            if status != "ready":
                raise Unavailable("transport initialization failed", transient=True, failure_kind="transport")

    def request(self, method, url, budget, *, maximum=MAX_DOCUMENT, timeout_seconds=None, **kwargs):
        requested = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        if not math.isfinite(requested) or requested <= 0 or not 0 < maximum <= MAX_DOCUMENT:
            raise ValueError("invalid request limits")
        allowed = budget.remaining(requested)
        limited_by_budget = allowed < requested
        # Cleanup is INCLUDED in the request/collection allowance, not borrowed
        # from the state/telemetry reserve. Small residual budgets stop early.
        cleanup = min(CLEANUP_SECONDS, allowed / 4)
        deadline = time.monotonic() + allowed - cleanup
        try:
            self._start(deadline)
            # The worker acknowledged readiness before send; it is reading this
            # command, not running network setup. Application payloads are bounded.
            if len(json.dumps(kwargs, default=lambda x: x.decode("utf-8") if isinstance(x, bytes) else None)) > MAX_DOCUMENT:
                raise ValueError("request payload byte limit exceeded")
            self._connection.send((method, url, deadline, maximum, kwargs))
            status, payload = self._receive(deadline)
            if status == "timeout":
                raise TimeoutError()
            if status == "invalid":
                raise ValueError("response byte/header limit or representation invalid")
            if status == "unavailable":
                transient, kind = payload
                raise Unavailable("transport request failed", transient=transient, failure_kind=kind)
            if status != "ok":
                raise Unavailable("transport protocol failed", transient=True, failure_kind="transport")
            budget.remaining()
            return payload
        except TimeoutError:
            self.close(cleanup)
            if limited_by_budget:
                raise BudgetExpired() from None
            raise Unavailable("request absolute deadline exceeded", transient=True, failure_kind="timeout") from None
        except (EOFError, BrokenPipeError, OSError):
            self.close(cleanup)
            raise Unavailable("transport worker unavailable", transient=True, failure_kind="transport") from None
        except Unavailable:
            # Also discard failed initialization and any uncertain transport.
            self.close(cleanup)
            raise
