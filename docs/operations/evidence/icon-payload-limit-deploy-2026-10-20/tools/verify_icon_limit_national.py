from pathlib import Path
import hashlib, json, posixpath, re, subprocess
import requests

from icon_limit_common import ROOT, REPO, OUT as DEPLOY_OUT
MAIN=REPO
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--name',default='national-http');args=parser.parse_args()
OUT=DEPLOY_OUT/args.name
OUT.mkdir(exist_ok=True)
BASE='https://meteofriul-national-weather-49007668366.europe-west1.run.app'
PREFIX=BASE+'/weather/v2/icon2i/'
fixture={}
def read(path):
    url=PREFIX+path
    r=requests.get(url,headers={'Origin':'https://localhost'},timeout=120)
    r.raise_for_status()
    assert r.headers.get('Access-Control-Allow-Origin')=='https://localhost'
    fixture[url]=r.text
    return r
def verify(raw, descriptor):
    assert len(raw)==descriptor['json_bytes']
    assert hashlib.sha256(raw).hexdigest()==descriptor['sha256']

cities=[('Milano','MI'),('Canazei','TN'),('Roma','RM'),('Napoli','NA'),('Palermo','PA'),('Cagliari','CA')]
checks=[]
for city, province in cities:
    resolution=read('resolve.json?city='+city+'&province='+province).json()
    block=read(resolution['block_path'])
    verify(block.content,{'json_bytes':resolution['block_json_bytes'],'sha256':resolution['block_sha256']})
    cell=next(c for c in block.json()['cells'] if c['cell_id']==resolution['cell_id'])
    assert block.json()['municipality_cells'][resolution['municipality']['istat_code']]==cell['cell_id']
    checks.append({'city':city,'province':province,'istat':resolution['municipality']['istat_code'],
                   'run':resolution['source_run_id'],'hours':len(block.json()['time_axis']),
                   'block_sha256':resolution['block_sha256']})
    print(json.dumps(checks[-1]),flush=True)
manifest_response=read(resolution['manifest']['path']);verify(manifest_response.content,resolution['manifest'])
index_response=read(resolution['index']['path']);verify(index_response.content,resolution['index'])
(OUT/'manifest.json').write_bytes(manifest_response.content)
(OUT/'municipality-index.json').write_bytes(index_response.content)
(OUT/'fixture.json').write_text(json.dumps(fixture),encoding='utf-8')

# Export exact legacy runtime modules. Only module resolution and Vite build
# environment are adapted for Node; client/adapter calculations stay unchanged.
clients=[]
for ref in ('2f02c8ba','8497e773'):
    target=OUT/ref;target.mkdir(exist_ok=True)
    (target/'package.json').write_text('{"type":"module"}\n')
    seen=set();inventory=[]
    def export(path):
        if path in seen:return
        seen.add(path)
        raw=subprocess.check_output(['git','-c','safe.directory='+MAIN.as_posix(),'-C',str(MAIN),'show',ref+':'+path])
        source=raw.decode('utf-8')
        inventory.append({'path':path,'sha256':hashlib.sha256(raw).hexdigest()})
        def rewrite(m):
            quote, value=m.group(1),m.group(2)
            if value.startswith('.'):
                resolved=posixpath.normpath(posixpath.join(posixpath.dirname(path),value))
                if not posixpath.splitext(resolved)[1]:resolved+='.js';value+='.js'
                export(resolved)
            elif value=='react':
                value=(ROOT/'frontend/node_modules/react/index.js').as_uri()
            else:raise ValueError('Unexpected external import '+value)
            return 'from '+quote+value+quote
        source=re.sub(r'from\s+([\x27\x22])([^\x27\x22]+)\1',rewrite,source)
        if 'import.meta.env' in source:source="import.meta.env = {MODE:'production'};\n"+source
        dest=target/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(source,encoding='utf-8')
    export('frontend/src/services/nationalWeatherV2Adapter.js')
    (target/'source-inventory.json').write_text(json.dumps(inventory,indent=2))
    (target/'verify.mjs').write_text('''
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {fetchNationalWeatherV2Bootstrap} from './frontend/src/services/nationalWeatherV2Adapter.js';
const fixture=JSON.parse(fs.readFileSync(new URL('../fixture.json',import.meta.url),'utf8'));
const cities=JSON.parse(process.argv[2]);const accepted=[];
for(const item of cities){
 const result=await fetchNationalWeatherV2Bootstrap({city:item.city,province:item.province,countryCode:'IT'}, {
  baseUrl:'https://meteofriul-national-weather-49007668366.europe-west1.run.app', storage:null, now:Date.now, force:true,
  fetchImpl:async url=>{assert.ok(Object.hasOwn(fixture,url),url);return new Response(fixture[url],{status:200})}
 });
 assert.equal(result.city,item.city);
 assert.equal(result.current.data_quality.mode,'national_contract_v2');
 assert.equal(result.current.data_quality.municipality_istat,item.istat);
 assert.equal(result.current.hourly_next_12h.length,12);
 assert.ok(result.forecast.forecast.length>=2);
 accepted.push({city:item.city,hours:result.current.hourly_next_12h.length,days:result.forecast.forecast.length});
}
console.log(JSON.stringify({accepted}));
''',encoding='utf-8')
    r=subprocess.run(['node',str(target/'verify.mjs'),json.dumps(checks)],capture_output=True,text=True)
    if r.returncode:raise RuntimeError(r.stderr)
    clients.append({'reader':ref,**json.loads(r.stdout)})
result={'service':BASE,'read_only':True,'sample_not_full_country':True,'cases':checks,'legacy_clients':clients,
        'manifest_and_index_integrity':True,'cors_android':True,'national_service_deployed':False}
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
