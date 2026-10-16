"""Bounded observation of published objects. No weather-write capability."""
from dataclasses import dataclass
import time
from . import contracts as c
from .core import empty_comparison, instant, stamp


class Unavailable(Exception):
    def __init__(self, reason, *, transient=False):
        super().__init__(reason)
        self.transient = transient


class BudgetExpired(Exception):
    pass


class Budget:
    def __init__(self, seconds=75, clock=time.monotonic):
        self.clock, self.end = clock, clock() + seconds

    def remaining(self, maximum=5):
        left = self.end - self.clock()
        if left <= 0:
            raise BudgetExpired()
        return min(left, maximum)


@dataclass(frozen=True)
class Object:
    body: bytes
    generation: str
    time_created: str
    size: int


def headers(product, *, diagnostic=False, resolver=False):
    result = {"Origin": "https://localhost", "Accept": "*/*" if resolver else "application/json",
              "Cache-Control": "max-age=0" if product == "fvg" and not diagnostic else "no-cache"}
    if product == "national":
        result["Pragma"] = "no-cache"
    return result


def once_more(operation, budget):
    for attempt in range(2):
        budget.remaining()
        try:
            return operation()
        except Unavailable as error:
            if not error.transient or attempt:
                raise


class Collector:
    def __init__(self, data, http, *, now, budget, grace=None, catalog_pair=None):
        self.data, self.http, self.now, self.budget = data, http, now, budget
        self.grace = grace or {"fvg": 60, "national": 60}
        if set(self.grace) != {"fvg", "national"} or any(
                type(v) not in (int, float) or not 30 <= v <= 90 for v in self.grace.values()):
            raise ValueError("transition grace must be 30..90 seconds for both products")
        self.catalog_pair = catalog_pair

    def call(self, fn):
        return once_more(fn, self.budget)

    def request(self, product, path, entry, *, diagnostic=False, resolver=False):
        request_headers = headers(product, diagnostic=diagnostic, resolver=resolver)
        entry.update({"result": "unreadable", "requested_at": stamp(self.now()),
                      "headers": request_headers})
        try:
            response = self.call(lambda: self.http.get(
                c.BASES[product] + path, request_headers, self.budget))
            entry.update({"status": response["status"], "received_at": stamp(self.now()),
                          "response_headers": response.get("headers", {})})
            if response["status"] != 200:
                raise Unavailable("HTTP response without a usable body")
            value = c.decode(response["body"])
            c.http_identity(product, value, resolver=resolver)
            entry.update({"result": "coherent", "source_run_id":
                          value["source_run_id"] if resolver or product == "national"
                          else value["latest"]["source_run_id"]})
            return value
        except (ValueError, KeyError, TypeError):
            entry["result"] = "incompatible"
            return None
        except Unavailable:
            entry["result"] = "unreadable"
            return None

    def collect(self, product):
        parent = self.budget
        try:
            self.budget = Budget(parent.remaining(35), clock=parent.clock)
            return self._collect(product)
        except BudgetExpired:
            return {"complete": False, "indeterminate": True, "critical_causes": [],
                    "budget_exhausted": True, "http_comparison": empty_comparison(product)}
        finally:
            self.budget = parent

    def _collect(self, product):
        obs = {"complete": False, "indeterminate": False, "critical_causes": [],
               "http_comparison": empty_comparison(product), "snapshots_attempted": 0}
        prefix, pointer_key = c.ROOTS[product], c.ROOTS[product] + c.POINTERS[product]
        try:
            # At most one reconstructed snapshot. All calls share one deadline.
            for attempt in range(2):
                obs["snapshots_attempted"] = attempt + 1
                obj = self.call(lambda: self.data.get(pointer_key, self.budget))
                ptr, run, descriptor = c.pointer(product, obj.body, catalog_pair=self.catalog_pair)
                created = instant(obj.time_created)
                if created > instant(self.now()) or created < instant(run["run_at"]):
                    raise ValueError("invalid pointer creation time")
                obs["run"] = {**run, "generation": obj.generation, "time_created": stamp(created)}
                obs["pointer_readable_at"] = stamp(self.now())
                comparison = empty_comparison(product)
                obs["http_comparison"] = comparison
                public = self.request(product, c.POINTERS[product], comparison["ordinary"])
                resolved = (self.request(product, c.RESOLVER, comparison["resolve"]["ordinary"], resolver=True)
                            if product == "national" else None)
                after = self.call(lambda: self.data.head(pointer_key, self.budget))
                obs["generation_after_http"] = after.generation
                if after.generation != obj.generation:
                    obs.setdefault("superseded_comparisons", []).append(comparison)
                    if attempt == 0:
                        continue
                    obs["indeterminate"] = True
                    comparison["ordinary"]["result"] = "indeterminate"
                    return obs
                for entries, label in ((comparison, "http_pointer"), (comparison["resolve"], "resolver")):
                    if entries["ordinary"]["result"] in ("unreadable", "incompatible"):
                        obs["critical_causes"].append(label + "_" + entries["ordinary"]["result"])
                # Keep already proven anomalies even if later metadata I/O
                # exhausts the budget. Uncertainty cannot erase this evidence.
                for value, entries, is_resolver, label in (
                        (public, comparison, False, "http_pointer"),
                        (resolved, comparison["resolve"], True, "resolver")):
                    if value is None:
                        continue
                    remote_id = c.http_identity(product, value, resolver=is_resolver)
                    if remote_id > run["source_run_id"]:
                        entries["ordinary"]["result"] = "http_newer"
                        obs["critical_causes"].append(label + "_newer_than_storage")
                    elif remote_id == run["source_run_id"]:
                        try:
                            if is_resolver:
                                if any(value[key] != ptr[key] for key in
                                       ("run_at", "generated_at", "manifest", "index")):
                                    raise ValueError("resolver common fields differ")
                            elif c.common(product, value) != c.common(product, ptr):
                                raise ValueError("public common fields differ")
                        except (KeyError, ValueError, TypeError):
                            entries["ordinary"]["result"] = "incompatible"
                            obs["critical_causes"].append(label + "_incompatible")
                break
            # Metadata remains tied to the stable pointer, even if HTTP failed.
            manifest_obj = self.call(lambda: self.data.get(prefix + descriptor["path"], self.budget))
            manifest_doc, descriptors, last_at = c.manifest(
                product, manifest_obj.body, descriptor, ptr, catalog_pair=self.catalog_pair)
            obs["last_at"] = last_at
            index_doc = None
            if product == "national":
                index_obj = self.call(lambda: self.data.get(prefix + manifest_doc["index"]["path"], self.budget))
                index_doc = c.index(index_obj.body, manifest_doc, catalog_pair=self.catalog_pair)
            listed = self.call(lambda: self.data.list(prefix + "runs/" + run["source_run_id"] + "/", self.budget))
            expected = [descriptor, *descriptors]
            # One fresh metadata listing confirms missing/wrong-size objects.
            def missing(items):
                return [item["path"] for item in expected
                        if items.get(prefix + item["path"]) != item["json_bytes"]]
            absent = missing(listed)
            if absent:
                absent = missing(self.call(lambda: self.data.list(
                    prefix + "runs/" + run["source_run_id"] + "/", self.budget)))
                if absent:
                    obs["critical_causes"].append("referenced_object_missing_or_wrong_size")
                    obs["invalid_objects"] = absent[:20]
            obs["referenced_object_count"] = len(expected)

            endpoints = [(comparison, public, False, c.POINTERS[product])]
            if product == "national":
                endpoints.append((comparison["resolve"], resolved, True, c.RESOLVER))
            for entries, value, is_resolver, path in endpoints:
                ordinary = entries["ordinary"]
                cause_prefix = "resolver" if is_resolver else "http_pointer"
                if value is None:
                    continue
                remote_run = c.http_identity(product, value, resolver=is_resolver)
                if remote_run != run["source_run_id"]:
                    direction = "http_older" if remote_run < run["source_run_id"] else "http_newer"
                    ordinary["result"] = direction
                    if direction == "http_newer":
                        obs["critical_causes"].append(cause_prefix + "_newer_than_storage")
                        continue
                    # Diagnostic is only after an ordinary mismatch; preserve it.
                    diagnostic = self.request(product, path, entries["diagnostic"],
                                              diagnostic=True, resolver=is_resolver)
                    final_head = self.call(lambda: self.data.head(pointer_key, self.budget))
                    if final_head.generation != obj.generation:
                        obs["indeterminate"] = True
                        entries["diagnostic"]["result"] = "indeterminate"
                        continue
                    if diagnostic is not None:
                        diagnostic_run = c.http_identity(product, diagnostic, resolver=is_resolver)
                        diagnostic_result = ("http_older" if diagnostic_run < run["source_run_id"]
                            else "http_newer" if diagnostic_run > run["source_run_id"] else "coherent")
                        if diagnostic_result == "coherent":
                            try:
                                if is_resolver:
                                    c.resolution(diagnostic, ptr, manifest_doc, index_doc)
                                elif c.common(product, diagnostic) != c.common(product, ptr):
                                    raise ValueError("diagnostic pointer differs")
                            except (ValueError, KeyError, TypeError, StopIteration):
                                diagnostic_result = "incompatible"
                        entries["diagnostic"]["result"] = diagnostic_result
                        if diagnostic_result in ("http_newer", "incompatible"):
                            obs["critical_causes"].append(cause_prefix + "_diagnostic_" + diagnostic_result)
                    elapsed = (instant(self.now()) - created).total_seconds()
                    if elapsed <= self.grace[product]:
                        obs["indeterminate"] = True
                    else:
                        # A diagnostic success cannot certify the ordinary path.
                        obs["critical_causes"].append(cause_prefix + "_older_than_storage")
                    continue
                try:
                    if is_resolver:
                        c.resolution(value, ptr, manifest_doc, index_doc)
                    elif c.common(product, value) != c.common(product, ptr):
                        raise ValueError("common pointer fields differ")
                except (ValueError, KeyError, TypeError, StopIteration):
                    ordinary["result"] = "incompatible"
                    obs["critical_causes"].append(cause_prefix + "_incompatible")
            obs["critical_causes"] = sorted(set(obs["critical_causes"]))
            obs["complete"] = not obs["indeterminate"] and not obs["critical_causes"]
        except BudgetExpired:
            obs["indeterminate"] = True
            obs["budget_exhausted"] = True
        except Unavailable as error:
            obs["critical_causes"].append("storage_unreadable")
            obs["error"] = str(error)
        except (ValueError, KeyError, TypeError, StopIteration, OverflowError) as error:
            obs["critical_causes"].append("document_invalid")
            obs["error"] = str(error)
        return obs
