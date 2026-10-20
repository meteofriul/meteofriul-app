from pathlib import Path
import json,subprocess,sys
ROOT=Path(r'F:\proggetto Meteo Friul App\meteo FRIUL')
OUT=ROOT/'.tmp/icon-checkpoint-hotfix-20261020'
OUT.mkdir(exist_ok=True)
GC=r'C:\Users\LOCAL_USER\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py'
PROJECT='meteo-friul';REGION='europe-west1';ACCOUNT='meteofriul@gmail.com'
PRODUCER='meteofriul-icon';QA='meteofriul-local-notice-tolerance-qa'
BASE_IMAGE='europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:b8719b7f26c355115ded47e282e19f8011ff270e0d0107a831526879155ac2f2'
ROLLBACK='europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:3be1d207321e8ea0cee07466c9ac29fcec230ba4e10b3267647fa8f0cb2315a6'
REPO=Path(r'C:\Users\LOCAL_USER\.codex\worktrees\icon2i-checkpoint-metadata\meteo FRIUL')
COMMIT='9ef1410e'
def save(name,value):
 (OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def cloud(name,*args):
 r=subprocess.run([sys.executable,GC,*args,'--project='+PROJECT,'--account='+ACCOUNT,'--format=json','--quiet'],capture_output=True)
 (OUT/(name+'.stderr.txt')).write_bytes(r.stderr)
 if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace'))
 value=json.loads(r.stdout);save(name,value);return value
