"""Read the next ordinary FVG sync, public API, and persisted public alert."""
from fvg_deploy_common import *
from datetime import datetime,timezone
import requests,hashlib
now=datetime.now(timezone.utc)
assert now>=datetime(2026,10,20,20,5,tzinfo=timezone.utc),'Wait for the ordinary 22:00 local execution'
checks=json.loads((OUT/'deployment-checks.json').read_text())
accounts=cloud('ordinary-auth','auth','list','--filter=status:ACTIVE');assert [x['account'] for x in accounts]==[ACCOUNT]
executions=cloud('ordinary-executions','run','jobs','executions','list','--job='+JOB,'--region='+REGION,'--limit=10')
matches=[e for e in executions if datetime(2026,10,20,20,tzinfo=timezone.utc)<=datetime.fromisoformat(e['metadata']['creationTimestamp'].replace('Z','+00:00'))<datetime(2026,10,20,20,30,tzinfo=timezone.utc)]
assert len(matches)==1,'Expected one ordinary execution; never create one'
execution=matches[0];name=execution['metadata']['name']
assert execution['metadata']['annotations']['run.googleapis.com/creator']=='official-alert-scheduler@meteo-friul.iam.gserviceaccount.com'
container=execution['spec']['template']['spec']['containers'][0]
assert container['image']==checks['candidate_image']
env={x['name']:x.get('value') for x in container['env']}
assert env['PUSH_OFFICIAL_ALERTS_MODE']=='send' and env['PUSH_OFFICIAL_ALERTS_REQUIRED']=='true'
completed=next(x for x in execution['status']['conditions'] if x['type']=='Completed')
if completed['status']=='Unknown':print(json.dumps({'execution':name,'status':'pending'}));raise SystemExit(2)
rows=cloud('ordinary-logs','logging','read','resource.type="cloud_run_job" AND resource.labels.job_name="'+JOB+'" AND resource.labels.location="'+REGION+'" AND labels."run.googleapis.com/execution_name"="'+name+'"','--order=asc','--limit=5000')
assert len(rows)<5000,'Complete log pagination required'
summaries=[]
for row in rows:
    payload=row.get('jsonPayload')
    if payload is None:
        try:payload=json.loads(row.get('textPayload',''))
        except json.JSONDecodeError:continue
    if isinstance(payload,dict) and 'push' in payload and 'refreshed' in payload:summaries.append(payload)
assert summaries,'Missing job result: do not infer success from exit code alone'
summary=summaries[-1];save('ordinary-job-summary',summary)
api=requests.get(PLAY_API+'/weather/official-alerts',timeout=(10,45));api.raise_for_status();api_body=api.json();save('ordinary-api',api_body)
default=requests.get('https://meteofriul-api-49007668366.europe-west1.run.app/api/weather/official-alerts',timeout=(10,45));default.raise_for_status();save('ordinary-default-api',default.json())
auth=subprocess.run([sys.executable,str(GC),'auth','print-access-token','--project='+PROJECT,'--account='+ACCOUNT],capture_output=True,check=True)
headers={'Authorization':'Bearer '+auth.stdout.decode().strip()}
r=requests.get('https://firestore.googleapis.com/v1/projects/meteo-friul/databases/(default)/documents/official_alert_snapshots/current',headers=headers,timeout=(10,45));r.raise_for_status()
def decode(v):
    for key in ('stringValue','timestampValue','booleanValue','nullValue'):
        if key in v:return v[key]
    if 'integerValue' in v:return int(v['integerValue'])
    if 'doubleValue' in v:return float(v['doubleValue'])
    if 'mapValue' in v:return {k:decode(x) for k,x in v['mapValue'].get('fields',{}).items()}
    if 'arrayValue' in v:return [decode(x) for x in v['arrayValue'].get('values',[])]
    raise ValueError('Unsupported Firestore field')
state={k:decode(v) for k,v in r.json()['fields'].items()}
save('ordinary-public-snapshot',{'update_time':r.json()['updateTime'],'data':state})
payload=state['payload']
assert datetime.fromisoformat(r.json()['updateTime'].replace('Z','+00:00'))>=datetime(2026,10,20,20,tzinfo=timezone.utc),'Snapshot predates the ordinary run'
sys.path.insert(0,str(OUT/'context/verification/package/verification/candidate'))
from app.services.official_alert_sources import fetch_official_alert_observations,reconcile_official_alert_observations
widget=requests.get('https://pianiemergenza.protezionecivile.fvg.it/api/alerts.jsonp',params={'callback':'pcrfvgit_widget_setup'},headers={'User-Agent':'MeteoFriul/3.0 (+https://meteofriul.it)','Referer':'https://www.protezionecivile.fvg.it/it/widget-allerta'},timeout=(10,45));widget.raise_for_status()
observed=fetch_official_alert_observations(widget_fetcher=lambda:widget.text,html_fetcher=None,telegram_fetcher=lambda:{'alerts':[],'can_confirm_inactive':False},now=lambda:now)
source=reconcile_official_alert_observations(None,observed,now=now);save('ordinary-public-sources',{'observations':observed,'result':source})
projection=lambda doc:[{k:a.get(k) for k in ('level','zone_levels','valid_from','valid_to','pdf_url')} for a in doc.get('alerts',[])]
assert not source.get('error'),'Current sources cannot be reconciled'
assert projection(api_body)==projection(payload)==projection(source)==projection(default.json()),'API / snapshot / live-source mismatch'
assert bool(api_body.get('active'))==bool(source.get('active'))
for alert in payload.get('alerts',[]):assert alert['corroboration']['revision_hash_schema']=='runtime-v3'
push=summary['push']
accepted={'sent','deduplicated','no_eligible_devices'}
if not source.get('active'):accepted.add('no_active_alert')
good=completed['status']=='True' and summary.get('refreshed') and summary.get('stored_in')=='firestore' and summary.get('cache_status')=='fresh' and not summary.get('upstream_failure') and push.get('status') in accepted and not push.get('failed') and not push.get('sent_unconfirmed')
result={'verified_at':now.isoformat(),'execution':name,'scheduler_creator_verified':True,'image':checks['candidate_image'],
 'job_completed':completed['status'],'job_summary':summary,'api_matches_persistent_snapshot_and_sources':True,
 'alerts':projection(api_body),'snapshot_update_time':r.json()['updateTime'],'manual_executions':0,
 'push_meaning':'sent means FCM accepted the request; it does not prove display on a physical phone',
 'success':bool(good),'physical_phone_delivery_verified':False}
save('ordinary-verification',result);print(json.dumps(result,ensure_ascii=False))
raise SystemExit(0 if good else 1)
