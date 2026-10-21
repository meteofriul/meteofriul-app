from icon_limit_common import *
from datetime import datetime, timezone
import copy
assert not (OUT/'deployment-intent.json').exists(), 'Inspect previous deployment before any retry'
build=json.loads((OUT/'build-status.json').read_text())
assert build['status']=='SUCCESS' and all(s.get('status')=='SUCCESS' for s in build['steps'])
verification=json.loads((OUT/'image-verification.json').read_text())
assert verification['status']=='SUCCESS' and len(verification['results'])==2
assert all(x['success'] for x in verification['results'])
image=build['results']['images'][0];digest=image['name'].rsplit(':',1)[0]+'@'+image['digest']
accounts=cloud('active-account-pre-deploy','auth','list','--filter=status:ACTIVE')
assert [a['account'] for a in accounts]==[ACCOUNT]
jobs=cloud('jobs-pre-deploy','run','jobs','list','--region='+REGION)
before=json.loads((OUT/'jobs-before.json').read_text())
specs=lambda xs:{j['metadata']['name']:j['spec'] for j in xs}
assert specs(jobs)==specs(before), 'Concurrent job changes: stop'
http=cloud('http-pre-deploy','run','services','describe','meteofriul-weather','--region='+REGION)
original_http=json.loads((OUT/'http-before.json').read_text())
assert http['spec']==original_http['spec'] and http['status']['traffic']==original_http['status']['traffic']
keys=('attemptDeadline','description','httpTarget','name','retryConfig','schedule','state','timeZone','pubsubTarget','appEngineHttpTarget')
projection=lambda xs:{x['name']:{k:x[k] for k in keys if k in x} for x in xs}
schedulers=cloud('schedulers-pre-deploy','scheduler','jobs','list','--location='+REGION)
assert projection(schedulers)==projection(json.loads((OUT/'schedulers-before.json').read_text()))
assert json.loads((OUT/'rollback-image.json').read_text())['image_summary']['fully_qualified_digest']==ROLLBACK
executions=cloud('producer-executions-pre-deploy','run','jobs','executions','list','--job='+PRODUCER,'--region='+REGION,'--limit=5')
assert all(e.get('status',{}).get('completionTime') for e in executions), 'Producer execution active: stop'
now=datetime.now(timezone.utc)
assert now<datetime(2026,10,21,5,45,tzinfo=timezone.utc), 'Too close to next ordinary run'
rollback_command='gcloud run jobs update '+PRODUCER+' --project='+PROJECT+' --region='+REGION+' --account='+ACCOUNT+' --image='+ROLLBACK+'\n'
(OUT/'rollback-command.txt').write_text(rollback_command,encoding='utf-8')
save('deployment-intent',{'time':now.isoformat(),'commit':COMMIT,'new_image':digest,'compatible_rollback':ROLLBACK,
 'action':'Producer image only; ordinary scheduler; no manual job executions','rollback_limit':'32 MiB; large fresh acquisitions may fail again; checkpoint schemas 1/2 supported'})
cloud('producer-update','run','jobs','update',PRODUCER,'--region='+REGION,'--image='+digest)
after=cloud('jobs-after-deploy','run','jobs','list','--region='+REGION)
old,new=specs(before),specs(after);assert set(old)==set(new)
for name,spec in old.items():
    if name!=PRODUCER: assert new[name]==spec,name
expected=copy.deepcopy(old[PRODUCER]['template']['spec'])
expected['template']['spec']['containers'][0]['image']=digest
assert new[PRODUCER]['template']['spec']==expected,'Unexpected producer config change'
schedulers_after=cloud('schedulers-after-deploy','scheduler','jobs','list','--location='+REGION)
assert projection(schedulers_after)==projection(schedulers)
http_after=cloud('http-after-deploy','run','services','describe','meteofriul-weather','--region='+REGION)
assert http_after['spec']==http['spec'] and http_after['status']['traffic']==http['status']['traffic']
executions_after=cloud('producer-executions-after-deploy','run','jobs','executions','list','--job='+PRODUCER,'--region='+REGION,'--limit=5')
assert [x['metadata']['name'] for x in executions_after]==[x['metadata']['name'] for x in executions]
result={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'producer':PRODUCER,'source_commit':COMMIT,
 'new_image':digest,'compatible_rollback':ROLLBACK,'rollback_checkpoint_schemas':[1,2],
 'rollback_limit':'32 MiB: same payload-size failure can recur on a fresh acquisition',
 'other_jobs_unchanged':len(old)-1,'schedulers_unchanged':len(schedulers_after),'http_unchanged':True,'only_image_changed':True,
 'manual_executions':0,'manual_qa_executions':0,'send_settings_changed':False,'new_executions_on_deploy':0,
 'next_scheduler_utc':'2026-10-21T06:00:00Z','new_run_validation':'pending',
 'report_path':str(REPO/'docs/operations/ICON2I_PAYLOAD_LIMIT_DEPLOY_20261020.md')}
save('deployment-checks',result);print(json.dumps({k:v for k,v in result.items() if k!='report_path'}))
