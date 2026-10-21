from fvg_deploy_common import *
from datetime import datetime,timezone
assert not (OUT/'build-submission-intent.json').exists(), 'Inspect prior attempt before retry'
p=json.loads((OUT/'source-provenance.json').read_text());assert p['source_commit']==COMMIT
save('build-submission-intent',{'time':datetime.now(timezone.utc).isoformat(),'source_commit':COMMIT,'tags':p['tags']})
r=cloud('build-submission','builds','submit',str(OUT/'context'),'--config='+str(OUT/'cloudbuild.json'),'--region='+BUILD_REGION,'--async')
print(json.dumps({'build_id':r['id'],'status':r['status'],'log_url':r.get('logUrl')}))
