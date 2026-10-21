from icon_limit_common import *
from datetime import datetime,timezone
import hashlib,requests
baseline=json.loads((OUT/'http-baseline.json').read_text())
latest_before=json.loads((OUT/'latest-before.json').read_text())
base='https://meteofriul-weather-49007668366.europe-west1.run.app/weather/v1/icon2i/'
def read(path):
    r=requests.get(base+path,headers={'Origin':'https://localhost'},timeout=90);r.raise_for_status()
    assert r.headers.get('Access-Control-Allow-Origin')=='https://localhost'
    return r
latest=read('latest.json');assert latest.json()==latest_before
manifest=read(latest_before['latest']['manifest_path'])
assert hashlib.sha256(manifest.content).hexdigest()==baseline['manifest_sha256']
for item in baseline['documents_reread']:
    body=read(manifest.json()['objects'][item['istat']]['path']).content
    assert hashlib.sha256(body).hexdigest()==item['sha256']
result={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'fvg_run':baseline['source_run_id'],
 'fvg_publication_unchanged':True,'fvg_documents_reread':3,'manifest_sha256':baseline['manifest_sha256'],
 'legacy_readers_reused_on_same_immutable_manifest':baseline['legacy_readers_reused_on_same_immutable_manifest'],
 'android_cors':True,'network_actions':'GET only','new_run_verification':'pending','manual_job_executions':0}
save('post-deploy-readback',result);print(json.dumps(result))
