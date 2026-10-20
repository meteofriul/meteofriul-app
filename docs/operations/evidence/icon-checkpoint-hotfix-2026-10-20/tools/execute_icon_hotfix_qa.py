from icon_hotfix_common import *
from datetime import datetime,timezone
import requests
assert not (OUT/'qa-submission-intent.json').exists() and not (OUT/'execution-submission.json').exists(),'One QA execution only; inspect existing evidence instead'
checks=json.loads((OUT/'new-run-http/result.json').read_text())
assert checks['new_run'] and checks['sidecars_verified']==215 and checks['public_documents_verified']==215
r=requests.get('https://meteofriul-weather-49007668366.europe-west1.run.app/weather/v1/icon2i/latest.json',timeout=60);r.raise_for_status()
assert r.json()['latest']['source_run_id']==checks['source_run_id'],'Run changed after verification'
jobs=cloud('jobs-before-qa','run','jobs','list','--region='+REGION)
before=json.loads((OUT/'jobs-after-deploy.json').read_text())
specs=lambda xs:{x['metadata']['name']:x['spec'] for x in xs}
assert specs(jobs)==specs(before),'Concurrent configuration change needs review'
job=next(j for j in jobs if j['metadata']['name']==QA)
spec=job['spec']['template']['spec']['template']['spec'];container=spec['containers'][0]
env={e['name']:e['value'] for e in container['env']}
assert env['LOCAL_NOTICE_DELIVERY_MODE']=='dry_run'
assert env['LOCAL_NOTICE_ICON_ACCUMULATION_SIDECAR_ENABLED']=='true'
assert container['command']==['python'] and container['args']==['-m','app.jobs.send_local_weather_notices']
sa='meteofriul-notice-qa@meteo-friul.iam.gserviceaccount.com'
assert spec['serviceAccountName']==sa and spec['maxRetries']==0
policy=cloud('iam-before-qa','projects','get-iam-policy',PROJECT)
roles=[b['role'] for b in policy['bindings'] if 'serviceAccount:'+sa in b.get('members',[])]
assert roles==['roles/datastore.user']
schedulers=cloud('schedulers-before-qa','scheduler','jobs','list','--location='+REGION)
assert not any(QA in json.dumps(s) for s in schedulers)
check={'job':QA,'mode':'dry_run','source_run_id':checks['source_run_id'],'image':container['image'],
 'service_account':sa,'roles':roles,'no_scheduler':True,
 'execution_start_bound_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}
save('pre-execution-checks',check)
save('qa-submission-intent',check)
execution=cloud('execution-submission','run','jobs','execute',QA,'--region='+REGION,'--async')
print(json.dumps({'execution':execution['metadata']['name'],'source_run_id':checks['source_run_id']}))
