from fvg_deploy_common import *
from concurrent.futures import ThreadPoolExecutor
accounts=cloud('auth-before','auth','list','--filter=status:ACTIVE')
assert [x['account'] for x in accounts]==[ACCOUNT]
tasks={'jobs-west8-before':('run','jobs','list','--region='+REGION),
 'jobs-west1-before':('run','jobs','list','--region='+BUILD_REGION),
 'schedulers-before':('scheduler','jobs','list','--location='+BUILD_REGION),
 'api-before':('run','services','describe','meteofriul-api','--region='+BUILD_REGION),
 'base-image':('artifacts','docker','images','describe',BASE),
 'executions-before':('run','jobs','executions','list','--job='+JOB,'--region='+REGION,'--limit=5')}
with ThreadPoolExecutor(max_workers=3) as pool:
    values=dict(zip(tasks,pool.map(lambda kv:cloud(kv[0],*kv[1]),tasks.items())))
j=next(x for x in values['jobs-west8-before'] if x['metadata']['name']==JOB)
container=j['spec']['template']['spec']['template']['spec']['containers'][0]
assert container['image']==BASE
env={e['name']:e.get('value') for e in container['env']}
assert env['PUSH_OFFICIAL_ALERTS_MODE']=='send' and env['PUSH_OFFICIAL_ALERTS_REQUIRED']=='true'
assert env['OFFICIAL_ALERTS_REQUIRE_PERSISTENT_STORAGE']=='true'
assert all(e.get('status',{}).get('completionTime') for e in values['executions-before'])
s=next(x for x in values['schedulers-before'] if x['name'].endswith('/'+JOB))
assert s['state']=='ENABLED' and s['schedule']=='0 */2 * * *' and s['timeZone']=='Europe/Rome'
assert '/europe-west8/jobs/'+JOB+':run' in s['httpTarget']['uri']
save('configuration-summary',{'job':JOB,'region':REGION,'image':BASE,'send_mode':env['PUSH_OFFICIAL_ALERTS_MODE'],
 'send_required':env['PUSH_OFFICIAL_ALERTS_REQUIRED'],'persistent_storage_required':True,
 'ordinary_next_run':s.get('scheduleTime'),'schedule':s['schedule'],'timezone':s['timeZone'],
 'recipient_policy':{k:env[k] for k in ('PUSH_PILOT_ENROLLMENT_MODE','PUSH_ENROLLMENT_GENERATION','PUSH_PLAY_BETA_MIN_VERSION_CODE') if k in env},
 'user_authorization':'Owner subsequently authorized ordinary notifications when eligible; preserve existing send mode and recipients'})
print(json.dumps(json.loads((OUT/'configuration-summary.json').read_text())))
