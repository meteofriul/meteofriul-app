from icon_limit_common import *
import hashlib, io, tarfile
old=json.loads((ROOT/'.tmp/icon-checkpoint-hotfix-20261020/source-provenance.json').read_text())
assert git('rev-parse','HEAD').decode().strip()==COMMIT
assert not git('status','--porcelain').strip()
publication=json.loads((ROOT/'.tmp/icon-payload-limit-20261020/main-publication-ci-result.json').read_text())
assert publication['main_commit']==COMMIT and publication['ci_conclusion']=='success'
paths=[f['path'] for f in old['files']]+['experiments/weather_autonomy/test_icon_snapshot_limits.py']
archive=git('archive','--format=tar',COMMIT,'--',*paths)
context=OUT/'context'; assert not context.exists();context.mkdir()
inventory=[]; changed=[]; previous={f['path']:f['sha256'] for f in old['files']}
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
    for path in paths:
        body=tf.extractfile(path).read();digest=hashlib.sha256(body).hexdigest()
        if previous.get(path)!=digest: changed.append(path)
        target=context/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
        inventory.append(dict(path=path,sha256=digest,bytes=len(body)))
runtime=['experiments/weather_autonomy/local_pipeline/snapshot_materializer.py','experiments/weather_autonomy/local_pipeline/operational_diagnostics.py']
assert set(changed)==set(runtime+['experiments/weather_autonomy/test_icon_snapshot_limits.py']),changed
image='europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker:icon-payload-limit-20261020-'+COMMIT[:8]
provenance=dict(commit=COMMIT,previous_deployed_commit=old['commit'],base_image=BASE_IMAGE,compatible_rollback=ROLLBACK,
 image_tag=image,changed_files=changed,files=inventory,runtime_changes=runtime,
 dependency_policy='Exact deployed base and installed dependencies; no pip or OS updates',
 ci=publication['ci_url'])
save('source-provenance',provenance)
worker=context/'experiments/weather_autonomy'
(worker/'payload-limit-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8',newline='\n')
verify='''from pathlib import Path
import hashlib,json,os,socket,sys,unittest,resource
here=Path(__file__).resolve().parent
root=here.parents[1]
os.chdir(here);sys.path.insert(0,str(here))
def forbidden(*a,**k):raise AssertionError("Network forbidden in image checks")
socket.socket.connect=forbidden;socket.socket.connect_ex=forbidden;socket.create_connection=forbidden
for item in json.loads((here/'payload-limit-provenance.json').read_text())['files']:
 assert hashlib.sha256((root/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
import eccodes
print(json.dumps({'runtime_eccodes_api_version':eccodes.codes_get_api_version(),'source_hashes':'verified','network':'blocked'}),flush=True)
names=['test_icon_snapshot_limits','test_run_pilot','test_operational_diagnostics','test_accumulation_tolerance','test_icon_quality','test_icon_checkpoint','test_icon_accumulation_sidecar','test_job_entrypoints','test_cloud_worker']
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
print(json.dumps({'verification':'candidate','tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'success':r.wasSuccessful(),'linux_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}),flush=True)
raise SystemExit(not r.wasSuccessful())
'''
(worker/'payload_limit_verify.py').write_text(verify,encoding='utf-8',newline='\n')
(context/'Dockerfile.limit').write_text('FROM '+BASE_IMAGE+'\nCOPY experiments/weather_autonomy/ /app/experiments/weather_autonomy/\nCOPY backend/app/data/fvg_municipalities.json backend/app/data/fvg_geography.json /app/backend/app/data/\nLABEL io.meteofriul.fix="icon-payload-limit-64mib" io.meteofriul.commit="'+COMMIT+'"\n',encoding='utf-8',newline='\n')
(context/'.gcloudignore').write_text('.git\n__pycache__/\n*.pyc\n',encoding='utf-8',newline='\n')
critical={f['path']:f['sha256'] for f in inventory if f['path'].endswith(('/run_pilot.py','/icon_checkpoint.py','/icon_quality.py'))}
rollback_verify='''import hashlib,json,socket,unittest
from pathlib import Path
def forbidden(*a,**k):raise AssertionError('Network forbidden in rollback checks')
socket.socket.connect=forbidden;socket.socket.connect_ex=forbidden;socket.create_connection=forbidden
expected='''+repr(critical)+'''
for path,digest in expected.items():assert hashlib.sha256((Path('/app')/path).read_bytes()).hexdigest()==digest,path
from local_pipeline.snapshot_materializer import MAX_ICON_JSON_BYTES
assert MAX_ICON_JSON_BYTES==32*1024**2
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(['test_icon_quality','test_icon_checkpoint','test_run_pilot']))
print(json.dumps({'verification':'rollback','tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'success':r.wasSuccessful(),'checkpoint_schemas':[1,2],'packing_reader_identical':True,'payload_limit_bytes':MAX_ICON_JSON_BYTES}),flush=True)
raise SystemExit(not r.wasSuccessful())
'''
build={'timeout':'900s','options':{'logging':'CLOUD_LOGGING_ONLY'},'steps':[
 {'name':'gcr.io/cloud-builders/docker','args':['build','-f','Dockerfile.limit','-t',image,'.']},
 {'name':'gcr.io/cloud-builders/docker','args':['run','--rm','--network=none','--memory=1g',image,'python','payload_limit_verify.py']},
 {'name':'gcr.io/cloud-builders/docker','args':['run','--rm','--network=none','--memory=1g',ROLLBACK,'python','-c',rollback_verify]}], 'images':[image]}
save('cloudbuild',build)
print(json.dumps({'commit':COMMIT,'source_files':len(inventory),'changed_files':changed,'image':image,'rollback_schema_checks':True,'container_memory_limit':'1GiB'}))
