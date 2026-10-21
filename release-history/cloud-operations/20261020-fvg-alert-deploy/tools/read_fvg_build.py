from fvg_deploy_common import *
ident=json.loads((OUT/'build-submission.json').read_text())['id']
r=cloud('build-status','builds','describe',ident,'--region='+BUILD_REGION)
print(json.dumps({'build_id':ident,'status':r['status'],'steps':[s.get('status') for s in r.get('steps',[])]}),flush=True)
if r['status'] in ('SUCCESS','FAILURE','TIMEOUT','CANCELLED'):
    rows=cloud('build-logs','logging','read','resource.type="build" AND resource.labels.build_id="'+ident+'"','--order=asc','--limit=2500')
    summaries=[]
    for row in rows:
        line=row.get('textPayload','')
        if '"verification":' in line:
            try:summaries.append(json.loads(line[line.index('{'):]))
            except (ValueError,json.JSONDecodeError):pass
    if r['status']=='SUCCESS':
        assert len(summaries)==2 and {x['verification'] for x in summaries}=={'candidate','rollback'}
        assert all(x['tests']==172 and x['success'] and not x['failures'] and not x['errors'] and not x['skipped'] for x in summaries)
        save('image-verification',{'build_id':ident,'status':'SUCCESS','results':summaries,'network':'none','memory_limit_bytes':512*1024**2})
    print(json.dumps({'summaries':summaries,'log_rows':len(rows)}))
