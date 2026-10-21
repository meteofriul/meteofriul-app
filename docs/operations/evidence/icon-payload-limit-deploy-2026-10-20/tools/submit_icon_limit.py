from icon_limit_common import *
from datetime import datetime,timezone
assert not (OUT/'build-submission.json').exists()
assert not (OUT/'build-submission-intent.json').exists(), 'Inspect previous submission before retry'
p=json.loads((OUT/'source-provenance.json').read_text())
assert p['commit']==COMMIT and len(p['files'])==181 and len(p['runtime_changes'])==2
save('build-submission-intent',{'time':datetime.now(timezone.utc).isoformat(),'commit':COMMIT,'image':p['image_tag'],'region':REGION})
r=cloud('build-submission','builds','submit',str(OUT/'context'),'--config='+str(OUT/'cloudbuild.json'),'--region='+REGION,'--async')
print(json.dumps({'id':r['id'],'status':r['status'],'region':REGION,'log_url':r.get('logUrl')}))
