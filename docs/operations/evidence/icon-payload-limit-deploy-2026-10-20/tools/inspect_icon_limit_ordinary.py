"""Read the scheduled 21 October run. Never submit or retry a job."""
from icon_limit_common import *
from datetime import datetime, timezone
import gzip, hashlib
now=datetime.now(timezone.utc)
assert now>=datetime(2026,10,21,6,20,tzinfo=timezone.utc), 'Before authorized observation time'
checks=json.loads((OUT/'deployment-checks.json').read_text())
assert checks['only_image_changed'] and checks['manual_executions']==0
accounts=cloud('ordinary-auth','auth','list','--filter=status:ACTIVE')
assert [x['account'] for x in accounts]==[ACCOUNT]
executions=cloud('ordinary-executions','run','jobs','executions','list','--job='+PRODUCER,'--region='+REGION,'--limit=10')
matches=[x for x in executions if datetime(2026,10,21,6,tzinfo=timezone.utc)<=datetime.fromisoformat(x['metadata']['creationTimestamp'].replace('Z','+00:00'))<datetime(2026,10,21,7,tzinfo=timezone.utc)]
assert len(matches)==1, 'Expected one ordinary morning execution; do not submit one'
execution=matches[0];name=execution['metadata']['name']
assert execution['metadata']['annotations']['run.googleapis.com/creator']=='meteofriul-weather-scheduler@meteo-friul.iam.gserviceaccount.com'
assert execution['spec']['template']['spec']['containers'][0]['image']==checks['new_image']
completed=next(x for x in execution['status']['conditions'] if x['type']=='Completed')
if completed['status']!='True':
    print(json.dumps({'execution':name,'completed':completed,'validation':'incomplete'}));raise SystemExit(2)
rows=cloud('ordinary-logs','logging','read','resource.type="cloud_run_job" AND resource.labels.job_name="'+PRODUCER+'" AND resource.labels.location="'+REGION+'" AND labels."run.googleapis.com/execution_name"="'+name+'"','--order=asc','--limit=5000')
assert len(rows)<5000,'Log result requires pagination'
events=[]
for row in rows:
    p=row.get('jsonPayload')
    if p is None:
        try:p=json.loads(row.get('textPayload',''))
        except json.JSONDecodeError:continue
    if isinstance(p,dict) and p.get('event')=='source_quality':events.append(p)
assert events and all(x.get('quality_available') is True for x in events), 'Missing source quality'
slot='20261021-am';uri='gs://meteo-friul-weather-state/pilot/state/dispatch/icon/'+slot+'/checkpoint.json.gz'
p=subprocess.run([sys.executable,str(GC),'storage','cat',uri,'--project='+PROJECT,'--account='+ACCOUNT],capture_output=True)
if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
body=p.stdout;assert len(body)<=16*1024**2
(OUT/'ordinary-checkpoint.json.gz').write_bytes(body)
sys.path.insert(0,str(OUT/'context/experiments/weather_autonomy'))
from local_pipeline.contract_v1 import load_catalog
from local_pipeline.icon_checkpoint import decode_checkpoint
from local_pipeline.icon_quality import quality_log_summary
checkpoint=decode_checkpoint(body,slot=slot,catalog=load_catalog())
assert json.loads(gzip.decompress(body))['schema_version']==2
assert checkpoint.intent.source_run_id>='20261021T000000Z'
assert {x['source_run_id'] for x in events}=={checkpoint.intent.source_run_id}
assert checkpoint.source_quality is not None
save('ordinary-source-quality',checkpoint.source_quality)
result={'verified_at_utc':now.isoformat(),'execution':name,'creator':'ordinary_scheduler','image':checks['new_image'],
 'source_run_id':checkpoint.intent.source_run_id,'checkpoint_schema':2,'checkpoint_sha256':hashlib.sha256(body).hexdigest(),
 'checkpoint_bytes':len(body),'source_quality_events':len(events),'quality':quality_log_summary(checkpoint.source_quality),
 'manual_executions':0,'manual_qa_executions':0,'http_validation':'run verify_icon_limit_http.py --name new-run-http --require-new next'}
save('ordinary-run-result',result);print(json.dumps(result))
