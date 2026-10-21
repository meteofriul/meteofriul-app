from pathlib import Path
import json, subprocess, sys
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '.tmp/icon-payload-limit-deploy-20261020'
OUT.mkdir(exist_ok=True)
GC = Path.home() / 'AppData/Local/Google/Cloud SDK/google-cloud-sdk/lib/gcloud.py'
PROJECT='meteo-friul'; REGION='europe-west1'; ACCOUNT='meteofriul@gmail.com'
PRODUCER='meteofriul-icon'; QA='meteofriul-local-notice-tolerance-qa'
BASE_IMAGE='europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:e72f606ffe1feec5f1c108f945ec5dbce43cfebef3d69913fc72c11b04cbcae2'
ROLLBACK=BASE_IMAGE
REPO=Path.home()/'.codex/worktrees/icon2i-monitor-main-verification/meteo FRIUL'
COMMIT='5cbcd35ca88088220ff167b299cb4353ebdaf6d4'
def save(name, value):
    (OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def cloud(name,*args):
    assert 'execute' not in args, 'Manual job executions forbidden'
    assert not ('executions' in args and 'create' in args)
    p=subprocess.run([sys.executable,str(GC),*args,'--project='+PROJECT,'--account='+ACCOUNT,'--format=json','--quiet'],capture_output=True)
    (OUT/(name+'.stderr.txt')).write_bytes(p.stderr)
    if p.returncode: raise RuntimeError(p.stderr.decode(errors='replace'))
    value=json.loads(p.stdout);save(name,value);return value
def git(*args):
    return subprocess.check_output(['git','-c','safe.directory='+REPO.as_posix(),'-C',str(REPO),*args])
