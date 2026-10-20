from pathlib import Path
import hashlib,json,os,socket,sys,unittest
here=Path(__file__).resolve().parent
root=here.parents[1]
os.chdir(here);sys.path.insert(0,str(here))
def forbidden(*a,**k):raise AssertionError("Network forbidden in producer image checks")
socket.socket.connect=forbidden;socket.socket.connect_ex=forbidden;socket.create_connection=forbidden
for item in json.loads((here/'checkpoint-fix-provenance.json').read_text())['files']:
 assert hashlib.sha256((root/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
import eccodes
print(json.dumps({'runtime_eccodes_api_version':eccodes.codes_get_api_version(),'source_hashes':'verified','network':'blocked'}),flush=True)
names=['test_run_pilot','test_operational_diagnostics','test_accumulation_tolerance','test_icon_quality','test_icon_checkpoint']
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
print(json.dumps({'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'success':r.wasSuccessful()}),flush=True)
raise SystemExit(not r.wasSuccessful())
