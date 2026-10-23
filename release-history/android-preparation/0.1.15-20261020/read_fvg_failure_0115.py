from fvg_deploy_common import GC,ROOT,OUT,PROJECT,ACCOUNT
from datetime import datetime,timezone
from collections import Counter
import json,subprocess,sys,requests
token=subprocess.check_output([sys.executable,str(GC),'auth','print-access-token','--project='+PROJECT,'--account='+ACCOUNT]).decode().strip()
fields=('state','error_code','attempt_count','claimed_at','alert_signature')
q={'structuredQuery':{'from':[{'collectionId':'push_official_alert_outbox'}],
 'select':{'fields':[{'fieldPath':k} for k in fields]},
 'where':{'fieldFilter':{'field':{'fieldPath':'updated_at'},'op':'GREATER_THAN_OR_EQUAL','value':{'timestampValue':'2026-10-20T20:00:00Z'}}},'limit':200}}
r=requests.post('https://firestore.googleapis.com/v1/projects/meteo-friul/databases/(default)/documents:runQuery',headers={'Authorization':'Bearer '+token},json=q,timeout=(10,40));r.raise_for_status()
docs=[x['document']['fields'] for x in r.json() if 'document' in x];assert len(docs)<200
sys.path.insert(0,str(OUT/'context/verification/package/verification/candidate'))
from app.services.push import _prepare_official_state
payload=json.loads((OUT/'ordinary-public-snapshot.json').read_text())['data']['payload']
prepared,state=_prepare_official_state(payload,now=datetime(2026,10,20,20,1,tzinfo=timezone.utc));assert state=='ready'
filtered=[d for d in docs if d.get('alert_signature',{}).get('stringValue')==prepared.signature]
counts=Counter((x.get('claimed_at',{}).get('timestampValue'),x.get('state',{}).get('stringValue'),x.get('error_code',{}).get('stringValue','')) for x in filtered)
result={'observed_at':datetime.now(timezone.utc).isoformat(),'same_alert_signature':True,'rows':len(filtered),
 'groups':[{'claimed_at':t,'state':s,'error_code':e,'count':n} for (t,s,e),n in sorted(counts.items())],
 'privacy':'Only projected state/error/time/signature read; no device IDs, target hashes or tokens collected',
 'limits':'Runtime FCM classifier conflates Unregistered and SenderIdMismatch; fcm_token_invalid alone cannot distinguish them'}
(ROOT/'.tmp/release-0-1-15-preparation-20261020/fvg-outbox-groups.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
