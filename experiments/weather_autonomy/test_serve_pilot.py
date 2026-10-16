"""Local-only contract and safety tests for the isolated diagnostic preview."""

from contextlib import redirect_stderr
import http.client
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

import serve_pilot


PAYLOAD = {"schema_version": 1, "status": "partial", "municipalities": []}
CAMS_PAYLOAD = {"schema_version": 1, "kind": "cams_point_preview", "run_utc": "2026-09-03T00:00:00Z", "variables": []}
CAMS_REGIONAL_PAYLOAD = {"schema_version": 2, "kind": "cams_region_point_extraction", "run_utc": "2026-09-03T00:00:00Z", "variables": [], "cells": [], "municipalities": [], "times_utc": []}


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="meteofriul-pilot-test-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "payload.json"
        self.path.write_text(json.dumps(PAYLOAD), encoding="utf-8")

    def test_valid_payload_is_returned_without_rewriting(self):
        original = self.path.read_bytes()
        self.assertEqual(serve_pilot.read_payload(self.path), original)
        self.assertEqual(self.path.read_bytes(), original)

    def test_rejects_missing_file(self):
        with self.assertRaises(ValueError):
            serve_pilot.read_payload(self.path.with_name("missing.json"))

    def test_rejects_directory(self):
        with self.assertRaises(ValueError):
            serve_pilot.read_payload(self.path.parent)

    def test_rejects_non_object_json(self):
        self.path.write_text("[]", encoding="utf-8")
        with self.assertRaises(ValueError):
            serve_pilot.read_payload(self.path)

    def test_rejects_wrong_or_boolean_schema(self):
        for schema in (None, "1", True, 2):
            with self.subTest(schema=schema):
                self.path.write_text(json.dumps({**PAYLOAD, "schema_version": schema}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    serve_pilot.read_payload(self.path)

    def test_rejects_missing_municipalities_array(self):
        self.path.write_text('{"schema_version":1,"municipalities":null}', encoding="utf-8")
        with self.assertRaises(ValueError):
            serve_pilot.read_payload(self.path)

    def test_rejects_invalid_json(self):
        self.path.write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            serve_pilot.read_payload(self.path)

    def test_rejects_nonfinite_json(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                self.path.write_text('{"schema_version":1,"municipalities":[],"value":'+value+'}', encoding="utf-8")
                with self.assertRaises(ValueError):
                    serve_pilot.read_payload(self.path)

    def test_read_is_bounded(self):
        with patch.object(serve_pilot, "MAX_PAYLOAD_BYTES", 4):
            with self.assertRaisesRegex(ValueError, "exceeds"):
                serve_pilot.read_payload(self.path)

    def test_port_validation(self):
        for port in (True, -1, 65536, "8767"):
            with self.subTest(port=port):
                with self.assertRaises(ValueError):
                    serve_pilot.make_server(self.path, port)

    def test_cams_payload_uses_a_separate_schema(self):
        self.path.write_text(json.dumps(CAMS_PAYLOAD), encoding="utf-8")
        self.assertEqual(json.loads(serve_pilot.read_payload(self.path, cams=True)), CAMS_PAYLOAD)
        with self.assertRaises(ValueError):
            serve_pilot.read_payload(self.path)

    def test_icon_payload_cannot_impersonate_cams(self):
        with self.assertRaises(ValueError):
            serve_pilot.read_payload(self.path, cams=True)

    def test_cams_regional_schema_is_supported_without_changing_icon_schema(self):
        self.path.write_text(json.dumps(CAMS_REGIONAL_PAYLOAD), encoding="utf-8")
        self.assertEqual(json.loads(serve_pilot.read_payload(self.path, cams=True)), CAMS_REGIONAL_PAYLOAD)
        with self.assertRaises(ValueError):
            serve_pilot.read_payload(self.path)

    def test_regional_cams_requires_shared_cells_map_and_time_axis(self):
        for key in ("cells", "municipalities", "times_utc"):
            with self.subTest(key=key):
                self.path.write_text(json.dumps({name: value for name, value in CAMS_REGIONAL_PAYLOAD.items() if name != key}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    serve_pilot.read_payload(self.path, cams=True)

    def test_cams_cannot_reuse_icon_file(self):
        with self.assertRaisesRegex(ValueError, "separate"):
            serve_pilot.make_server(self.path, cams_payload_path=self.path)

    def test_cli_requires_explicit_payload(self):
        with patch("sys.argv", ["serve_pilot.py"]), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                serve_pilot.main()
        self.assertEqual(result.exception.code, 2)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="meteofriul-pilot-http-")
        cls.path = Path(cls.directory.name) / "payload.json"
        cls.path.write_text(json.dumps(PAYLOAD), encoding="utf-8")
        cls.logging_patch = patch.object(serve_pilot.PilotHandler, "log_message")
        cls.logging_patch.start()
        cls.server = serve_pilot.make_server(cls.path, port=0)
        cls.thread = threading.Thread(
            target=lambda: cls.server.serve_forever(poll_interval=0.01), daemon=True
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.logging_patch.stop()
        cls.directory.cleanup()

    def setUp(self):
        self.path.write_text(json.dumps(PAYLOAD), encoding="utf-8")

    def request(self, path, method="GET", headers=None):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            client.request(method, path, headers=headers or {})
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            client.close()

    def test_server_is_bound_only_to_loopback(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_root_serves_fixed_html(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(body, serve_pilot.HTML_PATH.read_bytes())

    def test_payload_serves_selected_file(self):
        status, headers, body = self.request("/pilot.json")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(json.loads(body), PAYLOAD)

    def test_optional_cams_is_not_configured_by_default(self):
        status, _, body = self.request("/cams.json")
        self.assertEqual(status, 204)
        self.assertEqual(body, b"")

    def test_responses_disable_cache_and_cross_origin_access(self):
        for path in ("/", "/pilot.json", "/unavailable", "/favicon.ico"):
            with self.subTest(path=path):
                _, headers, _ = self.request(path)
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(headers["Cross-Origin-Resource-Policy"], "same-origin")
                self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
                self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_no_directory_listing_or_arbitrary_file_paths(self):
        for path in ("/../serve_pilot.py", "/%2e%2e/serve_pilot.py", "/serve_pilot.py", "/pilot_preview.html", "/pilot.json?file=other", "/?anything", "/experiments/"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)

    def test_methods_other_than_get_are_rejected_without_writing(self):
        original = self.path.read_bytes()
        for method in ("HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"):
            with self.subTest(method=method):
                status, headers, body = self.request("/pilot.json", method)
                self.assertEqual(status, 405)
                self.assertEqual(headers["Allow"], "GET")
                if method == "HEAD":
                    self.assertEqual(body, b"")
        self.assertEqual(self.path.read_bytes(), original)

    def test_favicon_has_no_body(self):
        status, _, body = self.request("/favicon.ico")
        self.assertEqual(status, 204)
        self.assertEqual(body, b"")

    def test_updated_payload_is_read_without_restart(self):
        self.assertEqual(json.loads(self.request("/pilot.json")[2])["status"], "partial")
        self.path.write_text(json.dumps({**PAYLOAD, "status": "updated"}), encoding="utf-8")
        self.assertEqual(json.loads(self.request("/pilot.json")[2])["status"], "updated")

    def test_invalid_payload_fails_closed_and_does_not_leak_path(self):
        self.path.write_text("invalid", encoding="utf-8")
        status, _, body = self.request("/pilot.json")
        self.assertEqual(status, 503)
        self.assertNotIn(str(self.path).encode(), body)

    def test_rejects_untrusted_host_header(self):
        self.assertEqual(self.request("/pilot.json", headers={"Host": "example.invalid"})[0], 403)

    def test_rejects_cross_origin_request(self):
        self.assertEqual(self.request("/pilot.json", headers={"Origin": "https://example.invalid"})[0], 403)

    def test_allows_same_origin_request(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        self.assertEqual(self.request("/pilot.json", headers={"Origin": origin})[0], 200)

    def test_allows_localhost_host_header(self):
        self.assertEqual(self.request("/pilot.json", headers={"Host": f"localhost:{self.server.server_port}"})[0], 200)


class CAMSHTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="meteofriul-cams-preview-test-")
        self.addCleanup(self.directory.cleanup)
        self.icon_path = Path(self.directory.name) / "icon.json"
        self.cams_path = Path(self.directory.name) / "cams.json"
        self.icon_path.write_text(json.dumps(PAYLOAD), encoding="utf-8")
        self.cams_path.write_text(json.dumps(CAMS_PAYLOAD), encoding="utf-8")
        self.logging_patch = patch.object(serve_pilot.PilotHandler, "log_message")
        self.logging_patch.start()
        self.addCleanup(self.logging_patch.stop)
        self.server = serve_pilot.make_server(self.icon_path, port=0, cams_payload_path=self.cams_path)
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.01), daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, path):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            client.request("GET", path)
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            client.close()

    def test_cams_and_icon_are_served_independently_without_rewriting(self):
        icon_before, cams_before = self.icon_path.read_bytes(), self.cams_path.read_bytes()
        status, headers, body = self.request("/cams.json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), CAMS_PAYLOAD)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(self.request("/pilot.json")[2], icon_before)
        self.assertEqual(self.icon_path.read_bytes(), icon_before)
        self.assertEqual(self.cams_path.read_bytes(), cams_before)

    def test_invalid_cams_does_not_break_icon(self):
        self.cams_path.write_text("not JSON", encoding="utf-8")
        status, _, body = self.request("/cams.json")
        self.assertEqual(status, 503)
        self.assertNotIn(str(self.cams_path).encode(), body)
        self.assertEqual(self.request("/pilot.json")[0], 200)

    def test_cams_endpoint_does_not_accept_a_caller_selected_path(self):
        self.assertEqual(self.request("/cams.json?path=other.json")[0], 404)

    def test_regional_snapshot_can_be_served_without_rewriting_icon(self):
        original = self.icon_path.read_bytes()
        self.cams_path.write_text(json.dumps(CAMS_REGIONAL_PAYLOAD), encoding="utf-8")
        status, _, body = self.request("/cams.json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), CAMS_REGIONAL_PAYLOAD)
        self.assertEqual(self.request("/pilot.json")[2], original)


class PreviewStructureTests(unittest.TestCase):
    def test_preview_only_fetches_fixed_local_payloads(self):
        html = serve_pilot.HTML_PATH.read_text(encoding="utf-8")
        self.assertEqual(html.count("fetch("), 2)
        self.assertIn("fetch('/pilot.json'", html)
        self.assertIn("fetch('/cams.json'", html)
        self.assertNotIn('<script src=', html)
        self.assertNotIn('rel="stylesheet"', html)

    def test_preview_uses_dom_text_instead_of_html_interpolation(self):
        html = serve_pilot.HTML_PATH.read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", html)
        self.assertNotIn("insertAdjacentHTML", html)
        self.assertIn("node.textContent=content", html)

    def test_cams_catalogue_attribution_discloses_documentation_disagreement(self):
        html = serve_pilot.HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("Classificazione secondo il catalogo ADS: 7 variabili", html)
        self.assertIn("La guida ECMWF più recente differisce", html)
        self.assertIn("monossido di azoto (NO)", html)
        self.assertIn("polveri minerali (dust)", html)
        self.assertIn("monossido di carbonio (CO)", html)
        self.assertIn("non è una validazione locale del pilota né una certificazione", html)


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the standalone preview JavaScript")
class PreviewBehaviourTests(unittest.TestCase):
    """Exercise the actual embedded JavaScript without a browser dependency."""

    def evaluate(self, expression):
        harness = r"""
const fs = require('fs'), vm = require('vm');
let script = fs.readFileSync(process.argv[1], 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
script = script.replace(/\n    load\(\);\s*$/, '\n');
class Node {
  constructor() { this.children=[]; this.attributes={}; this.hidden=false; this._text=''; }
  set textContent(value) { this._text=String(value); this.children=[]; }
  get textContent() { return this._text+this.children.map(child=>child.textContent).join(''); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this._text=''; this.children=nodes; }
  setAttribute(key,value) { this.attributes[key]=value; }
  addEventListener() {}
}
const nodes = new Map();
const find = key => { if(!nodes.has(key))nodes.set(key,new Node());return nodes.get(key); };
const context = vm.createContext({
  document:{getElementById:find,querySelector:find,createElement:()=>new Node(),createElementNS:()=>new Node()},
  window:{setInterval(){}},
  fetch:()=>{throw new Error('No network expected in unit tests');}
});
vm.runInContext(script,context);
const setup = `
  const testRun='2026-09-03T00:00:00Z';
  const testRows=Array.from({length:73},(_,index)=>({valid_at_utc:new Date(Date.parse(testRun)+index*3600000).toISOString(),temperature_c:15,apparent_temperature_c:14,wind_m_s:2,wind_gust_m_s:3,pressure_msl_hpa:1010,relative_humidity_pct:60,condition:{status:'valid',code:0,label:'Sereno'},precipitation_previous_hour_mm:null}));
  const testTown={id:'udine',name:'Udine',latitude:46.07,longitude:13.23,hourly:testRows,two_hourly:[],pollen:{status:'blocked_credentials_and_dataset_terms',values:null},current:{temperature_c:999,valid_at_utc:testRun}};
  state.payload={schema_version:1,status:'partial_pilot_not_production',run_utc:testRun,generated_at_utc:testRun,municipalities:[testTown],validation:{status:'fresh',usable:true},capabilities:[{id:'cams_pollen',status:'blocked',label:'Pollini CAMS'},{id:'precipitation_probability',status:'missing',label:'Probabilità'},{id:'visibility',status:'missing',label:'Visibilità'},{id:'five_day_forecast',status:'missing',label:'Cinque giorni'}]};
  state.municipality=testTown;
  const camsRaw={schema_version:1,run_utc:testRun,dataset:'cams-europe-air-quality-forecasts',requested_point:{latitude:45.95689,longitude:12.66051},grid_point:{lat:45.95,lon:12.65,distance:1.1},native_resolution_degrees:.1,variables:Object.keys(CAMS_LABELS).map((id,index)=>({id,metadata:{},hourly:Array.from({length:97},(_,lead)=>({valid_at_utc:new Date(Date.parse(testRun)+lead*3600000).toISOString(),value:index*100+lead,raw_value:(index*100+lead)/(id.endsWith('_pollen')?1:1e9),units:id.endsWith('_pollen')?'grains/m3':'ug/m3',source_units:id.endsWith('_pollen')?'grains/m3':'kg/m3',conversion_factor:id.endsWith('_pollen')?1:1e9,status:'valid',quality_flags:[]}))}))};
  const camsRegionalRaw={schema_version:2,kind:'cams_region_point_extraction',run_utc:testRun,dataset:'cams-europe-air-quality-forecasts',native_resolution_degrees:.1,times_utc:camsRaw.variables[0].hourly.map(row=>row.valid_at_utc),variables:camsRaw.variables.map(variable=>({id:variable.id,units:variable.hourly[0].units,source_units:variable.hourly[0].source_units,conversion_factor:variable.hourly[0].conversion_factor,quality_flags:[],metadata:{}})),cells:Array.from({length:3},(_,index)=>({id:String(index),grid_index:index,lat:45.95+index*.1,lon:12.65+index*.1,values:Object.fromEntries(camsRaw.variables.map(variable=>[variable.id,variable.hourly.map(row=>row.value+index*10000)])),raw_values:Object.fromEntries(camsRaw.variables.map(variable=>[variable.id,variable.hourly.map(row=>(row.value+index*10000)/row.conversion_factor)])),quality_flags:{}})),municipalities:Array.from({length:215},(_,index)=>({id:index===0?'udine':index===1?'pordenone':'test-town-'+index,name:index===0?'Udine':index===1?'Pordenone':'Comune test '+index,latitude:45.95+index%10*.01,longitude:12.65+index%10*.01,cell_id:String(index%3),distance_km:1+index%3*.1}))};
`;
vm.runInContext(setup,context);
console.log(JSON.stringify(vm.runInContext(process.argv[2],context)));
"""
        result = subprocess.run(
            [shutil.which("node"), "-e", harness, str(serve_pilot.HTML_PATH), expression],
            capture_output=True, text=True, encoding="utf-8", timeout=10, check=True,
        )
        return json.loads(result.stdout)

    def test_freshness_expires_from_browser_clock_not_saved_snapshot(self):
        result = self.evaluate("""
          [6,19,24,25,31].map(age=>dynamicWindow(testRun,testRows,Date.parse(testRun)+age*3600000).status)
        """)
        self.assertEqual(result, ["fresh", "stale", "stale", "expired", "expired"])

    def test_badge_recalculates_when_time_passes_without_reloading_payload(self):
        result = self.evaluate("""
          (()=>{Date.now=()=>Date.parse(testRun)+6*3600000;render();const before=$('badges').textContent;
          Date.now=()=>Date.parse(testRun)+25*3600000;render();return {before,after:$('badges').textContent,notice:$('coverage').className};})()
        """)
        self.assertIn("Copertura adesso: Recente", result["before"])
        self.assertIn("Copertura adesso: Scaduto", result["after"])
        self.assertEqual(result["notice"], "notice error")

    def test_missing_current_hour_is_not_replaced_with_frozen_current(self):
        result = self.evaluate("""
          (()=>{Date.now=()=>Date.parse(testRun)+6.5*3600000;testTown.hourly=testRows.slice(7);render();
          return {details:$('current-detail').textContent,cards:$('cards').textContent,notice:$('coverage').textContent};})()
        """)
        self.assertIn("Nessun punto", result["details"])
        self.assertIn("Manca un punto orario", result["notice"])
        self.assertNotIn("999", result["cards"])
        self.assertIn("Temperatura—", result["cards"])

    def test_invalid_conditions_never_use_a_supplied_clear_sky_label(self):
        result = self.evaluate("""
          [condition({condition:{status:'invalid',label:'Sereno'}}),condition({condition:{status:'unknown',code:99,label:'Sereno'}}),condition({condition:{status:'valid',code:0,label:'Sereno'}})]
        """)
        self.assertEqual(result, ["Condizione meteo non valida", "Codice meteo non riconosciuto (99)", "Sereno"])

    def test_null_and_zero_remain_distinct(self):
        self.assertEqual(self.evaluate("[fmt(null,' mm'),fmt(0,' mm'),fmt(false,' mm')]"), ["—", "0 mm", "—"])

    def test_future_run_and_duplicate_hours_are_invalid(self):
        result = self.evaluate("""
          [dynamicWindow(testRun,testRows,Date.parse(testRun)-1).status,
          dynamicWindow(testRun,[testRows[0],testRows[0],...testRows.slice(1)],Date.parse(testRun)+3600000).status]
        """)
        self.assertEqual(result, ["invalid", "invalid"])

    def test_capability_gaps_remain_prominent(self):
        result = self.evaluate("""
          (()=>{Date.now=()=>Date.parse(testRun)+6*3600000;render();return $('missing-components').textContent;})()
        """)
        for missing in ("pollini CAMS", "probabilità di precipitazione", "visibilità", "previsioni a cinque giorni", "Nessuno snapshot CAMS è collegato"):
            self.assertIn(missing, result)

    def test_two_hour_table_reads_actual_aggregates(self):
        result = self.evaluate("""
          (()=>{Date.now=()=>Date.parse(testRun)+6*3600000;
          testTown.two_hourly=[{start_at_utc:'2026-09-03T06:00:00Z',end_at_utc:'2026-09-03T08:00:00Z',source_hours:2,precipitation_mm:1.25,wind_gust_max_m_s:5,temperature_end_c:17,temperature_min_c:15,temperature_max_c:17,status:'valid',quality_flags:[]}];
          state.mode='two_hourly';render();return {text:$('timeline').textContent,headers:$('table-head').textContent};})()
        """)
        self.assertIn("Precipitaz. 2h", result["headers"])
        self.assertIn("1,3 mm", result["text"])
        self.assertIn("18 km/h", result["text"])

    def test_cams_preserves_all_variables_and_native_leads(self):
        result = self.evaluate("""
          (()=>{Date.now=()=>Date.parse(testRun)+6.5*3600000;state.cams=validateCams(camsRaw);render();
          return {variables:$('cams-summary').children.length,options:$('cams-variable').children.length,rows:$('cams-series').children.length,reference:$('cams-reference').textContent,firstValue:$('cams-summary').children[0].children[1].textContent};})()
        """)
        self.assertEqual(result["variables"], 28)
        self.assertEqual(result["options"], 28)
        self.assertEqual(result["rows"], 97)
        self.assertIn("lead 6 h", result["reference"])
        self.assertEqual(result["firstValue"], "6")

    def test_cams_summary_null_is_not_filled_from_previous_hour(self):
        result = self.evaluate("""
          (()=>{Date.now=()=>Date.parse(testRun)+6.5*3600000;camsRaw.variables[0].hourly[6].value=null;camsRaw.variables[0].hourly[6].status='missing';state.cams=validateCams(camsRaw);render();
          return {value:$('cams-summary').children[0].children[1].textContent,status:$('cams-summary').children[0].children[4].textContent,zero:camsValue(0),small:camsValue(0.00000125)};})()
        """)
        self.assertEqual(result["value"], "—")
        self.assertEqual(result["status"], "Mancante")
        self.assertEqual(result["zero"], "0")
        self.assertNotEqual(result["small"], "0")

    def test_cams_does_not_claim_spatial_coverage_for_other_municipalities(self):
        result = self.evaluate("""
          (()=>{Date.now=()=>Date.parse(testRun)+6*3600000;state.cams=validateCams(camsRaw);render();
          return {notice:$('missing-components').textContent,locality:$('cams-locality').textContent,payloadUnchanged:state.payload.capabilities[0].status};})()
        """)
        self.assertIn("pollini CAMS", result["notice"])
        self.assertIn("soltanto per Pordenone", result["notice"])
        self.assertIn("selettore ICON è su Udine", result["locality"])
        self.assertEqual(result["payloadUnchanged"], "blocked")

    def test_cams_pordenone_overlay_does_not_rewrite_icon_capabilities(self):
        result = self.evaluate("""
          (()=>{Date.now=()=>Date.parse(testRun)+6*3600000;state.municipality={...testTown,id:'pordenone',name:'Pordenone'};state.cams=validateCams(camsRaw);render();
          return {notice:$('missing-components').textContent,capabilities:state.payload.capabilities};})()
        """)
        self.assertNotIn("pollini CAMS", result["notice"])
        self.assertIn("probabilità", result["notice"])
        self.assertEqual(result["capabilities"][0]["status"], "blocked")

    def test_cams_does_not_apply_icon_thirty_hour_expiration(self):
        result = self.evaluate("""
          (()=>{Date.now=()=>Date.parse(testRun)+31*3600000;state.cams=validateCams(camsRaw);render();return {status:$('cams-status').textContent,style:$('cams-status').className,reference:$('cams-reference').textContent};})()
        """)
        self.assertNotEqual(result["style"], "notice error")
        self.assertIn("lead 31 h", result["reference"])
        self.assertNotIn("orizzonte CAMS è passato", result["status"])

    def test_cams_future_run_has_no_fake_current(self):
        result = self.evaluate("""
          (()=>{Date.now=()=>Date.parse(testRun)-3600000;state.cams=validateCams(camsRaw);render();return {reference:$('cams-reference').textContent,value:$('cams-summary').children[0].children[1].textContent};})()
        """)
        self.assertIn("Nessun orario già valido", result["reference"])
        self.assertEqual(result["value"], "—")

    def test_cams_technical_success_does_not_imply_scientific_validation(self):
        result = self.evaluate("""
          (()=>{Date.now=()=>Date.parse(testRun)+6*3600000;state.cams=validateCams(camsRaw);render();return {technical:$('cams-summary').children[0].children[4].textContent,pollen:$('cams-summary').children[0].children[5].textContent,air:camsQuality(state.cams.variables.find(v=>v.id==='nitrogen_monoxide'))};})()
        """)
        self.assertEqual(result["technical"], "Decodificato")
        self.assertIn("sperimentale", result["pollen"])
        self.assertIn("Secondo il catalogo ADS", result["pollen"])
        self.assertIn("Secondo il catalogo ADS", result["air"])
        self.assertIn("non validazione locale del pilota", result["air"])

    def test_cams_official_validation_scope_is_seven_and_twenty_one(self):
        result = self.evaluate("""
          (()=>{const p=validateCams(camsRaw);return {validated:p.variables.filter(v=>v.provider_validation==='regularly_validated_in_situ_by_provider').length,experimental:p.variables.filter(v=>v.provider_validation==='experimental_unvalidated_by_provider').length};})()
        """)
        self.assertEqual(result, {"validated": 7, "experimental": 21})

    def test_cams_adapter_rejects_wrong_point_duplicate_leads_or_unit_changes(self):
        result = self.evaluate("""
          (()=>{const errors=[];for(const modify of [p=>p.requested_point.latitude=46.1,p=>p.variables[0].hourly[1].valid_at_utc=p.run_utc,p=>p.variables[0].hourly[1].units='different']){const p=JSON.parse(JSON.stringify(camsRaw));modify(p);try{validateCams(p);errors.push(false);}catch{errors.push(true);}}return errors;})()
        """)
        self.assertEqual(result, [True, True, True])

    def test_cams_adapter_does_not_modify_original_snapshot(self):
        result = self.evaluate("""
          (()=>{const before=JSON.stringify(camsRaw);const adapted=validateCams(camsRaw);return {unchanged:before===JSON.stringify(camsRaw),lead:adapted.variables[0].hourly[96].lead_hour,unit:adapted.variables[0].units};})()
        """)
        self.assertTrue(result["unchanged"])
        self.assertEqual(result["lead"], 96)
        self.assertEqual(result["unit"], "grains/m3")

    def test_regional_cams_coordinates_both_sources_on_selected_municipality(self):
        result = self.evaluate("""
          (()=>{Date.now=()=>Date.parse(testRun)+6.5*3600000;state.cams=validateCams(camsRegionalRaw);render();const udine={title:$('cams-title').textContent,value:$('cams-summary').children[0].children[1].textContent};state.municipality={...testTown,id:'pordenone',name:'Pordenone'};render();return {udine,pordenone:{title:$('cams-title').textContent,value:$('cams-summary').children[0].children[1].textContent},rows:$('cams-series').children.length,vars:$('cams-summary').children.length,badges:$('cams-badges').textContent,notice:$('missing-components').textContent};})()
        """)
        self.assertIn("Udine", result["udine"]["title"])
        self.assertEqual(result["udine"]["value"], "6")
        self.assertIn("Pordenone", result["pordenone"]["title"])
        self.assertEqual(result["pordenone"]["value"], "10.006")
        self.assertEqual(result["rows"], 97)
        self.assertEqual(result["vars"], 28)
        self.assertIn("215 Comuni · 3 celle native", result["badges"])
        self.assertNotIn("pollini CAMS", result["notice"])

    def test_regional_cams_shared_cell_is_reused_without_expanding_all_towns(self):
        result = self.evaluate("""
          (()=>{state.cams=validateCams(camsRegionalRaw);const a=selectedCams();state.municipality={...testTown,id:'test-town-3',name:'Comune test 3'};const b=selectedCams();return {first:a.variables[0].hourly[8].value,second:b.variables[0].hourly[8].value,sameCell:a.selected_cell_id===b.selected_cell_id,storedCells:state.cams.cells.length,globalHasHourly:Object.hasOwn(state.cams.variables[0],'hourly'),cachedAgain:selectedCams()===b};})()
        """)
        self.assertEqual(result, {"first": 8, "second": 8, "sameCell": True, "storedCells": 3, "globalHasHourly": False, "cachedAgain": True})

    def test_regional_cams_missing_municipality_cannot_reuse_previous_selection(self):
        result = self.evaluate("""
          (()=>{Date.now=()=>Date.parse(testRun)+6*3600000;state.cams=validateCams(camsRegionalRaw);render();state.municipality={...testTown,id:'not-in-map',name:'Non presente'};render();return {summary:$('cams-summary').children.length,series:$('cams-series').children.length,status:$('cams-status').textContent,notice:$('missing-components').textContent};})()
        """)
        self.assertEqual(result["summary"], 0)
        self.assertEqual(result["series"], 0)
        self.assertIn("nessun valore viene preso da un altro Comune", result["status"])
        self.assertIn("pollini CAMS", result["notice"])

    def test_regional_cams_combines_sparse_anomalies_with_unit_provenance(self):
        result = self.evaluate("""
          (()=>{camsRegionalRaw.variables[0].quality_flags=['unit_provenance'];camsRegionalRaw.cells[0].values.alder_pollen[6]=null;camsRegionalRaw.cells[0].raw_values.alder_pollen[6]=-1;camsRegionalRaw.cells[0].quality_flags={alder_pollen:{'6':['negative_concentration_not_clipped']}};state.cams=validateCams(camsRegionalRaw);const row=selectedCams().variables[0].hourly[6];return {value:row.value,raw:row.raw_value,status:row.status,flags:row.quality_flags};})()
        """)
        self.assertIsNone(result["value"])
        self.assertEqual(result["raw"], -1)
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["flags"], ["unit_provenance", "negative_concentration_not_clipped"])

    def test_regional_cams_retains_zero_and_tiny_positive_values(self):
        result = self.evaluate("""
          (()=>{camsRegionalRaw.cells[0].values.alder_pollen[0]=0;camsRegionalRaw.cells[0].values.alder_pollen[1]=1e-9;state.cams=validateCams(camsRegionalRaw);const rows=selectedCams().variables[0].hourly;return [camsValue(rows[0].value),camsValue(rows[1].value),rows[1].value];})()
        """)
        self.assertEqual(result[0], "0")
        self.assertNotEqual(result[1], "0")
        self.assertEqual(result[2], 1e-9)

    def test_regional_cams_retains_seven_validated_and_twenty_one_experimental(self):
        result = self.evaluate("""
          (()=>{state.cams=validateCams(camsRegionalRaw);const p=selectedCams();return {validated:p.variables.filter(v=>v.provider_validation==='regularly_validated_in_situ_by_provider').length,experimental:p.variables.filter(v=>v.provider_validation==='experimental_unvalidated_by_provider').length};})()
        """)
        self.assertEqual(result, {"validated": 7, "experimental": 21})

    def test_regional_cams_rejects_broken_time_cell_and_quality_contracts(self):
        result = self.evaluate("""
          (()=>{return [p=>p.times_utc[1]=p.times_utc[0],p=>p.municipalities[0].cell_id='999',p=>p.cells[0].values.alder_pollen.pop(),p=>p.cells[0].values.alder_pollen[0]=-1,p=>p.cells[0].quality_flags={alder_pollen:{'97':['invalid']}},p=>p.variables[1].id=p.variables[0].id,p=>p.municipalities[1].id=p.municipalities[0].id].map(modify=>{const p=JSON.parse(JSON.stringify(camsRegionalRaw));modify(p);try{validateCams(p);return false;}catch{return true;}});})()
        """)
        self.assertEqual(result, [True] * 7)

    def test_regional_cams_does_not_mutate_archives(self):
        result = self.evaluate("""
          (()=>{const before=JSON.stringify(camsRegionalRaw),icon=JSON.stringify(state.payload);state.cams=validateCams(camsRegionalRaw);Date.now=()=>Date.parse(testRun)+6*3600000;render();return {cams:before===JSON.stringify(camsRegionalRaw),icon:icon===JSON.stringify(state.payload)};})()
        """)
        self.assertEqual(result, {"cams": True, "icon": True})


if __name__ == "__main__":
    unittest.main()
