from icon_limit_common import *
from datetime import datetime, timezone
import hashlib, requests
base='https://meteofriul-weather-49007668366.europe-west1.run.app/weather/v1/icon2i/'
def read(path):
    r=requests.get(base+path,headers={'Origin':'https://localhost'},timeout=90);r.raise_for_status()
    assert r.headers.get('Access-Control-Allow-Origin')=='https://localhost'
    return r
old=ROOT/'.tmp/icon-tolerance-phase3-20261019/current-run-http'
fixture=json.loads((old/'fixture.json').read_text())
latest=read('latest.json');save('latest-before',latest.json())
manifest=read(latest.json()['latest']['manifest_path'])
assert latest.content==fixture['latest'].encode() and manifest.content==fixture['manifest'].encode()
documents=[]
for code in ('093033','030129','031008'):
    body=read(manifest.json()['objects'][code]['path']).content
    assert body==fixture['documents'][code].encode()
    documents.append({'istat':code,'sha256':hashlib.sha256(body).hexdigest()})
result=json.loads((old/'result.json').read_text())
assert result['public_documents_verified']==215 and all(x['public_documents_accepted']==215 for x in result['legacy_clients'])
assert result['source_run_id']==latest.json()['latest']['source_run_id']
save('http-baseline',{'verified_at_utc':datetime.now(timezone.utc).isoformat(),'source_run_id':result['source_run_id'],
    'manifest_sha256':hashlib.sha256(manifest.content).hexdigest(),'documents_reread':documents,
    'legacy_readers_reused_on_same_immutable_manifest':result['legacy_clients'],'new_run_validation':'pending','requests':'GET only'})
print(json.dumps({'source_run_id':result['source_run_id'],'sample_reread':len(documents),'legacy_clients':result['legacy_clients']}))
