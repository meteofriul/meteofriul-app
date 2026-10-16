"""Versioned monitor state and a durable per-point outbox."""
from copy import deepcopy
import uuid
from .core import METRICS, PRODUCTS, evaluate, instant, log_record, slot, stamp
from .collect import BudgetExpired, Unavailable
from .schedule import require_active_slot


class Conflict(Exception):
    pass


class Rejected(Exception):
    """Monitoring explicitly rejected this single-point write (not a lost response)."""


def _validate_state(value, product):
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError("monitor state must be an object")
    if (value.get("schema_version") != 1 or value.get("product") != product
            or set(value.get("outbox", {})) != set(METRICS)):
        raise ValueError("invalid monitor state")
    slot(value["scheduled_slot_utc"])
    instant(value["observed_at"])
    if (type(value["critical_active"]) is not int or value["critical_active"] not in (0, 1)
            or type(value["check_state"]) is not int or value["check_state"] not in (0, 1, 2, 3)
            or type(value["check_completed"]) is not int or value["check_completed"] != 1):
        raise ValueError("invalid monitor metric state")
    for name, point in value["outbox"].items():
        if type(point["value"]) is not int or point["value"] != value[name]:
            raise ValueError("outbox differs from evaluation")
        if point["status"] not in ("ready", "prepared", "confirmed", "rejected", "conflict", "superseded"):
            raise ValueError("invalid outbox status")
    if not isinstance(value["history"], list) or len(value["history"]) != 6:
        raise ValueError("invalid slot history")
    for item in value["history"]:
        slot(item["slot"])
        if item["indeterminate"] is not None and type(item["indeterminate"]) is not bool:
            raise ValueError("invalid history result")
    if value["critical_active"] and not value["critical_causes"]:
        raise ValueError("critical state without causes")


def validate_state(value, product):
    try:
        _validate_state(value, product)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("incomplete monitor state") from error


class Runner:
    def __init__(self, state, metrics, collector, *, now, budget, emit):
        self.state, self.metrics, self.collector = state, metrics, collector
        self.now, self.budget, self.emit = now, budget, emit

    def read(self, product):
        self.budget.remaining()
        version, value = self.state.read(product, self.budget)
        validate_state(value, product)
        return version, value

    def run_product(self, product, planned_slot, observation=None):
        planned = stamp(slot(planned_slot))
        version, old = self.read(product)
        if old and instant(old["scheduled_slot_utc"]) > slot(planned):
            self.emit({"event": "icon2i_freshness_superseded", "product": product, "scheduled_slot_utc": planned})
            return old
        require_active_slot(planned, self.now())
        if not old or old["scheduled_slot_utc"] != planned:
            if observation is None:
                observation = self.collector.collect(product)
            for _ in range(3):
                require_active_slot(planned, self.now())
                next_state = evaluate(product, planned, self.now(), observation, old)
                if next_state is None:
                    break
                try:
                    self.state.cas(product, version, next_state, self.budget)
                    old = next_state
                    break
                except (Conflict, Unavailable):
                    # A failed response can hide a successful CAS. Read before deciding.
                    version, old = self.read(product)
            else:
                raise Unavailable("monitor state contention")
        if old and old["scheduled_slot_utc"] == planned:
            self.emit({**log_record(old), "phase": "evaluation_committed"})
            self.flush(product, planned)
            _, latest = self.read(product)
            if latest and latest["scheduled_slot_utc"] == planned:
                self.emit({**log_record(latest), "phase": "telemetry_result"})
                return latest
        return old

    def change_point(self, product, planned, name, transform):
        for _ in range(3):
            version, current = self.read(product)
            if not current or current["scheduled_slot_utc"] != planned:
                return None
            value = deepcopy(current)
            if not transform(value["outbox"][name]):
                return None
            try:
                self.state.cas(product, version, value, self.budget)
                return value
            except Conflict:
                continue
        raise Unavailable("outbox contention")

    def flush(self, product, planned):
        # Each metric is its own API write: a partially successful batch is not
        # confused with three acknowledged points. Pending writes are reconciled.
        for name in METRICS:
            require_active_slot(planned, self.now())
            _, state = self.read(product)
            if not state or state["scheduled_slot_utc"] != planned:
                return
            point = state["outbox"][name]
            if point["status"] in ("confirmed", "conflict", "superseded"):
                continue
            timestamp, value = state["observed_at"], point["value"]
            latest = self.metrics.latest(product, name, timestamp, self.budget)
            status = None
            if latest is not None:
                when, number = latest
                if instant(when) > instant(timestamp):
                    status = "superseded"
                elif instant(when) == instant(timestamp):
                    status = "confirmed" if number == value else "conflict"
            if status:
                self.change_point(product, planned, name, lambda p: self._set(p, status))
                continue
            # An absent sample does not prove a prepared request failed: the
            # original request can still be in flight or not yet visible.
            if point["status"] == "prepared" or point.get("attempts", 0) >= 2:
                continue
            owner = uuid.uuid4().hex
            def prepare(p):
                if p["status"] not in ("ready", "rejected") or p.get("attempts", 0) >= 2:
                    return False
                p.update(status="prepared", owner=owner, attempts=p.get("attempts", 0) + 1)
                return True
            prepared = self.change_point(product, planned, name, prepare)
            if prepared is None:
                continue
            # Check that a newer evaluation did not supersede us before I/O.
            _, current = self.read(product)
            if current["scheduled_slot_utc"] != planned or current["outbox"][name].get("owner") != owner:
                continue
            require_active_slot(planned, self.now())
            try:
                self.metrics.write(product, name, timestamp, value, self.budget)
                outcome = "confirmed"
            except Rejected:
                outcome = "rejected"
            except Unavailable:
                outcome = "prepared"  # Uncertain commit, never blindly resend.
            def finish(p):
                if p.get("owner") != owner or p["status"] != "prepared":
                    return False
                p["status"] = outcome
                return True
            self.change_point(product, planned, name, finish)

    @staticmethod
    def _set(point, status):
        point["status"] = status
        return True

    def run(self, planned_slot):
        results, observations, failures = {}, {}, set()
        # Observe both products before telemetry I/O can consume the reserve.
        for product in PRODUCTS:
            try:
                require_active_slot(planned_slot, self.now())
                _, old = self.read(product)
                if not old or slot(old["scheduled_slot_utc"]) < slot(planned_slot):
                    observations[product] = self.collector.collect(product)
            except (Unavailable, BudgetExpired, ValueError) as error:
                self.error(product, planned_slot, error)
                failures.add(product)
        for product in PRODUCTS:
            if product in failures:
                results[product] = None
                continue
            try:
                results[product] = self.run_product(product, planned_slot, observations.get(product))
            except (Unavailable, BudgetExpired, ValueError) as error:
                self.error(product, planned_slot, error)
                results[product] = None
        return results

    def error(self, product, planned_slot, error):
        # No synthetic zero or heartbeat after a persistence failure.
        self.emit({"event": "icon2i_freshness_monitor_error", "product": product,
                   "scheduled_slot_utc": stamp(slot(planned_slot)),
                   "error_type": type(error).__name__, "error": str(error)})
