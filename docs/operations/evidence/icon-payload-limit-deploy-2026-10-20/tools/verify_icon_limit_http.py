from icon_limit_common import *
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import argparse,hashlib,shutil,requests
ap=argparse.ArgumentParser();ap.add_argument('--name',required=True);ap.add_argument('--require-new',action='store_true');args=ap.parse_args()
dest=OUT/args.name
if (dest/'result.json').exists():
    result=json.loads((dest/'result.json').read_text())
    assert result['public_documents_verified']==215
    if args.require_new:assert result['new_run'] and result['sidecars_verified']==215 and result['source_run_id'] >= '20261021T000000Z'
    print(json.dumps(result));raise SystemExit(0)
base='https://meteofriul-weather-49007668366.europe-west1.run.app/weather/v1/icon2i/'
def get(path):
    r=requests.get(base+path,headers={'Origin':'https://localhost'},timeout=90);r.raise_for_status()
    assert r.headers.get('Access-Control-Allow-Origin')=='https://localhost'
    return r
def sha(b):return hashlib.sha256(b).hexdigest()
latest=get('latest.json');ref=latest.json()['latest']
old=json.loads((OUT/'latest-before.json').read_text())
new=ref['source_run_id']>old['latest']['source_run_id']
if args.require_new:
    assert new and ref['source_run_id'] >= '20261021T000000Z', 'Expected next ordinary source run is not published yet'
dest.mkdir(exist_ok=True)
manifest=get(ref['manifest_path']);assert sha(manifest.content)==ref['manifest_sha256'] and len(manifest.content)==ref['manifest_json_bytes']
descriptors=manifest.json()['objects'];assert len(descriptors)==215
sys.path.insert(0,str(OUT/'context/experiments/weather_autonomy'))
from local_pipeline.icon_accumulation_sidecar import validate_sidecar
def fetch(pair):
    code,d=pair;r=get(d['path'])
    assert sha(r.content)==d['sha256'] and len(r.content)==d['json_bytes'],code
    assert all('accumulation_quality' not in row for row in r.json()['hourly']),code
    evidence=None
    if new:
        side=get(d['path'].replace('/municipalities/','/accumulation-quality/'))
        validate_sidecar(side.content,r.content);evidence=side.text
    return code,r.text,evidence
with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(fetch,descriptors.items()))
documents={c:b for c,b,e in rows};sidecars={c:e for c,b,e in rows if e is not None}
old_reader=ROOT/'.tmp/icon-sidecar-legacy-reader'
fixture={'latest':latest.text,'manifest':manifest.text,'documents':documents,
    'enriched':json.loads((old_reader/'fixture.json').read_text())['enriched'],'target':'093033'}
(dest/'fixture.json').write_text(json.dumps(fixture),encoding='utf-8')
(dest/'sidecars.json').write_text(json.dumps(sidecars),encoding='utf-8')
clients=[]
for refname in ('2f02c8ba','8497e773'):
    shutil.copytree(old_reader/refname,dest/refname,dirs_exist_ok=True)
    check=subprocess.run(['node',str(dest/refname/'verify.mjs')],capture_output=True,text=True)
    assert check.returncode==0,check.stderr
    clients.append({'reader':refname,**json.loads(check.stdout)})
counts=Counter()
for body in sidecars.values():
    for item in json.loads(body)['hourly']:
        quality=item['accumulation_quality']
        if quality:
            for field,q in quality['fields'].items():counts[field+':'+q['state']+':'+(q.get('reason') or '')]+=1
# Old immutable public manifest remains byte-identical after the producer change.
old_manifest=get(old['latest']['manifest_path'])
assert sha(old_manifest.content)==old['latest']['manifest_sha256']
result={'source_run_id':ref['source_run_id'],'new_run':new,'public_documents_verified':len(documents),
    'sidecars_verified':len(sidecars),'sidecar_state_counts':dict(counts),'legacy_clients':clients,
    'old_manifest_unchanged':True,'android_cors':True,'network_actions':'GET only','sends':0}
(dest/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
