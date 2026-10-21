from icon_limit_common import *
build_id=json.loads((OUT/'build-submission.json').read_text())['id']
r=cloud('build-status','builds','describe',build_id,'--region='+REGION)
print(json.dumps({'id':build_id,'status':r['status'],'steps':[s.get('status') for s in r.get('steps',[])]}))
if r['status'] in ('SUCCESS','FAILURE','TIMEOUT','CANCELLED'):
    rows=cloud('build-logs','logging','read','resource.type="build" AND resource.labels.build_id="'+build_id+'"','--order=asc','--limit=2000')
    summaries=[]
    for row in rows:
        line=row.get('textPayload','')
        if '"verification": ' in line:
            try: summaries.append(json.loads(line[line.index('{'):]))
            except (ValueError,json.JSONDecodeError): pass
    if r['status']=='SUCCESS':
        assert len(summaries)==2 and all(x['success'] and not x['failures'] and not x['errors'] and not x['skipped'] for x in summaries), summaries
        assert next(x for x in summaries if x['verification']=='candidate')['tests']==183
        save('image-verification',{'build_id':build_id,'status':r['status'],'results':summaries,'network':'none','memory_limit_bytes':1024**3})
    print(json.dumps({'results':summaries,'log_rows':len(rows)}))
