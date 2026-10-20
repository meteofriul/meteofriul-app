from icon_hotfix_common import *
from datetime import datetime, timezone
import copy
assert not (OUT/'deployment-intent.json').exists(), 'Deployment already attempted; inspect current state'
build=json.loads((OUT/'build-status.json').read_text())
assert build['status']=='SUCCESS'
assert all(s.get('status')=='SUCCESS' for s in build['steps'])
image=build['results']['images'][0]
digest=image['name'].rsplit(':',1)[0]+'@'+image['digest']
accounts=cloud('active-account-pre-deploy','auth','list','--filter=status:ACTIVE')
assert [a['account'] for a in accounts]==[ACCOUNT]
jobs=cloud('jobs-pre-deploy','run','jobs','list','--region='+REGION)
before=json.loads((OUT/'jobs-before.json').read_text())
specs=lambda xs:{j['metadata']['name']:j['spec'] for j in xs}
assert specs(jobs)==specs(before), 'Concurrent job changes need review'
http=cloud('http-pre-deploy','run','services','describe','meteofriul-weather','--region='+REGION)
original_http=json.loads((OUT/'http-before.json').read_text())
assert http['spec']==original_http['spec'] and http['status']['traffic']==original_http['status']['traffic']
assert sum(x.get('percent',0) for x in http['status']['traffic'] if x['revisionName']=='meteofriul-weather-tol1-20261019')==100
qa=next(x for x in jobs if x['metadata']['name']==QA)
qa_env={e['name']:e.get('value') for e in qa['spec']['template']['spec']['template']['spec']['containers'][0]['env']}
assert qa_env['LOCAL_NOTICE_DELIVERY_MODE']=='dry_run' and qa_env['LOCAL_NOTICE_ICON_ACCUMULATION_SIDECAR_ENABLED']=='true'
assert json.loads((OUT/'rollback-image.json').read_text())['image_summary']['fully_qualified_digest']==ROLLBACK
executions=cloud('producer-executions-pre-deploy','run','jobs','executions','list','--job='+PRODUCER,'--region='+REGION,'--limit=5')
assert all(e.get('status',{}).get('completionTime') for e in executions), 'Active producer execution: wait'
save('deployment-intent',{'time':datetime.now(timezone.utc).isoformat(),'new_image':digest,'compatible_rollback':ROLLBACK,
 'action':'update producer image only; next existing scheduler run; no manual acquisition','sends_enabled':False})
cloud('producer-update','run','jobs','update',PRODUCER,'--region='+REGION,'--image='+digest)
after=cloud('jobs-after-deploy','run','jobs','list','--region='+REGION)
old,new=specs(before),specs(after)
assert set(old)==set(new)
for name,spec in old.items():
 if name!=PRODUCER: assert new[name]==spec, name
expected=copy.deepcopy(old[PRODUCER]['template']['spec'])
expected['template']['spec']['containers'][0]['image']=digest
assert new[PRODUCER]['template']['spec']==expected, 'Unexpected runtime config change'
schedulers=cloud('schedulers-after-deploy','scheduler','jobs','list','--location='+REGION)
keys=('attemptDeadline','description','httpTarget','name','retryConfig','schedule','state','timeZone','pubsubTarget','appEngineHttpTarget')
project=lambda xs:{x['name']:{k:x[k] for k in keys if k in x} for x in xs}
assert project(schedulers)==project(json.loads((OUT/'schedulers-before.json').read_text()))
http_after=cloud('http-after-deploy','run','services','describe','meteofriul-weather','--region='+REGION)
assert http_after['spec']==http['spec'] and http_after['status']['traffic']==http['status']['traffic']
result={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'producer':PRODUCER,'new_image':digest,'compatible_rollback':ROLLBACK,
 'other_jobs_unchanged':len(old)-1,'schedulers_unchanged':len(schedulers),'http_unchanged':True,'only_image_changed':True,
 'qa_mode':'dry_run','manual_executions':0,'next_scheduler_utc':'2026-10-20T18:00:00Z','new_run_validation':'pending'}
save('deployment-checks',result)
print(json.dumps(result))
