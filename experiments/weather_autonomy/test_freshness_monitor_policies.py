"""Run real PromQL semantics offline with a separately installed promtool."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

from freshness_monitor.definitions import (data_query, absence_query, selector,
                                           policies, descriptors, queries, deployment_plan)
from freshness_monitor.core import METRICS, PRODUCTS

HERE = Path(__file__).resolve().parent


def sample(labels, value=1):
    return {"labels": labels, "value": value}


def expr_case(expr, when, values):
    return {"expr": expr, "eval_time": when, "exp_samples": values}


def scenarios():
    data, absence = data_query("fvg"), absence_query()
    stopped = [{"series": selector(metric, product),
                "values": ("1" if metric == "check_completed" or
                           (product == "fvg" and metric == "critical_active") else "0")}
               for product in PRODUCTS for metric in METRICS]
    partial = [{"series": selector(metric, product),
                "values": "1" if (product, metric) == ("fvg", "critical_active") else "0+0x8"}
               for product in PRODUCTS for metric in METRICS]
    return {"evaluation_interval": "1m", "tests": [
        {"name": "critical then monitor stops: 30 minute overlap", "interval": "30m",
         "input_series": stopped, "promql_expr_test": [
             expr_case(data, "89m", [sample('{product="fvg"}')]),
             expr_case(absence, "89m", []),
             expr_case(data, "90m", [sample('{product="fvg"}')]),
             expr_case(absence, "90m", [sample("{}")]),
             expr_case(data, "119m", [sample('{product="fvg"}')]),
             expr_case(absence, "119m", [sample("{}")]),
             expr_case(data, "120m", []),
             expr_case(absence, "120m", [sample("{}")])]},
        {"name": "new zero closes normally without waiting 120 minutes", "interval": "30m",
         "input_series": [{"series": selector("critical_active", "fvg"), "values": "1 0 0"}],
         "promql_expr_test": [expr_case(data, "29m", [sample('{product="fvg"}')]),
                             expr_case(data, "30m", []), expr_case(data, "31m", [])]},
        {"name": "missing one state series despite heartbeat", "interval": "30m",
         "input_series": partial, "promql_expr_test": [
             expr_case(absence, "89m", []), expr_case(absence, "90m", [sample("{}")]),
             expr_case(data, "90m", [sample('{product="fvg"}')])]},
        {"name": "bootstrap never silently healthy", "interval": "30m", "input_series": [],
         "promql_expr_test": [expr_case(absence, "0m", [sample("{}")]),
                             expr_case(absence, "91m", [sample("{}")]), expr_case(data, "91m", [])]},
    ]}


class DefinitionTests(unittest.TestCase):
    def test_disabled_policies_and_fixed_cardinality(self):
        items = policies()
        self.assertEqual(len(items), 3)
        for p in items:
            self.assertFalse(p["enabled"])
            self.assertEqual(p["notificationChannels"], [])
            self.assertEqual(p["alertStrategy"]["notificationPrompts"], ["OPENED", "CLOSED"])
            self.assertEqual(len(p["conditions"]), 1)
            condition = p["conditions"][0]["conditionPrometheusQueryLanguage"]
            self.assertEqual((condition["duration"], condition["evaluationInterval"]), ("0s", "60s"))
        configured = policies(["projects/meteo-friul/notificationChannels/example"])
        for p in configured:
            self.assertEqual(p["alertStrategy"]["notificationPrompts"], ["OPENED", "CLOSED"])
            self.assertEqual(p["alertStrategy"]["notificationChannelStrategy"][0]["renotifyInterval"], "21600s")
            self.assertFalse(p["enabled"])
        self.assertEqual(len(descriptors()), 3)
        for metric in descriptors():
            self.assertEqual(metric["labels"][0]["key"], "product")
            self.assertEqual(len(metric["labels"]), 1)
        self.assertEqual(len(queries()), 3)
        self.assertEqual(deployment_plan()["scheduler"]["schedule"], "10,40 * * * *")

    def test_review_files_match_the_definitions(self):
        for filename, value in (("policies.json", policies()), ("metrics.json", descriptors()),
                                ("logging-queries.json", queries()), ("deployment-plan.json", deployment_plan())):
            path = HERE / "freshness_monitor" / "resources" / filename
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), value)

    @unittest.skipUnless(os.environ.get("PROMTOOL"), "Set PROMTOOL to a verified local promtool executable")
    def test_real_promql_windows_absence_bootstrap_and_recovery(self):
        with tempfile.TemporaryDirectory(prefix="icon2i-policy-tests-") as tmp:
            fixture = Path(tmp) / "policies.test.yml"
            fixture.write_text(json.dumps(scenarios(), indent=2), encoding="utf-8")
            result = subprocess.run([os.environ["PROMTOOL"], "test", "rules", str(fixture)],
                                    capture_output=True, text=True, timeout=45, cwd=tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
