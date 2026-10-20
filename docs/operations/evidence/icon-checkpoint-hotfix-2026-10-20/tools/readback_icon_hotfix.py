from icon_hotfix_common import *
from datetime import datetime,timezone
import hashlib,requests
OLD=ROOT/'.tmp/icon-tolerance-phase3-20261019'
base='https://meteofriul-weather-49007668366.europe-west1.run.app/weather/v1/icon2i/'
def read(url):
 r=requests.get(url,headers={'Origin':'https://localhost'},timeout=90);r.raise_for_status()
 assert r.headers.get('Access-Control-Allow-Origin')=='https://localhost'
 return r
fixture=json.loads((OLD/'current-run-http/fixture.json').read_text())
latest=read(base+'latest.json');assert latest.content==fixture['latest'].encode()
save('latest-before',latest.json())
manifest=read(base+latest.json()['latest']['manifest_path']);assert manifest.content==fixture['manifest'].encode()
for code in ('093033','030129','031008'):
 r=read(base+manifest.json()['objects'][code]['path']);assert r.content==fixture['documents'][code].encode()
oldresult=json.loads((OLD/'current-run-http/result.json').read_text())
assert oldresult['public_documents_verified']==215
assert all(x['public_documents_accepted']==215 for x in oldresult['legacy_clients'])
assert oldresult['source_run_id']==latest.json()['latest']['source_run_id']
national_old=json.loads((OLD/'national-http-20261020/result.json').read_text())
assert len(national_old['cases'])==6 and all(len(x['accepted'])==6 for x in national_old['legacy_clients'])
national=[]
nb=national_old['service']+'/weather/v2/icon2i/'
for item in national_old['cases']:
 q=read(nb+'resolve.json?city='+item['city']+'&province='+item['province']).json()
 assert q['source_run_id']==item['run'] and q['block_sha256']==item['block_sha256']
 block=read(nb+q['block_path'])
 assert hashlib.sha256(block.content).hexdigest()==q['block_sha256'] and len(block.content)==q['block_json_bytes']
 national.append({'city':item['city'],'source_run_id':q['source_run_id'],'same_legacy_validated_block':True})
result={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'fvg_run':latest.json()['latest']['source_run_id'],
 'fvg_manifest_sha256':hashlib.sha256(manifest.content).hexdigest(),'fvg_publication_unchanged':True,'fvg_documents_reread':3,
 'fvg_all_215_legacy_checks_reused_from_same_immutable_manifest':oldresult['legacy_clients'],
 'national_cases_reread':national,'national_legacy_checks_reused_from_identical_blocks':national_old['legacy_clients'],
 'android_cors':True,'new_run_verification':'pending','network_actions':'GET only','manual_producer_executions':0,'manual_qa_executions':0}
save('post-deploy-readback',result)
print(json.dumps({k:v for k,v in result.items() if 'legacy_checks' not in k}))
