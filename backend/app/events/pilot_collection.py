"""Bounded pilot job orchestration, deliberately independent of HTTP requests.

Adapters must return explicit ok/error status: an empty list alone does not
prove an upstream source succeeded. No shared engine cache is published here.
"""
import multiprocessing
import json
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from .pilot_source_policy import gate_batch
from .pilot_catalog import PILOT_PROJECT, merge_collection


def _run(source, adapter, sender):
    try:
        result = adapter()
        if not isinstance(result, dict) or result.get("status") not in {"ok", "error"}:
            result = {"status": "error", "error_type": "invalid_adapter_result"}
        sender.send(result)
    except Exception as exc:
        # Keep useful diagnostics without copying source URLs or unbounded text.
        detail = re.sub(r'https?://\S+', '[url]', str(exc))
        detail = ' '.join(detail.split())[:240]
        failure = {"status": "error", "error_type": "adapter_exception",
                   "exception_type": type(exc).__name__, "error_detail": detail}
        sender.send(failure)
        print(json.dumps({"event_source_failure": {"source": source, **failure}},
                         ensure_ascii=False), flush=True)
    finally:
        sender.close()


def collect(project, adapters, previous, collected_at, timeout=60, source_timeouts=None):
    if project != PILOT_PROJECT:
        raise ValueError("isolated pilot project required")
    if not 0 < timeout <= 120 or not 1 <= len(adapters) <= 15:
        raise ValueError("invalid collection bounds")
    source_timeouts = source_timeouts or {}
    if any(name not in adapters or not 0 < value <= 360 for name, value in source_timeouts.items()):
        raise ValueError("invalid source timeout")
    if sum(source_timeouts.get(name, timeout) for name in adapters) > 875:
        raise ValueError("total collection budget exceeded")
    context = multiprocessing.get_context("spawn")
    results = {}
    # Sequential sources cap load on providers and worker memory.
    for name, adapter in adapters.items():
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(target=_run, args=(name, adapter, sender))
        try:
            process.start()
            sender.close()
            if receiver.poll(source_timeouts.get(name, timeout)):
                try:
                    results[name] = receiver.recv()
                except EOFError:
                    results[name] = {"status": "error", "error_type": "worker_exit"}
            else:
                results[name] = {"status": "error", "error_type": "timeout"}
        finally:
            if process.pid is not None:
                process.join(timeout=0.2)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
                if process.is_alive():
                    process.kill()
                    process.join()
                process.close()
            sender.close()
            receiver.close()
    today = datetime.fromisoformat(collected_at.replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Rome')).date()
    previous_sources = (previous or {}).get('sources', {})
    results = {name: gate_batch(name, batch, today=today,
                               previous_batch=previous_sources.get(name))
               for name, batch in results.items()}
    return merge_collection(project, previous, results, collected_at)
