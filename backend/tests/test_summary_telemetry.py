from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from app.services.summary_telemetry import SourceTrace, execution_context, sanitize_source_trace, MAX_RUNS
from app.services.morning_forecast_delivery import MorningForecastDeliveryService
from app.services.evening_forecast_delivery import EveningForecastDeliveryService
from app.weather.local_notice_source import LocalNoticeSourceUnavailable
from app.jobs import send_morning_forecast, send_evening_forecast
import test_morning_forecast_delivery as morning
import test_evening_forecast_delivery as evening


class SummaryTelemetryTests(unittest.TestCase):
    def test_aggregates_groups_not_devices_and_keeps_run_rotation(self):
        trace=SourceTrace(); now=datetime(2026,10,25,6,30,tzinfo=timezone.utc)
        for run in ("20261024T120000Z","20261024T120000Z","20261025T000000Z"):
            trace.observe({"source_run_id":run,"token":"SECRET","coordinates":[1,2]},read_at=now)
        trace.observe({},read_at=now); trace.fetch_failed()
        result=sanitize_source_trace(trace.summary())
        self.assertEqual(result["fetched_groups"],4)
        self.assertEqual(result["fetch_failed_groups"],1)
        self.assertEqual(result["unknown_run_groups"],1)
        self.assertEqual([row["groups"] for row in result["runs"]],[2,1])
        self.assertNotIn("SECRET",json.dumps(result))
        self.assertNotIn("coordinates",json.dumps(result))

    def test_invalid_ids_never_leak_and_count_is_bounded(self):
        trace=SourceTrace();now=datetime(2026,10,25,tzinfo=timezone.utc)
        for value in (None,"SECRET","20269999T999999Z",True):
            trace.observe({"source_run_id":value},read_at=now)
        for i in range(MAX_RUNS+2):
            value=(now-timedelta(days=i)).strftime("%Y%m%dT%H%M%SZ")
            trace.observe({"source_run_id":value},read_at=now)
        result=sanitize_source_trace(trace.summary())
        self.assertEqual(len(result["runs"]),MAX_RUNS)
        self.assertEqual(result["omitted_run_groups"],2)
        self.assertEqual(result["unknown_run_groups"],4)
        self.assertNotIn("SECRET",json.dumps(result))

    def test_forged_trace_is_rejected(self):
        trace=SourceTrace(); trace.observe({"source_run_id":"20261025T000000Z"},read_at=datetime.now(timezone.utc))
        for key,value in (("fetched_groups",99),("fetched_groups",True),("unknown_run_groups",-1)):
            bad=trace.summary();bad[key]=value
            with self.assertRaises(ValueError):sanitize_source_trace(bad)

    def test_invocation_date_is_not_tomorrows_evening_forecast_date_or_origin(self):
        now=datetime(2026,10,25,23,30,tzinfo=timezone.utc)
        result=execution_context("evening",now,now,environment={"CLOUD_RUN_EXECUTION":"meteofriul-evening-forecast-abc12"})
        self.assertEqual(result["invocation_local_date"],"2026-10-26")
        self.assertEqual(result["origin"],"not_attested_by_worker")
        self.assertEqual(result["execution"],"meteofriul-evening-forecast-abc12")
        result=execution_context("evening",now,now,environment={"CLOUD_RUN_EXECUTION":"SECRET"})
        self.assertIsNone(result["execution"])

    def service(self,module,cls,source,devices=None):
        return cls(device_repository=module.FakeDeviceRepository(devices if devices is not None else [module.device()]),
                   source=source,sender=module.FakeSender(),config=module.config(),now=lambda:module.NOW)

    def test_both_services_add_metadata_without_changing_delivery(self):
        for module,cls,job in ((morning,MorningForecastDeliveryService,send_morning_forecast),
                               (evening,EveningForecastDeliveryService,send_evening_forecast)):
            with self.subTest(job=job.__name__):
                value=module.snapshot();value.setdefault("source_run_id","20260929T000000Z")
                service=self.service(module,cls,module.FakeSource(value))
                result=service.run()
                self.assertEqual(result.sent,1)
                trace=sanitize_source_trace(result.summary()["source_trace"])
                self.assertEqual(trace["fetched_groups"],1)
                self.assertEqual(trace["runs"][0]["source_run_id"],value["source_run_id"])
                output=io.StringIO()
                factory="get_morning_forecast_delivery_service" if module is morning else "get_evening_forecast_delivery_service"
                with patch.object(job,factory,return_value=service),patch.object(service,"run",return_value=result),redirect_stdout(output):
                    self.assertEqual(job.main(),0)
                payload=json.loads(output.getvalue())
                self.assertIn("execution_context",payload)
                self.assertNotIn("token-a",output.getvalue())

    def test_two_devices_one_place_has_one_source_group(self):
        devices=[morning.device(),morning.device(device_id="b"*64,token="second-private")]
        value=morning.snapshot();value["source_run_id"]="20260929T000000Z"
        service=self.service(morning,MorningForecastDeliveryService,morning.FakeSource(value),devices)
        result=service.run()
        self.assertEqual(result.sent,2)
        self.assertEqual(result.summary()["source_trace"]["fetched_groups"],1)

    def test_empty_audience_and_source_failure_have_honest_counts(self):
        service=self.service(morning,MorningForecastDeliveryService,morning.FakeSource(morning.snapshot()),[])
        result=service.run()
        self.assertEqual(result.status,"no_eligible_device")
        self.assertEqual(sanitize_source_trace(result.source_trace)["fetched_groups"],0)
        source=morning.FakeSource(morning.snapshot())
        with patch.object(source,"fetch",side_effect=LocalNoticeSourceUnavailable("private")):
            result=self.service(morning,MorningForecastDeliveryService,source).run()
        self.assertEqual(result.status,"failed")
        self.assertEqual(sanitize_source_trace(result.source_trace)["fetch_failed_groups"],1)
        self.assertNotIn("private",json.dumps(result.summary()))


if __name__ == "__main__":
    unittest.main()
