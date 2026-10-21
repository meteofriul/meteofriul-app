from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'.tmp/fvg-alerts-deploy-20261020';OUT.mkdir(exist_ok=True)
REPO=Path.home()/'.codex/worktrees/fvg-alerts-deploy/meteo FRIUL'
GC=Path.home()/'AppData/Local/Google/Cloud SDK/google-cloud-sdk/lib/gcloud.py'
PROJECT='meteo-friul';ACCOUNT='meteofriul@gmail.com';REGION='europe-west8';BUILD_REGION='europe-west1'
JOB='meteofriul-official-alert-sync'
COMMIT='5cbcd35ca88088220ff167b299cb4353ebdaf6d4'
BASE='europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:1f5171ad3e07748ac7fa8e3a8d1764458ee3ab4a3f4c4b78e8275925fa621d7f'
PLAY_API='https://play-b6fbe4d---meteofriul-api-bx24xqvcda-ew.a.run.app/api'
def save(name,value):
    (OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def cloud(name,*args):
    assert 'execute' not in args and not ('executions' in args and 'create' in args),'Manual executions forbidden'
    r=subprocess.run([sys.executable,str(GC),*args,'--project='+PROJECT,'--account='+ACCOUNT,'--format=json','--quiet'],capture_output=True)
    (OUT/(name+'.stderr.txt')).write_bytes(r.stderr)
    if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace'))
    value=json.loads(r.stdout);save(name,value);return value
def git(*args):return subprocess.check_output(['git','-c','safe.directory='+REPO.as_posix(),'-C',str(REPO),*args])
