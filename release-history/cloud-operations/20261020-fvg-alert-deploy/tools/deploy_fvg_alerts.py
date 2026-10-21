from fvg_deploy_common import *
from datetime import datetime,timezone,timedelta
import copy
assert not (OUT/'deployment-intent.json').exists(),'Inspect previous update before retry'
build=json.loads((OUT/'build-status.json').read_text());proof=json.loads((OUT/'image-verification.json').read_text())
assert build['status']=='SUCCESS' and proof['status']=='SUCCESS'
assert all(s.get('status')=='SUCCESS' for s in build['steps'])
tags=json.loads((OUT/'source-provenance.json').read_text())['tags']
images={kind:next(x['name'].rsplit(':',1)[0]+'@'+x['digest'] for x in build['results']['images'] if x['name']==tag) for kind,tag in tags.items()}
for kind,digest in images.items():
    r=cloud(kind+'-image','artifacts','docker','images','describe',digest)
    assert r['image_summary']['fully_qualified_digest']==digest
accounts=cloud('auth-pre-deploy','auth','list','--filter=status:ACTIVE');assert [a['account'] for a in accounts]==[ACCOUNT]
specs=lambda js:{j['metadata']['name']:j['spec'] for j in js}
before={}
for region,key in ((REGION,'west8'),(BUILD_REGION,'west1')):
    before[key]=cloud('jobs-'+key+'-pre-deploy','run','jobs','list','--region='+region)
    assert specs(before[key])==specs(json.loads((OUT/('jobs-'+key+'-before.json')).read_text())),'Concurrent job change'
api=cloud('api-pre-deploy','run','services','describe','meteofriul-api','--region='+BUILD_REGION)
original=json.loads((OUT/'api-before.json').read_text())
assert api['spec']==original['spec'] and api['status']['traffic']==original['status']['traffic']
keys=('attemptDeadline','description','httpTarget','name','retryConfig','schedule','state','timeZone','pubsubTarget','appEngineHttpTarget')
projection=lambda xs:{x['name']:{k:x[k] for k in keys if k in x} for x in xs}
schedulers=cloud('schedulers-pre-deploy','scheduler','jobs','list','--location='+BUILD_REGION)
assert projection(schedulers)==projection(json.loads((OUT/'schedulers-before.json').read_text()))
s=next(x for x in schedulers if x['name'].endswith('/'+JOB))
next_run=datetime.fromisoformat(s['scheduleTime'].replace('Z','+00:00'))
assert next_run-datetime.now(timezone.utc)>timedelta(minutes=5),'Too close to scheduled execution: do not race'
executions=cloud('executions-pre-deploy','run','jobs','executions','list','--job='+JOB,'--region='+REGION,'--limit=5')
assert all(e.get('status',{}).get('completionTime') for e in executions),'Active execution'
job=next(j for j in before['west8'] if j['metadata']['name']==JOB)
container=job['spec']['template']['spec']['template']['spec']['containers'][0]
assert container['image']==BASE
env={e['name']:e.get('value') for e in container['env']}
assert env['PUSH_OFFICIAL_ALERTS_MODE']=='send' and env['PUSH_OFFICIAL_ALERTS_REQUIRED']=='true'
assert env['OFFICIAL_ALERTS_REQUIRE_PERSISTENT_STORAGE']=='true'
save('deployment-intent',{'time':datetime.now(timezone.utc).isoformat(),'new_image':images['candidate'],'compatible_rollback':images['rollback'],
 'change':'image only; keep send/true, existing eligibility and persistent storage','authorization':'Owner explicitly authorized ordinary notifications after earlier no-send restriction','manual_executions':0})
cloud('job-update','run','jobs','update',JOB,'--region='+REGION,'--image='+images['candidate'])
after={}
for region,key in ((REGION,'west8'),(BUILD_REGION,'west1')):
    after[key]=cloud('jobs-'+key+'-after-deploy','run','jobs','list','--region='+region)
    old,new=specs(before[key]),specs(after[key]);assert old.keys()==new.keys()
    for name,spec in old.items():
        if key=='west8' and name==JOB:
            expected=copy.deepcopy(spec['template']['spec']);expected['template']['spec']['containers'][0]['image']=images['candidate']
            assert new[name]['template']['spec']==expected
        else:assert new[name]==spec,name
schedulers_after=cloud('schedulers-after-deploy','scheduler','jobs','list','--location='+BUILD_REGION)
assert projection(schedulers_after)==projection(schedulers)
api_after=cloud('api-after-deploy','run','services','describe','meteofriul-api','--region='+BUILD_REGION)
assert api_after['spec']==api['spec'] and api_after['status']['traffic']==api['status']['traffic']
executions_after=cloud('executions-after-deploy','run','jobs','executions','list','--job='+JOB,'--region='+REGION,'--limit=5')
assert [x['metadata']['name'] for x in executions_after]==[x['metadata']['name'] for x in executions]
result={'verified_at':datetime.now(timezone.utc).isoformat(),'project':PROJECT,'region':REGION,'job':JOB,'source_commit':COMMIT,
 'candidate_image':images['candidate'],'rollback_image':images['rollback'],'only_image_changed':True,
 'send_mode':'send','send_required':True,'existing_recipients_unchanged':True,'persistent_storage_required':True,
 'other_jobs_unchanged':sum(len(x) for x in before.values())-1,'schedulers_unchanged':len(schedulers),
 'api_unchanged':True,'manual_executions':0,'new_executions_on_deploy':0,'next_ordinary_run':s['scheduleTime'],'ordinary_verification':'pending'}
save('deployment-checks',result)
rollback='gcloud run jobs update '+JOB+' --project='+PROJECT+' --region='+REGION+' --account='+ACCOUNT+' --image='+images['rollback']+' --update-env-vars PUSH_OFFICIAL_ALERTS_MODE=off,PUSH_OFFICIAL_ALERTS_REQUIRED=false,OFFICIAL_ALERTS_REQUIRE_PERSISTENT_STORAGE=true\n'
(OUT/'rollback-command.txt').write_text(rollback,encoding='utf-8',newline='\n')
print(json.dumps(result))
