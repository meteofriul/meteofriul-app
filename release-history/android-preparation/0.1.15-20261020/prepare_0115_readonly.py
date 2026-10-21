"""Read service identity, public contracts and aggregate one ordinary outbox window."""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import json, subprocess, sys
import requests

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'.tmp/release-0-1-15-preparation-20261020'
OUT.mkdir(exist_ok=True)
GC=Path.home()/'AppData/Local/Google/Cloud SDK/google-cloud-sdk/lib/gcloud.py'
def gc(*args):
    r=subprocess.run([sys.executable,str(GC),*args,'--project=meteo-friul','--account=meteofriul@gmail.com'],capture_output=True,check=True)
    return r.stdout.decode().strip()
accounts=json.loads(gc('auth','list','--filter=status:ACTIVE','--format=json'))
assert [x['account'] for x in accounts]==['meteofriul@gmail.com']
headers={'Authorization':'Bearer '+gc('auth','print-access-token')}
def get(url):
    r=requests.get(url,headers=headers,timeout=(10,40));r.raise_for_status();return r.json()
base='https://run.googleapis.com/v2/projects/meteo-friul/locations/europe-west1'
def service(name):
    d=get(base+'/services/'+name)
    return name,{'name':d['name'],'traffic':d.get('trafficStatuses',[]),'images':[c['image'] for c in d['template']['containers']], 'latest_ready':d.get('latestReadyRevision')}
services=dict(ThreadPoolExecutor(max_workers=4).map(service,['meteofriul-api','meteofriul-community','meteofriul-events','meteofriul-weather','meteofriul-national-weather']))
play=next(t for t in services['meteofriul-api']['traffic'] if t.get('tag')=='play-b6fbe4d')
revision_path=play['revision'] if play['revision'].startswith('projects/') else 'projects/meteo-friul/locations/europe-west1/services/meteofriul-api/revisions/'+play['revision']
rev=get('https://run.googleapis.com/v2/'+revision_path)
services['play-api']={'revision':rev['name'],'images':[c['image'] for c in rev['containers']], 'uri':play.get('uri')}
jobs=[];token=None
while True:
    d=get(base+'/jobs?pageSize=100'+('&pageToken='+token if token else ''))
    jobs.extend({'name':j['name'].split('/')[-1],'images':[c['image'] for c in j['template']['template']['containers']]} for j in d.get('jobs',[]))
    token=d.get('nextPageToken')
    if not token:break
community='https://meteofriul-community-49007668366.europe-west1.run.app'
health=requests.get(community+'/api/community/health',timeout=(10,35));health.raise_for_status()
options=requests.options(community+'/api/community/reports',headers={'Origin':'https://localhost','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type,x-firebase-appcheck,x-meteo-community-rules'},timeout=(10,35))
public={
 'community_health':health.json(),
 'community_v3_preflight':{'status':options.status_code,'allow_headers':options.headers.get('access-control-allow-headers'),'allow_origin':options.headers.get('access-control-allow-origin')},
}
events=requests.get('https://meteofriul-events-49007668366.europe-west1.run.app/api/local/events',params={'city':'Pordenone','lat':45.9569,'lon':12.6605,'radius':20,'limit':100},headers={'Origin':'https://localhost'},timeout=(10,45));events.raise_for_status()
event_body=events.json()
(OUT/'events-public.json').write_text(json.dumps(event_body,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
public['events']={'http_status':events.status_code,'count':len(event_body.get('events',[])),'cache':event_body.get('cache'),'top_level_fields':sorted(event_body),'cors':events.headers.get('access-control-allow-origin')}
query={'structuredQuery':{'from':[{'collectionId':'push_official_alert_outbox'}],
 'select':{'fields':[{'fieldPath':k} for k in ('state','error_code','attempt_count','updated_at')]},
 'where':{'compositeFilter':{'op':'AND','filters':[
 {'fieldFilter':{'field':{'fieldPath':'updated_at'},'op':'GREATER_THAN_OR_EQUAL','value':{'timestampValue':'2026-10-20T20:00:00Z'}}},
 {'fieldFilter':{'field':{'fieldPath':'updated_at'},'op':'LESS_THAN','value':{'timestampValue':'2026-10-20T20:03:00Z'}}}]}},'limit':200}}
r=requests.post('https://firestore.googleapis.com/v1/projects/meteo-friul/databases/(default)/documents:runQuery',headers=headers,json=query,timeout=(10,40));r.raise_for_status()
docs=[x['document']['fields'] for x in r.json() if 'document' in x]
assert len(docs)<200,'Window truncated'
counts=Counter((x.get('state',{}).get('stringValue',''),x.get('error_code',{}).get('stringValue','')) for x in docs)
result={'observed_at':datetime.now(timezone.utc).isoformat(),'project':'meteo-friul','services':services,'jobs':jobs,'public':public,
 'fvg_outbox':{'window_utc':['2026-10-20T20:00:00Z','2026-10-20T20:03:00Z'],'count':len(docs),'states':[{'state':s,'error_code':e,'count':n} for (s,e),n in sorted(counts.items())],'identifiers_and_tokens_not_collected':True},
 'mutations':False,'manual_executions':0,'manual_notifications':0}
(OUT/'live-readback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'services':len(services),'jobs':len(jobs),'public':public,'outbox':result['fvg_outbox']},ensure_ascii=False))
